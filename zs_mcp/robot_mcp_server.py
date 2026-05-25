"""
智扫通 MCP 服务端 - 把扫地机器人客服能力以 MCP 协议对外暴露

与 agent/tools/agent_tools.py 能力对应，但通过 MCP 协议提供给远程客户端：
  - search_robot_knowledge   → 知识库检索（RAG）
  - get_robot_weather        → 城市天气
  - get_user_report          → 用户使用报告
  - get_user_location        → 用户所在城市
  - get_user_id              → 用户 ID
  - get_current_month        → 当前月份
  - get_cleaning_recommendation → 扫地建议
  - web_search                  → 联网搜索（DuckDuckGo）

直接运行本文件 → stdio 传输（适合 Cursor/CLI 挂载）
推荐运行 start_robot_mcp_server.py → SSE，供 Web Agent 连接
"""
import os
import sys
import datetime
import random

from ddgs import DDGS

# 保证能 import 项目根目录下的 rag、utils
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from fastmcp import FastMCP
from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path

# ===================================================================
# 1. 创建 MCP 服务实例
# ===================================================================
mcp_server = FastMCP(name="智扫通机器人MCP服务")

# ===================================================================
# 2. 共享数据（天气 + 用户报告 CSV）
# ===================================================================

# 天气数据（各函数共用，避免重复定义）
WEATHER_DATA = {
    "北京": {"temperature": 25, "humidity": 60, "condition": "晴朗",   "wind": "微风",     "suitable_for_cleaning": True},
    "上海": {"temperature": 28, "humidity": 75, "condition": "多云",   "wind": "东南风3级", "suitable_for_cleaning": True},
    "广州": {"temperature": 32, "humidity": 80, "condition": "雷阵雨", "wind": "南风4级",   "suitable_for_cleaning": False},
    "深圳": {"temperature": 30, "humidity": 78, "condition": "阴天",   "wind": "西南风2级", "suitable_for_cleaning": True},
    "杭州": {"temperature": 26, "humidity": 65, "condition": "小雨",   "wind": "东风3级",   "suitable_for_cleaning": False},
}

# 默认天气（城市未找到时使用）
DEFAULT_WEATHER = {
    "temperature": 22, "humidity": 50, "condition": "未知", "wind": "未知", "suitable_for_cleaning": True,
}

# 演示用的用户 ID 和月份列表
USER_IDS = ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1009", "1010"]
MONTHS = [
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
]

# RAG 服务实例
rag = RagSummarizeService()

# 用户使用记录缓存（首次调用时从 CSV 加载）
_external_data: dict = {}


def _now() -> str:
    """返回当前时间字符串，格式 YYYY-MM-DD HH:MM:SS"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _strip_quotes(s: str) -> str:
    """去除 CSV 字段两端的引号"""
    return s.replace('"', "")


def _load_external_data():
    """从 CSV 加载用户使用记录（只加载一次，结果缓存在 _external_data 中）"""
    if _external_data:
        return

    path = get_abs_path(agent_conf["external_data_path"])
    if not os.path.exists(path):
        raise FileNotFoundError(f"外部数据文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        for line in f.readlines()[1:]:          # 跳过表头
            fields = [_strip_quotes(col) for col in line.strip().split(",")]
            uid, feature, efficiency, consumables, comparison, month = fields[:6]

            if uid not in _external_data:
                _external_data[uid] = {}

            _external_data[uid][month] = {
                "特征": feature,
                "效率": efficiency,
                "耗材": consumables,
                "对比": comparison,
            }


# ===================================================================
# 3. 注册 MCP 工具（每个函数对外暴露为一个可调用的远程接口）
# ===================================================================

@mcp_server.tool()
def search_robot_knowledge(query: str) -> str:
    """搜索扫地机器人知识库（RAG 检索 + 总结）"""
    try:
        return rag.rag_summarize(query)
    except Exception as e:
        return f"搜索失败: {e}"


@mcp_server.tool()
def get_robot_weather(city: str) -> dict:
    """获取城市天气，并判断是否适合扫地"""
    weather = WEATHER_DATA.get(city, DEFAULT_WEATHER)
    result = {
        "city": city,
        "weather": weather,
        "recommendation": "天气适合扫地" if weather["suitable_for_cleaning"] else "天气不适合扫地",
        "timestamp": _now(),
    }
    if city not in WEATHER_DATA:
        result["message"] = f"未找到{city}的天气，返回默认数据"
    return result


@mcp_server.tool()
def get_user_report(user_id: str, month: str) -> dict:
    """获取指定用户在指定月份的使用报告（月份格式 YYYY-MM）"""
    try:
        _load_external_data()
        if user_id not in _external_data:
            return {"error": f"用户 {user_id} 不存在"}
        if month not in _external_data[user_id]:
            return {"error": f"用户 {user_id} 在 {month} 无记录"}
        return {
            "user_id": user_id,
            "month": month,
            "report": _external_data[user_id][month],
            "timestamp": _now(),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp_server.tool()
def get_user_location() -> dict:
    """获取用户所在城市（演示用随机）"""
    return {"city": random.choice(["深圳", "合肥", "杭州", "北京", "上海"]), "timestamp": _now()}


@mcp_server.tool()
def get_user_id() -> dict:
    """获取用户 ID（演示用随机）"""
    return {"user_id": random.choice(USER_IDS), "timestamp": _now()}


@mcp_server.tool()
def get_current_month() -> dict:
    """获取当前月份（演示用随机）"""
    return {"month": random.choice(MONTHS), "timestamp": _now()}


@mcp_server.tool()
def get_cleaning_recommendation(city: str) -> dict:
    """根据城市天气给出扫地建议"""
    if city not in WEATHER_DATA:
        return {"city": city, "recommendation": "无法获取天气信息", "tip": "请检查城市名称", "timestamp": _now()}

    weather = WEATHER_DATA[city]

    if weather["condition"] in ("雷阵雨", "小雨", "大雨"):
        recommendation = "不建议今天扫地，天气潮湿"
        tip = "建议等天气好转后再清扫"
    elif weather["humidity"] > 70:
        recommendation = "可以扫地，但湿度较高"
        tip = "建议开启除湿或选择干燥时段"
    else:
        recommendation = "非常适合扫地"
        tip = "天气条件良好，建议全面清扫"

    return {
        "city": city,
        "weather": {"condition": weather["condition"], "humidity": weather["humidity"]},
        "recommendation": recommendation,
        "tip": tip,
        "timestamp": _now(),
    }


# ===================================================================
# 联网搜索工具
# ===================================================================

@mcp_server.tool()
def web_search(query: str) -> str:
    """通过 DuckDuckGo 在互联网上搜索实时信息，当本地知识库无法回答时使用此工具"""
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=5))
        if not results:
            return f"未找到关于「{query}」的结果"
        summaries = []
        for r in results[:5]:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            summaries.append(f"标题：{title}\n摘要：{body}\n链接：{href}")
        return "\n---\n".join(summaries)
    except Exception as e:
        return f"搜索失败: {e}"


# ===================================================================
# 4. 独立启动（stdio 模式，非 Web 场景）
# ===================================================================
if __name__ == "__main__":
    print("启动 MCP 服务（stdio）… 工具: search_robot_knowledge, get_robot_weather, …")
    mcp_server.run()
