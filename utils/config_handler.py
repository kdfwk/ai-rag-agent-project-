"""
配置加载模块 - 统一管理所有 YAML 配置文件的读取和公共配置

整个项目只需要这一个加载函数，不同配置通过参数区分。
模块加载时自动读取以下配置并导出：
  - rag_conf      → config/rag.yml      (RAG 检索相关参数)
  - chroma_conf   → config/chroma.yml   (向量数据库参数)
  - prompts_conf  → config/prompts.yml  (提示词文件路径)
  - agent_conf    → config/agent.yml    (Agent 智能体参数)

同时提供 get_api_key() 函数，统一获取阿里云 API 密钥。
"""
import os
import yaml
from utils.path_tool import get_abs_path


def _load_yaml(filename: str) -> dict:
    """
    加载 config 目录下的 YAML 配置文件

    Args:
        filename: 相对于项目根目录的文件路径，如 "config/rag.yml"

    Returns:
        解析后的字典
    """
    filepath = get_abs_path(filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_api_key() -> str:
    """
    获取阿里云 DashScope API Key（统一入口）

    按优先级依次检查三个环境变量，取第一个有值的：
      DASHSCOPE_API_KEY → OPEMAO_API_KEY → ALIYUN_API_KEY

    Returns:
        API Key 字符串，未找到时返回空字符串
    """
    return (
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("OPEMAO_API_KEY")
        or os.getenv("ALIYUN_API_KEY")
        or ""
    )


# ── 模块加载时自动读取四份配置，其他文件直接 import 这些变量即可 ──
rag_conf      = _load_yaml("config/rag.yml")
chroma_conf   = _load_yaml("config/chroma.yml")
prompts_conf  = _load_yaml("config/prompts.yml")
agent_conf    = _load_yaml("config/agent.yml")


if __name__ == '__main__':
    print("RAG 配置:", rag_conf)
    print("Chroma 配置:", chroma_conf)
    print("提示词配置:", prompts_conf)
    print("Agent 配置:", agent_conf)
