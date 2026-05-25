"""
RAG检索节点
处理需要知识库检索的问题
"""

from agent.state import AgentState
from rag.rag_service import RagSummarizeService
from utils.logger_handler import logger
from agent.memory import memory_service


async def rag_node(state: AgentState) -> AgentState:
    """执行RAG检索和回答生成"""
    query = state["query"]

    try:
        # 【长期记忆检索】获取用户历史信息，用于个性化回答
        try:
            long_term_memories = memory_service.search_vector_memory(query, k=2)
            facts = memory_service.extract_facts(state.get("messages", []))
        except Exception as e:
            long_term_memories = []
            facts = []
        
        # 初始化RAG服务
        rag_service = RagSummarizeService()

        # 执行RAG（传入记忆上下文）
        answer = await rag_service.arag_summarize(query, long_term_memories, facts)

        # 更新状态
        state["final_answer"] = answer
        state["is_finished"] = True

        logger.info(f"[RAG] 成功生成回答，长度: {len(answer)}")

    except Exception as e:
        logger.error(f"[RAG] 执行失败: {e}")
        state["final_answer"] = f"RAG检索失败: {e}"
        state["is_finished"] = True

    return state
