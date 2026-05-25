"""
启动智扫通 MCP 服务（SSE，供 Web Agent 连接）

用法:
  python mcp/start_robot_mcp_server.py

连接地址（与 app 单服模式默认一致）:
  http://localhost:8001/sse
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))# noqa
from robot_mcp_server import mcp_server

if __name__ == "__main__":
    print("智扫通 MCP 服务 | SSE | http://0.0.0.0:8001/sse")
    mcp_server.run(
        transport="sse",
        host="0.0.0.0",
        port=8001,
        path="/sse",
        log_level="info",
    )
