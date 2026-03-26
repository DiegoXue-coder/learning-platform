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
            c.execute("SELECT id, title, subject, due_date, created_at FROM tasks WHERE created_by=? ORDER BY due_date", (user["id"],))
            tasks = c.fetchall()
            conn.close()

            if tasks:
                for task in tasks:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"### 📋 {task[1]}")
                            st.write(f"**学科：** {task[2]} | **截止：** {task[3]}")
                        with col2:
                            if st.button("查看/编辑", key=f"teacher_view_{task[0]}"):
                                st.session_state.current_task_id = task[0]
                                st.session_state.task_source = "teacher"
                                st.rerun()
                        with col3:
                            if st.button("🗑️ 删除", key=f"teacher_del_{task[0]}"):
                                conn = sqlite3.connect("learning_platform.db")
                                c = conn.cursor()
                                c.execute("DELETE FROM tasks WHERE id=?", (task[0],))
                                c.execute("DELETE FROM task_files WHERE task_id=?", (task[0],))
                                c.execute("DELETE FROM progress WHERE task_id=?", (task[0],))
                                conn.commit()
                                conn.close()
                                st.success("任务已删除")
                                st.rerun()
                        st.divider()
            else:
                st.info("还没有发布任何任务")

    with tab4:
            st.write("### 💬 AI 助手")
            st.write("查看学生进度，或者让我帮你起草任务说明")
            from chat_component import show_chat
            progress_summary = get_teacher_progress_summary()
            system_prompt = f"你是一个教学助手，帮助老师管理课程和学生进度。以下是所有学生的任务进度：\n\n{progress_summary}\n\n今天的日期是 {datetime.now().strftime('%Y-%m-%d')}。请用中文回答。"
            show_chat("teacher_ai_messages", system_prompt, "问我任何问题，比如：哪些学生还没完成任务？")