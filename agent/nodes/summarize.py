"""
记忆摘要节点
生成对话历史摘要
"""

from agent.state import AgentState
from model.factory import chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from utils.prompt_loader import load_prompts
from utils.logger_handler import logger


async def summarize_node(state: AgentState) -> AgentState:
    """生成对话摘要"""
    messages = state["messages"]

    # 只取最近10条消息避免太长
    recent_messages = messages[-10:]

    # 加载摘要提示词
    summary_prompt = load_prompts("summary_prompts")

    system_prompt = f"""{summary_prompt}

请将以下对话总结为简洁的摘要，保留关键信息："""

    # 构建消息文本
    message_text = "\n".join([
        f"{'用户' if msg.type == 'human' else '助手'}: {msg.content[:100]}"
        for msg in recent_messages
    ])

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=message_text)
    ]

    try:
        # 调用模型生成摘要
        response = await chat_model.ainvoke(messages)
        summary = response.content.strip()

        # 更新状态
        state["memory_summary"] = summary
        logger.info(f"[Summarize] 生成摘要: {summary[:50]}...")

    except Exception as e:
        logger.error(f"[Summarize] 摘要生成失败: {e}")
        # 失败时不更新摘要

    return state
