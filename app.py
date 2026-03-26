import streamlit as st
from database import init_db
import sqlite3

st.set_page_config(page_title="AI 学习平台", layout="wide")

from style import apply_styles
apply_styles()

init_db()

def login(username, password):
    conn = sqlite3.connect("learning_platform.db")
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    return user

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("AI 学习平台")
    st.write("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("### 请选择身份登录")

        role = st.selectbox("选择身份", ["学生", "老师", "家长"])

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
                    # 验证角色是否匹配
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

    if user["role"] == "teacher":
        from teacher_view import show_teacher_view
        show_teacher_view(user)
    elif user["role"] == "parent":
        from parent_view import show_parent_view
        show_parent_view(user)
    else:
        from student_view import show_student_view
        show_student_view(user)