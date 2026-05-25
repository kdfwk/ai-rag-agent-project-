"""
重规划节点
评估执行结果，决定下一步
"""

from agent.state import AgentState
from model.factory import chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from utils.prompt_loader import load_prompts
from utils.logger_handler import logger


async def replanner_node(state: AgentState) -> AgentState:
    """评估执行结果，决定下一步"""
    plan = state["plan"]
    current_step = state["current_step"]
    step_results = state["step_results"]

    # 检查是否完成所有步骤
    if current_step >= len(plan):
        state["is_finished"] = True
        return state

    # 加载重规划提示词
    replan_prompt = load_prompts("replan_prompts")

    # 构建评估上下文
    results_summary = "\n".join([
        f"步骤 {r['step']}: {r['task']} - {r['status']}"
        for r in step_results
    ])

    system_prompt = f"""{replan_prompt}

当前计划共 {len(plan)} 步，已完成 {current_step} 步。

执行结果:
{results_summary}

请判断:
1. 计划是否已完成？
2. 是否需要修改剩余步骤？
3. 是否可以继续执行？

只返回以下之一:
- "continue" - 继续执行下一步
- "revise" - 需要修改计划
- "finish" - 计划已完成"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="评估当前状态")
    ]

    # 调用模型评估
    response = await chat_model.ainvoke(messages)
    decision = response.content.strip().lower()

    logger.info(f"[Replanner] 决策: {decision}")

    # 根据决策设置状态
    if decision == "finish":
        state["is_finished"] = True
    elif decision == "revise":
        # 标记需要重新规划
        state["intent"] = "complex"
        state["current_step"] = 0  # 重置步骤
    # "continue" - 保持当前状态，继续执行

    return state
