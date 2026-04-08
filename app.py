from typing import Callable, TypeVar
import os
import inspect
import json
import streamlit as st
import streamlit_analytics2 as streamlit_analytics
from dotenv import load_dotenv
from streamlit_chat import message
from streamlit_pills import pills
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from streamlit.delta_generator import DeltaGenerator
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from custom_callback_handler import CustomStreamlitCallbackHandler
from agents import define_graph
import shutil
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# ==================== 配置持久化函数 ====================
CONFIG_FILE = "temp/app_config.json"

def load_persistent_config():
    """从JSON文件加载持久化配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}
    return {}

def save_persistent_config(config):
    """保存配置到JSON文件"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        return False

# 从环境变量或 .env 设置，如果不存在则尝试从 Streamlit secrets 获取
def get_secret(key, default=""):
    # 优先从环境变量获取（包括 .env）
    val = os.getenv(key)
    if val is not None:
        return val
    # 其次尝试从 st.secrets 获取，避免 StreamlitSecretNotFoundError
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

os.environ["LINKEDIN_EMAIL"] = get_secret("LINKEDIN_EMAIL")
os.environ["LINKEDIN_PASS"] = get_secret("LINKEDIN_PASS")
os.environ["LANGCHAIN_API_KEY"] = get_secret("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = get_secret("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_PROJECT"] = get_secret("LANGCHAIN_PROJECT")
os.environ["SERPER_API_KEY"] = get_secret("SERPER_API_KEY")
os.environ["FIRECRAWL_API_KEY"] = get_secret("FIRECRAWL_API_KEY")
os.environ["LINKEDIN_SEARCH"] = get_secret("LINKEDIN_JOB_SEARCH")
os.environ["DASHSCOPE_API_KEY"] = get_secret("DASHSCOPE_API_KEY")
os.environ["OPENAI_API_KEY"] = get_secret("OPENAI_API_KEY")
os.environ["OPENAI_BASE_URL"] = get_secret("OPENAI_BASE_URL")
os.environ["DEEPSEEK_API_KEY"] = get_secret("DEEPSEEK_API_KEY")
os.environ["DEEPSEEK_BASE_URL"] = get_secret("DEEPSEEK_BASE_URL")
os.environ["QWEN_API_KEY"] = get_secret("QWEN_API_KEY")
os.environ["QWEN_BASE_URL"] = get_secret("QWEN_BASE_URL")

# 页面配置
st.set_page_config(
    page_title="JobAgent-MultiAgent 职业助手",
    page_icon="👨‍💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 样式
st.markdown("""
<style>
    /* 主标题样式 */
    h1 {
        color: #1f77b4;
        font-weight: 600;
    }
    
    /* 侧边栏样式 */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    
    /* 按钮样式优化 */
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* 输入框样式 */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea {
        border-radius: 8px;
        font-size: 14px;
    }
    
    /* 文件上传器样式 */
    [data-testid="stFileUploader"] {
        border-radius: 8px;
        border: 2px dashed #ccc;
        padding: 10px;
    }
    
    /* 成功/警告/错误消息样式 */
    .stSuccess, .stWarning, .stError, .stInfo {
        border-radius: 8px;
        padding: 10px;
        font-size: 14px;
    }
    
    /* Pills 样式优化 */
    .stPills {
        margin-top: 10px;
    }
    
    /* 聊天消息容器 - 缩小字体 */
    [data-testid="stChatMessageContent"] {
        border-radius: 10px;
        font-size: 14px;
    }
    
    /* 聊天消息内容 */
    .stChatMessage {
        font-size: 14px;
    }
    
    /* Markdown 内容字体 */
    .stMarkdown {
        font-size: 14px;
    }
    
    /* 减小标题字体 */
    h5 {
        font-size: 16px;
    }
</style>
""", unsafe_allow_html=True)

streamlit_analytics.start_tracking()

# 🔴 优化：简化目录和路径设置
temp_dir = "temp"
dummy_resume_path = os.path.abspath("dummy_resume.pdf")

if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)


# ==================== 侧边栏配置 ====================
st.sidebar.title("⚙️ 系统配置")

# 简历上传区域
st.sidebar.markdown("### 📄 简历管理")
uploaded_document = st.sidebar.file_uploader(
    "上传简历（PDF格式）", 
    type="pdf",
    help="支持 PDF 格式的简历文件"
)

# 🔴 优化：简化简历处理逻辑
if not uploaded_document:
    # 检查是否有演示简历
    if os.path.exists(dummy_resume_path):
        uploaded_document = open(dummy_resume_path, "rb")
        st.sidebar.info("💡 未上传简历，正在使用演示简历")
        with st.sidebar.expander("查看演示简历信息"):
            st.markdown(f"[点击查看演示简历]({'https://drive.google.com/file/d/1vTdtIPXEjqGyVgUgCO6HLiG9TSPcJ5eM/view?usp=sharing'})")
    else:
        st.sidebar.warning("⚠️ 请上传简历以使用完整功能")
        uploaded_document = None
        
# 🔴 优化：避免重复保存简历
if uploaded_document:
    # 检查是否是新文件
    current_filename = getattr(uploaded_document, 'name', 'dummy_resume.pdf')
    if not st.session_state.get("resume_saved", False) or st.session_state.get("resume_filename", "") != current_filename:
        bytes_data = uploaded_document.read()
        filepath = os.path.join(temp_dir, "resume.pdf")
        with open(filepath, "wb") as f:
            f.write(bytes_data)
        
        # 更新会话状态
        st.session_state["resume_saved"] = True
        st.session_state["resume_filename"] = current_filename
        
        print(f"新简历已保存: {current_filename}, 简历已保存到: {filepath}, 大小: {len(bytes_data)} bytes")
        st.sidebar.success(f"✅ 简历上传成功：{current_filename}")
    else:
        st.sidebar.success(f"✅ 已加载简历：{current_filename}")

# ==================== 大模型配置 ====================
st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 大模型配置")

# 加载持久化配置
persistent_config = load_persistent_config()

# 初始化持久化配置 - 修复配置不持久化的bug
if "saved_model_name" not in st.session_state:
    st.session_state["saved_model_name"] = persistent_config.get("model_name") or get_secret("MODEL_NAME") or "qwen-plus"
if "saved_api_key" not in st.session_state:
    st.session_state["saved_api_key"] = persistent_config.get("api_key") or get_secret("OPENAI_API_KEY") or get_secret("DASHSCOPE_API_KEY") or ""
if "saved_base_url" not in st.session_state:
    st.session_state["saved_base_url"] = persistent_config.get("base_url") or get_secret("OPENAI_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
if "saved_temperature" not in st.session_state:
    st.session_state["saved_temperature"] = persistent_config.get("temperature", 0.3)
if "saved_serper_key" not in st.session_state:
    st.session_state["saved_serper_key"] = persistent_config.get("serper_key") or get_secret("SERPER_API_KEY") or ""
if "saved_firecrawl_key" not in st.session_state:
    st.session_state["saved_firecrawl_key"] = persistent_config.get("firecrawl_key") or get_secret("FIRECRAWL_API_KEY") or ""

# 自定义模型配置
with st.sidebar.expander("🔧 模型参数设置", expanded=True):
    # 常用模型选择
    model_preset = st.selectbox(
        "选择预设模型",
        ["自定义", "qwen-plus", "qwen-max", "qwen-turbo", "gpt-4", "gpt-3.5-turbo", "deepseek-chat"],
        help="选择常用模型或自定义输入"
    )
    
    # 根据预设自动填充
    if model_preset != "自定义":
        default_model = model_preset
        # 自动填充对应的 Base URL
        if model_preset.startswith("qwen"):
            default_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        elif model_preset.startswith("gpt"):
            default_base_url = "https://api.openai.com/v1"
        elif model_preset == "deepseek-chat":
            default_base_url = "https://api.deepseek.com/v1"
        else:
            default_base_url = st.session_state["saved_base_url"]
    else:
        default_model = st.session_state["saved_model_name"]
        default_base_url = st.session_state["saved_base_url"]
    
    model_name = st.text_input(
        "模型名称",
        value=default_model,
        help="输入模型名称，如：qwen-plus, gpt-4, deepseek-chat 等",
        key="model_name_input"
    )
    
    api_key = st.text_input(
        "API Key",
        value=st.session_state["saved_api_key"],
        type="password",
        help="输入您的 API 密钥",
        key="api_key_input"
    )
    
    base_url = st.text_input(
        "API Base URL",
        value=default_base_url,
        help="输入 API 端点地址",
        key="base_url_input"
    )
    
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state["saved_temperature"],
        step=0.1,
        help="控制输出的随机性，值越低越确定",
        key="temperature_input"
    )
    
    # 保存配置按钮
    if st.button("💾 保存配置", use_container_width=True):
        st.session_state["saved_model_name"] = model_name
        st.session_state["saved_api_key"] = api_key
        st.session_state["saved_base_url"] = base_url
        st.session_state["saved_temperature"] = temperature
        
        # 保存到持久化存储
        config_to_save = {
            "model_name": model_name,
            "api_key": api_key,
            "base_url": base_url,
            "temperature": temperature,
            "serper_key": st.session_state.get("saved_serper_key", ""),
            "firecrawl_key": st.session_state.get("saved_firecrawl_key", "")
        }
        if save_persistent_config(config_to_save):
            st.success("✅ 配置已保存并持久化")
        else:
            st.error("❌ 配置保存失败")
    
    # 显示当前配置提示
    if model_preset != "自定义":
        st.info(f"💡 已选择预设模型：{model_preset}")
        if model_preset.startswith("qwen"):
            st.caption("✓ 通义千问模型，推荐用于中文任务")
        elif model_preset.startswith("gpt"):
            st.caption("✓ OpenAI GPT 模型，需要 OpenAI API Key")
        elif model_preset == "deepseek-chat":
            st.caption("✓ DeepSeek 模型，需要 DeepSeek API Key")
    
    # 测试连接按钮
    if st.button("🔗 测试连接", use_container_width=True):
        if not api_key or not base_url:
            st.error("❌ 请先填写 API Key 和 Base URL")
        else:
            with st.spinner("正在测试连接..."):
                try:
                    from llms import get_llm
                    test_llm = get_llm(
                        provider="openai",
                        model=model_name,
                        api_key=api_key,
                        base_url=base_url,
                        temperature=0.1
                    )
                    # 发送一个简单的测试消息
                    response = test_llm.invoke("Hi")
                    st.success(f"✅ 连接成功！模型响应正常")
                    with st.expander("查看测试响应"):
                        st.text(response.content[:200] + "..." if len(response.content) > 200 else response.content)
                except Exception as e:
                    st.error(f"❌ 连接失败：{str(e)}")
                    if "404" in str(e):
                        st.warning("⚠️ 模型不存在或无权访问，请检查模型名称")
                    elif "401" in str(e):
                        st.warning("⚠️ API Key 无效，请检查密钥")
                    elif "timeout" in str(e).lower():
                        st.warning("⚠️ 连接超时，请检查网络或 Base URL")

# 保存模型配置
st.session_state["model_name"] = model_name

# 构建统一的 settings
settings = {
    "model": model_name,
    "model_provider": "openai",  # 统一使用 OpenAI 兼容接口
    "temperature": temperature,
    "OPENAI_API_KEY": api_key,
    "OPENAI_BASE_URL": base_url,
}

# ==================== 外部服务配置 ====================
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔌 外部服务配置")

with st.sidebar.expander("🔍 搜索与抓取服务"):
    serper_api_key = st.text_input(
        "Serper API Key",
        value=st.session_state["saved_serper_key"],
        type="password",
        help="用于网络搜索功能",
        key="serper_key_input"
    )
    
    firecrawl_api_key = st.text_input(
        "FireCrawl API Key",
        value=st.session_state["saved_firecrawl_key"],
        type="password",
        help="用于网页内容抓取",
        key="firecrawl_key_input"
    )
    
    # 保存外部服务配置
    if st.button("💾 保存服务配置", use_container_width=True, key="save_services"):
        st.session_state["saved_serper_key"] = serper_api_key
        st.session_state["saved_firecrawl_key"] = firecrawl_api_key
        
        # 保存到持久化存储
        config_to_save = {
            "model_name": st.session_state.get("saved_model_name", ""),
            "api_key": st.session_state.get("saved_api_key", ""),
            "base_url": st.session_state.get("saved_base_url", ""),
            "temperature": st.session_state.get("saved_temperature", 0.3),
            "serper_key": serper_api_key,
            "firecrawl_key": firecrawl_api_key
        }
        if save_persistent_config(config_to_save):
            st.success("✅ 服务配置已保存并持久化")
        else:
            st.error("❌ 服务配置保存失败")
    
    # 更新环境变量
    if serper_api_key:
        os.environ["SERPER_API_KEY"] = serper_api_key
    if firecrawl_api_key:
        os.environ["FIRECRAWL_API_KEY"] = firecrawl_api_key

# ==================== 功能状态显示 ====================
st.sidebar.markdown("---")
st.sidebar.markdown("### 🛠️ 功能状态")

# 显示当前使用的模型
if api_key and base_url:
    st.sidebar.success(f"✅ 当前模型：{model_name}")
    with st.sidebar.expander("查看模型详情"):
        st.markdown(f"""
        - **模型名称**: `{model_name}`
        - **API 端点**: `{base_url}`
        - **Temperature**: `{temperature}`
        """)
else:
    st.sidebar.error("❌ 请配置模型 API Key 和 Base URL")

# 搜索功能状态
if serper_api_key:
    st.sidebar.success("✅ Serper 搜索功能已启用")
else:
    st.sidebar.warning("⚠️ Serper 未配置，搜索功能受限")

# 网页抓取状态
if firecrawl_api_key:
    st.sidebar.success("✅ FireCrawl 网页抓取已启用")
else:
    st.sidebar.warning("⚠️ FireCrawl 未配置，网页抓取受限")

# 工具调用支持 - 改为更灵活的判断
# 通义千问系列、GPT系列、DeepSeek等主流模型都支持工具调用
if any(keyword in model_name.lower() for keyword in ["qwen", "gpt", "deepseek", "glm", "claude"]):
    st.sidebar.success("✅ 支持高级工具调用功能")
else:
    st.sidebar.info("ℹ️ 基础模型，部分高级功能可能受限")

# ==================== 主界面 ====================
# 标题和介绍
st.title("JobAgent-MultiAgent 职业助手 👨‍💼")
st.markdown("""
<div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
    <p style='margin: 0; color: #31333F;'>
        🚀 基于 LangGraph 的多智能体求职助手系统<br>
        💡 支持简历分析、岗位搜索、求职信生成、公司调研等功能<br>
        📧 <a href='http://mail.qq.com/cgi-bin/qm_share?t=qm_mailme&email=HC4lKS4sKyovLSpcbW0yf3Nx' target='_blank'>联系作者</a>
    </p>
</div>
""", unsafe_allow_html=True)

# 创建代理流程
flow_graph = define_graph()
message_history = StreamlitChatMessageHistory()

# 初始化会话状态变量
if "active_option_index" not in st.session_state:
    st.session_state["active_option_index"] = None
if "interaction_history" not in st.session_state:
    st.session_state["interaction_history"] = []
if "response_history" not in st.session_state:
    st.session_state["response_history"] = ["你好！我是 JobAgent-MultiAgent 职业助手，请问需要什么帮助？"]
if "user_query_history" not in st.session_state:
    st.session_state["user_query_history"] = ["你好! 👋"]
if "resume_saved" not in st.session_state:
    st.session_state["resume_saved"] = False
if "resume_filename" not in st.session_state:
    st.session_state["resume_filename"] = ""
if "DASHSCOPE_API_KEY" not in st.session_state:
    st.session_state["DASHSCOPE_API_KEY"] = ""
if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""
if "stop_execution" not in st.session_state:
    st.session_state["stop_execution"] = False
if "is_processing" not in st.session_state:
    st.session_state["is_processing"] = False
if "input_key" not in st.session_state:
    st.session_state["input_key"] = 0

# 聊天界面的容器
conversation_container = st.container()
input_section = st.container()

def initialize_callback_handler(main_container: DeltaGenerator):
    V = TypeVar("V")

    def wrap_function(func: Callable[..., V]) -> Callable[..., V]:
        context = get_script_run_ctx()

        def wrapped(*args, **kwargs) -> V:
            add_script_run_ctx(ctx=context)
            return func(*args, **kwargs)

        return wrapped

    streamlit_callback_instance = CustomStreamlitCallbackHandler(
        parent_container=main_container
    )

    for method_name, method in inspect.getmembers(
        streamlit_callback_instance, predicate=inspect.ismethod
    ):
        setattr(streamlit_callback_instance, method_name, wrap_function(method))

    return streamlit_callback_instance

# 🔴 优化：简化对话执行逻辑
def execute_chat_conversation(user_input, graph):
    callback_handler_instance = initialize_callback_handler(st.container())
    callback_handler = callback_handler_instance
    
    # 重置停止标志
    st.session_state["stop_execution"] = False
    st.session_state["is_processing"] = True
    
    try:
        print(f"执行对话，用户输入: {user_input}")
        
        # 清除之前的agent序列
        callback_handler.clear_agent_sequence()
        
        # 检查是否被停止
        if st.session_state.get("stop_execution", False):
            st.session_state["is_processing"] = False
            return "⚠️ 执行已被用户停止"
        
        # 🔴 优化：简化消息处理
        output = graph.invoke(
            {
                "messages": list(message_history.messages) + [HumanMessage(content=user_input)],
                "user_input": user_input,
                "config": settings,
                "callback": callback_handler,
                "recursion_count": 0,  # 初始化递归计数
            },
            {"recursion_limit": 15},  # 增加递归限制以支持多步骤任务
        )
        
        # 再次检查是否被停止
        if st.session_state.get("stop_execution", False):
            st.session_state["is_processing"] = False
            return "⚠️ 执行已被用户停止"
        
        # 显示agent执行序列
        agent_sequence = callback_handler.get_agent_sequence()
        if agent_sequence:
            st.markdown("**🤖 Agent执行顺序:**")
            agent_emojis = []
            for agent in agent_sequence:
                if "ResumeAnalyzer" in agent:
                    agent_emojis.append("📄")
                elif "JobSearcher" in agent:
                    agent_emojis.append("💼")
                elif "CoverLetterGenerator" in agent:
                    agent_emojis.append("✍️")
                elif "WebResearcher" in agent:
                    agent_emojis.append("🔍")
                elif "ChatBot" in agent:
                    agent_emojis.append("🤖")
                else:
                    agent_emojis.append("🔄")
            
            st.markdown(" → ".join([f"{emoji} {agent}" for emoji, agent in zip(agent_emojis, agent_sequence)]))
        
        # 🔴 优化：简化消息提取
        message_output = output.get("messages")[-1]
        messages_list = output.get("messages")
        message_history.clear()
        message_history.add_messages(messages_list)
        
        st.session_state["is_processing"] = False
        return message_output.content

    except Exception as exc:
        st.session_state["is_processing"] = False
        
        # 检查是否是用户主动停止
        if st.session_state.get("stop_execution", False):
            return "⚠️ 执行已被用户停止"
        
        print(f"详细错误: {exc}")
        import traceback
        traceback.print_exc()
        st.error(f"执行错误: {str(exc)}")
        return ":( 抱歉，发生了一些错误。请重试。"

# 清除聊天功能
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🗑️ 清除聊天", use_container_width=True):
        st.session_state["user_query_history"] = []
        st.session_state["response_history"] = []
        st.session_state["stop_execution"] = False
        st.session_state["is_processing"] = False
        st.session_state["input_key"] += 1  # 增加 key 以重新创建输入框
        message_history.clear()
        st.rerun()

streamlit_analytics.start_tracking()

# ==================== 输入区域 ====================
with input_section:
    # 快捷问题选项（放在输入框上方）
    st.markdown("##### 💡 快捷问题")
    options = [
        "总结我的简历",
        "搜索 GenAI 相关岗位",
        "分析我的简历并推荐合适岗位",
        "生成求职信",
        "识别 GenAI 相关的科技行业最新趋势",
        "查找新兴技术及其对岗位机会的影响",
        "根据我的简历生成职业路径可视化",
        "阿里的 GenAI 相关岗位",
    ]
    icons = ["📝", "🔍", "💼", "✉️", "🌐", "🔍", "📈", "🏢"]

    # 使用 columns 来创建按钮式的快捷问题
    cols = st.columns(4)
    for idx, (option, icon) in enumerate(zip(options, icons)):
        with cols[idx % 4]:
            if st.button(f"{icon} {option}", key=f"quick_{idx}", use_container_width=True, disabled=st.session_state.get("is_processing", False)):
                # 验证逻辑
                if not uploaded_document:
                    st.error("❌ 请先上传您的简历，然后再提交查询。")
                elif not api_key or not base_url:
                    st.error("❌ 请先配置模型 API Key 和 Base URL。")
                else:
                    # 直接添加到历史并触发对话
                    st.session_state["user_query_history"].append(option)
                    st.session_state["response_history"].append("🤔 正在思考中...")
                    st.session_state["last_input"] = option
                    st.session_state["is_processing"] = True
                    st.session_state["stop_execution"] = False
                    st.session_state["input_key"] += 1  # 增加 key 以重新创建输入框
                    st.rerun()
    
    # 使用 chat_input 替代 text_area（chat_input 默认 Enter 发送，Shift+Enter 换行）
    if not st.session_state.get("is_processing", False):
        user_input_query = st.chat_input(
            "😀请输入您的问题（按 Enter 发送，Shift+Enter 换行）",
            key=f"chat_input_{st.session_state['input_key']}",
            disabled=False
        )
        
        if user_input_query:
            # 验证逻辑
            if not uploaded_document:
                st.error("❌ 请先上传您的简历，然后再提交查询。")
            elif not api_key or not base_url:
                st.error("❌ 请先配置模型 API Key 和 Base URL。")
            else:
                # 先添加用户消息到历史
                st.session_state["user_query_history"].append(user_input_query)
                st.session_state["response_history"].append("🤔 正在思考中...")
                st.session_state["last_input"] = user_input_query
                st.session_state["is_processing"] = True
                st.session_state["stop_execution"] = False
                st.session_state["input_key"] += 1  # 增加 key 以重新创建输入框（清空内容）
                # 重新渲染以显示思考状态
                st.rerun()
    else:
        # 处理中时显示禁用的输入框和停止按钮
        st.chat_input(
            "💬 处理中，请稍候...",
            key=f"chat_input_disabled_{st.session_state['input_key']}",
            disabled=True
        )
        
        # 停止按钮
        col1, col2 = st.columns([5, 1])
        with col2:
            if st.button("⏹️ 停止", use_container_width=True, type="secondary", key="stop_btn_inline"):
                st.session_state["stop_execution"] = True
                st.session_state["is_processing"] = False
                # 更新最后一条响应为停止消息
                if st.session_state["response_history"] and st.session_state["response_history"][-1] == "🤔 正在思考中...":
                    st.session_state["response_history"][-1] = "⚠️ 执行已被用户停止"
                st.rerun()

# ==================== 显示聊天历史 ====================
if st.session_state["response_history"]:
    with conversation_container:
        for i in range(len(st.session_state["response_history"])):
            message(
                st.session_state["user_query_history"][i],
                is_user=True,
                key=str(i) + "_user",
                avatar_style="adventurer",
            )
            
            # 如果是思考状态，执行实际查询
            if st.session_state["response_history"][i] == "🤔 正在思考中...":
                # 检查是否被停止
                if st.session_state.get("stop_execution", False):
                    st.session_state["response_history"][i] = "⚠️ 执行已被用户停止"
                    st.session_state["is_processing"] = False
                    st.rerun()
                else:
                    with st.spinner("🤔 AI 正在思考中..."):
                        chat_output = execute_chat_conversation(
                            st.session_state["user_query_history"][i], 
                            flow_graph
                        )
                        st.session_state["response_history"][i] = chat_output
                        st.rerun()
            
            message(
                st.session_state["response_history"][i],
                key=str(i),
                avatar_style="bottts",
            )

streamlit_analytics.stop_tracking()