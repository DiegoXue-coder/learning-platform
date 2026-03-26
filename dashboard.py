import streamlit as st
import sqlite3
from datetime import datetime, date

STATUS_MAP = {
    "pending": "待接收",
    "in_progress": "进行中",
    "submitted": "待内容审核",
    "needs_revision": "需修改",
    "content_approved": "内容通过",
    "check_confirmed": "检测确认",
    "submit_approved": "待提交截图",
    "completed": "已完成"
}

STEPS = ["pending", "in_progress", "submitted", "content_approved", "check_confirmed", "submit_approved", "completed"]
STEP_LABELS = ["待接收", "进行中", "待审核", "内容通过", "检测确认", "审批提交", "已完成"]

def render_progress_bar(current_status):
    if current_status == "needs_revision":
        current_idx = 2
    else:
        current_idx = STEPS.index(current_status) if current_status in STEPS else 0

    cols = st.columns(len(STEPS))
    for i, (step, label) in enumerate(zip(STEPS, STEP_LABELS)):
        with cols[i]:
            if i < current_idx:
                st.markdown(f"<div style='text-align:center;color:#22c55e;font-size:20px'>✅</div><div style='text-align:center;font-size:11px;color:#22c55e'>{label}</div>", unsafe_allow_html=True)
            elif i == current_idx:
                if current_status == "needs_revision":
                    st.markdown(f"<div style='text-align:center;color:#ef4444;font-size:20px'>🔴</div><div style='text-align:center;font-size:11px;color:#ef4444;font-weight:bold'>需修改</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='text-align:center;color:#2563eb;font-size:20px'>🔵</div><div style='text-align:center;font-size:11px;color:#2563eb;font-weight:bold'>{label}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center;color:#d1d5db;font-size:20px'>⭕</div><div style='text-align:center;font-size:11px;color:#9ca3af'>{label}</div>", unsafe_allow_html=True)

