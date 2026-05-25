"""
闲聊节点
处理简单对话
"""

from agent.state import AgentState
from model.factory import chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from utils.prompt_loader import load_system_prompts
from agent.memory import memory_service


async def chat_node(state: AgentState) -> AgentState:
    """处理闲聊对话"""
    query = state["query"]
    memory_summary = state.get("memory_summary", "")

    # 【长期记忆检索】从向量数据库中检索用户历史信息
    try:
        # 搜索与当前问题相关的历史对话（最多3条）
        long_term_memories = memory_service.search_vector_memory(query, k=3)
        
        # 提取关键事实（如用户姓名、偏好等）
        facts = memory_service.extract_facts(state.get("messages", []))
    except Exception as e:
        long_term_memories = []
        facts = []

    # 加载系统提示词
    system_prompt = load_system_prompts()

    # 【长期记忆注入】如果有历史记忆，加入上下文
    if long_term_memories:
        memory_text = "\n".join([f"- {doc.page_content}" for doc in long_term_memories])
        system_prompt += f"\n\n【用户长期记忆档案】\n{memory_text}\n请根据以上历史信息个性化回答用户问题。"
    
    # 【事实注入】如果提取到关键事实，也加入上下文
    if facts:
        facts_text = "\n".join([f"- {fact}" for fact in facts])
        system_prompt += f"\n\n【用户关键信息】\n{facts_text}"

    # 如果有短期记忆摘要，也加入上下文
    if memory_summary:
        system_prompt += f"\n\n本次对话历史摘要:\n{memory_summary}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query)
    ]

    # 调用模型生成回答
    response = await chat_model.ainvoke(messages)

    # 更新状态
    state["final_answer"] = response.content
    state["is_finished"] = True

    return state
