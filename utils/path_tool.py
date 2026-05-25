"""
路径工具 - 为整个项目提供统一的路径计算

为什么需要这个模块？
  项目中很多文件用相对路径引用（如 "config/rag.yml"），
  但 Python 运行时的"当前目录"可能不确定。
  本模块通过计算项目根目录的绝对路径，确保无论从哪里启动程序，
  都能正确找到配置文件、数据文件等资源。

用法:
  from utils.path_tool import get_abs_path
  abs_path = get_abs_path("config/rag.yml")
  # 返回: /你的项目路径/config/rag.yml
"""
import os


def get_project_root() -> str:
    """
    获取项目根目录的绝对路径

    原理: 本文件在 utils/path_tool.py，往上两级就是项目根目录
          utils/path_tool.py  →  utils/  →  项目根目录
    """
    current_file = os.path.abspath(__file__)        # 本文件的绝对路径
    current_dir = os.path.dirname(current_file)      # utils/ 目录
    project_root = os.path.dirname(current_dir)      # 项目根目录
    return project_root


def get_abs_path(relative_path: str) -> str:
    """
    把相对路径转换成绝对路径

    Args:
        relative_path: 相对于项目根目录的路径，如 "config/rag.yml"

    Returns:
        完整的绝对路径
    """
    return os.path.join(get_project_root(), relative_path)


if __name__ == '__main__':
    print("项目根目录:", get_project_root())
    print("示例路径:", get_abs_path("config/rag.yml"))
