import streamlit as st
import base64
import os
from datetime import datetime
from database import get_conn
from ai_helper import call_claude, get_teacher_progress_summary

def show_teacher_view(user):
    from task_detail import show_task_detail

    if st.session_state.get("current_task_id") and st.session_state.get("task_source") == "teacher":
        show_task_detail(st.session_state.current_task_id, user)
        return

    st.subheader("老师端")
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 总览", "📝 发布任务", "📋 查看所有任务", "💬 AI 助手"])

    with tab1:
        from dashboard import show_teacher_dashboard
        show_teacher_dashboard(user)

    with tab2:
        st.write("### 发布新任务")
        title = st.text_input("任务标题")
        description = st.text_area("任务说明")
        subject = st.text_input("学科")
        due_date = st.date_input("截止日期")
        uploaded_files = st.file_uploader("上传文件（PDF）", type=["pdf"], accept_multiple_files=True)

        if st.button("发布任务"):
            if title:
                conn = get_conn()
                c = conn.cursor()
                c.execute("INSERT INTO tasks (title, description, due_date, subject, created_by) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (title, description, str(due_date), subject, user["id"]))
                task_id = c.fetchone()[0]
                os.makedirs("uploads", exist_ok=True)
                for f in uploaded_files:
                    filepath = f"uploads/{task_id}_{f.name}"
                    with open(filepath, "wb") as out:
                        out.write(f.read())
                    c.execute("INSERT INTO task_files (task_id, filename, filepath) VALUES (%s, %s, %s)",
                        (task_id, f.name, filepath))
                conn.commit()
                conn.close()
                st.success(f"任务「{title}」发布成功！")
            else:
                st.error("请输入任务标题")

    with tab3:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT dr.id, t.title, u.username, dr.reason, dr.created_at, dr.task_id
            FROM delete_requests dr
            JOIN tasks t ON dr.task_id = t.id
            JOIN users u ON dr.student_id = u.id
            WHERE dr.status = 'pending'
        """)
        requests = c.fetchall()
        conn.close()

        if requests:
            st.warning(f"⚠️ 有 {len(requests)} 个待审批的删除申请")
            for req in requests:
                with st.expander(f"📋 {req[1]} — 学生：{req[2]}"):
                    st.write(f"**申请理由：** {req[3] or '无'}")
                    st.write(f"**申请时间：** {req[4]}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ 批准删除", key=f"approve_{req[0]}"):
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute("DELETE FROM tasks WHERE id=%s", (req[5],))
                            c.execute("DELETE FROM task_files WHERE task_id=%s", (req[5],))
                            c.execute("DELETE FROM progress WHERE task_id=%s", (req[5],))
                            c.execute("UPDATE delete_requests SET status='approved' WHERE id=%s", (req[0],))
                            conn.commit()
                            conn.close()
                            st.success("已批准，任务已删除")
                            st.rerun()
                    with col2:
                        if st.button("❌ 拒绝", key=f"reject_{req[0]}"):
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute("UPDATE delete_requests SET status='rejected' WHERE id=%s", (req[0],))
                            conn.commit()
                            conn.close()
                            st.success("已拒绝申请")
                            st.rerun()
            st.divider()

        st.write("### 所有任务")
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT t.id, t.title, t.subject, t.due_date, t.created_by, u.username
            FROM tasks t
            JOIN users u ON t.created_by = u.id
            ORDER BY t.due_date
        """)
        tasks = c.fetchall()
        conn.close()

        if tasks:
            for task in tasks:
                task_id, title, subject, due_date, created_by, creator_name = task
                is_owner = created_by == user["id"]
                conn2 = get_conn()
                c2 = conn2.cursor()
                c2.execute("SELECT role FROM users WHERE id=%s", (created_by,))
                creator = c2.fetchone()
                conn2.close()
                is_owner = created_by == user["id"] or (creator and creator[0] == "student")

                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        owner_tag = "✏️ 我发布的" if created_by == user["id"] else f"👤 {creator_name} 发布"
                        st.write(f"### 📋 {title}")
                        st.write(f"**学科：** {subject} | **截止：** {due_date} | {owner_tag}")
                    with col2:
                        btn_label = "查看/编辑" if is_owner else "查看"
                        if st.button(btn_label, key=f"teacher_view_{task_id}"):
                            st.session_state.current_task_id = task_id
                            st.session_state.task_source = "teacher"
                            st.rerun()
                    with col3:
                        if is_owner:
                            if st.button("🗑️ 删除", key=f"teacher_del_{task_id}"):
                                conn = get_conn()
                                c = conn.cursor()
                                c.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
                                c.execute("DELETE FROM task_files WHERE task_id=%s", (task_id,))
                                c.execute("DELETE FROM progress WHERE task_id=%s", (task_id,))
                                conn.commit()
                                conn.close()
                                st.success("任务已删除")
                                st.rerun()
                        else:
                            st.write("🔒 无编辑权限")
                    st.divider()
        else:
            st.info("还没有任何任务")

    with tab4:
        st.write("### 💬 AI 助手")

        with st.expander("📎 上传文件让AI分析（可选）", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                uploaded_pdf = st.file_uploader("上传 PDF", type=["pdf"], key="teacher_ai_pdf")
            with col2:
                uploaded_img = st.file_uploader("上传图片", type=["jpg","jpeg","png","webp"], key="teacher_ai_img")

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
                if st.button("🗑️ 移除文件", key="remove_teacher_file"):
                    del st.session_state["ai_file_context"]
                    st.rerun()

        col1, col2, col3, col4 = st.columns(4)
        quick_prompt = None
        with col1:
            if st.button("📋 总结文件", key="tqs1"):
                quick_prompt = "请帮我总结这份文件的主要内容。"
        with col2:
            if st.button("📝 起草任务说明", key="tqs2"):
                quick_prompt = "请根据这份文件内容，帮我起草一份学生任务说明。"
        with col3:
            if st.button("❓ 出练习题", key="tqs3"):
                quick_prompt = "请根据这份文件内容，出5道练习题并提供答案。"
        with col4:
            if st.button("📊 分析进度", key="tqs4"):
                quick_prompt = "请分析一下学生的整体学习进度，有哪些需要关注的地方？"

        from chat_component import show_chat_with_files
        progress_summary = get_teacher_progress_summary()
        system_prompt = f"你是一个教学助手，帮助老师管理课程和学生进度。以下是所有学生的任务进度：\n\n{progress_summary}\n\n今天的日期是 {datetime.now().strftime('%Y-%m-%d')}。请用中文回答。"
        show_chat_with_files("teacher_ai_messages", system_prompt, "问我任何问题，比如：哪些学生还没完成任务？", user_id=user["id"], quick_prompt=quick_prompt)