"""
提示词加载模块 - 从文件读取 AI 的"指令手册"

项目中有三类提示词（System Prompt），都存放在 prompts/ 目录下，
路径由 config/prompts.yml 配置。本模块负责把它们读出来：

  - load_system_prompts()  → 主提示词（Agent 日常对话时使用的角色设定）
  - load_rag_prompts()     → RAG 总结提示词（让 AI 根据参考资料回答问题）
  - load_report_prompts()  → 报告生成提示词（让 AI 写出用户使用报告）
"""
from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


def _load_prompt(config_key: str, error_label: str) -> str:
    """
    通用的提示词文件加载器（内部使用）

    Args:
        config_key:  prompts.yml 中的键名，如 "main_prompt_path"
        error_label: 出错时日志里显示的名称，方便定位问题

    Returns:
        提示词的文本内容
    """
    try:
        prompt_path = get_abs_path(prompts_conf[config_key])
    except KeyError:
        logger.error(f"[{error_label}] 配置项中缺少 '{config_key}'")
        raise

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"[{error_label}] 加载提示词失败: {e}")
        raise


def load_system_prompts() -> str:
    """加载主系统提示词（Agent 的角色设定和行为规则）"""
    return _load_prompt("main_prompt_path", "系统提示词")


def load_rag_prompts() -> str:
    """加载 RAG 总结提示词（用于根据检索资料生成回答）"""
    return _load_prompt("rag_summarize_prompt_path", "RAG总结提示词")


def load_report_prompts() -> str:
    """加载报告生成提示词（用于生成用户使用报告）"""
    return _load_prompt("report_prompt_path", "报告生成提示词")


def load_prompts(key: str) -> str:
    """通用提示词加载器（支持 plan, replan, summary 等）"""
    return _load_prompt(key, key)


def load_plan_prompts() -> str:
    """加载任务规划提示词"""
    return _load_prompt("plan_prompts", "规划提示词")


def load_replan_prompts() -> str:
    """加载重规划提示词"""
    return _load_prompt("replan_prompts", "重规划提示词")


def load_summary_prompts() -> str:
    """加载摘要提示词"""
    return _load_prompt("summary_prompts", "摘要提示词")


if __name__ == '__main__':
    print("=== 系统提示词 ===")
    print(load_system_prompts()[:100], "...")
