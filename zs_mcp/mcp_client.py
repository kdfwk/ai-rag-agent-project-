"""
单 MCP 服务器客户端 - 连接一个远程 MCP 服务并获取其工具

使用流程（ReactAgent 初始化时会自动执行）:
  1. connect()   → 通过 SSE/HTTP 连接到 MCP 服务端
  2. get_tools() → 拉取该服务提供的所有工具，转成 LangChain Tool 格式
  3. disconnect() → 断开连接
"""
from typing import List, Optional

try:
    from fastmcp import Client
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    Client = None

from langchain_core.tools import Tool
from utils.logger_handler import logger
from zs_mcp.tool_adapter import mcp_tools_to_langchain


class MCPClient:
    """连接单个 MCP 服务，供 ReactAgent 加载远程工具"""

    def __init__(self, server_url: str = "http://localhost:8001/sse"):
        self.server_url = server_url
        self._client: Optional[Client] = None
        self.tools: List[Tool] = []

    async def connect(self) -> Optional[Client]:
        """连接到 MCP 服务端"""
        if not FASTMCP_AVAILABLE:
            logger.error("[MCP] fastmcp 未安装，无法连接 MCP 服务器")
            return None

        if self._client is None:
            logger.info(f"[MCP] 正在连接 {self.server_url}")
            self._client = Client(transport=self.server_url)
            await self._client.__aenter__()
            logger.info("[MCP] 连接成功")
        return self._client

    async def disconnect(self):
        """断开 MCP 连接"""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def get_tools(self) -> List[Tool]:
        """获取远程工具列表（自动转成 LangChain Tool 格式）"""
        if not FASTMCP_AVAILABLE:
            logger.warning("[MCP] fastmcp 未安装，返回空工具列表")
            return []

        client = await self.connect()
        if client is None:
            return []

        tools_info = await client.list_tools()
        logger.info(f"[MCP] 获取到 {len(tools_info)} 个远程工具")
        self.tools = mcp_tools_to_langchain(client, tools_info)
        return self.tools
