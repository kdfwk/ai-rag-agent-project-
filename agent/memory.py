"""
记忆管理模块
实现摘要记忆和向量长记忆
"""

import os
from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from model.factory import chat_model, embed_model
from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.config_handler import chroma_conf, rag_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


class MemoryService:
    """记忆服务：摘要记忆 + 向量长记忆"""

    def __init__(self):
        # 向量记忆集合
        memory_collection = chroma_conf.get("memory_collection_name", "agent_memory")

        self.vector_memory = Chroma(
            collection_name=memory_collection,# 向量集合名称
            embedding_function=embed_model,
            persist_directory=get_abs_path(chroma_conf["persist_directory"]),# 向量数据库目录
        )

        # 摘要记忆
        self.summary: Optional[str] = None

    def add_to_vector_memory(self, content: str, metadata: dict = None):
        """添加到向量记忆"""
        try:
            doc = Document(
                page_content=content,
                metadata=metadata or {"type": "memory"}
            )
            self.vector_memory.add_documents([doc])
            logger.info(f"[Memory] 添加向量记忆: {content[:30]}...")
        except Exception as e:
            logger.error(f"[Memory] 向量记忆添加失败：{e}")

    def search_vector_memory(self, query: str, k: int = 3) -> List[Document]:
        """检索向量记忆"""
        try:
            docs = self.vector_memory.similarity_search(query, k=k)
            logger.info(f"[Memory] 检索到 {len(docs)} 条记忆")
            return docs
        except Exception as e:
            logger.error(f"[Memory] 向量记忆检索失败：{e}")
            return []

    async def generate_summary(self, messages: List[BaseMessage]) -> str:
        """生成对话摘要"""
        try:
            # 取最近 10 条消息
            recent = messages[-10:]

            message_text = "\n".join([
                f"{'用户' if isinstance(m, HumanMessage) else '助手'}: {m.content[:100]}"
                for m in recent
            ])

            prompt = f"""请将以下对话总结为简洁的摘要，保留关键信息（用户偏好、重要事实、待办事项）：

{message_text}

摘要："""

            response = await chat_model.ainvoke(prompt)
            self.summary = response.content.strip()

            logger.info(f"[Memory] 生成摘要：{self.summary[:50]}...")
            return self.summary

        except Exception as e:
            logger.error(f"[Memory] 摘要生成失败：{e}")
            return self.summary or ""

    def get_summary(self) -> str:
        """获取当前摘要"""
        return self.summary or ""

    def should_save_memory(self, messages: List[BaseMessage]) -> bool:
        """判断是否应该保存当前对话到记忆"""
        # 简单规则：消息数大于 5 且有助手回答
        if len(messages) < 5:
            return False

        has_assistant = any(isinstance(m, AIMessage) for m in messages)
        return has_assistant

    def extract_facts(self, messages: List[BaseMessage]) -> List[str]:
        """从对话中提取重要事实"""
        facts = []

        for msg in messages:
            content = msg.content if hasattr(msg, 'content') else str(msg)

            # 简单规则：包含"我叫"、"我喜欢"、"我是"等句子的内容可能是重要事实
            indicators = ["我叫", "我喜欢", "我是", "我家", "我有一个", "我住"]
            for indicator in indicators:
                if indicator in content:
                    facts.append(content)
                    break

        return facts


# 全局记忆服务实例
memory_service = MemoryService()
