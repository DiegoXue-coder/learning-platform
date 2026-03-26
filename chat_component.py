import streamlit as st
from datetime import datetime

def show_chat(session_key, system_prompt, placeholder="输入你的问题..."):
    from ai_helper import call_claude

    if session_key not in st.session_state:
        st.session_state[session_key] = []

    # 显示历史消息
    for msg in st.session_state[session_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 自动滚动到底部的锚点
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
            st.rerun()

    # 输入框
    question = st.chat_input(placeholder)

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state[session_key].append({"role": "user", "content": question})

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                answer = call_claude(system_prompt, st.session_state[session_key])
            st.markdown(answer)

        st.session_state[session_key].append({"role": "assistant", "content": answer})
        st.rerun()