"""
智扫通机器人智能客服 - Web 应用入口

这是用户看到的界面（基于 Streamlit 框架），负责：
  1. 显示聊天界面（对话框、消息气泡）
  2. 侧边栏提供 MCP 配置选项
  3. 把用户输入传给 ReactAgent，把回答流式显示出来

MCP 三种模式（侧边栏切换）:
  - 仅本地工具:    只用 agent_tools.py 中的本地工具
  - 单服务器模式:  手动填一个 MCP 地址（默认本地 8001）
  - 多服务器模式:  使用 zs_mcp/mcp_config.py 里 enabled=True 的配置

启动方式:
  streamlit run app.py
"""
import os
import json
import time
import streamlit as st
from agent.react_agent import ReactAgent
from zs_mcp.mcp_config import ALL_MCP_SERVERS, get_enabled_servers

# 用户信息持久化文件
USER_INFO_FILE = "user_info.json"

def load_user_info() -> dict:
    """从文件加载用户信息"""
    if os.path.exists(USER_INFO_FILE):
        try:
            with open(USER_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_user_info(user_info: dict):
    """保存用户信息到文件"""
    with open(USER_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(user_info, f, ensure_ascii=False)

# ── 页面基本配置 ──
st.set_page_config(
    page_title="智扫通机器人智能客服",
    page_icon="🤖",
    layout="centered",
)

st.title("🤖 智扫通机器人智能客服")
st.caption("基于 ReAct + RAG + MCP 的智能问答系统")
st.divider()

# ── 侧边栏：MCP 配置 ──
with st.sidebar:
    st.header("⚙️ 系统配置")
    st.subheader("🔌 MCP")

    # 让用户选择工具来源模式
    mcp_mode = st.radio(
        "工具来源",
        ["仅本地工具", "单服务器模式", "多服务器模式"],
        index=0,
    )

    mcp_url = None
    if mcp_mode == "单服务器模式":
        mcp_url = st.text_input(
            "MCP 地址",
            value="http://localhost:8001/sse",
            help="需先运行: python zs_mcp/start_robot_mcp_server.py",
        )
    elif mcp_mode == "多服务器模式":
        enabled = get_enabled_servers()
        if enabled:
            st.success(f"已启用 {len(enabled)} 个服务")
            for key, cfg in ALL_MCP_SERVERS.items():
                icon = "✅" if key in enabled else "❌"
                with st.expander(f"{icon} {cfg['name']}"):
                    st.caption(cfg["description"])
                    st.text(f"{cfg['transport']} | {cfg['url'][:50]}…")
        else:
            st.warning("无已启用服务，请编辑 zs_mcp/mcp_config.py")
        st.caption("在 zs_mcp/mcp_config.py 中设置 enabled=True")

    st.divider()
    st.markdown("""
**功能**
- 知识库检索（RAG）
- 天气 / 用户报告
- MCP 远程工具扩展
""")

# ── 初始化 Agent（当模式变化时重新创建） ──
need_reinit = (
    "agent" not in st.session_state
    or st.session_state.get("mcp_mode") != mcp_mode
    or st.session_state.get("mcp_url") != mcp_url
)

if need_reinit:
    with st.spinner("正在初始化…"):
        if mcp_mode == "多服务器模式":
            configs = get_enabled_servers()
            st.session_state["agent"] = (
                ReactAgent(mcp_server_configs=configs) if configs else ReactAgent()
            )
        elif mcp_mode == "单服务器模式" and mcp_url:
            st.session_state["agent"] = ReactAgent(mcp_server_url=mcp_url)
        else:
            st.session_state["agent"] = ReactAgent()
        st.session_state["mcp_mode"] = mcp_mode
        st.session_state["mcp_url"] = mcp_url

# ── 聊天消息管理 ──
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# ── 用户信息持久化 ──
# 优先从文件加载（持久化），其次用 session_state
if "user_info" not in st.session_state:
    st.session_state["user_info"] = load_user_info()

def extract_user_info(messages: list) -> dict:
    """从对话中提取用户信息"""
    import re

    user_info = st.session_state.get("user_info", {}).copy()

    for msg in messages:
        content = msg.get("content", "")
        if msg.get("role") == "user":
            # 提取名字
            if "我叫" in content:
                match = re.search(r'我叫([^\s，。,；?!]+)', content)
                if match:
                    user_info["name"] = match.group(1)
            # 提取家庭信息
            elif "我家" in content:
                match = re.search(r'我家(.{2,10})', content)
                if match:
                    user_info["home_info"] = match.group(1)

    return user_info

# 每次加载时从历史消息提取用户信息
st.session_state["user_info"] = extract_user_info(st.session_state["messages"])

# 持久化到文件
save_user_info(st.session_state["user_info"])

# 显示用户信息（如果有）
user_info = st.session_state.get("user_info", {})
if user_info.get("name"):
    st.caption(f"👤 已记住您的信息")
if user_info.get("home_info"):
    st.caption(f"🏠 已记住家庭信息")

# 显示历史消息
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ── 处理用户输入 ──
prompt = st.chat_input("请输入您的问题，例如：扫地机器人如何清理主刷？")

if prompt:
    # 添加用户消息到历史
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 重新显示用户消息
    with st.chat_message("user"):
        st.write(prompt)

    # 调用 Agent 并流式显示回答
    response_container = st.chat_message("assistant")
    message_placeholder = response_container.empty()

    full_response = ""
    with st.spinner("思考中…"):
        # 注入用户信息到上下文
        user_info = st.session_state.get("user_info", {})
        context_prefix = ""
        if user_info.get("name"):
            context_prefix = f"[用户信息：用户名叫 {user_info['name']}]\n"

        # 带上下文的完整查询
        full_query = context_prefix + prompt

        res_stream = st.session_state["agent"].execute_stream_with_history(
            st.session_state["messages"][:-1], full_query
        )

        # 流式显示响应
        for chunk in res_stream:
            full_response += chunk
            message_placeholder.markdown(full_response + "▌")

    # 移除光标指示器并保存完整响应
    message_placeholder.markdown(full_response)
    st.session_state["messages"].append({"role": "assistant", "content": full_response})

    # 重新提取用户信息并保存到文件（因为可能有新信息）
    st.session_state["user_info"] = extract_user_info(st.session_state["messages"])
    save_user_info(st.session_state["user_info"])
