import streamlit as st
import sqlite3
import os
from datetime import datetime
from ai_helper import call_claude, get_teacher_progress_summary

def show_teacher_view(user):
    from task_detail import show_task_detail

    # 如果在任务详情页
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
                conn = sqlite3.connect("learning_platform.db")
                c = conn.cursor()
                c.execute(
                    "INSERT INTO tasks (title, description, due_date, subject, created_by) VALUES (?, ?, ?, ?, ?)",
                    (title, description, str(due_date), subject, user["id"])
                )
                task_id = c.lastrowid
                os.makedirs("uploads", exist_ok=True)
                for f in uploaded_files:
                    filepath = f"uploads/{task_id}_{f.name}"
                    with open(filepath, "wb") as out:
                        out.write(f.read())
                    c.execute(
                        "INSERT INTO task_files (task_id, filename, filepath) VALUES (?, ?, ?)",
                        (task_id, f.name, filepath)
                    )
                conn.commit()
                conn.close()
                st.success(f"任务「{title}」发布成功！")
            else:
                st.error("请输入任务标题")

    with tab3:
            # 待审批的删除申请
            conn = sqlite3.connect("learning_platform.db")
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
                                conn = sqlite3.connect("learning_platform.db")
                                c = conn.cursor()
                                c.execute("DELETE FROM tasks WHERE id=?", (req[5],))
                                c.execute("DELETE FROM task_files WHERE task_id=?", (req[5],))
                                c.execute("DELETE FROM progress WHERE task_id=?", (req[5],))
                                c.execute("UPDATE delete_requests SET status='approved' WHERE id=?", (req[0],))
                                conn.commit()
                                conn.close()
                                st.success("已批准，任务已删除")
                                st.rerun()
                        with col2:
                            if st.button("❌ 拒绝", key=f"reject_{req[0]}"):
                                conn = sqlite3.connect("learning_platform.db")
                                c = conn.cursor()
                                c.execute("UPDATE delete_requests SET status='rejected' WHERE id=?", (req[0],))
                                conn.commit()
                                conn.close()
                                st.success("已拒绝申请")
                                st.rerun()
                st.divider()

            st.write("### 所有任务")
            conn = sqlite3.connect("learning_platform.db")
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
                    # 自己发布 OR 学生发布的任务，老师都有权限
                    conn2 = sqlite3.connect("learning_platform.db")
                    c2 = conn2.cursor()
                    c2.execute("SELECT role FROM users WHERE id=?", (created_by,))
                    creator = c2.fetchone()
                    conn2.close()
                    is_owner = created_by == user["id"] or (creator and creator[0] == "student")

                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            owner_tag = "✏️ 我发布的" if is_owner else f"👤 {creator_name} 发布"
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
                                    conn = sqlite3.connect("learning_platform.db")
                                    c = conn.cursor()
                                    c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
                                    c.execute("DELETE FROM task_files WHERE task_id=?", (task_id,))
                                    c.execute("DELETE FROM progress WHERE task_id=?", (task_id,))
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
            st.write("查看学生进度，或者让我帮你起草任务说明")
            from chat_component import show_chat
            progress_summary = get_teacher_progress_summary()
            system_prompt = f"你是一个教学助手，帮助老师管理课程和学生进度。以下是所有学生的任务进度：\n\n{progress_summary}\n\n今天的日期是 {datetime.now().strftime('%Y-%m-%d')}。请用中文回答。"
            show_chat("teacher_ai_messages", system_prompt, "问我任何问题，比如：哪些学生还没完成任务？")