"""
Moodle content import — receives structured JSON from the standalone moodle-agent tool.
No browser automation or scraping here; all extraction is done by the external agent.
"""
import streamlit as st
import json
import os
from database import get_conn


def _save_items(student_id, course_name, course_code, items):
    conn = get_conn()
    c = conn.cursor()
    saved = 0
    for item in items:
        c.execute(
            "SELECT id FROM moodle_content WHERE student_id=%s AND title=%s AND course_code=%s",
            (student_id, item.get("title", ""), course_code or ""),
        )
        if c.fetchone():
            continue
        c.execute(
            """INSERT INTO moodle_content
               (student_id, course_code, course_name, content_type, title, body, due_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (
                student_id, course_code or "", course_name,
                item.get("type", "resource"),
                item.get("title", "未命名"),
                item.get("body", ""),
                item.get("due_date") or None,
            ),
        )
        saved += 1
    conn.commit()
    conn.close()
    return saved


def _create_tasks(student_id, course_name, course_code, items):
    conn = get_conn()
    c = conn.cursor()
    created = 0
    for item in items:
        if item.get("type") == "assignment" and item.get("due_date"):
            c.execute("SELECT id FROM tasks WHERE title=%s AND created_by=%s",
                      (item["title"], student_id))
            if c.fetchone():
                continue
            body = item.get("body", "")
            desc = f"{body}\n\n[来源: Moodle — {course_name}]" if body else f"[来源: Moodle — {course_name}]"
            c.execute(
                "INSERT INTO tasks (title, description, due_date, subject, created_by) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (item["title"], desc, item["due_date"], course_code or course_name, student_id),
            )
            task_id = c.fetchone()[0]
            c.execute("SELECT id FROM progress WHERE student_id=%s AND task_id=%s", (student_id, task_id))
            if not c.fetchone():
                c.execute("INSERT INTO progress (student_id, task_id, status) VALUES (%s,%s,'pending')",
                          (student_id, task_id))
            created += 1
    conn.commit()
    conn.close()
    return created


def _import_from_json(user, raw_json: str):
    """
    Accept JSON from the moodle-agent tool and import into the platform.

    Supported formats:
      1. moodle_agent format: {"source":"moodle_agent","courses":[{...}]}
      2. Simple courses array:  {"courses":[{...}]}
    """
    student_id = user["id"]
    raw = raw_json.strip()
    if not raw:
        st.error("内容为空")
        return

    try:
        data = json.loads(raw)
    except Exception as e:
        st.error(f"JSON 格式错误：{e}")
        return

    courses = data.get("courses", [])
    if not courses:
        st.error("未找到课程数据（courses 列表为空）")
        return

    total_saved = total_tasks = total_pdfs = 0

    for course in courses:
        cname = course.get("name") or course.get("fullname", "未知课程")
        ccode = course.get("code") or course.get("shortname", "")

        # Build unified items list from various fields
        items = []

        # Assignments
        for a in course.get("assignments", []):
            items.append({
                "type": "assignment",
                "title": a.get("title", a.get("name", "")),
                "body": a.get("description", a.get("body", "")),
                "due_date": a.get("due_date", ""),
            })

        # Announcements / forum posts
        for ann in course.get("announcements", []):
            items.append({
                "type": "announcement",
                "title": ann.get("title", ""),
                "body": ann.get("content", ann.get("body", "")),
                "due_date": "",
            })

        # Generic items array (from extension_v2 or other formats)
        for item in course.get("items", []):
            items.append(item)

        saved = _save_items(student_id, cname, ccode, items)
        created = _create_tasks(student_id, cname, ccode, items)
        total_saved += saved
        total_tasks += created

        # Handle PDF files if present (from moodle-agent)
        for f in course.get("files", []):
            local_path = f.get("local_path", "")
            if local_path and os.path.exists(local_path) and local_path.endswith(".pdf"):
                _import_pdf_file(student_id, cname, ccode, local_path, f.get("filename", ""))
                total_pdfs += 1

    msg = f"✅ 导入完成：{len(courses)} 门课程，{total_saved} 条内容，{total_tasks} 个任务"
    if total_pdfs:
        msg += f"，{total_pdfs} 个 PDF"
    st.success(msg)


def _import_pdf_file(student_id, course_name, course_code, filepath, filename):
    """Import a local PDF file into course_materials."""
    from parse_course import read_pdf, parse_course_outline
    import hashlib
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        file_hash = hashlib.md5(data).hexdigest()
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id FROM course_materials WHERE file_hash=%s AND student_id=%s",
                  (file_hash, student_id))
        if c.fetchone():
            conn.close()
            return
        pdf_text = read_pdf(filepath)
        result = parse_course_outline(pdf_text, filename=filename)
        c.execute(
            """INSERT INTO course_materials
               (course_code, course_name, week_number, title, filepath, student_id, file_hash, content)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                (result or {}).get("course_code") or course_code,
                (result or {}).get("course_name") or course_name,
                (result or {}).get("week_number"),
                filename, filepath, student_id, file_hash, pdf_text[:10000],
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        st.warning(f"PDF 导入失败（{filename}）：{e}")


# ── Public view ───────────────────────────────────────────────────────────────

def show_moodle_import(user):
    student_id = user["id"]

    st.write("### 🔗 导入 Moodle 课程数据")
    st.info(
        "使用 **Moodle AI 导出工具**（独立项目）从 Moodle 提取课程数据后，"
        "将生成的 `output.json` 上传到此处，或直接粘贴 JSON 内容。"
    )

    tab_file, tab_paste = st.tabs(["📁 上传 JSON 文件", "📋 粘贴 JSON"])

    with tab_file:
        uploaded = st.file_uploader("上传 moodle-agent 生成的 output.json", type=["json"], key="moodle_json_upload")
        if uploaded:
            raw = uploaded.read().decode("utf-8")
            st.caption(f"文件大小：{len(raw)//1024} KB")
            if st.button("✅ 导入", type="primary", key="import_file"):
                _import_from_json(user, raw)

    with tab_paste:
        paste = st.text_area("粘贴 JSON 数据", height=120, key="moodle_paste",
                             placeholder='{"courses":[...]}')
        if st.button("✅ 导入", type="primary", key="import_paste", disabled=not paste):
            _import_from_json(user, paste)

    # ── History ──────────────────────────────────────────────────────────────
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT course_name, course_code, content_type, title, due_date
        FROM moodle_content WHERE student_id=%s ORDER BY created_at DESC
    """, (student_id,))
    history = c.fetchall()
    conn.close()

    if history:
        st.divider()
        st.write("### 已导入内容")
        by_course = {}
        for row in history:
            key = row[1] or row[0]
            if key not in by_course:
                by_course[key] = {"name": row[0], "code": row[1], "items": []}
            by_course[key]["items"].append(row)
        icons = {"announcement": "📢", "assignment": "📝", "resource": "📁", "quiz": "📊"}
        for key, course in by_course.items():
            label = f"📘 {course['code'] + ' ' if course['code'] else ''}{course['name']} — {len(course['items'])} 条"
            with st.expander(label):
                for item in course["items"]:
                    icon = icons.get(item[2], "📌")
                    due = f" | {item[4]}" if item[4] else ""
                    st.write(f"{icon} {item[3]}{due}")