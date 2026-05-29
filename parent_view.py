import os
import base64
import streamlit as st
from datetime import datetime
from database import get_conn
from dashboard import STATUS_MAP, render_progress_bar
from chat_component import show_chat_with_files

def show_parent_view(user):
    st.subheader("家长端")

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE role='student' ORDER BY username")
    students = c.fetchall()
    conn.close()

    if not students:
        st.info("暂时没有学生账号")
        return

    tab1, tab2 = st.tabs(["📊 学习总览", "💬 AI 助手"])

    with tab1:
        if len(students) > 1:
            student_names = [s[1] for s in students]
            selected_name = st.selectbox("选择学生", student_names)
            selected_student = next(s for s in students if s[1] == selected_name)
        else:
            selected_student = students[0]

        student_id = selected_student[0]
        student_name = selected_student[1]

        st.write(f"### 👤 {student_name} 的学习情况")

        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT t.id, t.title, t.subject, t.due_date,
                   COALESCE(p.status, 'pending') as status
            FROM tasks t
            LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = %s
            ORDER BY t.due_date
        """, (student_id,))
        tasks = c.fetchall()
        conn.close()

        if not tasks:
            st.info("暂无任务")
        else:
            total = len(tasks)
            completed = sum(1 for t in tasks if t[4] == "completed")
            in_progress = sum(1 for t in tasks if t[4] not in ["pending", "completed"])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📋 总任务", total)
            with col2:
                st.metric("🔵 进行中", in_progress)
            with col3:
                st.metric("✅ 已完成", completed)

            st.divider()
            st.write("### 📊 任务进度")
            for task in tasks:
                task_id, title, subject, due_date, status = task
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"**{title}** | {subject} | 截止：{due_date or '未设定'}")
                    with col2:
                        if st.button("查看详情", key=f"parent_view_{task_id}"):
                            st.session_state.current_task_id = task_id
                            st.session_state.task_source = "parent"
                            st.rerun()
                    render_progress_bar(status)
                    st.write("")

    with tab2:
        st.write("### 💬 AI 助手")

        with st.expander("📎 上传文件让AI分析（可选）", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                uploaded_pdf = st.file_uploader("上传 PDF", type=["pdf"], key="parent_ai_pdf")
            with col2:
                uploaded_img = st.file_uploader("上传图片", type=["jpg","jpeg","png","webp"], key="parent_ai_img")

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
                if st.button("🗑️ 移除文件", key="remove_parent_file"):
                    del st.session_state["ai_file_context"]
                    st.rerun()

        col1, col2, col3 = st.columns(3)
        quick_prompt = None
        with col1:
            if st.button("📋 总结文件", key="pqs1"):
                quick_prompt = "请帮我总结这份文件的主要内容。"
        with col2:
            if st.button("📊 孩子学习情况", key="pqs2"):
                quick_prompt = "请帮我分析孩子目前的学习情况，有什么需要注意的？"
        with col3:
            if st.button("💡 学习建议", key="pqs3"):
                quick_prompt = "请根据孩子目前的任务情况，给出一些具体的学习建议。"

        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT t.title, t.subject, t.due_date,
                   COALESCE(p.status, 'pending') as status
            FROM tasks t
            LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = %s
            ORDER BY t.due_date
        """, (students[0][0],))
        task_data = c.fetchall()
        conn.close()

        status_map_cn = {"pending": "未接收", "in_progress": "进行中", "submitted": "待审核",
                        "content_approved": "内容通过", "check_confirmed": "检测确认",
                        "submit_approved": "待提交", "completed": "已完成", "needs_revision": "需修改"}
        task_summary = "\n".join([
            f"- 任务：{t[0]}，学科：{t[1]}，截止：{t[2]}，状态：{status_map_cn.get(t[3], t[3])}"
            for t in task_data
        ])
        system_prompt = f"""你是一个学习助手，帮助家长了解孩子的学习情况。
以下是学生 {students[0][1]} 的任务进度：\n{task_summary}\n今天的日期是 {datetime.now().strftime('%Y-%m-%d')}。
请用温和、积极的语气回答，用中文。"""

        show_chat_with_files("parent_ai_messages", system_prompt, "询问孩子的学习情况...", user_id=user["id"], quick_prompt=quick_prompt)