def show_student_dashboard(user):
    today = date.today()

    conn = sqlite3.connect("learning_platform.db")
    c = conn.cursor()
    c.execute("""
        SELECT t.id, t.title, t.subject, t.due_date,
               COALESCE(p.status, 'pending') as status
        FROM tasks t
        LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = ?
        ORDER BY t.due_date
    """, (user["id"],))
    tasks = c.fetchall()
    conn.close()

    if not tasks:
        st.info("暂时没有任务")
        return

    total = len(tasks)
    completed = sum(1 for t in tasks if t[4] == "completed")
    pending = sum(1 for t in tasks if t[4] == "pending")
    needs_action = sum(1 for t in tasks if t[4] in ["in_progress", "needs_revision", "content_approved", "submit_approved"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 总任务", total)
    with col2:
        st.metric("⏳ 待接收", pending)
    with col3:
        st.metric("🔔 需要行动", needs_action)
    with col4:
        st.metric("✅ 已完成", completed)

    st.divider()

    # 即将截止提醒
    urgent_tasks = []
    for t in tasks:
        if t[3] and t[4] != "completed":
            try:
                due = datetime.strptime(t[3], "%Y-%m-%d").date()
                days_left = (due - today).days
                if days_left <= 7:
                    urgent_tasks.append((t, days_left))
            except:
                pass

    if urgent_tasks:
        st.write("### 🔔 即将截止")
        for t, days in urgent_tasks:
            if days < 0:
                st.error(f"**{t[1]}** — 已逾期 {abs(days)} 天")
            elif days == 0:
                st.error(f"**{t[1]}** — 今天截止！")
            else:
                st.warning(f"**{t[1]}** — 还有 {days} 天截止")
        st.divider()

    # 任务进度（只显示未完成）
    st.write("### 📊 任务进度")
    active_tasks = [t for t in tasks if t[4] != "completed"]
    if active_tasks:
        for task in active_tasks:
            task_id, title, subject, due_date, status = task
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{title}** | {subject} | 截止：{due_date or '未设定'}")
                with col2:
                    if st.button("查看详情", key=f"dash_view_{task_id}"):
                        st.session_state.current_task_id = task_id
                        st.session_state.task_source = "student"
                        st.rerun()
                render_progress_bar(status)
                st.write("")
    else:
        st.success("🎉 所有任务已完成！")

    # 已完成任务折叠显示
    completed_tasks = [t for t in tasks if t[4] == "completed"]
    if completed_tasks:
        with st.expander(f"查看已完成任务（{len(completed_tasks)}）"):
            for task in completed_tasks:
                st.write(f"✅ **{task[1]}** | {task[2]} | 截止：{task[3] or '未设定'}")

def show_teacher_dashboard(user):
    conn = sqlite3.connect("learning_platform.db")
    c = conn.cursor()

    c.execute("""
        SELECT t.id, t.title, u.username, p.updated_at
        FROM progress p
        JOIN tasks t ON p.task_id = t.id
        JOIN users u ON p.student_id = u.id
        WHERE p.status = 'submitted'
    """)
    content_reviews = c.fetchall()

    c.execute("""
        SELECT t.id, t.title, u.username, p.updated_at
        FROM progress p
        JOIN tasks t ON p.task_id = t.id
        JOIN users u ON p.student_id = u.id
        WHERE p.status = 'check_confirmed'
    """)
    submit_reviews = c.fetchall()

    c.execute("""
        SELECT dr.id, t.title, u.username, dr.created_at
        FROM delete_requests dr
        JOIN tasks t ON dr.task_id = t.id
        JOIN users u ON dr.student_id = u.id
        WHERE dr.status = 'pending'
    """)
    delete_reviews = c.fetchall()

    c.execute("""
        SELECT t.id, t.title, t.subject, t.due_date,
               u.username,
               COALESCE(p.status, 'pending') as status
        FROM tasks t
        CROSS JOIN users u
        LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = u.id
        WHERE u.role = 'student'
        ORDER BY t.due_date
    """)
    
    all_progress = c.fetchall()
    conn.close()

    total_pending = len(content_reviews) + len(submit_reviews) + len(delete_reviews)
    completed_count = sum(1 for p in all_progress if p[5] == "completed")

    # 顶部统计
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📝 待内容审核", len(content_reviews))
    with col2:
        st.metric("🎯 待提交审批", len(submit_reviews))
    with col3:
        st.metric("🗑️ 待删除审批", len(delete_reviews))
    with col4:
        st.metric("✅ 已完成", completed_count)

    st.divider()

    # 审批提醒
    if total_pending > 0:
        st.write(f"### 🔔 待处理审批（{total_pending}）")

        if content_reviews:
            st.write("**📝 待内容审核：**")
            for r in content_reviews:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{r[1]}** — 学生：{r[2]} — {r[3]}")
                with col2:
                    if st.button("去审核", key=f"dash_content_{r[0]}_{r[2]}"):
                        st.session_state.current_task_id = r[0]
                        st.session_state.task_source = "teacher"
                        st.rerun()

        if submit_reviews:
            st.write("**🎯 待提交审批：**")
            for r in submit_reviews:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{r[1]}** — 学生：{r[2]} — {r[3]}")
                with col2:
                    if st.button("去审批", key=f"dash_submit_{r[0]}_{r[2]}"):
                        st.session_state.current_task_id = r[0]
                        st.session_state.task_source = "teacher"
                        st.rerun()

        if delete_reviews:
            st.write("**🗑️ 待删除审批：**")
            for r in delete_reviews:
                st.write(f"**{r[1]}** — 学生：{r[2]} — {r[3]}")

        st.divider()

    # 学生任务进度（只显示未完成）
    st.write("### 📊 学生任务进度总览")
    active_progress = [p for p in all_progress if p[5] != "completed"]

    if active_progress:
        current_task = None
        for p in active_progress:
            if current_task != p[0]:
                current_task = p[0]
                st.write(f"**{p[1]}** | {p[2]} | 截止：{p[3] or '未设定'}")
            col1, col2, col3 = st.columns([1, 4, 1])
            with col1:
                st.write(f"👤 {p[4]}")
            with col2:
                render_progress_bar(p[5])
            with col3:
                if st.button("详情", key=f"dash_teacher_{p[0]}_{p[4]}"):
                    st.session_state.current_task_id = p[0]
                    st.session_state.task_source = "teacher"
                    st.rerun()
            st.write("")
    else:
        st.success("🎉 所有学生任务均已完成！")

    # 已完成折叠显示
    completed_progress = [p for p in all_progress if p[5] == "completed"]
    if completed_progress:
        with st.expander(f"查看已完成任务（{len(completed_progress)}）"):
            for p in completed_progress:
                st.write(f"✅ **{p[1]}** | 学生：{p[4]}")