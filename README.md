# 🤖 智扫通机器人智能客服

> **版本**: 3.0 (优化重构版) | 基于 **ReAct + RAG + MCP** 的智能问答系统

## 📖 项目简介

智扫通是一个扫地机器人智能客服系统，支持：
- 🔍 **RAG 知识库检索** - 从专业文档中检索答案
- 📚 **多格式支持** - PDF/Word/图片/TXT，自动OCR识别图文混合内容
- 🛠️ **多种工具调用** - 天气、用户报告、位置信息等
- 🔌 **MCP 协议扩展** - 连接远程工具服务，实现工具即服务
- 💬 **流式对话** - 基于 Streamlit 的 Web 界面

## ✨ 核心特性

### 1. ReAct Agent 架构
- 基于 LangChain 的 ReAct 模式
- 支持思维链推理和工具调用
- 中间件系统（监控、日志、提示词切换）

### 2. RAG 知识检索
- Chroma 向量数据库
- **支持 PDF/Word/图片/TXT** 多格式文档
- **图文混合处理** - 自动OCR识别图片和扫描版PDF
- 智能文本分片和向量化
- MD5去重机制

### 3. MCP 协议集成（新功能）
- **服务端**：将本地工具通过 MCP 协议暴露
- **客户端**：从远程 MCP 服务器动态获取工具
- **混合模式**：本地工具 + 远程工具同时使用
- **自动降级**：MCP 服务器不可用时自动使用本地工具

## 🚀 快速开始

