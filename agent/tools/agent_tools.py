"""
Agent 本地工具集 - 为 ReAct 智能体提供可调用的能力

每个 @tool 函数就是 Agent 能"使用"的一个工具：
  - rag_summarize        → 知识库检索（RAG）
  - get_weather          → 查天气
  - get_user_location    → 获取用户城市
  - get_user_id          → 获取用户 ID
  - get_current_month    → 获取当前月份
  - fetch_external_data  → 查询用户使用记录
  - fill_context_for_report → 触发报告生成的提示词切换
  - web_search            → 联网搜索（DuckDuckGo）
"""
import os
import random
from langchain_core.tools import tool
from ddgs import DDGS
from rag.rag_service import RagSummarizeService
from utils.logger_handler import logger
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path

# ── 共享数据 ──
rag = RagSummarizeService()

USER_IDS = ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1009", "1010"]
MONTHS = [
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
]

# 用户使用记录缓存（首次调用 fetch_external_data 时从 CSV 加载）
_external_data: dict = {}


def _strip_quotes(s: str) -> str:
    """去除 CSV 字段两端的引号"""
    return s.replace('"', "")


def _load_external_data():
    """
    从 CSV 加载用户使用记录（只加载一次）

    数据结构:
        {
            "用户ID": {
                "2025-01": {"特征": "...", "效率": "...", "耗材": "...", "对比": "..."},
                "2025-02": {...},
            },
            ...
        }
    """
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
# 工具定义（@tool 装饰器让 Agent 能识别并调用它们）
# ===================================================================

@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    """从知识库检索与问题相关的参考资料"""
    return rag.rag_summarize(query)


@tool(description="获取指定城市的天气，以消息字符串的形式返回")
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return f"城市{city}天气为晴天，气温26摄氏度，空气湿度50%，南风1级，AQI21，最近6小时降雨概率极低"


@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() -> str:
    """获取用户当前所在城市（演示用随机）"""
    return random.choice(["深圳", "合肥", "杭州"])


@tool(description="获取用户的ID，以纯字符串形式返回")
def get_user_id() -> str:
    """获取当前用户的 ID（演示用随机）"""
    return random.choice(USER_IDS)


@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() -> str:
    """获取当前月份（演示用随机）"""
    return random.choice(MONTHS)


@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回，如果未检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    """查询指定用户在指定月份的使用记录"""
    _load_external_data()

    try:
        return _external_data[user_id][month]
    except KeyError:
        logger.warning(f"[fetch_external_data] 未找到用户 {user_id} 在 {month} 的记录")
        return ""


@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    """触发报告生成场景的上下文注入（由中间件拦截处理）"""
    return "fill_context_for_report已调用"


# ===================================================================
# 联网搜索工具
# ===================================================================


@tool(description="通过 DuckDuckGo 在互联网上搜索实时信息，当本地知识库无法回答时使用此工具")
def web_search(query: str) -> str:
    """使用互联网搜索引擎查找最新信息并返回结果摘要"""
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
