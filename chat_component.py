import streamlit as st
from datetime import datetime
from database import get_conn

def load_chat_history(session_key, user_id):
    """从数据库加载聊天记录"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT role, content FROM chat_history
            WHERE user_id = %s AND session_key = %s
            ORDER BY created_at ASC
        """, (user_id, session_key))
        rows = c.fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in rows]
    except:
        return []

def save_message(session_key, user_id, role, content):
    """保存单条消息到数据库"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO chat_history (user_id, session_key, role, content)
            VALUES (%s, %s, %s, %s)
        """, (user_id, session_key, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print("保存消息失败:", e)

def clear_chat_history(session_key, user_id):
    """清除数据库里的聊天记录"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            DELETE FROM chat_history
            WHERE user_id = %s AND session_key = %s
        """, (user_id, session_key))
        conn.commit()
        conn.close()
    except Exception as e:
        print("清除记录失败:", e)

def show_chat(session_key, system_prompt, placeholder="输入你的问题...", user_id=None):
    from ai_helper import call_claude

    # 首次加载时从数据库读取历史记录
    if session_key not in st.session_state:
        if user_id:
            st.session_state[session_key] = load_chat_history(session_key, user_id)
        else:
            st.session_state[session_key] = []

    # 显示历史消息
    for msg in st.session_state[session_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 自动滚动到底部
    st.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)
    st.markdown("""
        <script>
            var element = document.getElementById('chat-bottom');
            if (element) {
                element.scrollIntoView({behavior: 'smooth'});
            }
        </script>
    """, unsafe_allow_html=True)

    # 清除按钮
    if st.session_state[session_key]:
        if st.button("🗑️ 清除对话", key=f"clear_{session_key}"):
            st.session_state[session_key] = []
            if user_id:
                clear_chat_history(session_key, user_id)
            st.rerun()

    # 输入框
    question = st.chat_input(placeholder)

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state[session_key].append({"role": "user", "content": question})
        if user_id:
            save_message(session_key, user_id, "user", question)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                answer = call_claude(system_prompt, st.session_state[session_key])
            st.markdown(answer)

        st.session_state[session_key].append({"role": "assistant", "content": answer})
        if user_id:
            save_message(session_key, user_id, "assistant", answer)

        st.rerun()


def show_chat_with_files(session_key, system_prompt, placeholder="输入你的问题...", user_id=None, quick_prompt=None):
    """支持文件上传和快捷按钮的增强版对话组件"""
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    try:
        import streamlit as st
        API_KEY = st.secrets["ANTHROPIC_API_KEY"]
    except:
        import os
        API_KEY = os.getenv("ANTHROPIC_API_KEY")

    if session_key not in st.session_state:
        if user_id:
            st.session_state[session_key] = load_chat_history(session_key, user_id)
        else:
            st.session_state[session_key] = []

    # 显示历史消息
    for msg in st.session_state[session_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state[session_key]:
        if st.button("🗑️ 清除对话", key=f"clear_{session_key}"):
            st.session_state[session_key] = []
            if user_id:
                clear_chat_history(session_key, user_id)
            st.rerun()

    question = quick_prompt or st.chat_input(placeholder)

    if question:
        with st.chat_message("user"):
            st.markdown(question)

        # 构建带文件的消息
        file_ctx = st.session_state.get("ai_file_context")
        if file_ctx:
            if file_ctx["type"] == "pdf":
                user_content = [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": file_ctx["b64"]}},
                    {"type": "text", "text": question}
                ]
            else:
                user_content = [
                    {"type": "image", "source": {"type": "base64", "media_type": file_ctx["media_type"], "data": file_ctx["b64"]}},
                    {"type": "text", "text": question}
                ]
        else:
            user_content = question

        api_messages = list(st.session_state[session_key]) + [{"role": "user", "content": user_content}]

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-opus-4-5", "max_tokens": 2000, "system": system_prompt, "messages": api_messages}
                )
                result = response.json()
                answer = next(
                    (block["text"] for block in result.get("content", []) if block.get("type") == "text"),
                    "抱歉，无法获取回复"
                )
            st.markdown(answer)

        st.session_state[session_key].append({"role": "user", "content": question})
        st.session_state[session_key].append({"role": "assistant", "content": answer})
        if user_id:
            save_message(session_key, user_id, "user", question)
            save_message(session_key, user_id, "assistant", answer)

        st.rerun()