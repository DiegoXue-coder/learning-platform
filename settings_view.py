import streamlit as st
from database import get_setting, set_setting


def show_settings(user):
    st.write("### ⚙️ 平台设置")

    st.write("#### 角色与功能模式")

    is_multi = get_setting("multi_role_mode", "false") == "true"
    new_val = st.toggle(
        "启用多角色模式（老师/家长功能）",
        value=is_multi,
        key="toggle_multi_role",
        help="关闭后，登录界面只显示学生角色，隐藏老师审批和家长查看功能"
    )

    if new_val:
        st.info("✅ **多角色模式**：老师可发布/审批任务，家长可查看学生进度。登录界面显示全部角色。")
    else:
        st.info("🎓 **单学生模式**：专注个人课程管理，界面简化。登录界面仅显示学生角色。")

    if new_val != is_multi:
        set_setting("multi_role_mode", "true" if new_val else "false")
        st.success("✅ 设置已保存，页面将刷新生效")
        st.rerun()

    st.divider()
    st.caption("AI 学习平台 · 基于 Streamlit + Claude AI · UNSW")
