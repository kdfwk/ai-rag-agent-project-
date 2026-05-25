"""
模型工厂 - 创建项目使用的 AI 模型实例

提供两个全局实例，其他模块直接 import 使用：
  - chat_model   → 对话模型（通义千问 qwen3-max），用于理解和回答用户问题
  - embed_model  → 向量模型（text-embedding-v4），用于把文字转成向量存入数据库
"""
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from utils.config_handler import rag_conf, get_api_key


# 创建对话模型：负责理解用户问题、调用工具、生成回答
chat_model = ChatTongyi(
    model=rag_conf["chat_model_name"],
    dashscope_api_key=get_api_key(),
)

# 创建向量模型：负责把文字转成数字向量，用于知识库的存储和检索
embed_model = DashScopeEmbeddings(
    model=rag_conf["embedding_model_name"],
    dashscope_api_key=get_api_key(),
)
