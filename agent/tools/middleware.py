"""
Agent 中间件 - 在工具调用和模型执行的前后插入自定义逻辑

什么是中间件？
  就像高速公路上的收费站，数据经过时可以做检查、记录、修改等操作。
  本模块定义了三个中间件，分别在不同时机执行：

  1. monitor_tool         → 工具调用前后：记录日志 + 拦截特定工具
  2. log_before_model     → 模型执行之前：输出调试日志
  3. report_prompt_switch → 动态切换提示词：报告场景用报告提示词，其他用默认提示词
"""
from typing import Callable
from utils.prompt_loader import load_system_prompts, load_report_prompts
from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from utils.logger_handler import logger


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,# 工具调用请求
    handler: Callable[[ToolCallRequest], ToolMessage | Command],# 工具调用处理函数
) -> ToolMessage | Command:
    """
    工具调用监控（在每个工具执行前后运行）

    作用：
      1. 记录哪个工具被调用了、传了什么参数
      2. 如果是 fill_context_for_report 工具，在上下文中打个标记，
         后续 report_prompt_switch 会根据这个标记切换提示词
    """
    tool_name = request.tool_call['name']
    tool_args = request.tool_call['args']

    logger.info(f"[tool monitor] 执行工具: {tool_name}")
    logger.info(f"[tool monitor] 传入参数: {tool_args}")

    try:
        result = handler(request)     # 执行工具本身
        logger.info(f"[tool monitor] 工具 {tool_name} 调用成功")

        # 特殊处理：报告生成场景，打标记
        if tool_name == "fill_context_for_report":
            request.runtime.context["report"] = True

        return result
    except Exception as e:
        logger.error(f"工具 {tool_name} 调用失败: {e}")
        raise


@before_model
def log_before_model(state: AgentState, runtime: Runtime):
    """
    模型执行前的日志记录

    每次 AI 模型被调用之前，输出当前有多少条消息、最后一条消息的内容。
    方便开发者调试，观察 Agent 的思考过程。
    """
    messages = state['messages']
    logger.info(f"[log_before_model] 即将调用模型，带有 {len(messages)} 条消息")
    logger.debug(f"[log_before_model] 最后一条: {type(messages[-1]).__name__} | {messages[-1].content.strip()}")

    return None     # 返回 None 表示不修改状态，继续正常执行


@dynamic_prompt
def report_prompt_switch(request: ModelRequest) -> str:
    """
    动态切换系统提示词

    普通对话 → 使用 main_prompt.txt（通用客服角色）
    报告生成 → 使用 report_prompt.txt（报告写手角色）

    判断依据：上下文中是否有 report=True 标记（由 monitor_tool 设置）
    """
    is_report = request.runtime.context.get("report", False)

    if is_report:
        return load_report_prompts()      # 报告生成场景的专用提示词
    return load_system_prompts()          # 日常对话的默认提示词
