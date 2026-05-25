"""
多 MCP 服务器客户端 - 同时连接多个远程 MCP 服务，合并所有工具

与单客户端的区别：
  - 单客户端：只连一个 MCP 服务
  - 多客户端：从 mcp_config.py 读取所有 enabled=True 的服务，逐个连接

为了避免不同服务出现同名工具冲突，多服务时工具名会自动加上服务前缀。
例如: local_python_search_robot_knowledge
"""
from typing import List, Dict, Any

try:
    from fastmcp import Client
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    Client = Any

from langchain_core.tools import Tool
from utils.logger_handler import logger
from zs_mcp.tool_adapter import mcp_tools_to_langchain


class MultiServerMCPClient:
    """连接多个 MCP 服务，合并所有远程工具供 Agent 使用"""

    def __init__(self, server_configs: Dict[str, Dict[str, Any]]):
        """
        Args:
            server_configs: 服务配置字典，格式同 mcp_config.py 中的 ALL_MCP_SERVERS
        """
        self.server_configs = server_configs
        self.clients: Dict[str, Client] = {}
        self.all_tools: List[Tool] = []
        self.tools_by_server: Dict[str, List[Tool]] = {}

    async def connect_all(self):
        """连接所有配置中的 MCP 服务"""
        if not FASTMCP_AVAILABLE:
            logger.debug("[MCP] fastmcp 未安装，跳过连接多服务器")
            return

        logger.info("[MCP] 开始连接多个服务器...")
        for server_key, config in self.server_configs.items():
            try:
                await self._connect_one(server_key, config)
            except Exception as e:
                name = config.get("name", server_key)
                logger.warning(f"[MCP] 连接 {name} 失败: {e}")

        logger.info(f"[MCP] 已连接 {len(self.clients)} 个服务，共 {len(self.all_tools)} 个工具")

    async def _connect_one(self, server_key: str, config: Dict[str, Any]):
        """连接单个 MCP 服务（内部方法）"""
        url = config["url"]
        name = config.get("name", server_key)
        headers = config.get("headers", {})

        logger.debug(f"[MCP] 连接 {name} ({url})")
        try:
            client = Client(transport=url, headers=headers)
        except TypeError:
            client = Client(transport=url)

        await client.__aenter__()
        tools_info = await client.list_tools()
        logger.debug(f"[MCP]   → {len(tools_info)} 个工具")

        # 转换工具格式，并加上服务前缀避免命名冲突
        server_tools = mcp_tools_to_langchain(
            client, tools_info,
            name_prefix=f"{server_key}_",
            desc_prefix=f"[{name}] ",
        )

        self.clients[server_key] = client
        self.tools_by_server[server_key] = server_tools
        self.all_tools.extend(server_tools)

    async def get_tools(self) -> List[Tool]:
        """返回所有服务合并后的工具列表"""
        if not FASTMCP_AVAILABLE:
            logger.debug("[MCP] fastmcp 未安装，返回空工具列表")
            return []
        return self.all_tools

    async def disconnect_all(self):
        """断开所有 MCP 连接"""
        for server_key, client in self.clients.items():
            try:
                await client.__aexit__(None, None, None)
            except Exception:
                pass
        self.clients.clear()
