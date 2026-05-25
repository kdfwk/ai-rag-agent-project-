"""
意图分类节点
分析用户查询，判断是闲聊、RAG检索还是复杂任务
"""

from agent.state import AgentState
from model.factory import chat_model
from langchain_core.messages import HumanMessage, SystemMessage


async def classify_node(state: AgentState) -> AgentState:
    """分类用户意图"""
    query = state["query"]

    # 构建分类提示词
    system_prompt = """你是一个任务分类器。分析用户问题，判断属于哪一类：

1. chat - 闲聊、问候、简单问答（不需要检索知识库）
2. rag - 需要查询扫地机器人知识库的问题
3. complex - 复杂任务，需要多步骤执行（如生成报告、综合分析）

只返回分类结果，不要解释。"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"问题: {query}")
    ]

    # 调用模型分类
    response = await chat_model.ainvoke(messages)
    intent = response.content.strip().lower()

    # 验证意图有效性
    if intent not in ["chat", "rag", "complex"]:
        intent = "rag"  # 默认使用RAG

    state["intent"] = intent
    return state
