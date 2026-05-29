from database import get_conn
import streamlit as st
import os
import base64
from datetime import datetime

STATUS_MAP = {
    "pending": "⏳ 待接收",
    "in_progress": "🔵 进行中",
    "submitted": "📤 待内容审核",
    "needs_revision": "🔴 需修改",
    "content_approved": "✅ 内容通过，待查重确认",
    "check_confirmed": "🔍 检测已确认，待老师审批",
    "submit_approved": "🎯 已批准，待提交截图",
    "completed": "🟢 已完成"
}

def preview_pdf(filepath, key):
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="500px"></iframe>', unsafe_allow_html=True)

def show_task_detail(task_id, user):
    # 一次连接取所有需要的数据
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, description, due_date, subject, video_url FROM tasks WHERE id=%s", (task_id,))
    task = c.fetchone()
    c.execute("SELECT filename, filepath FROM task_files WHERE task_id=%s", (task_id,))
    files = c.fetchall()
    c.execute("SELECT status FROM progress WHERE student_id=%s AND task_id=%s", (user["id"], task_id))
    progress = c.fetchone()
    c.execute("""
        SELECT submission_type, filename, filepath, comment, created_at
        FROM submissions WHERE task_id=%s AND student_id=%s
        ORDER BY created_at DESC
    """, (task_id, user["id"]))
    submissions = c.fetchall()

    # 老师额外需要的数据
    task_owner = None
    student_progress = []
    all_submissions = []
    if user["role"] == "teacher":
        c.execute("""
            SELECT t.created_by, u.role FROM tasks t
            JOIN users u ON t.created_by = u.id
            WHERE t.id=%s
        """, (task_id,))
        task_owner = c.fetchone()
        c.execute("""
            SELECT u.username, p.status, p.updated_at, p.student_id
            FROM progress p JOIN users u ON p.student_id = u.id
            WHERE p.task_id=%s
        """, (task_id,))
        student_progress = c.fetchall()
        c.execute("""
            SELECT s.submission_type, s.filename, s.filepath, s.comment, s.created_at, u.username, p.status, s.student_id
            FROM submissions s
            JOIN users u ON s.student_id = u.id
            JOIN progress p ON p.task_id = s.task_id AND p.student_id = s.student_id
            WHERE s.task_id=%s AND s.submission_type != 'teacher_feedback'
            ORDER BY s.created_at DESC
        """, (task_id,))
        all_submissions = c.fetchall()
    conn.close()

    if not task:
        st.error("任务不存在")
        return

    if st.button("← 返回任务列表"):
        st.session_state.current_task_id = None
        st.rerun()

    st.title(f"📋 {task[1]}")
    current_status = progress[0] if progress else "pending"

    col1, col2 = st.columns([2, 1])
    with col1:
        st.write(f"**学科：** {task[4]}")
        st.write(f"**截止日期：** {task[3] or '未设定'}")
    with col2:
        st.write(f"**状态：** {STATUS_MAP.get(current_status, current_status)}")

    st.divider()

    st.write("### 📝 任务说明")
    if task[2]:
        st.write(task[2])
    else:
        st.info("暂无说明")

    if task[5]:
        st.write("### 🎥 教学视频")
        st.video(task[5])

    if files:
        st.write("### 📎 参考附件")
        for f in files:
            if os.path.exists(f[1]):
                col1, col2 = st.columns([1, 1])
                with col1:
                    with open(f[1], "rb") as file_data:
                        st.download_button(label=f"📄 下载 {f[0]}", data=file_data,
                            file_name=f[0], mime="application/pdf", key=f"detail_dl_{f[0]}")
                with col2:
                    if f[1].endswith(".pdf"):
                        if st.button(f"👁️ 预览", key=f"preview_{f[0]}"):
                            st.session_state[f"show_preview_{f[0]}"] = not st.session_state.get(f"show_preview_{f[0]}", False)
                if st.session_state.get(f"show_preview_{f[0]}", False):
                    preview_pdf(f[1], f"attach_{f[0]}")

    st.divider()

    def update_status(new_status):
        conn = get_conn()
        c = conn.cursor()
        if progress:
            c.execute("UPDATE progress SET status=%s, updated_at=%s WHERE student_id=%s AND task_id=%s",
                (new_status, datetime.now().isoformat(), user["id"], task_id))
        else:
            c.execute("INSERT INTO progress (student_id, task_id, status) VALUES (%s, %s, %s)",
                (user["id"], task_id, new_status))
        conn.commit()
        conn.close()

    # ========== 学生操作区 ==========
    if user["role"] == "student":

        if current_status == "pending":
            st.write("### 📬 确认接收任务")
            st.info("请阅读任务说明和附件后，点击确认接收开始任务。")
            if st.button("✅ 确认接收，开始任务"):
                update_status("in_progress")
                st.success("已接收任务！")
                st.rerun()

        elif current_status in ["in_progress", "needs_revision"]:
            if current_status == "needs_revision":
                st.write("### 🔄 需要修改")
                # 单独查一次评语
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT comment FROM submissions WHERE task_id=%s AND student_id=%s AND submission_type='teacher_feedback' ORDER BY created_at DESC LIMIT 1", (task_id, user["id"]))
                feedback = c.fetchone()
                conn.close()
                if feedback:
                    st.error(f"**老师评语：** {feedback[0]}")

            st.write("### 📤 提交作业")
            uploaded = st.file_uploader("上传作业文件（可选，支持PDF/Word/PPT/图片）",
                type=["pdf", "docx", "pptx", "zip", "jpg", "jpeg", "png"])
            comment = st.text_area("备注（如有在线链接或说明请填写在此）")

            if st.button("提交作业"):
                os.makedirs("submissions", exist_ok=True)
                filepath = None
                filename = None
                if uploaded:
                    filepath = f"submissions/{task_id}_{user['id']}_{uploaded.name}"
                    filename = uploaded.name
                    with open(filepath, "wb") as f:
                        f.write(uploaded.read())
                conn = get_conn()
                c = conn.cursor()
                c.execute("INSERT INTO submissions (task_id, student_id, submission_type, filename, filepath, comment) VALUES (%s, %s, %s, %s, %s, %s)",
                    (task_id, user["id"], "assignment", filename, filepath, comment))
                conn.commit()
                conn.close()
                update_status("submitted")
                st.success("✅ 作业已提交，等待老师审核")
                st.rerun()

        elif current_status == "submitted":
            st.info("📋 作业已提交，等待老师审核...")

        elif current_status == "content_approved":
            st.write("### 🔍 查重和AI检测确认")
            st.success("✅ 内容已通过老师审核！")
            st.write("---")
            st.write("**请自行完成以下检测，确认合格后勾选提交：**")
            st.markdown("""
            | 检测项目 | 要求 |
            |---|---|
            | 📊 查重率 | 不高于 **15%** |
            | 🤖 AI生成率 | 不高于 **20%** |
            """)
            st.write("推荐工具：Turnitin（查重）、GPTZero（AI检测）")
            st.write("---")
            plagiarism_ok = st.checkbox("✅ 我确认查重率不高于 15%")
            ai_ok = st.checkbox("✅ 我确认AI生成率不高于 20%")
            if st.button("申请提交"):
                if not plagiarism_ok or not ai_ok:
                    st.warning("请确认两项检测均已通过后再申请提交")
                else:
                    update_status("check_confirmed")
                    st.success("✅ 已申请提交，等待老师审批")
                    st.rerun()

        elif current_status == "check_confirmed":
            st.info("🔍 已申请提交，等待老师审批...")

        elif current_status == "submit_approved":
            st.write("### 🎯 上传提交截图")
            st.success("✅ 老师已批准提交！请在学校系统正式提交后，上传截图作为凭证。")
            screenshot = st.file_uploader("上传提交截图", type=["jpg", "jpeg", "png", "pdf"])
            if st.button("完成任务") and screenshot:
                os.makedirs("submissions", exist_ok=True)
                filepath = f"submissions/{task_id}_{user['id']}_screenshot_{screenshot.name}"
                with open(filepath, "wb") as f:
                    f.write(screenshot.read())
                conn = get_conn()
                c = conn.cursor()
                c.execute("INSERT INTO submissions (task_id, student_id, submission_type, filename, filepath, comment) VALUES (%s, %s, %s, %s, %s, %s)",
                    (task_id, user["id"], "screenshot", screenshot.name, filepath, "提交截图"))
                conn.commit()
                conn.close()
                update_status("completed")
                st.success("🎉 任务已完成！")
                st.rerun()

        elif current_status == "completed":
            st.success("🎉 任务已完成！")

        if submissions:
            st.write("---")
            st.write("### 📁 提交历史")
            type_map = {"assignment": "作业文件", "screenshot": "提交截图", "teacher_feedback": "老师评语"}
            for sub in submissions:
                st.write(f"**{type_map.get(sub[0], sub[0])}** — {sub[4]}")
                if sub[1] and sub[2] and os.path.exists(sub[2]):
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        with open(sub[2], "rb") as f:
                            st.download_button(label=f"下载 {sub[1]}", data=f,
                                file_name=sub[1], key=f"sub_dl_{sub[4]}_{sub[0]}")
                    with col2:
                        if sub[2].endswith(".pdf"):
                            if st.button(f"👁️ 预览", key=f"sub_preview_{sub[4]}_{sub[0]}"):
                                st.session_state[f"show_sub_{sub[4]}_{sub[0]}"] = not st.session_state.get(f"show_sub_{sub[4]}_{sub[0]}", False)
                    if st.session_state.get(f"show_sub_{sub[4]}_{sub[0]}", False):
                        preview_pdf(sub[2], f"sub_{sub[4]}")
                if sub[3]:
                    st.caption(f"备注：{sub[3]}")

        st.write("---")
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id FROM delete_requests WHERE task_id=%s AND student_id=%s AND status='pending'",
            (task_id, user["id"]))
        existing_request = c.fetchone()
        conn.close()

        if existing_request:
            st.warning("⏳ 你已提交删除申请，等待老师审批")
        else:
            with st.expander("申请删除此任务"):
                reason = st.text_input("申请理由（可选）")
                if st.button("提交删除申请"):
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("INSERT INTO delete_requests (task_id, student_id, reason) VALUES (%s, %s, %s)",
                        (task_id, user["id"], reason))
                    conn.commit()
                    conn.close()
                    st.success("✅ 删除申请已提交")
                    st.rerun()

    # ========== 老师操作区 ==========
    if user["role"] == "teacher":
        is_owner = task_owner and (
            task_owner[0] == user["id"] or task_owner[1] == "student"
        )

        if student_progress:
            st.write("### 👥 学生进度")
            for sp in student_progress:
                st.write(f"**{sp[0]}** — {STATUS_MAP.get(sp[1], sp[1])} — {sp[2]}")

        if all_submissions:
            st.write("### 📥 学生提交")
            type_map = {"assignment": "作业文件", "screenshot": "提交截图"}
            for sub in all_submissions:
                with st.expander(f"{sub[5]} — {type_map.get(sub[0], sub[0])} — {sub[4]}"):
                    if sub[2] and os.path.exists(sub[2]):
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            with open(sub[2], "rb") as f:
                                st.download_button(label=f"下载 {sub[1]}", data=f,
                                    file_name=sub[1], key=f"teacher_dl_{sub[4]}_{sub[5]}")
                        with col2:
                            if sub[2].endswith(".pdf"):
                                if st.button(f"👁️ 预览", key=f"teacher_preview_{sub[4]}_{sub[5]}"):
                                    st.session_state[f"show_teacher_{sub[4]}_{sub[5]}"] = not st.session_state.get(f"show_teacher_{sub[4]}_{sub[5]}", False)
                        if st.session_state.get(f"show_teacher_{sub[4]}_{sub[5]}", False):
                            preview_pdf(sub[2], f"teacher_{sub[4]}")
                    if sub[3]:
                        st.caption(f"备注：{sub[3]}")

                    current_student_status = sub[6]
                    student_id = sub[7]

                    if current_student_status == "submitted" and sub[0] == "assignment":
                        feedback = st.text_area("评语（需修改时必填）", key=f"feedback_{sub[4]}")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ 内容通过", key=f"approve_content_{sub[4]}"):
                                conn = get_conn()
                                c = conn.cursor()
                                c.execute("UPDATE progress SET status='content_approved', updated_at=%s WHERE task_id=%s AND student_id=%s",
                                    (datetime.now().isoformat(), task_id, student_id))
                                if feedback:
                                    c.execute("INSERT INTO submissions (task_id, student_id, submission_type, comment) VALUES (%s, %s, %s, %s)",
                                        (task_id, student_id, "teacher_feedback", feedback))
                                conn.commit()
                                conn.close()
                                st.success("已通过内容审核")
                                st.rerun()
                        with col2:
                            if st.button("🔄 需修改", key=f"revise_{sub[4]}"):
                                if feedback:
                                    conn = get_conn()
                                    c = conn.cursor()
                                    c.execute("UPDATE progress SET status='needs_revision', updated_at=%s WHERE task_id=%s AND student_id=%s",
                                        (datetime.now().isoformat(), task_id, student_id))
                                    c.execute("INSERT INTO submissions (task_id, student_id, submission_type, comment) VALUES (%s, %s, %s, %s)",
                                        (task_id, student_id, "teacher_feedback", feedback))
                                    conn.commit()
                                    conn.close()
                                    st.success("已发回修改")
                                    st.rerun()
                                else:
                                    st.warning("请填写评语说明修改原因")

        if student_progress:
            for sp in student_progress:
                if sp[1] == "check_confirmed":
                    st.write("---")
                    st.write(f"### 🔍 审批 {sp[0]} 的提交申请")
                    st.info(f"学生 **{sp[0]}** 已确认查重和AI检测合格，申请正式提交。")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ 批准提交", key=f"approve_submit_{sp[3]}"):
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute("UPDATE progress SET status='submit_approved', updated_at=%s WHERE task_id=%s AND student_id=%s",
                                (datetime.now().isoformat(), task_id, sp[3]))
                            conn.commit()
                            conn.close()
                            st.success("已批准提交")
                            st.rerun()
                    with col2:
                        if st.button(f"🔄 退回修改", key=f"reject_submit_{sp[3]}"):
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute("UPDATE progress SET status='needs_revision', updated_at=%s WHERE task_id=%s AND student_id=%s",
                                (datetime.now().isoformat(), task_id, sp[3]))
                            conn.commit()
                            conn.close()
                            st.success("已退回修改")
                            st.rerun()

        if not is_owner:
            st.info("ℹ️ 你可以审批此任务，但编辑权限归任务创建者所有")

        if is_owner:
            st.write("---")
            st.write("### ✏️ 编辑任务")
            with st.form("edit_task_form"):
                new_title = st.text_input("任务标题", value=task[1])
                new_desc = st.text_area("任务说明", value=task[2] or "")
                new_due = st.text_input("截止日期 (YYYY-MM-DD)", value=task[3] or "")
                new_subject = st.text_input("学科", value=task[4] or "")
                new_video = st.text_input("教学视频链接", value=task[5] or "")
                new_files = st.file_uploader("添加附件", type=["pdf"], accept_multiple_files=True)

                if st.form_submit_button("保存修改"):
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("UPDATE tasks SET title=%s, description=%s, due_date=%s, subject=%s, video_url=%s WHERE id=%s",
                        (new_title, new_desc, new_due, new_subject, new_video, task_id))
                    os.makedirs("uploads", exist_ok=True)
                    for f in new_files:
                        filepath = f"uploads/{task_id}_{f.name}"
                        with open(filepath, "wb") as out:
                            out.write(f.read())
                        c.execute("INSERT INTO task_files (task_id, filename, filepath) VALUES (%s, %s, %s)",
                            (task_id, f.name, filepath))
                    conn.commit()
                    conn.close()
                    st.success("任务已更新！")
                    st.rerun()