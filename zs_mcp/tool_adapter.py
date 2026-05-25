"""
MCP 工具 → LangChain Tool 的转换（单服/多服共用）
"""
from typing import List, Any, Optional

try:
    from fastmcp import Client
except ImportError:
    Client = Any  # 类型提示用

from langchain_core.tools import Tool


def mcp_tools_to_langchain(
    client: Client,
    tools_info: List[Any],
    name_prefix: str = "",
    desc_prefix: str = "",
) -> List[Tool]:
    """把 list_tools 的结果包装成 Agent 可调用的 LangChain Tool"""
    langchain_tools = []

    for tool_info in tools_info:
        tool_name = tool_info.name
        exposed_name = f"{name_prefix}{tool_name}" if name_prefix else tool_name
        base_desc = tool_info.description or f"远程工具: {tool_name}"
        description = f"{desc_prefix}{base_desc}" if desc_prefix else base_desc

        async def call_remote(*, _client=client, _name=tool_name, **kwargs):
            try:
                return await _client.call_tool(_name, kwargs)
            except Exception as e:
                return f"调用 {_name} 失败: {e}"

        langchain_tools.append(
            Tool(
                name=exposed_name,
                description=description,
                func=None,
                coroutine=call_remote,
            )
        )

    return langchain_tools
