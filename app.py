from database import get_conn, get_setting
import streamlit as st
from database import init_db

st.set_page_config(page_title="AI 学习平台", layout="wide")

from style import apply_styles
apply_styles()

# init_db 只在第一次启动时跑，不每次刷新都跑
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

def login(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE username=%s AND password=%s", (username, password))
    user = c.fetchone()
    conn.close()
    return user

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("AI 学习平台")
    st.write("---")

    multi_role_on = get_setting("multi_role_mode", "false") == "true"
    available_roles = ["学生", "老师", "家长"] if multi_role_on else ["学生"]

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("### 请选择身份登录")

        role = st.selectbox("选择身份", available_roles)

        role_hints = {
            "学生": "student",
            "老师": "teacher 或 teacher2",
            "家长": "parent"
        }

        username = st.text_input("用户名", placeholder=f"例如：{role_hints[role]}")
        password = st.text_input("密码", type="password")

        if st.button("登录", use_container_width=True):
            if username and password:
                user = login(username, password)
                if user:
                    role_map = {"学生": "student", "老师": "teacher", "家长": "parent"}
                    if user[2] == role_map[role]:
                        st.session_state.user = {"id": user[0], "username": user[1], "role": user[2]}
                        st.rerun()
                    else:
                        st.error("身份选择与账号不匹配，请重新选择")
                else:
                    st.error("用户名或密码错误")
            else:
                st.warning("请输入用户名和密码")

else:
    user = st.session_state.user
    role_label = {"teacher": "老师", "student": "学生", "parent": "家长"}

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.title(f"AI 学习平台 — 你好，{user['username']} ({role_label.get(user['role'], '')})")
    with col2:
        st.write("")
    with col3:
        if st.button("退出登录"):
            st.session_state.user = None
            st.rerun()

    # Auto-import when redirected from Chrome extension with URL param
    if st.query_params.get("moodle_data"):
        import base64 as _b64
        try:
            raw = _b64.b64decode(st.query_params["moodle_data"]).decode("utf-8")
            st.session_state["mc_auto_import"] = raw
            st.query_params.clear()
            st.rerun()
        except Exception:
            st.query_params.clear()

    if st.session_state.get("mc_auto_import"):
        raw = st.session_state.pop("mc_auto_import")
        st.info("📥 检测到 Moodle 课程数据，正在自动导入...")
        from moodle_import import _import_from_json
        _import_from_json(user, raw)

    if user["role"] == "teacher":
        from teacher_view import show_teacher_view
        show_teacher_view(user)
    elif user["role"] == "parent":
        from parent_view import show_parent_view
        show_parent_view(user)
    else:
        from student_view import show_student_view
        show_student_view(user)