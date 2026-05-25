"""
工具调用节点
执行单个工具调用
"""

from agent.state import AgentState
from agent.tools.agent_tools import (
    rag_summarize, get_weather, get_user_location,
    get_user_id, get_current_month, fetch_external_data,
    fill_context_for_report, web_search
)
from utils.logger_handler import logger

# 工具映射表
TOOL_MAP = {
    "rag_summarize": rag_summarize,
    "get_weather": get_weather,
    "get_user_location": get_user_location,
    "get_user_id": get_user_id,
    "get_current_month": get_current_month,
    "fetch_external_data": fetch_external_data,
    "fill_context_for_report": fill_context_for_report,
    "web_search": web_search,
}


async def tools_node(state: AgentState) -> AgentState:
    """执行工具调用"""
    # 这里假设工具名称和参数已经在状态中
    tool_name = state.get("tool_name")
    tool_args = state.get("tool_args", {})

    if not tool_name or tool_name not in TOOL_MAP:
        state["tool_error"] = f"工具不存在: {tool_name}"
        return state

    try:
        tool = TOOL_MAP[tool_name]
        result = tool.invoke(tool_args)

        state["tool_result"] = result
        state["tool_error"] = None

        logger.info(f"[Tools] 成功调用: {tool_name}")

    except Exception as e:
        logger.error(f"[Tools] 工具调用失败: {tool_name}, 错误: {e}")
        state["tool_error"] = str(e)
        state["tool_result"] = None

    return state
