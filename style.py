import streamlit as st

def apply_styles():
    st.markdown("""
    <style>
    /* 全局字体和背景 */
    .stApp {
        background-color: #f8fafc;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* 隐藏 Streamlit 默认菜单和页脚 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 主内容区域 */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* 标题样式 */
    h1 {
        color: #1e293b;
        font-weight: 700;
        font-size: 1.8rem !important;
        padding-bottom: 0.5rem;
    }
    
    h2 {
        color: #1e293b;
        font-weight: 600;
        font-size: 1.3rem !important;
    }
    
    h3 {
        color: #334155;
        font-weight: 600;
        font-size: 1.1rem !important;
    }
    
    /* 按钮样式 */
    .stButton > button {
        background-color: #1e40af;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.4rem 1rem;
        font-weight: 500;
        font-size: 0.85rem;
        transition: all 0.2s;
        cursor: pointer;
    }
    
    .stButton > button:hover {
        background-color: #1d4ed8;
        box-shadow: 0 4px 12px rgba(30, 64, 175, 0.3);
        transform: translateY(-1px);
    }
    
    /* 危险按钮（删除类） */
    .stButton > button[kind="secondary"] {
        background-color: white;
        color: #ef4444;
        border: 1px solid #ef4444;
    }
    
    /* 输入框样式 */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        padding: 0.5rem 0.75rem;
        background-color: white;
        font-size: 0.9rem;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #1e40af;
        box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
    }
    
    .stTextArea > div > div > textarea {
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        background-color: white;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #1e40af;
        box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
    }
    
    /* Tab 样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: #f1f5f9;
        padding: 4px;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 0.4rem 1rem;
        font-size: 0.85rem;
        font-weight: 500;
        color: #64748b;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: white !important;
        color: #1e40af !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.1);
    }
    
    /* Metric 卡片 */
    [data-testid="metric-container"] {
        background-color: white;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    
    [data-testid="metric-container"] [data-testid="stMetricLabel"] {
        font-size: 0.8rem;
        color: #64748b;
        font-weight: 500;
    }
    
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #1e293b;
    }
    
    /* Expander 样式 */
    .streamlit-expanderHeader {
        background-color: white;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        font-weight: 500;
        color: #334155;
    }
    
    .streamlit-expanderContent {
        border: 1px solid #e2e8f0;
        border-top: none;
        border-radius: 0 0 8px 8px;
        background-color: white;
    }
    
    /* Info/Warning/Error 消息 */
    .stAlert {
        border-radius: 8px;
        border: none;
    }
    
    /* Divider */
    hr {
        border-color: #e2e8f0;
        margin: 1rem 0;
    }
    
    /* Select box */
    .stSelectbox > div > div {
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        background-color: white;
    }
    
    /* File uploader */
    [data-testid="stFileUploader"] {
        border-radius: 8px;
        border: 2px dashed #cbd5e1;
        background-color: white;
        padding: 0.5rem;
    }
    
    /* Chat messages */
    [data-testid="stChatMessage"] {
        border-radius: 12px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }
    
    /* 任务卡片容器 */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        background-color: white;
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        margin-bottom: 0.5rem;
    }

    /* 登录页居中 */
    .login-container {
        max-width: 400px;
        margin: 5rem auto;
        background: white;
        padding: 2.5rem;
        border-radius: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
    }
    
    /* 侧边栏 */
    [data-testid="stSidebar"] {
        background-color: #1e293b;
    }
    </style>
    """, unsafe_allow_html=True)