**详细指南请查看：** [QUICKSTART.md](file:///E:/AI大模型RAG与智能体开发_Agent项目/QUICKSTART.md)

### 1. 安装依赖
```bash
# 激活虚拟环境
.venv\Scripts\activate

# 安装核心依赖
pip install langchain langchain-chroma langchain-community streamlit fastmcp
pip install pdf2image Pillow python-docx dashscope
```

**Windows用户：** 需要安装poppler（PDF转图片工具）
- 下载：http://blog.alivate.com.au/poppler-windows/
- 将bin/目录添加到系统PATH

### 2. 配置 API Key
```powershell
# Windows PowerShell
$env:OPEMAO_API_KEY="sk-your-api-key-here"
```

### 3. 准备知识库
将文档放入 `data/` 目录：
- PDF文件（产品手册、故障排除指南）
- Word文件（.docx格式）
- 图片文件（jpg/png，会自动OCR）
- TXT文件

### 4. 构建知识库
```bash
python rag/vector_store.py
```

### 5. 启动应用
```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`

### 4. 使用 MCP 扩展（可选）

**启动 MCP 服务器：**
```bash
# 终端 1：启动 MCP 服务器
python mcp\start_robot_mcp_server.py

# 终端 2：启动 Web 应用
streamlit run app.py
```

然后在 Web 界面侧边栏启用 MCP 功能。

## 📁 项目结构（优化版）

```
项目根目录/
├── app.py                      # Streamlit Web 应用（主入口）
├── agent/                      # Agent 核心逻辑
│   ├── react_agent.py          # ReAct Agent（支持MCP）
│   └── tools/                  # 工具和中间件
│       ├── agent_tools.py      # 本地工具定义
│       └── middleware.py       # 中间件（监控、日志、提示词切换）
├── rag/                        # RAG 知识检索
│   ├── vector_store.py         # 向量存储服务
│   ├── rag_service.py          # RAG总结服务
│   └── multimodal_ocr.py       # 多模态OCR服务
├── mcp/                        # MCP 协议实现
│   ├── mcp_client.py           # MCP客户端（单服务器）
│   ├── multi_server_client.py  # MCP客户端（多服务器）
│   ├── mcp_config.py           # MCP服务器配置
│   └── robot_mcp_server.py     # MCP服务器
├── utils/                      # 工具类模块（优化重构）
│   ├── file_utils.py           # 文件操作工具
│   ├── document_loader.py      # 文档加载器（PDF/Word/图片/TXT）
│   ├── loader_factory.py       # 加载器工厂（统一接口）
│   ├── config_handler.py       # 配置加载器
│   ├── prompt_loader.py        # 提示词加载器
│   ├── logger_handler.py       # 日志处理器
│   └── path_tool.py            # 路径工具
├── model/                      # 模型工厂
│   └── factory.py              # Chat/Embedding模型创建
├── config/                     # 配置文件
│   ├── rag.yml                 # RAG配置（模型名称等）
│   ├── chroma.yml              # Chroma配置（分片参数等）
│   ├── prompts.yml             # 提示词路径配置
│   └── agent.yml               # Agent配置
├── prompts/                    # 提示词模板
│   ├── main_prompt.txt         # 主提示词
│   ├── rag_summarize.txt       # RAG总结提示词
│   └── report_prompt.txt       # 报告生成提示词
└── data/                       # 知识库数据
    ├── *.pdf                   # PDF文档
    ├── *.docx                  # Word文档
    ├── *.txt                   # 文本文件
    └── *.jpg/png               # 图片文件
```

**优化亮点：**
- ✅ **模块化设计** - utils拆分为独立的功能模块
- ✅ **工厂模式** - 统一的文档加载接口
- ✅ **职责清晰** - 每个文件只负责一项功能
- ✅ **易于扩展** - 新增文件格式只需添加映射

## 🔧 核心功能详解

### 1. ReactAgent（支持 MCP）

```python
# 模式 1：只使用本地工具（原有模式）
agent = ReactAgent()

# 模式 2：混合模式（本地工具 + MCP 远程工具）
agent = ReactAgent(mcp_server_url="http://localhost:8001/sse")
```

**工作流程：**
1. 用户输入问题
2. Agent 分析需要使用哪些工具
3. 调用本地工具或 MCP 远程工具
4. 整合工具结果生成回答
5. 流式输出给用户

### 2. MCP 架构

**服务端（robot_mcp_server.py）：**
```python
@mcp_server.tool()
def search_robot_knowledge(query: str) -> str:
    """搜索扫地机器人知识库"""
    return rag.rag_summarize(query)
```

**客户端（mcp_client.py）：**
```python
# 对应老师演示的代码
mcp_client = MCPClient("http://localhost:8001/sse")
mcp_tools = await mcp_client.get_tools()  # 动态获取工具
agent = create_agent(llm, tools=mcp_tools)
```

**可用 MCP 工具：**
| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `search_robot_knowledge` | 搜索知识库 | `query: str` |
| `get_robot_weather` | 查询天气 | `city: str` |
| `get_user_report` | 用户报告 | `user_id, month` |
| `get_cleaning_recommendation` | 扫地建议 | `city: str` |
| `get_user_location` | 获取位置 | 无 |
| `get_user_id` | 获取用户 ID | 无 |

## 🎯 使用示例

### 示例 1：知识库查询
```
用户：扫地机器人如何清理主刷？
Agent：
1. 调用 search_robot_knowledge("清理主刷")
2. 从 RAG 检索相关知识
3. 生成详细回答
```

### 示例 2：天气判断
```
用户：今天适合扫地吗？
Agent：
1. 调用 get_robot_weather("深圳")
2. 分析天气数据
3. 给出建议："今天天气晴朗，非常适合扫地"
```

### 示例 3：用户报告
```
用户：帮我生成使用报告
Agent：
1. 调用 get_user_id() 获取用户 ID
2. 调用 get_current_month() 获取月份
3. 调用 get_user_report(user_id, month)
4. 分析数据生成报告
```

## 📚 技术栈

| 技术 | 用途 | 版本 |
|------|------|------|
| Python | 编程语言 | 3.14 |
| LangChain | AI 应用框架 | - |
| FastMCP | MCP 协议实现 | 3.3.1 |
| Chroma | 向量数据库 | - |
| Streamlit | Web 界面 | - |
| Qwen3-Max | 大语言模型 | 阿里通义千问 |

## 🔌 MCP 集成架构

```
┌─────────────────────────────────────────┐
│         Streamlit Web 应用              │
│  ┌──────────────────────────────────┐   │
│  │      ReactAgent                  │   │
│  │  ┌──────────┐  ┌──────────────┐  │   │
│  │  │ 本地工具  │  │ MCP 远程工具  │  │   │
│  │  │ - RAG    │  │ - 动态加载   │  │   │
│  │  │ - 天气   │  │ - HTTP/SSE   │  │   │
│  │  │ - 报告   │  │ - 自动降级   │  │   │
│  │  └──────────┘  └──────┬───────┘  │   │
│  └───────────────────────┼──────────┘   │
└──────────────────────────┼──────────────┘
                           │
                    HTTP/SSE
                           │
              ┌────────────┴────────────┐
              │   MCP 服务器 (8001)     │
              │  ┌──────────────────┐   │
              │  │ robot_mcp_server │   │
              │  │ - 7 个工具       │   │
              │  │ - SSE 传输       │   │
              │  └──────────────────┘   │
              └─────────────────────────┘
```

## 🎓 学习资源

- [MCP 协议官方文档](https://modelcontextprotocol.io/)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [LangChain Agents](https://python.langchain.com/docs/modules/agents/)

## 📝 更新日志

### v2.0 (2026-05-16)
- ✅ 集成 MCP 协议支持
- ✅ 实现 MCP 客户端和服务器
- ✅ 支持混合工具模式
- ✅ 重构 ReactAgent 支持 MCP
- ✅ 更新 Web 界面添加 MCP 配置
- ✅ 重写项目文档

### v1.0 (2025-01)
- ✅ 基础 ReAct Agent 实现
- ✅ RAG 知识检索
- ✅ Streamlit Web 界面
- ✅ 多工具支持

## 📄 许可证

本项目仅供学习和研究使用。

## 🙏 致谢

感谢以下开源项目：
- LangChain
- FastMCP
- Streamlit
- Chroma

---

**版本**: 2.0 | **最后更新**: 2026-05-16
