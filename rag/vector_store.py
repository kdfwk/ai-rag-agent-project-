"""
向量存储服务 - 管理 Chroma 向量数据库

向量数据库是什么？
  普通数据库用关键词搜索，向量数据库用"语义"搜索。
  比如搜"机器人迷路了"，能找到包含"机器人定位异常"的文档，
  因为它们意思相近（向量距离近）。

本模块的功能:
  1. load_documents()   → 把文档加载、切块、转成向量，存入数据库
  2. get_retriever()    → 获取一个"检索器"，输入问题就能找到相关文档
  3. MD5 去重           → 同一个文件不重复入库
"""
import os
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.config_handler import chroma_conf
from model.factory import embed_model
from utils.path_tool import get_abs_path
from utils.loader_factory import load_document, get_supported_extensions
from utils.file_utils import get_file_md5_hex, list_files_by_extension
from utils.logger_handler import logger


class VectorStoreService:
    """向量存储服务：负责文档的入库和检索"""

    def __init__(self):
        # 连接 Chroma 向量数据库（本地持久化存储）
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=chroma_conf["persist_directory"],
        )

        # 文本分片器：长文档切成小段，方便精确检索
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],           # 每段最多多少字
            chunk_overlap=chroma_conf["chunk_overlap"],     # 相邻段重叠多少字（保持上下文连贯）
            separators=chroma_conf["separators"],           # 按什么符号切分（优先按段落，其次按句子）
            length_function=len,
        )

    def get_retriever(self):
        """
        获取检索器（给 RAG 服务用的）

        用法: retriever.invoke("扫地机器人怎么迷路") → 返回最相关的文档片段
        """
        return self.vector_store.as_retriever(
            search_kwargs={"k": chroma_conf["k"]}   # 每次检索返回 k 个最相关的片段
        )

    # ── MD5 去重机制（避免同一个文件重复入库） ──

    def _check_md5_exists(self, md5_hex: str) -> bool:
        """检查这个文件的 MD5 是否已经入库过"""
        md5_file = get_abs_path(chroma_conf["md5_hex_store"])

        if not os.path.exists(md5_file):
            open(md5_file, "w", encoding="utf-8").close()
            return False

        with open(md5_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == md5_hex:
                    return True
        return False

    def _save_md5(self, md5_hex: str):
        """入库成功后，把文件 MD5 记录下来"""
        md5_file = get_abs_path(chroma_conf["md5_hex_store"])
        with open(md5_file, "a", encoding="utf-8") as f:
            f.write(md5_hex + "\n")

    # ── 文档入库主流程 ──

    def load_documents(self):
        """
        从 data/ 文件夹加载所有支持的文档，向量化后存入向量库

        流程: 扫描文件 → 计算MD5检查去重 → 加载文档 → 文本分片 → 存入向量库
        """
        # 1. 确定要处理哪些文件类型
        supported_exts = tuple(get_supported_extensions())

        # 2. 列出 data/ 下所有符合条件的文件
        data_dir = get_abs_path(chroma_conf["data_path"])
        file_list = list_files_by_extension(data_dir, supported_exts)

        if not file_list:
            logger.warning(f"[知识库] {data_dir} 下未找到支持的文件")
            return

        logger.info(f"[知识库] 发现 {len(file_list)} 个文件待处理")

        # 3. 逐个处理文件
        for filepath in file_list:
            # 计算文件指纹（MD5），已处理过的跳过
            md5_hex = get_file_md5_hex(filepath)
            if not md5_hex:
                logger.warning(f"[知识库] 跳过: {filepath} (MD5计算失败)")
                continue

            if self._check_md5_exists(md5_hex):
                logger.info(f"[知识库] 跳过: {filepath} (已处理)")
                continue

            try:
                # 加载文档内容
                documents = load_document(filepath)
                if not documents:
                    logger.warning(f"[知识库] 跳过: {filepath} (无有效内容)")
                    continue

                # 把长文档切成小段
                split_docs = self.splitter.split_documents(documents)
                if not split_docs:
                    logger.warning(f"[知识库] 跳过: {filepath} (分片后无内容)")
                    continue

                # 存入向量数据库（自动转成向量）
                self.vector_store.add_documents(split_docs)

                # 记录已处理的 MD5
                self._save_md5(md5_hex)
                logger.info(f"[知识库] 入库成功: {filepath} ({len(split_docs)}个片段)")

            except Exception as e:
                logger.error(f"[知识库] 入库失败: {filepath} 错误: {e}", exc_info=True)
                continue


if __name__ == '__main__':
    vs = VectorStoreService()
    vs.load_documents()

    retriever = vs.get_retriever()
    res = retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("-" * 20)
