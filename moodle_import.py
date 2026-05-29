import streamlit as st
import json
import re
from database import get_conn
from ai_helper import call_claude


def _extract_text(html_content):
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()
        return soup.get_text(separator='\n', strip=True)
    except ImportError:
        text = re.sub(r'<[^>]+>', ' ', html_content)
        return re.sub(r'\s+', '\n', text).strip()


def _parse_with_claude(text, course_hint=""):
    hint = f"\n课程提示：{course_hint}" if course_hint else ""
    prompt = (
        f"以下是从 Moodle 课程页面提取的文字内容，请分析并提取结构化信息。{hint}\n\n"
        "返回JSON格式（只返回JSON，不要其他文字）：\n"
        '{"course_name":"完整课程名","course_code":"课程代码如COMP1511（无则空字符串）","items":['
        '{"type":"announcement|assignment|resource|quiz","title":"标题",'
        '"body":"内容摘要不超过150字","due_date":"截止日期YYYY-MM-DD（无则空字符串）"}]}\n\n'
        f"页面内容（前6000字）：\n{text[:6000]}"
    )
    result = call_claude(
        "你是专业的 Moodle 课程内容解析助手，擅长提取作业、公告和资料信息。",
        [{"role": "user", "content": prompt}],
        max_tokens=3000
    )
    m = re.search(r'\{.*\}', result, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None


def _save_items(student_id, course_name, course_code, items):
    conn = get_conn()
    c = conn.cursor()
    saved = 0
    for item in items:
        c.execute(
            "SELECT id FROM moodle_content WHERE student_id=%s AND title=%s AND course_code=%s",
            (student_id, item.get('title', ''), course_code or '')
        )
        if c.fetchone():
            continue
        c.execute("""
            INSERT INTO moodle_content (student_id, course_code, course_name, content_type, title, body, due_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            student_id, course_code or '', course_name,
            item.get('type', 'resource'),
            item.get('title', '未命名'),
            item.get('body', ''),
            item.get('due_date') or None
        ))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def _create_tasks(student_id, course_name, course_code, items):
    conn = get_conn()
    c = conn.cursor()
    created = 0
    for item in items:
        if item.get('type') == 'assignment' and item.get('due_date'):
            c.execute("SELECT id FROM tasks WHERE title=%s AND created_by=%s",
                      (item['title'], student_id))
            if c.fetchone():
                continue
            body = item.get('body', '')
            desc = f"{body}\n\n[来源: Moodle — {course_name}]" if body else f"[来源: Moodle — {course_name}]"
            c.execute("""
                INSERT INTO tasks (title, description, due_date, subject, created_by)
                VALUES (%s,%s,%s,%s,%s) RETURNING id
            """, (item['title'], desc, item['due_date'], course_code or course_name, student_id))
            task_id = c.fetchone()[0]
            # Add initial progress record
            c.execute("SELECT id FROM progress WHERE student_id=%s AND task_id=%s",
                      (student_id, task_id))
            if not c.fetchone():
                c.execute("INSERT INTO progress (student_id, task_id, status) VALUES (%s,%s,'pending')",
                          (student_id, task_id))
            created += 1
    conn.commit()
    conn.close()
    return created


def show_moodle_import(user):
    student_id = user['id']

    st.write("### 🔗 Moodle 课程内容导入")

    with st.expander("📖 使用说明", expanded=False):
        st.markdown("""
1. 在浏览器中打开你的 **Moodle 课程页面**
2. 按 **Ctrl+S**（Mac: **Cmd+S**），选择保存类型为「**仅 HTML（.htm/.html）**」
3. 上传保存的 `.html` 文件
4. AI 自动提取：课程公告、作业（含截止日期）、资料列表
5. 确认后：内容存入资料库，**有截止日期的作业自动创建任务**
""")

    course_hint = st.text_input(
        "课程代码提示（可选，帮助 AI 识别，如 COMP1511）",
        key="mc_hint",
        placeholder="COMP1511"
    )
    uploaded = st.file_uploader(
        "上传 Moodle 课程页面 HTML 文件",
        type=["html", "htm"],
        key="mc_file"
    )

    if uploaded:
        st.caption(f"已选择：{uploaded.name} ({uploaded.size // 1024} KB)")
        if st.button("🤖 AI 解析内容", type="primary"):
            with st.spinner("AI 正在解析 Moodle 内容，请稍候..."):
                content = uploaded.read().decode('utf-8', errors='ignore')
                text = _extract_text(content)
                if len(text.strip()) < 50:
                    st.error("无法从文件中提取内容，请确认保存的是 HTML 文件")
                    st.stop()
                parsed = _parse_with_claude(text, course_hint)

            if parsed:
                st.session_state['mc_parsed'] = parsed
            else:
                st.error("解析失败，请重试或检查文件是否完整")

    if st.session_state.get('mc_parsed'):
        parsed = st.session_state['mc_parsed']
        items = parsed.get('items', [])
        cname = parsed.get('course_name', '未知课程')
        ccode = parsed.get('course_code', '')

        st.write(f"### 解析结果：{(ccode + ' ') if ccode else ''}{cname}")

        assignments = [i for i in items if i.get('type') == 'assignment']
        announcements = [i for i in items if i.get('type') == 'announcement']
        resources = [i for i in items if i.get('type') not in ('assignment', 'announcement')]

        if assignments:
            st.write(f"**📝 作业（{len(assignments)} 项）** — 有截止日期的将自动创建任务")
            for a in assignments:
                due = f" ｜ ⏰ 截止: **{a['due_date']}**" if a.get('due_date') else " ｜ 无截止日期"
                st.write(f"- {a['title']}{due}")
                if a.get('body'):
                    st.caption(f"  {a['body'][:120]}")

        if announcements:
            st.write(f"**📢 公告（{len(announcements)} 项）**")
            for a in announcements:
                st.write(f"- {a['title']}")

        if resources:
            st.write(f"**📁 其他资料（{len(resources)} 项）**")
            for r in resources:
                st.write(f"- {r['title']}")

        if not items:
            st.warning("未提取到任何内容，建议检查 HTML 文件格式或尝试重新保存页面")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 确认导入", type="primary"):
                saved = _save_items(student_id, cname, ccode, items)
                created = _create_tasks(student_id, cname, ccode, items)
                del st.session_state['mc_parsed']
                st.success(f"✅ 导入完成：{saved} 条内容已保存，{created} 个作业任务已自动创建")
                st.rerun()
        with col2:
            if st.button("取消", key="mc_cancel"):
                del st.session_state['mc_parsed']
                st.rerun()

    # Show existing Moodle content history
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT course_name, course_code, content_type, title, due_date, created_at
        FROM moodle_content WHERE student_id=%s ORDER BY created_at DESC
    """, (student_id,))
    history = c.fetchall()
    conn.close()

    if history:
        st.divider()
        st.write("### 已导入的 Moodle 内容")

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
                    icon = icons.get(item[2], '📌')
                    due = f" | {item[4]}" if item[4] else ""
                    st.write(f"{icon} {item[3]}{due}")
