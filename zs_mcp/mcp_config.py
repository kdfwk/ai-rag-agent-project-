"""
MCP 服务器连接配置（多服务器模式在 app 侧边栏选用）

修改方式:
  1. 在下方增加或修改一项配置
  2. 将 enabled 设为 True
  3. Web 界面选择「多服务器模式」后生效
"""
from typing import Dict, Any

# --- 各 MCP 服务定义 ---

LOCAL_PYTHON_MCP: Dict[str, Any] = {
    "name": "扫地机器人本地服务",
    "url": "http://localhost:8001/sse",
    "transport": "sse",
    "description": "知识库检索、天气、用户报告等（需先运行 start_robot_mcp_server.py）",
    "enabled": True,
}

# 注册表：新增服务时在这里加一项
ALL_MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    "local_python": LOCAL_PYTHON_MCP,
}


def get_enabled_servers() -> Dict[str, Dict[str, Any]]:
    """返回 enabled=True 的配置，供 ReactAgent 多服模式使用"""
    return {
        name: cfg
        for name, cfg in ALL_MCP_SERVERS.items()
        if cfg.get("enabled", False)
    }


if __name__ == "__main__":
    for name, cfg in ALL_MCP_SERVERS.items():
        flag = "ON " if cfg.get("enabled") else "OFF"
        print(f"[{flag}] {name}: {cfg['name']} | {cfg['transport']}")
