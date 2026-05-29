import streamlit as st
import requests
import base64
import os
from datetime import datetime
from database import get_conn

try:
    import streamlit as st
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except:
    import os
    API_KEY = os.getenv("ANTHROPIC_API_KEY")

def load_workspace_history(user_id):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT role, content FROM chat_history
            WHERE user_id = %s AND session_key = 'ai_workspace'
            ORDER BY created_at ASC
        """, (user_id,))
        rows = c.fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in rows]
    except:
        return []

def save_workspace_message(user_id, role, content):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO chat_history (user_id, session_key, role, content)
            VALUES (%s, 'ai_workspace', %s, %s)
        """, (user_id, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print("保存失败:", e)

def clear_workspace_history(user_id):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            DELETE FROM chat_history
            WHERE user_id = %s AND session_key = 'ai_workspace'
        """, (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def file_to_base64(file_bytes):
    return base64.standard_b64encode(file_bytes).decode("utf-8")

def call_claude_with_files(messages, system_prompt="你是一个学习助手，用中文回答。"):
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-opus-4-5",
            "max_tokens": 2000,
            "system": system_prompt,
            "messages": messages
        }
    )
    result = response.json()
    return next(
        (block["text"] for block in result.get("content", []) if block.get("type") == "text"),
        "抱歉，无法获取回复"
    )

def show_ai_workspace(user):
    st.write("### 🤖 AI 工作台")
    st.caption("上传文件或图片，让AI帮你分析讲解；也可以直接对话，生成作业提纲、总结等内容。")

    user_id = user["id"]

    # 初始化对话历史
    if "workspace_messages" not in st.session_state:
        st.session_state.workspace_messages = load_workspace_history(user_id)
    if "workspace_file_context" not in st.session_state:
        st.session_state.workspace_file_context = None

    # 文件上传区
    with st.expander("📎 上传文件或图片（可选）", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            uploaded_pdf = st.file_uploader(
                "上传 PDF 文档",
                type=["pdf"],
                key="workspace_pdf"
            )
        with col2:
            uploaded_img = st.file_uploader(
                "上传图片",
                type=["jpg", "jpeg", "png", "gif", "webp"],
                key="workspace_img"
            )

        if uploaded_pdf:
            pdf_bytes = uploaded_pdf.read()
            b64 = file_to_base64(pdf_bytes)
            st.session_state.workspace_file_context = {
                "type": "pdf",
                "name": uploaded_pdf.name,
                "b64": b64
            }
            st.success(f"✅ 已加载：{uploaded_pdf.name}，现在可以提问了")

        if uploaded_img:
            img_bytes = uploaded_img.read()
            b64 = file_to_base64(img_bytes)
            ext = uploaded_img.name.split(".")[-1].lower()
            media_type_map = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "gif": "image/gif", "webp": "image/webp"
            }
            st.session_state.workspace_file_context = {
                "type": "image",
                "name": uploaded_img.name,
                "b64": b64,
                "media_type": media_type_map.get(ext, "image/jpeg")
            }
            st.image(uploaded_img, caption=uploaded_img.name, use_column_width=True)
            st.success(f"✅ 已加载：{uploaded_img.name}，现在可以提问了")

        if st.session_state.workspace_file_context:
            if st.button("🗑️ 移除当前文件", key="remove_file"):
                st.session_state.workspace_file_context = None
                st.rerun()

    # 快捷提示词
    st.write("**💡 快捷操作：**")
    col1, col2, col3, col4 = st.columns(4)
    quick_prompt = None
    with col1:
        if st.button("📋 总结这份文件", key="quick_summary"):
            quick_prompt = "请帮我总结这份文件的主要内容，用要点形式列出。"
    with col2:
        if st.button("📝 生成作业提纲", key="quick_outline"):
            quick_prompt = "请根据这份文件的内容，帮我生成一份作业提纲，包括主要论点和结构建议。"
    with col3:
        if st.button("❓ 出几道练习题", key="quick_quiz"):
            quick_prompt = "请根据这份文件的内容，出5道练习题帮我巩固知识，并提供答案。"
    with col4:
        if st.button("🔍 解释难点", key="quick_explain"):
            quick_prompt = "请找出这份文件中最难理解的概念，用简单易懂的方式解释。"

    st.divider()

    # 显示对话历史
    for msg in st.session_state.workspace_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 清除按钮
    if st.session_state.workspace_messages:
        if st.button("🗑️ 清除对话记录", key="clear_workspace"):
            st.session_state.workspace_messages = []
            clear_workspace_history(user_id)
            st.rerun()

    # 处理快捷提示词或用户输入
    question = quick_prompt or st.chat_input("问我任何问题，或者让我帮你生成内容...")

    if question:
        with st.chat_message("user"):
            st.markdown(question)

        # 构建发给API的消息
        # 如果有文件context且是第一次带文件提问，把文件内容附在第一条消息里
        api_messages = list(st.session_state.workspace_messages)

        file_ctx = st.session_state.workspace_file_context
        if file_ctx:
            if file_ctx["type"] == "pdf":
                user_content = [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": file_ctx["b64"]
                        }
                    },
                    {"type": "text", "text": question}
                ]
            else:
                user_content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": file_ctx["media_type"],
                            "data": file_ctx["b64"]
                        }
                    },
                    {"type": "text", "text": question}
                ]
        else:
            user_content = question

        api_messages.append({"role": "user", "content": user_content})

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                answer = call_claude_with_files(
                    api_messages,
                    system_prompt="你是一个学习助手，帮助学生理解课程内容、分析文件、生成学习材料。请用中文回答，语言清晰易懂。"
                )
            st.markdown(answer)

        # 保存到session和数据库（只保存文字，不保存文件内容）
        st.session_state.workspace_messages.append({"role": "user", "content": question})
        st.session_state.workspace_messages.append({"role": "assistant", "content": answer})
        save_workspace_message(user_id, "user", question)
        save_workspace_message(user_id, "assistant", answer)

        st.rerun()