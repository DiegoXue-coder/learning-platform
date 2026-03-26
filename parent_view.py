import os
import streamlit as st
import sqlite3
from datetime import datetime
from dashboard import STATUS_MAP, render_progress_bar
from chat_component import show_chat

def show_parent_view(user):
    from task_detail import show_task_detail

    st.subheader("家长端")

    # 直接获取所有学生，无需绑定
    conn = sqlite3.connect("learning_platform.db")
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE role='student' ORDER BY username")
    students = c.fetchall()
    conn.close()

    if not students:
        st.info("暂时没有学生账号")
        return

    tab1, tab2 = st.tabs(["📊 学习总览", "💬 AI 助手"])

    with tab1:
        # 选择查看哪个学生
        if len(students) > 1:
            student_names = [s[1] for s in students]
            selected_name = st.selectbox("选择学生", student_names)
            selected_student = next(s for s in students if s[1] == selected_name)
        else:
            selected_student = students[0]

        student_id = selected_student[0]
        student_name = selected_student[1]

        st.write(f"### 👤 {student_name} 的学习情况")

        # 获取学生任务进度
        conn = sqlite3.connect("learning_platform.db")
        c = conn.cursor()
        c.execute("""
            SELECT t.id, t.title, t.subject, t.due_date,
                   COALESCE(p.status, 'pending') as status
            FROM tasks t
            LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = ?
            ORDER BY t.due_date
        """, (student_id,))
        tasks = c.fetchall()
        conn.close()

        if not tasks:
            st.info("暂无任务")
        else:
            # 统计
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

            # 任务进度列表
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

            # 查看任务详情（只读模式）
            if st.session_state.get("current_task_id") and st.session_state.get("task_source") == "parent":
                st.divider()
                task_id = st.session_state.current_task_id
                st.write("### 📋 任务详情")

                if st.button("← 返回"):
                    st.session_state.current_task_id = None
                    st.rerun()

                conn = sqlite3.connect("learning_platform.db")
                c = conn.cursor()
                c.execute("SELECT title, description, due_date, subject FROM tasks WHERE id=?", (task_id,))
                task = c.fetchone()
                c.execute("SELECT status FROM progress WHERE student_id=? AND task_id=?", (student_id, task_id))
                progress = c.fetchone()
                c.execute("""
                    SELECT submission_type, filename, created_at
                    FROM submissions
                    WHERE task_id=? AND student_id=? AND submission_type != 'teacher_feedback'
                    ORDER BY created_at DESC
                """, (task_id, student_id))
                submissions = c.fetchall()
                conn.close()

                if task:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**学科：** {task[3]}")
                        st.write(f"**截止日期：** {task[2] or '未设定'}")
                        if task[1]:
                            st.write(f"**任务说明：** {task[1]}")
                    with col2:
                        status = progress[0] if progress else "pending"
                        st.write(f"**当前状态：** {STATUS_MAP.get(status, status)}")

                    st.divider()

                    # 提交记录详情
                    if submissions:
                        st.write("### 📁 孩子的提交记录")
                        type_map = {
                            "assignment": "📄 作业文件",
                            "screenshot": "🖼️ 提交截图",
                            "teacher_feedback": "💬 老师评语"
                        }
                        
                        # 获取老师评语
                        conn2 = sqlite3.connect("learning_platform.db")
                        c2 = conn2.cursor()
                        c2.execute("""
                            SELECT comment, created_at FROM submissions
                            WHERE task_id=? AND student_id=? AND submission_type='teacher_feedback'
                            ORDER BY created_at DESC
                        """, (task_id, student_id))
                        feedbacks = c2.fetchall()
                        conn2.close()

                        for sub in submissions:
                            sub_type, filename, created_at = sub
                            with st.expander(f"{type_map.get(sub_type, sub_type)} — {created_at}"):
                                if filename:
                                    # 检查是否是链接（备注里）
                                    conn2 = sqlite3.connect("learning_platform.db")
                                    c2 = conn2.cursor()
                                    c2.execute("""
                                        SELECT filepath, comment FROM submissions
                                        WHERE task_id=? AND student_id=? AND submission_type=? AND created_at=?
                                    """, (task_id, student_id, sub_type, created_at))
                                    sub_detail = c2.fetchone()
                                    conn2.close()

                                    if sub_detail:
                                        filepath, comment = sub_detail
                                        if filepath and os.path.exists(filepath):
                                            with open(filepath, "rb") as f:
                                                st.download_button(
                                                    label=f"下载 {filename}",
                                                    data=f,
                                                    file_name=filename,
                                                    key=f"parent_dl_{task_id}_{created_at}"
                                                )
                                        if comment:
                                            st.write(f"**备注/链接：**")
                                            st.code(comment)

                        if feedbacks:
                            st.write("### 💬 老师评语记录")
                            for fb in feedbacks:
                                st.warning(f"**{fb[1]}** — {fb[0]}")
                    else:
                        st.info("孩子还没有提交任何文件")

    with tab2:
        st.write("### 💬 AI 学习助手")
        st.write("了解孩子的学习情况")

        # 获取学生任务摘要
        conn = sqlite3.connect("learning_platform.db")
        c = conn.cursor()
        c.execute("""
            SELECT t.title, t.subject, t.due_date,
                   COALESCE(p.status, 'pending') as status
            FROM tasks t
            LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = ?
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
以下是学生 {students[0][1]} 的任务进度：

{task_summary}

今天的日期是 {datetime.now().strftime('%Y-%m-%d')}。
请用温和、积极的语气向家长汇报孩子的学习情况，用中文回答。"""

        show_chat("parent_ai_messages", system_prompt, "询问孩子的学习情况，比如：孩子最近学习怎么样？")