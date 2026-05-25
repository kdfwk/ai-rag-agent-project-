"""
ReactAgent - 扫地机器人智能客服的核心大脑

工作原理（ReAct 模式 = 思考 → 行动 → 观察 → 再思考）：
  1. 用户提问
  2. Agent 分析问题，决定调用哪些工具
  3. 工具返回结果
  4. Agent 根据结果继续思考或生成最终回答
  5. 重复 2-4 直到信息足够，输出回答

工具来源（可组合）:
  - 本地工具: agent/tools/agent_tools.py（RAG、天气、报告等）
  - 远程工具: zs_mcp/ 下的 MCP 服务提供的远程能力
"""
import asyncio
from typing import Optional, List, Dict, Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from utils.logger_handler import logger
from agent.tools.agent_tools import (
    rag_summarize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
    web_search,
)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch


class ReactAgent:
    """ReAct 智能体 - 具备自主思考和工具调用能力的 AI 客服"""

    def __init__(
        self,
        mcp_server_url: Optional[str] = None,
        mcp_server_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        初始化智能体

        Args:
            mcp_server_url:     单个 MCP 服务地址（如 http://localhost:8001/sse）
            mcp_server_configs: 多个 MCP 服务配置（来自 mcp_config.get_enabled_servers()）
        """
        # 本地工具：始终可用
        self.local_tools = [
            rag_summarize, get_weather, get_user_location, get_user_id,
            get_current_month, fetch_external_data, fill_context_for_report,
            web_search,
        ]
        self.all_tools = list(self.local_tools)
        self._mcp_clients = []  # 保持 MCP 连接，远程工具调用时才可用

        # 按需加载远程工具
        if mcp_server_configs:
            self._append_mcp_tools(self._load_multi_mcp(mcp_server_configs))
        elif mcp_server_url:
            self._append_mcp_tools(self._load_single_mcp(mcp_server_url))

        # 创建 Agent（核心引擎）
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=self.all_tools,
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    # ── 工具管理 ─────────────────────────────────────────────

    def _append_mcp_tools(self, remote_tools: List):
        """将远程工具合并到工具列表中"""
        if remote_tools:
            self.all_tools = self.local_tools + remote_tools
            logger.info(f"[Agent] 本地 {len(self.local_tools)} + 远程 {len(remote_tools)} 个工具")
        else:
            logger.debug("[Agent] 未加载到远程工具，仅使用本地工具")

    def _load_single_mcp(self, server_url: str) -> List:
        """连接单个 MCP 服务并获取其工具"""
        from zs_mcp.mcp_client import MCPClient

        async def _run():
            client = MCPClient(server_url)
            await client.connect()
            tools = await client.get_tools()
            self._mcp_clients.append(client)
            return tools

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.debug(f"[Agent] 单服 MCP 连接失败: {e}")
            return []

    def _load_multi_mcp(self, configs: Dict[str, Dict[str, Any]]) -> List:
        """连接多个 MCP 服务并获取所有工具"""
        from zs_mcp.multi_server_client import MultiServerMCPClient

        async def _run():
            client = MultiServerMCPClient(configs)
            await client.connect_all()
            tools = await client.get_tools()
            self._mcp_clients.append(client)
            return tools

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.debug(f"[Agent] 多服 MCP 连接失败: {e}")
            return []

    # ── 消息处理（核心逻辑） ─────────────────────────────────

    def _build_messages(self, history: List[Dict], current_query: str) -> List:
        """
        把历史记录和当前问题转换成 Agent 能理解的消息格式

        Args:
            history:       历史对话列表 [{"role": "user"/"assistant", "content": "..."}]
            current_query: 用户当前输入的问题

        Returns:
            LangChain 消息对象列表
        """
        messages = []
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=current_query))
        return messages

    def _stream_response(self, messages: List):
        """
        提交消息给 Agent，以流式方式返回回答（逐块输出）

        Args:
            messages: LangChain 消息对象列表

        Yields:
            每一段回答文本（字符串）
        """
        input_dict = {"messages": messages}
        for chunk in self.agent.stream(
            input_dict, stream_mode="values", context={"report": False}
        ):
            latest = chunk["messages"][-1]
            if latest.content:
                yield latest.content.strip() + "\n"

    # ── 对外接口 ─────────────────────────────────────────────

    def execute_stream(self, query: str):
        """
        单轮对话：提交一个问题，流式返回回答

        Args:
            query: 用户的问题文本
        """
        messages = [HumanMessage(content=query)]
        return self._stream_response(messages)

    def execute_stream_with_history(self, history: list, current_query: str):
        """
        多轮对话：带上历史上下文，流式返回回答

        Args:
            history:       历史对话列表 [{"role": "user"/"assistant", "content": "..."}]
            current_query: 用户当前输入的问题
        """
        messages = self._build_messages(history, current_query)
        return self._stream_response(messages)


if __name__ == "__main__":
    agent = ReactAgent()
    for chunk in agent.execute_stream("给我生成我的使用报告"):
        print(chunk, end="", flush=True)


# ── LangGraph Agent（新增）────────────────────────────────────

from langgraph.checkpoint.memory import MemorySaver
from agent.graph import get_graph
from agent.state import AgentState
from agent.memory import memory_service
from utils.config_handler import agent_conf


class LangGraphAgent:
    """基于 LangGraph 的新一代智能体 - 支持规划、记忆、循环执行"""

    def __init__(
        self,
        mcp_server_url: Optional[str] = None,
        mcp_server_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        初始化 LangGraph 智能体

        Args:
            mcp_server_url:     单个 MCP 服务地址
            mcp_server_configs: 多个 MCP 服务配置
        """
        # 加载配置
        self.max_retries = agent_conf.get("max_retries", 3)
        self.max_iterations = agent_conf.get("max_iterations", 10)

        # 获取编译后的图
        self.graph = get_graph()

        # 创建线程配置（用于状态持久化）
        self.config = {"configurable": {"thread_id": "default"}}

        logger.info("[LangGraphAgent] 初始化完成")

    async def execute_stream(self, query: str):
        """单轮对话：流式返回回答（异步生成器）"""
        initial_state: AgentState = {
            "messages": [],
            "query": query,
            "intent": "",
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "retry_count": 0,
            "max_retries": self.max_retries,
            "memory_summary": "",
            "tool_result": None,
            "tool_error": None,
            "is_finished": False,
            "final_answer": None,
        }

        # 运行图
        async for state in self.graph.astream(initial_state, self.config):
            if "final_answer" in state and state["final_answer"]:
                yield state["final_answer"]

    def execute_stream_sync(self, query: str):
        """同步版本的单轮对话（兼容旧代码）"""
        return list(self.execute_stream(query))

    def execute_stream_with_history(self, history: List[Dict], current_query: str):
        """多轮对话：带记忆和历史上下文"""
        # 构建消息历史
        messages = []
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # 添加当前查询
        messages.append(HumanMessage(content=current_query))

        # 获取记忆摘要
        memory_summary = memory_service.get_summary()

        initial_state: AgentState = {
            "messages": messages,
            "query": current_query,
            "intent": "",
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "retry_count": 0,
            "max_retries": self.max_retries,
            "memory_summary": memory_summary,
            "tool_result": None,
            "tool_error": None,
            "is_finished": False,
            "final_answer": None,
        }

        # 运行图
        final_answer = ""
        for state in self.graph.stream(initial_state, self.config):
            if "final_answer" in state and state["final_answer"]:
                final_answer = state["final_answer"]
                yield final_answer

        # 更新记忆
        if messages:
            memory_service.add_to_vector_memory(
                content=f"用户: {current_query}\n助手: {final_answer}",
                metadata={"type": "conversation", "query": current_query}
            )
