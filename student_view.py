import streamlit as st
import os
import re
import json
import base64
from datetime import datetime
from parse_course import read_pdf, parse_course_outline, get_file_hash
from ai_helper import call_claude, get_student_task_summary
from database import get_conn

def show_student_view(user):
    from task_detail import show_task_detail

    if st.session_state.get("current_task_id") and st.session_state.get("task_source") == "student":
        show_task_detail(st.session_state.current_task_id, user)
        return

    st.subheader("学生端")
    tab_tt, tab_overview, tab_tasks, tab_moodle, tab_ai, tab_files, tab_lib, tab_settings = st.tabs([
        "📅 课程表", "🏠 总览", "✅ 任务", "🔗 Moodle", "💬 AI 助手", "📁 上传资料", "📚 资料库", "⚙️ 设置"
    ])

    with tab_tt:
        from timetable_view import show_timetable
        show_timetable(user)

    with tab_overview:
        from dashboard import show_student_dashboard
        show_student_dashboard(user)

    with tab_moodle:
        from moodle_import import show_moodle_import
        show_moodle_import(user)

    with tab_settings:
        from settings_view import show_settings
        show_settings(user)

    with tab_tasks:
        st.write("### 我的任务")
        conn = get_conn()
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

    with tab_ai:
        st.write("### 💬 AI 助手")

        with st.expander("📎 上传文件让AI分析（可选）", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                uploaded_pdf = st.file_uploader("上传 PDF", type=["pdf"], key="ai_pdf")
            with col2:
                uploaded_img = st.file_uploader("上传图片", type=["jpg","jpeg","png","webp"], key="ai_img")

            if uploaded_pdf:
                pdf_bytes = uploaded_pdf.read()
                st.session_state["ai_file_context"] = {
                    "type": "pdf", "name": uploaded_pdf.name,
                    "b64": base64.standard_b64encode(pdf_bytes).decode()
                }
                st.success(f"✅ 已加载：{uploaded_pdf.name}")

            if uploaded_img:
                img_bytes = uploaded_img.read()
                ext = uploaded_img.name.split(".")[-1].lower()
                media_map = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}
                st.session_state["ai_file_context"] = {
                    "type": "image", "name": uploaded_img.name,
                    "b64": base64.standard_b64encode(img_bytes).decode(),
                    "media_type": media_map.get(ext, "image/jpeg")
                }
                st.image(uploaded_img, width=300)
                st.success(f"✅ 已加载：{uploaded_img.name}")

            if st.session_state.get("ai_file_context"):
                st.caption(f"当前文件：{st.session_state['ai_file_context']['name']}")
                if st.button("🗑️ 移除文件", key="remove_ai_file"):
                    del st.session_state["ai_file_context"]
                    st.rerun()

        col1, col2, col3, col4 = st.columns(4)
        quick_prompt = None
        with col1:
            if st.button("📋 总结文件", key="qs1"):
                quick_prompt = "请帮我总结这份文件的主要内容，用要点形式列出。"
        with col2:
            if st.button("📝 生成提纲", key="qs2"):
                quick_prompt = "请根据这份文件内容，帮我生成一份作业提纲。"
        with col3:
            if st.button("❓ 出练习题", key="qs3"):
                quick_prompt = "请根据这份文件内容，出5道练习题并提供答案。"
        with col4:
            if st.button("🔍 解释难点", key="qs4"):
                quick_prompt = "请找出这份文件中最难理解的概念，用简单易懂的方式解释。"

        from chat_component import show_chat_with_files
        task_summary = get_student_task_summary(user["id"])
        system_prompt = f"""你是一个学习助手，以下是这位学生的任务和课程资料信息：

{task_summary}

今天的日期是 {datetime.now().strftime('%Y-%m-%d')}。

重要规则：
- 只根据上面提供的真实信息回答
- 如果课程资料库显示文件无法读取，绝对不要编造文件内容
- 请用中文回答"""
        show_chat_with_files("student_ai_messages", system_prompt, "问我任何问题，或上传文件让我分析...", user_id=user["id"], quick_prompt=quick_prompt)

    with tab_files:
        st.write("### 上传课程文件")
        st.write("上传任何课程 PDF，系统自动识别类型并归类")

        outline_files = st.file_uploader("上传 PDF 文件", type=["pdf"], key="outline_uploader", accept_multiple_files=True)

        if outline_files and st.button("开始解析"):
            os.makedirs("outlines", exist_ok=True)

            for outline_file in outline_files:
                st.write(f"---\n#### 正在处理：{outline_file.name}")

                file_bytes = outline_file.read()
                filepath = f"outlines/{outline_file.name}"
                with open(filepath, "wb") as f:
                    f.write(file_bytes)

                file_hash = get_file_hash(filepath)
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT title FROM course_materials WHERE file_hash=%s AND student_id=%s", (file_hash, user["id"]))
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

                    # 存文件内容到数据库（核心改动：content 字段）
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO course_materials (course_code, course_name, week_number, title, filepath, student_id, file_hash, content) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (course_code, course_name, week_number, outline_file.name, filepath, user["id"], file_hash, pdf_text[:10000])
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"✅ 已归类到课程资料库（内容已保存）")
                else:
                    st.error(f"{outline_file.name} 解析失败")

            st.info("解析完成！去「我的任务」或「课程资料」查看结果")

    with tab_lib:
        st.write("### 课程资料库")

        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT id, course_code, course_name, week_number, title, filepath, created_at
            FROM course_materials
            WHERE student_id = %s
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

            if "classify_suggestions" in st.session_state and st.session_state.classify_suggestions:
                st.write("### 🤖 AI 归类建议")
                all_codes = [(code, data["name"]) for code, data in courses_dict.items() if code != "None"]
                code_options = ["不归类（保留在 None）"] + [f"{c[0]} - {c[1]}" for c in all_codes]
                confirmed = {}
                for suggestion in st.session_state.classify_suggestions:
                    file_id = suggestion["file_id"]
                    suggested = suggestion.get("suggested_course_code")
                    confidence = suggestion.get("confidence", "low")
                    reason = suggestion.get("reason", "")
                    file_title = next((f[4] for f in materials if f[0] == file_id), f"文件{file_id}")
                    st.write(f"**{file_title}**")
                    st.caption(f"AI 建议：{suggested or '无法匹配'} | 置信度：{confidence} | 理由：{reason}")
                    default_idx = 0
                    if suggested:
                        for i, c in enumerate(all_codes):
                            if c[0] == suggested:
                                default_idx = i + 1
                                break
                    choice = st.selectbox("归类到", code_options, index=default_idx, key=f"classify_{file_id}")
                    confirmed[file_id] = choice
                    st.divider()

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 确认应用所有归类"):
                        conn = get_conn()
                        c = conn.cursor()
                        updated = 0
                        for file_id, choice in confirmed.items():
                            if choice != "不归类（保留在 None）":
                                course_code = choice.split(" - ")[0]
                                course_name = choice.split(" - ")[1]
                                c.execute("UPDATE course_materials SET course_code=%s, course_name=%s WHERE id=%s",
                                    (course_code, course_name, file_id))
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
                        checked = st.checkbox("", key=f"chk_{file_id}",
                            value=st.session_state.checked_files.get(file_id, False))
                        st.session_state.checked_files[file_id] = checked
                    with col2:
                        st.write(f"📄 {week} — {f[4]}")
                    with col3:
                        if os.path.exists(f[5]):
                            with open(f[5], "rb") as file_data:
                                st.download_button(label="下载", data=file_data,
                                    file_name=f[4], mime="application/pdf", key=f"dl_{file_id}")
                st.divider()

            selected = [m for m in materials if st.session_state.checked_files.get(m[0], False)]

            if selected:
                st.info(f"已选择 {len(selected)} 个文件")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 提取选中文件的作业任务"):
                        st.session_state.pending_tasks = []
                        for f in selected:
                            st.write(f"正在分析：{f[4]}")
                            with st.spinner("AI 深度分析中..."):
                                # 优先从数据库读content，读不到再读文件
                                conn = get_conn()
                                c = conn.cursor()
                                c.execute("SELECT content FROM course_materials WHERE id=%s", (f[0],))
                                row = c.fetchone()
                                conn.close()
                                pdf_text = row[0] if row and row[0] else read_pdf(f[5])

                                from ai_helper import API_KEY
                                import requests
                                response = requests.post(
                                    "https://api.anthropic.com/v1/messages",
                                    headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                                    json={"model": "claude-opus-4-5", "max_tokens": 2000, "messages": [{"role": "user", "content": f"""这是一份作业相关文件，请提取所有作业任务信息。严格按照JSON格式返回：\n{{"tasks": [{{"title": "作业名称","due_date": "YYYY-MM-DD或null","weight": "占比或null","description": "简短说明"}}]}}\n文件内容：{pdf_text}"""}]}
                                )
                                result = response.json()
                                text = next((block["text"] for block in result.get("content", []) if block.get("type") == "text"), "")
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
                        conn = get_conn()
                        c = conn.cursor()
                        for f in selected:
                            c.execute("DELETE FROM course_materials WHERE id=%s AND student_id=%s", (f[0], user["id"]))
                            if os.path.exists(f[5]):
                                os.remove(f[5])
                            st.session_state.checked_files.pop(f[0], None)
                        conn.commit()
                        conn.close()
                        st.success(f"已删除 {len(selected)} 个文件")
                        st.rerun()

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
                        conn = get_conn()
                        c = conn.cursor()
                        added = 0
                        for task in st.session_state.pending_tasks:
                            if task["selected"]:
                                c.execute("INSERT INTO tasks (title, description, due_date, subject, created_by) VALUES (%s, %s, %s, %s, %s)",
                                    (task["title"], f"{task['description']} 占比：{task['weight']}", task["due_date"], task["subject"], user["id"]))
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