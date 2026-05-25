"""
文件工具模块 - 提供文件操作相关功能
"""
import os
import hashlib
from utils.logger_handler import logger


def get_file_md5_hex(filepath: str) -> str | None:
    """
    计算文件的MD5哈希值（十六进制字符串）
    
    Args:
        filepath: 文件路径
        
    Returns:
        MD5十六进制字符串，失败返回None
    """
    if not os.path.exists(filepath):
        logger.error(f"[MD5计算] 文件不存在: {filepath}")
        return None

    if not os.path.isfile(filepath):
        logger.error(f"[MD5计算] 路径不是文件: {filepath}")
        return None

    md5_obj = hashlib.md5()
    chunk_size = 4096  # 4KB分片，避免大文件占用过多内存
    
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
        return md5_obj.hexdigest()
    except Exception as e:
        logger.error(f"[MD5计算] 失败: {filepath}, 错误: {e}")
        return None


def list_files_by_extension(path: str, allowed_extensions: tuple[str]) -> tuple[str]:
    """
    列出目录下指定扩展名的文件
    
    Args:
        path: 目录路径
        allowed_extensions: 允许的文件扩展名元组，如 ('.pdf', '.txt')
        
    Returns:
        文件路径元组
    """
    if not os.path.isdir(path):
        logger.error(f"[文件列表] 路径不是目录: {path}")
        return ()

    files = []
    for filename in os.listdir(path):
        if filename.lower().endswith(allowed_extensions):
            files.append(os.path.join(path, filename))
    
    return tuple(files)
