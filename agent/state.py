"""
LangGraph State Definition
定义智能体运行时的共享状态结构
"""

from typing import TypedDict, List, Dict, Any, Optional, Union
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """智能体状态定义"""

    # 消息历史
    messages: List[BaseMessage]

    # 用户原始查询
    query: str

    # 任务分类结果
    intent: str  # "chat" | "rag" | "complex"

    # 执行计划（Plan-and-Execute）
    plan: List[Dict[str, Any]]  # [{"step": 1, "task": "xxx", "tool": "tool_name"}]
    current_step: int  # 当前执行到第几步
    step_results: List[Dict[str, Any]]  # 每步执行结果

    # 重试计数
    retry_count: int
    max_retries: int

    # 记忆摘要
    memory_summary: str  # 历史对话摘要

    # 工具调用结果
    tool_result: Optional[str]
    tool_error: Optional[str]

    # 是否结束
    is_finished: bool

    # 最终回答
    final_answer: Optional[str]
