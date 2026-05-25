"""
RAG 总结服务 - 检索参考资料 + 让 AI 根据资料回答问题

RAG = Retrieval-Augmented Generation（检索增强生成）
工作流程：
  1. 用户提出问题
  2. 从向量数据库中检索与问题相关的文档片段（参考资料）
  3. 把问题 + 参考资料一起提交给 AI 模型
  4. AI 模型根据参考资料生成准确的回答
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from model.factory import chat_model
from utils.logger_handler import logger


def _debug_print_prompt(prompt):
    """调试辅助：打印发送给 AI 的完整提示词（方便排查问题）"""
    logger.debug(f"[RAG Prompt]\n{prompt.to_string()}")
    return prompt


class RagSummarizeService:
    """RAG 总结服务：检索知识库 → 组装提示词 → 调用模型 → 返回回答"""

    def __init__(self):
        # 1. 初始化向量数据库和检索器
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()

        # 2. 加载 RAG 专用的提示词模板
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)

        # 3. 构建处理链：提示词模板 → 调试打印 → AI 模型 → 提取纯文本
        self.model = chat_model
        self.chain = self.prompt_template | _debug_print_prompt | self.model | StrOutputParser()

    def retriever_docs(self, query: str) -> list[Document]:
        """从向量库检索与 query 相关的文档片段"""
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str) -> str:
        """
        完整的 RAG 流程：检索 → 组装 → 生成

        Args:
            query: 用户的问题

        Returns:
            AI 根据参考资料生成的回答
        """
        # 第一步：检索相关文档
        context_docs = self.retriever_docs(query)

        # 第二步：把检索结果拼接成结构化的参考资料文本
        context_parts = []
        for i, doc in enumerate(context_docs, start=1):
            context_parts.append(
                f"【参考资料{i}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}"
            )
        context = "\n".join(context_parts)

        # 第三步：提交给 AI 模型生成回答
        return self.chain.invoke({"input": query, "context": context})

    async def arag_summarize(self, query: str, long_term_memories=None, facts=None) -> str:
        """
        异步版本的 RAG 流程（支持长期记忆）

        Args:
            query: 用户的问题
            long_term_memories: 从向量数据库检索的历史对话记忆
            facts: 提取的用户关键事实

        Returns:
            AI 根据参考资料生成的回答
        """
        # 第一步：检索相关文档
        context_docs = self.retriever_docs(query)

        # 第二步：拼接参考资料
        context_parts = []
        for i, doc in enumerate(context_docs, start=1):
            context_parts.append(
                f"【参考资料{i}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}"
            )
        context = "\n".join(context_parts)
        
        # 【新增】第三步：构建记忆上下文
        memory_context = ""
        if long_term_memories:
            memory_text = "\n".join([f"- {doc.page_content}" for doc in long_term_memories])
            memory_context += f"\n\n【用户历史记忆】\n{memory_text}"
        
        if facts:
            facts_text = "\n".join([f"- {fact}" for fact in facts])
            memory_context += f"\n\n【用户关键信息】\n{facts_text}"

        # 第四步：异步调用 AI 模型生成回答（传入记忆上下文）
        return await self.chain.ainvoke({
            "input": query, 
            "context": context + memory_context
        })


if __name__ == '__main__':
    rag = RagSummarizeService()
    print(rag.rag_summarize("小户型适合哪些扫地机器人"))
