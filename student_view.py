import streamlit as st
import sqlite3
import os
import re
import json
import pandas as pd
from datetime import datetime
from parse_course import read_pdf, parse_course_outline, get_file_hash
from ai_helper import call_claude, get_student_task_summary

def show_student_view(user):
    from task_detail import show_task_detail

    # 任务详情页路由
    if st.session_state.get("current_task_id") and st.session_state.get("task_source") == "student":
        show_task_detail(st.session_state.current_task_id, user)
        return

    st.subheader("学生端")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 总览", "📋 我的任务", "💬 AI 助手", "📁 上传课程文件", "📚 课程资料库"])

    with tab1:
        from dashboard import show_student_dashboard
        show_student_dashboard(user)

    with tab2:
        st.write("### 我的任务")
        conn = sqlite3.connect("learning_platform.db")
        c = conn.cursor()
        c.execute("SELECT id, title, subject, due_date, created_at FROM tasks ORDER BY due_date")
        tasks = c.fetchall()
        conn.close()

        if tasks:
            for task in tasks:
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"### 📋 {task[1]}")
                        st.write(f"**学科：** {task[2]} | **截止：** {task[3]}")
                    with col2:
                        if st.button("查看详情", key=f"student_view_{task[0]}"):
                            st.session_state.current_task_id = task[0]
                            st.session_state.task_source = "student"
                            st.rerun()
                    st.divider()
        else:
            st.info("暂时没有任务")

    with tab3:
            st.write("### 💬 AI 学习助手")
            from chat_component import show_chat
            from ai_helper import get_student_task_summary
            task_summary = get_student_task_summary(user["id"])
            system_prompt = f"你是一个学习助手，以下是这位学生的所有任务信息：\n\n{task_summary}\n\n今天的日期是 {datetime.now().strftime('%Y-%m-%d')}。请根据这些信息回答学生的问题，用中文回答。"
            show_chat("student_ai_messages", system_prompt, "问我任何问题，比如：这周我要做什么？")

    with tab4:
        st.write("### 上传课程文件")
        st.write("上传任何课程 PDF，系统自动识别类型并归类")

        outline_files = st.file_uploader("上传 PDF 文件", type=["pdf"], key="outline_uploader", accept_multiple_files=True)

        if outline_files and st.button("开始解析"):
            os.makedirs("outlines", exist_ok=True)

            for outline_file in outline_files:
                st.write(f"---\n#### 正在处理：{outline_file.name}")

                filepath = f"outlines/{outline_file.name}"
                with open(filepath, "wb") as f:
                    f.write(outline_file.read())

                file_hash = get_file_hash(filepath)
                conn = sqlite3.connect("learning_platform.db")
                c = conn.cursor()
                c.execute("SELECT title FROM course_materials WHERE file_hash=? AND student_id=?", (file_hash, user["id"]))
                existing = c.fetchone()
                conn.close()

                if existing:
                    st.warning(f"⚠️ 文件已存在，跳过")
                    os.remove(filepath)
                    continue

                with st.spinner(f"AI 正在分析 {outline_file.name}..."):
                    pdf_text = read_pdf(filepath)
                    result = parse_course_outline(pdf_text, filename=outline_file.name)

                if result:
                    course_code = result.get("course_code", "未知")
                    course_name = result.get("course_name", "未知课程")
                    week_number = result.get("week_number")
                    material_type = result.get("material_type", "其他")

                    st.info(f"📚 课程：{course_name} ({course_code}) | 类型：{material_type} | 周数：{week_number or '未知'}")

                    conn = sqlite3.connect("learning_platform.db")
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO course_materials (course_code, course_name, week_number, title, filepath, student_id, file_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (course_code, course_name, week_number, outline_file.name, filepath, user["id"], file_hash)
                    )

                    conn.commit()
                    conn.close()
                    st.success(f"✅ 已归类到课程资料库")

                else:
                    st.error(f"{outline_file.name} 解析失败")

            st.info("解析完成！去「我的任务」或「课程资料」查看结果")

    with tab5:
        st.write("### 课程资料库")

        conn = sqlite3.connect("learning_platform.db")
        c = conn.cursor()
        c.execute("""
            SELECT id, course_code, course_name, week_number, title, filepath, created_at
            FROM course_materials
            WHERE student_id = ?
            ORDER BY course_code, week_number
        """, (user["id"],))
        materials = c.fetchall()
        conn.close()

        if materials:
            if "checked_files" not in st.session_state:
                st.session_state.checked_files = {}

            courses_dict = {}
            for m in materials:
                code = m[1]
                if code not in courses_dict:
                    courses_dict[code] = {"name": m[2], "files": []}
                courses_dict[code]["files"].append(m)

            # 智能整理 None 文件
            if None in courses_dict:
                st.warning(f"⚠️ 有 {len(courses_dict[None]['files'])} 个文件未能自动归类")
                if st.button("🤖 智能整理 None 文件"):
                    from ai_helper import smart_classify_files
                    
                    none_files = [(f[0], f[4], f[5]) for f in courses_dict[None]["files"]]
                    existing_courses = [(code, data["name"]) for code, data in courses_dict.items() if code is not None]
                    
                    with st.spinner("AI 正在分析文件内容，智能匹配课程..."):
                        result = smart_classify_files(none_files, existing_courses)
                    
                    if result:
                        st.session_state.classify_suggestions = result["classifications"]
                        st.rerun()

            # 显示归类建议
            if "classify_suggestions" in st.session_state and st.session_state.classify_suggestions:
                st.write("### 🤖 AI 归类建议")
                st.write("请确认或修改以下归类建议：")
                
                all_codes = [(code, data["name"]) for code, data in courses_dict.items() if code != "None"]
                code_options = ["不归类（保留在 None）"] + [f"{c[0]} - {c[1]}" for c in all_codes]
                
                confirmed = {}
                for suggestion in st.session_state.classify_suggestions:
                    file_id = suggestion["file_id"]
                    suggested = suggestion.get("suggested_course_code")
                    confidence = suggestion.get("confidence", "low")
                    reason = suggestion.get("reason", "")
                    
                    # 找到文件名
                    file_title = next((f[4] for f in materials if f[0] == file_id), f"文件{file_id}")
                    
                    st.write(f"**{file_title}**")
                    st.caption(f"AI 建议：{suggested or '无法匹配'} | 置信度：{confidence} | 理由：{reason}")
                    
                    # 默认选中 AI 建议的课程
                    default_idx = 0
                    if suggested:
                        for i, c in enumerate(all_codes):
                            if c[0] == suggested:
                                default_idx = i + 1
                                break
                    
                    choice = st.selectbox(
                        "归类到",
                        code_options,
                        index=default_idx,
                        key=f"classify_{file_id}"
                    )
                    confirmed[file_id] = choice
                    st.divider()
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 确认应用所有归类"):
                        conn = sqlite3.connect("learning_platform.db")
                        c = conn.cursor()
                        updated = 0
                        for file_id, choice in confirmed.items():
                            if choice != "不归类（保留在 None）":
                                course_code = choice.split(" - ")[0]
                                course_name = choice.split(" - ")[1]
                                c.execute(
                                    "UPDATE course_materials SET course_code=?, course_name=? WHERE id=?",
                                    (course_code, course_name, file_id)
                                )
                                updated += 1
                        conn.commit()
                        conn.close()
                        del st.session_state.classify_suggestions
                        st.success(f"✅ 已更新 {updated} 个文件的归类")
                        st.rerun()
                with col2:
                    if st.button("❌ 取消"):
                        del st.session_state.classify_suggestions
                        st.rerun()

            for code, data in courses_dict.items():
                st.write(f"### 📖 {data['name']} ({code or '未归类'})")
                files_sorted = sorted(data["files"], key=lambda x: x[3] or 999)

                for f in files_sorted:
                    file_id = f[0]
                    week = f"Week {f[3]}" if f[3] else "未知"
                    col1, col2, col3 = st.columns([0.05, 0.6, 0.35])

                    with col1:
                        checked = st.checkbox(
                            "",
                            key=f"chk_{file_id}",
                            value=st.session_state.checked_files.get(file_id, False)
                        )
                        st.session_state.checked_files[file_id] = checked

                    with col2:
                        st.write(f"📄 {week} — {f[4]}")

                    with col3:
                        if os.path.exists(f[5]):
                            with open(f[5], "rb") as file_data:
                                st.download_button(
                                    label="下载",
                                    data=file_data,
                                    file_name=f[4],
                                    mime="application/pdf",
                                    key=f"dl_{file_id}"
                                )

                st.divider()

            selected = [
                m for m in materials
                if st.session_state.checked_files.get(m[0], False)
            ]

            if selected:
                st.info(f"已选择 {len(selected)} 个文件")
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🔍 提取选中文件的作业任务"):
                        st.session_state.pending_tasks = []
                        for f in selected:
                            st.write(f"正在分析：{f[4]}")
                            with st.spinner("AI 深度分析中..."):
                                pdf_text = read_pdf(f[5])
                                from ai_helper import API_KEY
                                import requests
                                response = requests.post(
                                    "https://api.anthropic.com/v1/messages",
                                    headers={
                                        "x-api-key": API_KEY,
                                        "anthropic-version": "2023-06-01",
                                        "content-type": "application/json"
                                    },
                                    json={
                                        "model": "claude-opus-4-5",
                                        "max_tokens": 2000,
                                        "messages": [{
                                            "role": "user",
                                            "content": f"""这是一份作业相关文件，请提取所有作业任务信息。

严格按照JSON格式返回，不要返回其他文字：

{{
  "tasks": [
    {{
      "title": "作业名称，比如Assignment 1",
      "due_date": "截止日期YYYY-MM-DD格式，没有则填null",
      "weight": "占比，比如30%，没有则填null",
      "description": "简短说明"
    }}
  ]
}}

文件内容：
{pdf_text}"""
                                        }]
                                    }
                                )
                                result = response.json()
                                # 修复：按 type 过滤，避免 KeyError
                                text = next(
                                    (block["text"] for block in result.get("content", []) if block.get("type") == "text"),
                                    ""
                                )
                                try:
                                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                                    if json_match:
                                        parsed = json.loads(json_match.group())
                                        for task in parsed.get("tasks", []):
                                            if task.get("title"):
                                                st.session_state.pending_tasks.append({
                                                    "title": task["title"],
                                                    "due_date": task.get("due_date"),
                                                    "description": task.get("description", ""),
                                                    "weight": task.get("weight", ""),
                                                    "subject": f[1],
                                                    "selected": True
                                                })
                                except:
                                    st.error(f"{f[4]} 解析失败")
                        st.rerun()

                with col2:
                    if st.button("🗑️ 删除选中文件"):
                        conn = sqlite3.connect("learning_platform.db")
                        c = conn.cursor()
                        for f in selected:
                            c.execute("DELETE FROM course_materials WHERE id=? AND student_id=?",
                                (f[0], user["id"]))
                            if os.path.exists(f[5]):
                                os.remove(f[5])
                            st.session_state.checked_files.pop(f[0], None)
                        conn.commit()
                        conn.close()
                        st.success(f"已删除 {len(selected)} 个文件")
                        st.rerun()

            # 待确认任务列表
            if "pending_tasks" in st.session_state and st.session_state.pending_tasks:
                st.write("---")
                st.write("### ✅ 确认以下任务添加到任务列表")

                for i, task in enumerate(st.session_state.pending_tasks):
                    col1, col2 = st.columns([0.05, 0.95])
                    with col1:
                        task["selected"] = st.checkbox("", value=task["selected"], key=f"pending_{i}")
                    with col2:
                        st.write(f"**{task['title']}** — 截止：{task['due_date'] or '未知'} — 占比：{task['weight'] or '未知'}")
                        if task["description"]:
                            st.caption(task["description"])

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 确认添加选中任务"):
                        conn = sqlite3.connect("learning_platform.db")
                        c = conn.cursor()
                        added = 0
                        for task in st.session_state.pending_tasks:
                            if task["selected"]:
                                c.execute(
                                    "INSERT INTO tasks (title, description, due_date, subject, created_by) VALUES (?, ?, ?, ?, ?)",
                                    (task["title"], f"{task['description']} 占比：{task['weight']}", task["due_date"], task["subject"], user["id"])
                                )
                                added += 1
                        conn.commit()
                        conn.close()
                        del st.session_state.pending_tasks
                        st.success(f"✅ 已添加 {added} 个任务到任务列表")
                        st.rerun()
                with col2:
                    if st.button("❌ 取消"):
                        del st.session_state.pending_tasks
                        st.rerun()
        else:
            st.info("还没有上传任何课程资料，去「上传课程文件」开始上传")
    
