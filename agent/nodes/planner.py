"""
规划器节点
为复杂任务生成执行计划
"""

from agent.state import AgentState
from model.factory import chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from utils.prompt_loader import load_prompts
from utils.logger_handler import logger
import json


async def planner_node(state: AgentState) -> AgentState:
    """生成任务执行计划"""
    query = state["query"]

    # 加载规划提示词
    plan_prompt = load_prompts("plan_prompts")

    system_prompt = f"""{plan_prompt}

请为以下任务生成详细的执行计划。计划应该是JSON格式，包含以下字段：
- steps: 步骤列表
- 每个步骤包含: step(步骤序号), task(任务描述), tool(使用的工具名称，可选)

可用工具:
- rag_summarize: 查询知识库
- get_weather: 查询天气
- get_user_location: 获取用户位置
- get_user_id: 获取用户ID
- get_current_month: 获取当前月份
- fetch_external_data: 获取外部数据
- fill_context_for_report: 填充报告上下文
- web_search: 网络搜索

只返回JSON，不要其他解释。"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"任务: {query}")
    ]

    try:
        # 调用模型生成计划
        response = await chat_model.ainvoke(messages)
        plan_text = response.content.strip()

        # 解析JSON计划
        # 移除可能的markdown代码块标记
        if "```json" in plan_text:
            plan_text = plan_text.split("```json")[1].split("```")[0].strip()
        elif "```" in plan_text:
            plan_text = plan_text.split("```")[1].split("```")[0].strip()

        plan_data = json.loads(plan_text)

        # 验证计划格式
        if isinstance(plan_data, dict) and "steps" in plan_data:
            state["plan"] = plan_data["steps"]
        elif isinstance(plan_data, list):
            state["plan"] = plan_data
        else:
            # 格式错误，创建默认计划
            logger.warning(f"[Planner] 计划格式错误，使用默认计划: {plan_text}")
            state["plan"] = [{"step": 1, "task": query, "tool": "rag_summarize"}]

        state["current_step"] = 0
        logger.info(f"[Planner] 生成计划: {len(state['plan'])} 步")

    except Exception as e:
        logger.error(f"[Planner] 计划生成失败: {e}")
        # 创建默认计划
        state["plan"] = [{"step": 1, "task": query, "tool": "rag_summarize"}]
        state["current_step"] = 0

    return state
