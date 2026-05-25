"""
LangGraph StateGraph 构建
定义智能体的完整工作流程：分类 → 分支执行 → 循环/结束
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState
from agent.nodes.classify import classify_node
from agent.nodes.planner import planner_node
from agent.nodes.executor import executor_node
from agent.nodes.replanner import replanner_node
from agent.nodes.chat import chat_node
from agent.nodes.rag import rag_node
from agent.nodes.summarize import summarize_node
from agent.memory import memory_service
from utils.logger_handler import logger


def build_graph():
    """构建 StateGraph"""

    # 初始化图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("classify", classify_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("replanner", replanner_node)
    graph.add_node("chat", chat_node)
    graph.add_node("rag", rag_node)
    graph.add_node("summarize", summarize_node)

    # 设置入口点
    graph.add_edge(START, "classify")

    # 分类后分支
    def route_after_classify(state: AgentState) -> str:
        intent = state.get("intent", "rag")
        logger.info(f"[Graph] 路由到：{intent}")

        if intent == "chat":
            return "chat"
        elif intent == "rag":
            return "rag"
        elif intent == "complex":
            return "planner"
        else:
            return "rag"

    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        ["chat", "rag", "planner"]
    )

    # 闲聊分支
    graph.add_edge("chat", "summarize")
    graph.add_edge("summarize", END)

    # RAG 分支
    graph.add_edge("rag", "summarize")
    graph.add_edge("summarize", END)

    # 复杂任务分支（Plan-and-Execute）
    graph.add_edge("planner", "executor")

    # 执行器后到重规划器
    graph.add_edge("executor", "replanner")

    # 重规划器后条件分支
    def route_after_replan(state: AgentState) -> str:
        if state.get("is_finished"):
            return "summarize"
        else:
            return "executor"

    graph.add_conditional_edges(
        "replanner",
        route_after_replan,
        ["summarize", "executor"]
    )

    # 摘要后结束
    graph.add_edge("summarize", END)

    # 编译图
    memory = MemorySaver()
    compiled_graph = graph.compile(checkpointer=memory)

    logger.info("[Graph] StateGraph 构建完成")
    return compiled_graph


# 全局图实例
_graph = None


def get_graph():
    """获取图实例（单例）"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
