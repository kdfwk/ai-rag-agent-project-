"""
文档加载器工厂 - 根据文件类型自动选择对应的加载器
"""
from typing import Callable
from langchain_core.documents import Document
from utils.document_loader import load_pdf, load_docx, load_image, load_txt
from utils.logger_handler import logger


# 文件扩展名到加载器的映射
LOADER_MAP: dict[str, Callable[[str], list[Document]]] = {
    '.pdf': load_pdf,
    '.docx': load_docx,
    '.txt': load_txt,
    '.jpg': load_image,
    '.jpeg': load_image,
    '.png': load_image,
}


def get_loader(filepath: str) -> Callable[[str], list[Document]] | None:
    """
    根据文件扩展名获取对应的加载器
    
    Args:
        filepath: 文件路径
        
    Returns:
        加载器函数，不支持的格式返回None
    """
    ext = '.' + filepath.lower().rsplit('.', 1)[-1] if '.' in filepath else ''
    return LOADER_MAP.get(ext)


def load_document(filepath: str) -> list[Document]:
    """
    智能加载文档：自动识别文件类型并调用对应加载器
    
    Args:
        filepath: 文件路径
        
    Returns:
        Document列表
    """
    loader = get_loader(filepath)
    
    if loader is None:
        logger.warning(f"[文档加载] 不支持的文件格式: {filepath}")
        return []
    
    try:
        return loader(filepath)
    except Exception as e:
        logger.error(f"[文档加载] {filepath} 失败: {e}", exc_info=True)
        return []


def get_supported_extensions() -> tuple[str]:
    """获取支持的文件扩展名列表"""
    return tuple(LOADER_MAP.keys())
