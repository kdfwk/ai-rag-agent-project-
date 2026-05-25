"""
执行器节点
执行计划中的当前步骤
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


async def executor_node(state: AgentState) -> AgentState:
    """执行当前步骤"""
    current_step = state["current_step"]
    plan = state["plan"]

    # 检查是否已完成所有步骤
    if current_step >= len(plan):
        state["is_finished"] = True
        return state

    # 获取当前步骤
    step = plan[current_step]
    tool_name = step.get("tool")
    task = step.get("task", "")

    logger.info(f"[Executor] 执行步骤 {current_step + 1}: {task}")

    # 如果有工具，调用工具
    if tool_name and tool_name in TOOL_MAP:
        try:
            tool = TOOL_MAP[tool_name]

            # 准备工具参数
            if tool_name == "rag_summarize":
                result = tool.invoke({"query": state["query"]})
            elif tool_name == "get_weather":
                # 从任务中提取城市
                import re
                city_match = re.search(r'城市["\s]*(.+?)["\s]', task)
                city = city_match.group(1) if city_match else "北京"
                result = tool.invoke({"city": city})
            elif tool_name == "fetch_external_data":
                # 从状态获取用户ID和月份
                user_id = state.get("user_id", "1001")
                month = state.get("month", "2025-01")
                result = tool.invoke({"user_id": user_id, "month": month})
            else:
                # 无参数工具
                result = tool.invoke({})

            # 记录结果
            state["step_results"].append({
                "step": current_step + 1,
                "task": task,
                "result": result,
                "status": "success"
            })

            state["tool_result"] = result
            state["tool_error"] = None

        except Exception as e:
            logger.error(f"[Executor] 工具调用失败: {tool_name}, 错误: {e}")

            # 检查是否需要重试
            if state["retry_count"] < state["max_retries"]:
                state["retry_count"] += 1
                logger.info(f"[Executor] 重试第 {state['retry_count']} 次")
                return state  # 保持 current_step 不变，下次循环重试

            # 重试次数用尽，记录错误
            state["step_results"].append({
                "step": current_step + 1,
                "task": task,
                "result": str(e),
                "status": "failed"
            })

            state["tool_result"] = None
            state["tool_error"] = str(e)

    else:
        # 无工具，直接记录任务
        state["step_results"].append({
            "step": current_step + 1,
            "task": task,
            "result": "无工具执行",
            "status": "success"
        })

    # 进入下一步
    state["current_step"] += 1
    state["retry_count"] = 0  # 重置重试计数

    return state
