"""
日志模块 - 统一管理系统运行时的日志输出

日志会同时输出到两个地方：
  1. 控制台（终端窗口）  → 方便开发时实时查看
  2. 日志文件（logs/目录）→ 方便事后排查问题

日志级别从低到高：
  DEBUG → 调试信息（最详细，只写文件不显示在控制台）
  INFO  → 普通信息（正常运行时的关键事件）
  WARNING → 警告（有异常但不影响运行）
  ERROR → 错误（某个功能失败了）

用法:
  from utils.logger_handler import logger
  logger.info("服务启动成功")
  logger.error("数据库连接失败")
"""
import os
import logging
from datetime import datetime
from utils.path_tool import get_abs_path

# 日志保存的根目录
LOG_ROOT = get_abs_path("logs")
os.makedirs(LOG_ROOT, exist_ok=True)     # 确保目录存在

# 日志格式：时间 - 模块名 - 级别 - 文件名:行号 - 消息内容
LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)


def get_logger(
    name: str = "agent",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    log_file: str = None,
) -> logging.Logger:
    """
    创建或获取一个日志记录器

    Args:
        name:          日志器名称（通常用模块名）
        console_level: 控制台显示的最低日志级别
        file_level:    文件记录的最低日志级别
        log_file:      自定义日志文件路径（默认按日期自动生成）

    Returns:
        配置好的 Logger 对象
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 Handler（多次调用 get_logger 时）
    if logger.handlers:
        return logger

    # 控制台 Handler：开发时实时查看
    console_handler = logging.StreamHandler()# 创建控制台 Handler
    console_handler.setLevel(console_level)
    console_handler.setFormatter(LOG_FORMAT)
    logger.addHandler(console_handler)

    # 文件 Handler：持久化保存，方便排查
    if not log_file:
        log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")# 日志文件

    file_handler = logging.FileHandler(log_file, encoding='utf-8')# 创建文件 Handler
    file_handler.setLevel(file_level)
    file_handler.setFormatter(LOG_FORMAT)
    logger.addHandler(file_handler)

    return logger


# 默认的全局日志器，其他模块直接 import 即可
logger = get_logger()


if __name__ == '__main__':
    logger.info("信息日志")
    logger.error("错误日志")
    logger.warning("警告日志")
    logger.debug("调试日志")
