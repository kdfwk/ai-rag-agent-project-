# 联网搜索与 MCP 功能详细说明文档

## 目录

1. [整体架构图](#1-整体架构图)
2. [联网搜索功能详解](#2-联网搜索功能详解)
3. [MCP 协议详解](#3-mcp-协议详解)
4. [MCP 服务端实现](#4-mcp-服务端实现)
5. [MCP 客户端实现](#5-mcp-客户端实现)
6. [工具格式转换](#6-工具格式转换)
7. [ReactAgent 如何组装和使用工具](#7-reactagent-如何组装和使用工具)
8. [中间件系统](#8-中间件系统)
9. [Web 界面如何驱动整个系统](#9-web-界面如何驱动整个系统)
10. [完整调用链路（每一步的函数调用栈）](#10-完整调用链路每一步的函数调用栈)
11. [为什么有了本地工具还要 MCP](#11-为什么有了本地工具还要-mcp)
12. [新增一个工具的操作步骤](#12-新增一个工具的操作步骤)
13. [常见问题排查](#13-常见问题排查)

---

## 1. 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Web 界面 (app.py)                              │
│  Streamlit 页面 → 用户输入 → 调用 ReactAgent → 流式显示回答                  │
│  侧边栏: 选择工具来源模式（仅本地 / 单MCP服务器 / 多MCP服务器）                │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ 初始化时
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ReactAgent (react_agent.py)                         │
│                                                                             │
│  ┌──────────────────────────────┐   ┌──────────────────────────────────┐   │
│  │       本地工具列表             │   │         远程工具列表              │   │
│  │  (agent_tools.py)             │   │  (通过 MCP 协议连接获取)          │   │
│  │                               │   │                                  │   │
│  │  - rag_summarize              │   │  ┌────────────────────────┐     │   │
│  │  - get_weather                │   │  │ MCPClient (单服)       │     │   │
│  │  - get_user_location          │   │  │   ↓ connect()          │     │   │
│  │  - get_user_id                │   │  │   ↓ get_tools()        │     │   │
│  │  - get_current_month          │   │  └────────────────────────┘     │   │
│  │  - fetch_external_data        │   │                                  │   │
│  │  - fill_context_for_report    │   │  ┌────────────────────────┐     │   │
│  │  - web_search                 │   │  │ MultiServerMCPClient   │     │   │
│  │                               │   │  │   ↓ connect_all()      │     │   │
│  └──────────────┬───────────────┘   │  │   ↓ get_tools()        │     │   │
│                 │                   │  └────────────────────────┘     │   │
│                 └──────┬──────────┘   └──────────────────────────────────┘   │
│                        ▼                                                     │
│            ┌───────────────────────┐                                         │
│            │   all_tools =         │                                         │
│            │   local_tools +       │                                         │
│            │   remote_tools        │                                         │
│            └───────────┬───────────┘                                         │
│                        ▼                                                     │
│            ┌───────────────────────────────────────────┐                     │
│            │  LangChain create_agent(                  │                     │
│            │    model=chat_model,                      │                     │
│            │    tools=all_tools,                       │                     │
│            │    middleware=[monitor_tool,              │                     │
│            │                  log_before_model,        │                     │
│            │                  report_prompt_switch]    │                     │
│            │  )                                        │                     │
│            └───────────────────────────────────────────┘                     │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ 工具被调用时
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       工具执行层（分两条路）                                   │
│                                                                             │
│  本地工具路径:                        MCP 远程工具路径:                        │
│  ┌──────────────────────┐            ┌──────────────────────────────────┐   │
│  │ 直接在进程内执行      │            │ 通过 HTTP/SSE 发送请求            │   │
│  │ 如 web_search()      │            │ 到 MCP Server                     │   │
│  │ 调用 DDGS().text()   │            │                                  │   │
│  │ 返回结果字符串        │            │  ┌────────────────────────────┐  │   │
│  └──────────────────────┘            │  │ MCP Server (8001端口)      │  │   │
│                                      │  │ @mcp_server.tool() 注册的   │  │   │
│                                      │  │ 函数被执行                  │  │   │
│                                      │  │ 返回结果 → SSE 响应         │  │   │
│                                      │  └────────────────────────────┘  │   │
│                                      └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 联网搜索功能详解

### 2.1 依赖库

```
duckduckgo-search  (Python 包，import 名为 ddgs)
```

这个库封装了 DuckDuckGo 搜索引擎的接口，允许你在 Python 代码中直接发起网络搜索请求，而不需要打开浏览器。

安装方式（requirements.txt 中）：
```
duckduckgo-search
```

### 2.2 本地工具中的 web_search 实现

文件位置：[`agent/tools/agent_tools.py`](agent/tools/agent_tools.py)

#### 2.2.1 导入部分（第 17 行）

```python
from ddgs import DDGS
```

这行代码从 `ddgs` 模块导入 `DDGS` 类。`DDGS` 是 DuckDuckGo Search 的缩写，它是这个库的核心类，用于发起搜索请求。

#### 2.2.2 工具定义（第 134-150 行）

```python
@tool(description="通过 DuckDuckGo 在互联网上搜索实时信息，当本地知识库无法回答时使用此工具")
def web_search(query: str) -> str:
    """使用互联网搜索引擎查找最新信息并返回结果摘要"""
```

**逐行解释：**

- `@tool(...)` —— 这是 LangChain 提供的装饰器。被这个装饰器装饰的函数会被注册为一个"工具"，Agent 的大模型可以看到函数的 `description` 和参数签名，并在需要时决定是否调用它。
- `description` 参数 —— 这段文字会被发送给大模型，告诉大模型这个工具是干什么的、什么时候该用它。
- `query: str` —— 函数接收一个字符串参数，即用户想要搜索的关键词。
- `-> str` —— 函数返回一个字符串，即搜索结果的摘要文本。

#### 2.2.3 搜索逻辑（第 137-150 行）

**第一步：创建搜索客户端**
```python
ddgs = DDGS()
```
这行代码创建一个 `DDGS` 对象。这个对象就像一个"搜索引擎遥控器"，你可以用它发起各种搜索。

**第二步：执行搜索**
```python
results = list(ddgs.text(query, max_results=5))
```
- `ddgs.text(query, max_results=5)` —— 调用 `DDGS` 对象的 `text` 方法，参数 `query` 是搜索关键词，`max_results=5` 表示最多返回 5 条结果。
- 这个方法会**实际向 DuckDuckGo 的服务器发送 HTTP 请求**，DuckDuckGo 返回搜索结果。
- 返回值是一个**迭代器**（不是一次性返回所有数据，而是逐条返回），所以用 `list()` 把它转换为列表。
- 每条结果是一个字典，包含 `title`（标题）、`body`（摘要）、`href`（链接）等字段。

**第三步：处理空结果**
```python
if not results:
    return f"未找到关于「{query}」的结果"
```
如果搜索结果为空（列表为空），直接返回提示信息。

**第四步：提取和格式化结果**
```python
summaries = []
for r in results[:5]:
    title = r.get("title", "")
    body = r.get("body", "")
    href = r.get("href", "")
    summaries.append(f"标题：{title}\n摘要：{body}\n链接：{href}")
```
- 遍历结果列表（最多 5 条，`[:5]` 是切片操作确保不超过 5 条）。
- `r.get("title", "")` —— 从字典中取出标题，如果没有这个键就返回空字符串。
- 每条结果格式化为三行文本：标题、摘要、链接。
- 所有格式化后的结果存入 `summaries` 列表。

**第五步：拼接返回**
```python
return "\n---\n".join(summaries)
```
把所有结果用分隔线 `---` 连接成一个长字符串，返回给 Agent。

**第六步：异常处理**
```python
except Exception as e:
    return f"搜索失败: {e}"
```
如果搜索过程中出现任何错误（如网络问题），捕获异常并返回错误信息。

#### 2.2.4 一个实际的返回结果示例

当调用 `web_search("扫地机器人品牌排行")` 时，可能返回：

```
标题：2024年扫地机器人品牌排行榜
摘要：本文对比了市面上主流的扫地机器人品牌，包括科沃斯、石头、iRobot等...
链接：https://example.com/robot-vacuum-ranking
---
标题：十大最佳扫地机器人推荐
摘要：根据用户评价和专业评测，我们列出了2024年最值得购买的扫地机器人...
链接：https://example.com/best-robot-vacuums
---
...（最多5条）
```

### 2.3 MCP 服务中的 web_search 实现

文件位置：[`zs_mcp/robot_mcp_server.py`](zs_mcp/robot_mcp_server.py)

#### 2.3.1 代码实现（第 201-217 行）

```python
@mcp_server.tool()
def web_search(query: str) -> str:
    """通过 DuckDuckGo 在互联网上搜索实时信息，当本地知识库无法回答时使用此工具"""
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=5))
        if not results:
            return f"未找到关于「{query}」的结果"
        summaries = []
        for r in results[:5]:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            summaries.append(f"标题：{title}\n摘要：{body}\n链接：{href}")
        return "\n---\n".join(summaries)
    except Exception as e:
        return f"搜索失败: {e}"
```

**与本地工具的区别：**

| 对比项 | 本地工具 | MCP 工具 |
|-------|---------|---------|
| 装饰器 | `@tool(description="...")` | `@mcp_server.tool()` |
| 框架 | LangChain | FastMCP |
| 调用方式 | 直接函数调用 | 通过 HTTP/SSE 网络请求 |
| 搜索逻辑 | 完全相同 | 完全相同 |

---

## 3. MCP 协议详解

### 3.1 什么是 MCP

MCP（Model Context Protocol，模型上下文协议）是一个**标准化的通信协议**，由 Anthropic 提出。它的目的是让 AI 模型能够以统一的方式调用外部工具和服务。

### 3.2 核心概念

```
MCP Server（服务端）          MCP Client（客户端）
    │                              │
    │  暴露工具                     │  发现工具
    │  执行工具                     │  调用工具
    │                              │
    └────────── 网络连接 ──────────┘
       （SSE 或 stdio 传输）
```

- **MCP Server**：一个运行中的程序，它声明自己能提供哪些"工具"（如搜索、天气查询等），并在收到调用请求时执行这些工具、返回结果。
- **MCP Client**：另一个程序，它连接到 MCP Server，询问"你有哪些工具"，然后把这些工具转给 AI 模型使用。

### 3.3 传输方式

MCP 支持两种传输方式：

| 方式 | 说明 | 适用场景 |
|------|------|---------|
| **stdio** | 通过标准输入/输出通信 | 本地命令行工具、IDE 插件 |
| **SSE** (Server-Sent Events) | 通过 HTTP + SSE 通信 | Web 应用、远程服务 |

本项目使用 **SSE** 方式，MCP Server 运行在 `http://localhost:8001/sse`。

### 3.4 MCP 通信流程（SSE 模式）

```
步骤 1: 客户端连接
   Client ──HTTP GET /sse──→ Server
   Client ←─SSE stream───── Server

步骤 2: 客户端询问工具列表
   Client ──POST /sse (请求: list_tools)──→ Server
   Client ←─SSE 响应 (返回工具列表)────── Server

步骤 3: 客户端调用某个工具
   Client ──POST /sse (请求: call_tool "web_search", 参数: query="xxx")──→ Server
   Client ←─SSE 响应 (返回搜索结果)───────────────────────────────────── Server
```

---

## 4. MCP 服务端实现

### 4.1 创建 MCP Server 实例

文件：[`zs_mcp/robot_mcp_server.py`](zs_mcp/robot_mcp_server.py)，第 36 行

```python
from fastmcp import FastMCP

mcp_server = FastMCP(name="智扫通机器人MCP服务")
```

这行代码创建一个 MCP 服务实例，名字为"智扫通机器人MCP服务"。这个 `mcp_server` 对象就是服务的核心，后续的 `@mcp_server.tool()` 装饰器会把函数注册到这个服务上。

### 4.2 注册工具（以 search_robot_knowledge 为例）

第 109-115 行：

```python
@mcp_server.tool()
def search_robot_knowledge(query: str) -> str:
    """搜索扫地机器人知识库（RAG 检索 + 总结）"""
    try:
        return rag.rag_summarize(query)
    except Exception as e:
        return f"搜索失败: {e}"
```

**`@mcp_server.tool()` 装饰器做了什么：**

1. 把 `search_robot_knowledge` 这个函数注册到 `mcp_server` 上
2. 提取函数的名称、参数签名（`query: str`）、文档字符串（`"""..."""`）
3. 当客户端调用 `list_tools` 时，这个函数会出现在返回的工具列表中
4. 当客户端调用 `call_tool("search_robot_knowledge", {"query": "..."})` 时，这个函数会被实际执行

### 4.3 服务端注册的所有工具

在 [`robot_mcp_server.py`](zs_mcp/robot_mcp_server.py) 中，共有 8 个工具被注册：

| 工具名 | 函数 | 作用 | 行号 |
|-------|------|------|------|
| `search_robot_knowledge` | 搜索知识库 | RAG 检索 + 总结 | 110-115 |
| `get_robot_weather` | 查天气 | 返回指定城市的天气信息 | 119-130 |
| `get_user_report` | 用户报告 | 返回指定用户某月的使用记录 | 134-149 |
| `get_user_location` | 用户位置 | 随机返回一个城市（演示用） | 153-155 |
| `get_user_id` | 用户 ID | 随机返回一个用户 ID（演示用） | 159-161 |
| `get_current_month` | 当前月份 | 随机返回一个月份（演示用） | 165-167 |
| `get_cleaning_recommendation` | 扫地建议 | 根据天气给出扫地建议 | 171-194 |
| `web_search` | 联网搜索 | DuckDuckGo 搜索 | 202-217 |

### 4.4 启动 MCP 服务

文件：[`zs_mcp/start_robot_mcp_server.py`](zs_mcp/start_robot_mcp_server.py)

```python
from robot_mcp_server import mcp_server

mcp_server.run(
    transport="sse",     # 传输方式：SSE（HTTP Server-Sent Events）
    host="0.0.0.0",      # 监听所有网络接口
    port=8001,           # 端口号
    path="/sse",         # URL 路径
    log_level="info",    # 日志级别
)
```

**启动后发生了什么：**

1. FastMCP 框架启动一个 HTTP 服务器，监听 `0.0.0.0:8001`
2. 所有通过 `@mcp_server.tool()` 注册的函数都可以通过 `/sse` 路径访问
3. 客户端可以通过 `http://localhost:8001/sse` 连接并调用这些工具

---

## 5. MCP 客户端实现

### 5.1 单服务器客户端

文件：[`zs_mcp/mcp_client.py`](zs_mcp/mcp_client.py)

#### 5.1.1 类定义和初始化

```python
class MCPClient:
    def __init__(self, server_url: str = "http://localhost:8001/sse"):
        self.server_url = server_url       # MCP 服务的地址
        self._client: Optional[Client] = None  # FastMCP Client 对象（连接后才有值）
        self.tools: List[Tool] = []        # 转换后的 LangChain 工具列表
```

#### 5.1.2 connect() 方法（第 31-42 行）

```python
async def connect(self) -> Optional[Client]:
    if not FASTMCP_AVAILABLE:
        logger.error("[MCP] fastmcp 未安装，无法连接 MCP 服务器")
        return None

    if self._client is None:
        logger.info(f"[MCP] 正在连接 {self.server_url}")
        self._client = Client(transport=self.server_url)  # 创建客户端对象
        await self._client.__aenter__()                    # 建立连接（异步上下文管理器）
        logger.info("[MCP] 连接成功")
    return self._client
```

**逐行解释：**

- `FASTMCP_AVAILABLE` —— 检查 `fastmcp` 库是否已安装，没有安装则无法使用 MCP。
- `Client(transport=self.server_url)` —— 创建一个 FastMCP 客户端，传入 SSE 地址。
- `await self._client.__aenter__()` —— 建立 HTTP 连接。这里用的是 Python 的异步上下文管理器协议（`__aenter__`），相当于 `async with Client(...) as client:` 中的进入步骤。

#### 5.1.3 get_tools() 方法（第 50-63 行）

```python
async def get_tools(self) -> List[Tool]:
    if not FASTMCP_AVAILABLE:
        return []

    client = await self.connect()  # ① 先确保已连接
    if client is None:
        return []

    tools_info = await client.list_tools()  # ② 向服务端请求工具列表
    logger.info(f"[MCP] 获取到 {len(tools_info)} 个远程工具")

    # ③ 把 MCP 工具格式转换为 LangChain Tool 格式
    self.tools = mcp_tools_to_langchain(client, tools_info)
    return self.tools
```

**关键步骤 `client.list_tools()`：**
- 这是一个异步方法，向 MCP Server 发送请求："你有哪些工具？"
- 服务端返回工具信息列表，每个工具包含：名称、描述、参数定义。

#### 5.1.4 disconnect() 方法（第 44-48 行）

```python
async def disconnect(self):
    if self._client is not None:
        await self._client.__aexit__(None, None, None)  # 关闭连接
        self._client = None
```

### 5.2 多服务器客户端

文件：[`zs_mcp/multi_server_client.py`](zs_mcp/multi_server_client.py)

#### 5.2.1 为什么需要多服务器客户端

单服务器客户端只连接一个 MCP 服务。但在实际项目中，可能有多个独立的 MCP 服务：
- 服务 A：扫地机器人相关工具
- 服务 B：智能家居控制工具
- 服务 C：其他工具

多服务器客户端可以**同时连接多个服务，合并所有工具**。

#### 5.2.2 connect_all() 方法（第 38-52 行）

```python
async def connect_all(self):
    if not FASTMCP_AVAILABLE:
        return

    logger.info("[MCP] 开始连接多个服务器...")
    for server_key, config in self.server_configs.items():  # 遍历所有配置
        try:
            await self._connect_one(server_key, config)      # 逐个连接
        except Exception as e:
            name = config.get("name", server_key)
            logger.warning(f"[MCP] 连接 {name} 失败: {e}")

    logger.info(f"[MCP] 已连接 {len(self.clients)} 个服务，共 {len(self.all_tools)} 个工具")
```

#### 5.2.3 _connect_one() 方法（第 54-79 行）

```python
async def _connect_one(self, server_key: str, config: Dict[str, Any]):
    url = config["url"]                       # 服务地址
    name = config.get("name", server_key)     # 服务名称
    headers = config.get("headers", {})       # 可选的 HTTP 请求头

    # 创建客户端（尝试带 headers，如果不支持则不带）
    try:
        client = Client(transport=url, headers=headers)
    except TypeError:
        client = Client(transport=url)

    await client.__aenter__()                 # 建立连接
    tools_info = await client.list_tools()    # 获取工具列表

    # 转换格式 + 加前缀避免命名冲突
    server_tools = mcp_tools_to_langchain(
        client, tools_info,
        name_prefix=f"{server_key}_",         # 工具名加前缀，如 local_python_web_search
        desc_prefix=f"[{name}] ",             # 描述加前缀
    )

    self.clients[server_key] = client          # 保存客户端
    self.tools_by_server[server_key] = server_tools  # 按服务分类保存工具
    self.all_tools.extend(server_tools)        # 合并到总工具列表
```

**为什么要加前缀？** 如果两个 MCP 服务都有一个叫 `web_search` 的工具，不加前缀就会冲突。加了前缀后：
- 服务 A 的 `web_search` → `local_python_web_search`
- 服务 B 的 `web_search` → `other_service_web_search`

### 5.3 MCP 配置管理

文件：[`zs_mcp/mcp_config.py`](zs_mcp/mcp_config.py)

```python
LOCAL_PYTHON_MCP: Dict[str, Any] = {
    "name": "扫地机器人本地服务",          # 显示名称
    "url": "http://localhost:8001/sse",    # SSE 地址
    "transport": "sse",                    # 传输方式
    "description": "知识库检索、天气、用户报告等",  # 描述
    "enabled": True,                       # 是否启用
}

ALL_MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    "local_python": LOCAL_PYTHON_MCP,      # key 是服务的唯一标识
}

def get_enabled_servers() -> Dict[str, Dict[str, Any]]:
    """返回 enabled=True 的配置"""
    return {
        name: cfg
        for name, cfg in ALL_MCP_SERVERS.items()
        if cfg.get("enabled", False)
    }
```

**如何新增一个 MCP 服务：**

```python
NEW_SERVICE: Dict[str, Any] = {
    "name": "我的新服务",
    "url": "http://localhost:9000/sse",
    "transport": "sse",
    "description": "描述这个服务提供什么",
    "enabled": True,   # 设为 True 启用
}

ALL_MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    "local_python": LOCAL_PYTHON_MCP,
    "my_new_service": NEW_SERVICE,  # 新增这一行
}
```

---

## 6. 工具格式转换

文件：[`zs_mcp/tool_adapter.py`](zs_mcp/tool_adapter.py)

### 6.1 为什么需要转换

MCP 服务端返回的工具格式和 LangChain Agent 需要的工具格式是不同的。`mcp_tools_to_langchain` 函数负责把 MCP 工具包装成 LangChain 工具。

### 6.2 转换逻辑（第 14-44 行）

```python
def mcp_tools_to_langchain(
    client: Client,          # FastMCP 客户端
    tools_info: List[Any],   # list_tools() 返回的工具信息
    name_prefix: str = "",   # 工具名前缀（多服模式用）
    desc_prefix: str = "",   # 工具描述前缀
) -> List[Tool]:
    langchain_tools = []

    for tool_info in tools_info:
        tool_name = tool_info.name           # 工具名，如 "web_search"
        exposed_name = f"{name_prefix}{tool_name}"  # 加前缀后，如 "local_python_web_search"
        base_desc = tool_info.description or f"远程工具: {tool_name}"
        description = f"{desc_prefix}{base_desc}"   # 加描述前缀

        # 关键：定义一个异步函数，调用远程 MCP 服务
        async def call_remote(*, _client=client, _name=tool_name, **kwargs):
            try:
                return await _client.call_tool(_name, kwargs)  # 实际调用！
            except Exception as e:
                return f"调用 {_name} 失败: {e}"

        # 创建 LangChain Tool 对象
        langchain_tools.append(
            Tool(
                name=exposed_name,      # 工具名称
                description=description,  # 工具描述（给 LLM 看的）
                func=None,              # 同步函数（不用，因为我们用异步）
                coroutine=call_remote,  # 异步函数（Agent 调用时会用这个）
            )
        )

    return langchain_tools
```

### 6.3 `call_remote` 函数详解

这是整个转换的核心。这个函数做了什么：

```python
async def call_remote(*, _client=client, _name=tool_name, **kwargs):
    return await _client.call_tool(_name, kwargs)
```

- `_client=client` —— 把当前的 FastMCP 客户端"绑定"到这个函数上（闭包）。每个工具都有自己的 `_client`。
- `_name=tool_name` —— 把工具名也绑定到这个函数上。
- `**kwargs` —— 调用时传入的参数，如 `{"query": "扫地机器人"}`。
- `_client.call_tool(_name, kwargs)` —— 实际执行！这行代码通过 HTTP 向 MCP Server 发送请求："请执行 `web_search` 工具，参数是 `kwargs`"。

**当 Agent 调用这个 LangChain Tool 时，实际执行的链路是：**

```
Agent 调用 web_search(query="扫地机器人")
    ↓
LangChain 框架执行 Tool.coroutine(**kwargs)
    ↓
执行 call_remote(_client=客户端, _name="web_search", query="扫地机器人")
    ↓
await _client.call_tool("web_search", {"query": "扫地机器人"})
    ↓
HTTP POST 到 http://localhost:8001/sse
    ↓
MCP Server 接收请求，执行 web_search 函数
    ↓
DDGS().text("扫地机器人") → DuckDuckGo 返回结果
    ↓
结果通过 SSE 返回给客户端
    ↓
call_remote 返回结果给 Agent
```

---

## 7. ReactAgent 如何组装和使用工具

文件：[`agent/react_agent.py`](agent/react_agent.py)

### 7.1 初始化过程（`__init__` 方法，第 34-67 行）

```python
def __init__(self, mcp_server_url=None, mcp_server_configs=None):
    # 第一步：定义本地工具列表
    self.local_tools = [
        rag_summarize,          # 从 agent_tools.py import 的函数
        get_weather,
        get_user_location,
        get_user_id,
        get_current_month,
        fetch_external_data,
        fill_context_for_report,
        web_search,
    ]
    self.all_tools = list(self.local_tools)  # 初始只包含本地工具

    # 第二步：按需加载远程工具
    if mcp_server_configs:
        # 多服务器模式
        self._append_mcp_tools(self._load_multi_mcp(mcp_server_configs))
    elif mcp_server_url:
        # 单服务器模式
        self._append_mcp_tools(self._load_single_mcp(mcp_server_url))

    # 第三步：创建 Agent
    self.agent = create_agent(
        model=chat_model,              # 大语言模型
        system_prompt=load_system_prompts(),  # 系统提示词
        tools=self.all_tools,          # 工具列表（本地 + 远程）
        middleware=[monitor_tool, log_before_model, report_prompt_switch],
    )
```

### 7.2 _load_single_mcp 方法（第 79-94 行）

```python
def _load_single_mcp(self, server_url: str) -> List:
    from zs_mcp.mcp_client import MCPClient

    async def _run():
        client = MCPClient(server_url)  # 创建 MCP 客户端
        await client.connect()          # 建立连接
        tools = await client.get_tools()  # 获取远程工具列表
        self._mcp_clients.append(client)  # 保存客户端引用（保持连接）
        return tools

    try:
        return asyncio.run(_run())      # 运行异步代码
    except Exception as e:
        logger.debug(f"[Agent] 单服 MCP 连接失败: {e}")
        return []
```

**`asyncio.run(_run())` 做了什么：**
- Python 的 `asyncio.run()` 会创建一个新的事件循环，运行 `_run()` 这个异步函数，等待完成后返回结果并关闭事件循环。
- 这使得即使 `ReactAgent` 的 `__init__` 是同步方法，也能执行异步的 MCP 连接操作。

### 7.3 _load_multi_mcp 方法（第 96-111 行）

```python
def _load_multi_mcp(self, configs: Dict[str, Dict[str, Any]]) -> List:
    from zs_mcp.multi_server_client import MultiServerMCPClient

    async def _run():
        client = MultiServerMCPClient(configs)  # 创建多服客户端
        await client.connect_all()              # 连接所有配置的服务
        tools = await client.get_tools()         # 获取合并后的工具列表
        self._mcp_clients.append(client)
        return tools

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.debug(f"[Agent] 多服 MCP 连接失败: {e}")
        return []
```

### 7.4 _append_mcp_tools 方法（第 71-77 行）

```python
def _append_mcp_tools(self, remote_tools: List):
    if remote_tools:
        self.all_tools = self.local_tools + remote_tools
        logger.info(f"[Agent] 本地 {len(self.local_tools)} + 远程 {len(remote_tools)} 个工具")
    else:
        logger.debug("[Agent] 未加载到远程工具，仅使用本地工具")
```

这个方法把远程工具追加到本地工具列表后面，合并成 `all_tools`。

### 7.5 LangChain create_agent 内部做了什么

```python
self.agent = create_agent(
    model=chat_model,
    system_prompt=load_system_prompts(),
    tools=self.all_tools,
    middleware=[monitor_tool, log_before_model, report_prompt_switch],
)
```

`create_agent` 是 LangChain 提供的函数，它内部做了以下事情：

1. **分析工具列表**：遍历 `self.all_tools` 中的每个工具，提取工具名、参数定义、描述信息。
2. **构建工具描述**：把所有工具的信息整合成一段文本，发送给大模型。
3. **创建 ReAct 循环**：Agent 的执行逻辑是：
   - 接收用户消息
   - 大模型分析问题 → 决定是否需要调用工具
   - 如果需要，调用对应工具，获取结果
   - 大模型根据工具结果继续分析或生成最终回答
4. **注册中间件**：在工具调用前后、模型执行前插入自定义逻辑。

### 7.6 流式响应（`_stream_response` 方法，第 135-151 行）

```python
def _stream_response(self, messages: List):
    input_dict = {"messages": messages}
    for chunk in self.agent.stream(
        input_dict, stream_mode="values", context={"report": False}
    ):
        latest = chunk["messages"][-1]
        if latest.content:
            yield latest.content.strip() + "\n"
```

- `self.agent.stream(...)` —— LangChain Agent 的流式输出方法。它会逐步产出内容，而不是一次性返回全部。
- `stream_mode="values"` —— 每次产出的是 Agent 状态的完整值。
- `context={"report": False}` —— 初始上下文，`report` 标记用于中间件判断是否需要切换提示词。
- `chunk["messages"][-1]` —— 取最新的消息对象。
- `yield` —— 逐块返回内容，实现流式输出（用户能一个字一个字地看到回答）。

---

## 8. 中间件系统

文件：[`agent/tools/middleware.py`](agent/tools/middleware.py)

中间件是插入到 Agent 执行过程中的"钩子"（hooks），在特定时机运行自定义代码。

### 8.1 monitor_tool —— 工具调用监控

```python
@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    tool_name = request.tool_call['name']    # 获取工具名，如 "web_search"
    tool_args = request.tool_call['args']    # 获取参数，如 {"query": "xxx"}

    logger.info(f"[tool monitor] 执行工具: {tool_name}")
    logger.info(f"[tool monitor] 传入参数: {tool_args}")

    result = handler(request)     # 真正执行工具

    logger.info(f"[tool monitor] 工具 {tool_name} 调用成功")

    # 特殊处理：如果是 fill_context_for_report 工具，在上下文中打报告标记
    if tool_name == "fill_context_for_report":
        request.runtime.context["report"] = True

    return result
```

**执行时机：** 每个工具被调用时，`monitor_tool` 先执行（前置逻辑），然后 `handler(request)` 执行工具本身，最后 `monitor_tool` 再执行后置逻辑。

**执行流程：**
```
Agent 决定调用 web_search(query="xxx")
    ↓
① monitor_tool 被触发
    logger.info("[tool monitor] 执行工具: web_search")
    logger.info("[tool monitor] 传入参数: {'query': 'xxx'}")
    ↓
② handler(request) 被执行
    实际调用 web_search("xxx") → DDGS().text("xxx")
    ↓
③ monitor_tool 后置逻辑
    logger.info("[tool monitor] 工具 web_search 调用成功")
    ↓
返回结果给 Agent
```

### 8.2 log_before_model —— 模型执行前日志

```python
@before_model
def log_before_model(state: AgentState, runtime: Runtime):
    messages = state['messages']
    logger.info(f"[log_before_model] 即将调用模型，带有 {len(messages)} 条消息")
    logger.debug(f"[log_before_model] 最后一条: {type(messages[-1]).__name__} | {messages[-1].content.strip()}")
    return None     # 返回 None 表示不修改状态，继续执行
```

**执行时机：** 每次大模型被调用之前。

**做了什么：**
- 记录当前有多少条消息在对话历史中。
- 记录最后一条消息的类型和内容（方便调试）。
- 返回 `None` 表示"我不修改任何东西，继续正常执行"。

### 8.3 report_prompt_switch —— 动态提示词切换

```python
@dynamic_prompt
def report_prompt_switch(request: ModelRequest) -> str:
    is_report = request.runtime.context.get("report", False)

    if is_report:
        return load_report_prompts()      # 报告生成场景的专用提示词
    return load_system_prompts()          # 日常对话的默认提示词
```

**执行时机：** 每次大模型被调用之前（在 `log_before_model` 之后）。

**做了什么：**
- 检查上下文中的 `report` 标记（由 `monitor_tool` 在 `fill_context_for_report` 被调用时设置）。
- 如果 `report=True` → 使用报告提示词（告诉大模型"你是一个报告生成助手"）。
- 否则 → 使用默认提示词（告诉大模型"你是一个扫地机器人客服"）。

---

## 9. Web 界面如何驱动整个系统

文件：[`app.py`](app.py)

### 9.1 启动流程

用户在终端执行：
```bash
streamlit run app.py
```

Streamlit 启动一个 Web 服务器，浏览器打开页面。

### 9.2 用户选择工具来源模式（第 39-63 行）

```python
mcp_mode = st.radio(
    "工具来源",
    ["仅本地工具", "单服务器模式", "多服务器模式"],
    index=0,   # 默认选中"仅本地工具"
)
```

Streamlit 的单选按钮组件，用户可以选择三种模式之一。

### 9.3 Agent 初始化逻辑（第 74-92 行）

```python
need_reinit = (
    "agent" not in st.session_state          # Agent 不存在，需要初始化
    or st.session_state.get("mcp_mode") != mcp_mode   # 模式变了
    or st.session_state.get("mcp_url") != mcp_url     # URL 变了
)

if need_reinit:
    with st.spinner("正在初始化…"):
        if mcp_mode == "多服务器模式":
            configs = get_enabled_servers()
            st.session_state["agent"] = (
                ReactAgent(mcp_server_configs=configs) if configs else ReactAgent()
            )
        elif mcp_mode == "单服务器模式" and mcp_url:
            st.session_state["agent"] = ReactAgent(mcp_server_url=mcp_url)
        else:
            st.session_state["agent"] = ReactAgent()  # 仅本地工具
```

**三种模式对应的 ReactAgent 初始化方式：**

| 模式 | ReactAgent 初始化 | 说明 |
|------|-------------------|------|
| 仅本地工具 | `ReactAgent()` | 不传任何参数，只使用本地工具 |
| 单服务器模式 | `ReactAgent(mcp_server_url="http://...")` | 传入单个 MCP 地址 |
| 多服务器模式 | `ReactAgent(mcp_server_configs={...})` | 传入多个服务配置 |

### 9.4 对话流程（第 106-131 行）

```python
prompt = st.chat_input("请输入您的问题...")

if prompt:
    # 1. 保存用户消息到历史
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 2. 显示用户消息
    with st.chat_message("user"):
        st.write(prompt)

    # 3. 调用 Agent 并流式获取回答
    response_container = st.chat_message("assistant")
    message_placeholder = response_container.empty()

    full_response = ""
    with st.spinner("思考中…"):
        res_stream = st.session_state["agent"].execute_stream_with_history(
            st.session_state["messages"][:-1], prompt
        )

        # 4. 逐块显示回答
        for chunk in res_stream:
            full_response += chunk
            message_placeholder.markdown(full_response + "▌")

    # 5. 保存完整回答
    message_placeholder.markdown(full_response)
    st.session_state["messages"].append({"role": "assistant", "content": full_response})
```

**逐行解释：**

- `st.chat_input(...)` —— 显示一个聊天输入框，用户输入后返回文本。
- `st.session_state["messages"]` —— Streamlit 的会话状态，用于保存对话历史。每次页面刷新时数据还在。
- `execute_stream_with_history(history, prompt)` —— 调用 ReactAgent，传入历史消息和当前问题。
- `for chunk in res_stream:` —— 逐块接收回答，实现打字机效果。
- `message_placeholder.markdown(full_response + "▌")` —— 用 Markdown 格式显示当前已累积的内容，加上光标指示器 `▌`。

---

## 10. 完整调用链路（每一步的函数调用栈）

### 10.1 场景：用户在 Web 界面输入"帮我搜索最新的扫地机器人推荐"

#### 阶段一：用户输入到 Agent 接收

```
① 用户在浏览器输入框中输入"帮我搜索最新的扫地机器人推荐"，按回车
   ↓
② app.py:106 → prompt = st.chat_input(...) 接收到文本
   ↓
③ app.py:108 → st.session_state["messages"].append({"role": "user", "content": prompt})
   用户消息保存到会话历史
   ↓
④ app.py:120 → st.session_state["agent"].execute_stream_with_history(history, prompt)
   调用 ReactAgent 的流式对话方法
```

#### 阶段二：ReactAgent 处理

```
⑤ react_agent.py:165 → execute_stream_with_history(history, current_query)
   接收历史消息和当前问题
   ↓
⑥ react_agent.py:173 → messages = self._build_messages(history, current_query)
   把字典格式的历史消息转换为 LangChain Message 对象列表
   ↓
⑦ react_agent.py:126-133 → _build_messages() 内部循环：
   for msg in history:
       if msg["role"] == "user":
           messages.append(HumanMessage(content=msg["content"]))
       elif msg["role"] == "assistant":
           messages.append(AIMessage(content=msg["content"]))
   messages.append(HumanMessage(content=current_query))
   转换完成后，messages 列表形如：
   [HumanMessage("之前的对话"), AIMessage("之前的回答"), HumanMessage("帮我搜索最新的扫地机器人推荐")]
   ↓
⑧ react_agent.py:163 → return self._stream_response(messages)
   调用流式响应方法
   ↓
⑨ react_agent.py:145 → input_dict = {"messages": messages}
   把消息包装成字典，传给 Agent
   ↓
⑩ react_agent.py:146 → for chunk in self.agent.stream(input_dict, ...)
   开始流式调用 LangChain Agent
```

#### 阶段三：LangChain Agent 内部处理

```
⑪ LangChain create_agent 内部：
    - 接收 input_dict，包含消息列表
    - 启动 ReAct 循环
    ↓
⑫ 中间件 log_before_model 触发：
    logger.info(f"[log_before_model] 即将调用模型，带有 {len(messages)} 条消息")
    ↓
⑬ 中间件 report_prompt_switch 触发：
    检查 context["report"] → False（默认不是报告场景）
    → 返回 load_system_prompts()（默认客服提示词）
    ↓
⑭ 大模型（LLM）被调用：
    系统提示词 + 用户消息 → 发送给 LLM
    LLM 分析问题，判断需要搜索互联网
    LLM 输出：需要调用工具 web_search，参数 query="最新的扫地机器人推荐"
```

#### 阶段四：工具调用

```
⑮ LangChain Agent 检测到需要调用工具 web_search
    ↓
⑯ 中间件 monitor_tool 触发：
    logger.info("[tool monitor] 执行工具: web_search")
    logger.info("[tool monitor] 传入参数: {'query': '最新的扫地机器人推荐'}")
    ↓
⑰ 判断 web_search 是本地工具还是远程工具：

    【情况 A：本地工具】（默认情况）
        → 直接调用 agent_tools.py 中的 web_search 函数
        → DDGS() 创建搜索客户端
        → ddgs.text("最新的扫地机器人推荐", max_results=5)
        → DuckDuckGo 服务器返回 5 条搜索结果
        → 格式化为文本字符串返回

    【情况 B：MCP 远程工具】（如果启用 MCP 模式）
        → LangChain 调用 Tool.coroutine(**kwargs)
        → 执行 tool_adapter.py 中的 call_remote 函数
        → await client.call_tool("web_search", {"query": "..."})
        → HTTP POST 发送到 http://localhost:8001/sse
        → MCP Server (robot_mcp_server.py) 接收请求
        → 执行 @mcp_server.tool() 注册的 web_search 函数
        → DDGS().text("最新的扫地机器人推荐", max_results=5)
        → DuckDuckGo 返回结果
        → 结果通过 SSE 返回给 Agent
    ↓
⑱ monitor_tool 后置逻辑：
    logger.info("[tool monitor] 工具 web_search 调用成功")
    ↓
⑲ 搜索结果返回给 LLM
```

#### 阶段五：LLM 生成回答

```
⑳ LLM 收到工具返回的搜索结果
    ↓
㉑ 中间件 log_before_model 再次触发（LLM 再次被调用）
    ↓
㉒ 中间件 report_prompt_switch 再次触发（判断提示词）
    ↓
㉓ LLM 基于搜索结果生成用户友好的回答
    例如："根据搜索结果，以下是2024年值得推荐的扫地机器人品牌：..."
    ↓
㉔ Agent 输出最终回答
```

#### 阶段六：流式返回到前端

```
㉕ react_agent.py:149 → latest = chunk["messages"][-1]
    从每个 chunk 中提取最新消息
    ↓
㉖ react_agent.py:150 → if latest.content: yield latest.content.strip() + "\n"
    逐块 yield 内容
    ↓
㉗ app.py:125 → for chunk in res_stream:
    逐块接收内容
    ↓
㉘ app.py:126 → full_response += chunk
    累积内容
    ↓
㉙ app.py:127 → message_placeholder.markdown(full_response + "▌")
    在浏览器中实时更新显示
    ↓
㉚ app.py:130 → message_placeholder.markdown(full_response)
    完成后移除光标指示器
    ↓
㉛ app.py:131 → st.session_state["messages"].append({"role": "assistant", "content": full_response})
    保存回答到历史，下次对话能看到
```

---

## 11. 为什么有了本地工具还要 MCP

### 11.1 本质区别

| 维度 | 本地工具 | MCP 远程工具 |
|------|---------|-------------|
| 代码位置 | 同一个项目内 | 可以在任何地方 |
| 调用方式 | 直接函数调用（进程内） | HTTP/SSE 网络请求 |
| 语言限制 | 必须用 Python | 可以用任何语言（Node.js、Go、Java 等） |
| 部署位置 | 必须在同一台机器 | 可以在任何能联网的机器上 |
| 复用性 | 只能被当前项目使用 | 可以被多个项目、多个 Agent 使用 |
| 依赖管理 | 共享当前项目的依赖 | 有自己的独立依赖 |

### 11.2 具体场景分析

**场景 1：当前项目的开发调试（用本地工具）**

你正在开发这个项目，需要频繁修改代码、测试效果。本地工具最简单直接：
- 改完代码，直接重新运行 `streamlit run app.py`
- 不需要启动额外的服务
- 调试方便，IDE 可以直接断点调试

**场景 2：多个 Agent 共享同一套工具（用 MCP）**

假设你有：
- Agent A：客服机器人（Python）
- Agent B：数据分析助手（Node.js）
- Agent C：运维监控（Go）

三个 Agent 都需要"搜索"和"查天气"的能力。

如果不使用 MCP：
- 需要在三个项目中各写一份搜索和天气的代码
- 代码重复，维护困难

使用 MCP：
- 写一个 MCP Server（如 `robot_mcp_server.py`）
- 三个 Agent 各自通过 MCP Client 连接
- 搜索和天气的逻辑只维护一份

**场景 3：工具部署在云端（用 MCP）**

假设你的搜索工具需要：
- 访问付费的搜索 API
- 有 API Key 等敏感信息
- 需要限流和监控

把这些放在本地工具中：
- 每个用户的机器上都要配置 API Key
- 无法控制谁在用、用多少

放在 MCP Server 中（部署在云服务器上）：
- API Key 只保存在服务端
- 服务端可以做鉴权、限流、统计
- 客户端只需知道 MCP 地址

**场景 4：第三方提供的工具（用 MCP）**

假设有一个公司提供了"智能家居控制"的 MCP Server：
- 你不需要知道他们的实现细节
- 只需要连接他们的 MCP 地址
- 就能调用他们的工具（开灯、调空调等）

### 11.3 项目的选择

当前项目**默认使用本地工具**，因为：
1. 这是一个教学/开发项目，目的是让你理解整个流程
2. 本地工具最简单，不需要额外的配置
3. 开发和调试方便

**MCP 是可选的增强功能**，当你需要时才启用：
- 在 `mcp_config.py` 中设置 `enabled: True`
- 先运行 `python zs_mcp/start_robot_mcp_server.py` 启动 MCP 服务
- 然后在 Web 界面选择"多服务器模式"或"单服务器模式"

---

## 12. 新增一个工具的操作步骤

### 12.1 新增本地工具

**步骤 1：在 `agent/tools/agent_tools.py` 中添加函数**

```python
@tool(description="计算两个数字的和")
def add_numbers(a: int, b: int) -> str:
    """计算两个整数的和"""
    return f"{a} + {b} = {a + b}"
```

**步骤 2：在 `agent/react_agent.py` 中导入并添加到 local_tools**

```python
# 修改 import 语句（第 23-27 行）
from agent.tools.agent_tools import (
    rag_summarize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
    web_search, add_numbers,  # ← 新增
)

# 修改 local_tools 列表（第 47-51 行）
self.local_tools = [
    rag_summarize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
    web_search, add_numbers,  # ← 新增
]
```

**步骤 3：在系统提示词中告诉 Agent 什么时候用这个工具**

编辑提示词文件（在 `prompts/` 目录下），添加使用说明。

**步骤 4：运行测试**
```bash
streamlit run app.py
# 在聊天框中输入"帮我算一下 3 加 5 等于多少"
```

### 12.2 新增 MCP 远程工具

**步骤 1：在 `zs_mcp/robot_mcp_server.py` 中添加函数**

```python
@mcp_server.tool()
def add_numbers(a: int, b: int) -> str:
    """计算两个数字的和"""
    return f"{a} + {b} = {a + b}"
```

**步骤 2：重启 MCP 服务**
```bash
# 如果已经在运行，先停止，再重新启动
python zs_mcp/start_robot_mcp_server.py
```

**步骤 3：客户端连接时会自动获取新工具**

不需要修改客户端代码，`client.list_tools()` 会自动包含新工具。

---

## 13. 常见问题排查

### 13.1 联网搜索不工作

**症状：** Agent 不调用 `web_search` 工具，或调用后返回空。

**排查步骤：**

1. **检查网络**：DuckDuckGo 需要能访问外网。在终端测试：
   ```bash
   python -c "from ddgs import DDGS; print(list(DDGS().text('test', max_results=1)))"
   ```

2. **检查工具注册**：确认 `web_search` 在 `local_tools` 列表中。

3. **检查提示词**：确认系统提示词中有引导 Agent 使用搜索的说明。

4. **查看日志**：运行后检查日志中是否有 `[tool monitor] 执行工具: web_search`。

### 13.2 MCP 连接失败

**症状：** Web 界面选择 MCP 模式后，工具未加载。

**排查步骤：**

1. **确认 MCP 服务已启动**：
   ```bash
   python zs_mcp/start_robot_mcp_server.py
   # 应输出：智扫通 MCP 服务 | SSE | http://0.0.0.0:8001/sse
   ```

2. **测试连接**：
   ```bash
   curl http://localhost:8001/sse
   ```

3. **检查 `mcp_config.py`**：确认 `enabled: True`。

4. **查看日志**：
   - 成功：`[MCP] 获取到 X 个远程工具`
   - 失败：`[Agent] 单服/多服 MCP 连接失败: ...`

### 13.3 工具调用失败

**症状：** Agent 调用了工具但返回错误。

**排查步骤：**

1. **查看工具监控日志**：
   ```
   [tool monitor] 执行工具: xxx
   [tool monitor] 传入参数: {...}
   ```

2. **检查参数**：确认传入的参数类型和数量与函数定义一致。

3. **检查依赖**：确认工具依赖的库已安装（如 `ddgs`）。
