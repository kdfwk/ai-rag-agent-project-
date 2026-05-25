# LangGraph 智能体升级指南（详细版）

## 一、升级概述

本项目将智能体核心从 LangChain 的 ReAct 模式升级为 LangGraph 架构。这次升级不是简单的 API 替换，而是整个执行模型的变革，涉及状态管理、工作流程控制、记忆系统和错误处理等多个层面的重构。

升级的核心目标是：**让智能体的行为变得可控、可观测、可调试**。

### 1.1 升级涉及的主要模块

| 模块 | 旧版本 | 新版本 | 变化程度 |
|------|--------|--------|----------|
| 状态管理 | 无持久状态 | StateGraph 状态流 | 重大 |
| 执行模式 | ReAct 单步循环 | Plan-and-Execute | 重大 |
| 记忆系统 | 简单消息列表 | 摘要+向量双记忆 | 重大 |
| 路由决策 | 单一流程 | 意图分类+条件分支 | 中等 |
| 错误处理 | 直接返回错误 | 重试+容错机制 | 中等 |

---

## 二、状态管理升级：从黑盒到可观测

### 2.1 改了哪里

**新增文件**：`agent/state.py`

```python
# agent/state.py - 第10-42行
class AgentState(TypedDict):
    """智能体状态定义"""

    # 消息历史
    messages: List[BaseMessage]

    # 用户原始查询
    query: str

    # 任务分类结果
    intent: str  # "chat" | "rag" | "complex"

    # 执行计划（Plan-and-Execute）
    plan: List[Dict[str, Any]]  # [{"step": 1, "task": "xxx", "tool": "tool_name"}]
    current_step: int  # 当前执行到第几步
    step_results: List[Dict[str, Any]]  # 每步执行结果

    # 重试计数
    retry_count: int
    max_retries: int

    # 记忆摘要
    memory_summary: str  # 历史对话摘要

    # 工具调用结果
    tool_result: Optional[str]
    tool_error: Optional[str]

    # 是否结束
    is_finished: bool

    # 最终回答
    final_answer: Optional[str]
```

**为什么要改**：旧版 ReAct Agent 的状态完全由 LangChain 内部管理，开发者无法直接访问和修改。状态流转是封闭的，出了问题只能看日志猜。

**不改会怎样**：当智能体执行出错时，你只能看到最终的错误信息，无法知道是哪个步骤出了问题、哪个变量状态不对。调试只能靠加 print 语句。

**这么做的好处**：

1. **状态完全透明**：每个节点都可以读取和修改状态，开发者可以随时打印状态内容
2. **支持条件分支**：根据 `intent` 是 "chat"、"rag" 还是 "complex"，图结构可以路由到不同节点
3. **支持循环执行**：通过 `is_finished` 和 `current_step` 控制 Plan-and-Execute 的循环
4. **支持断点恢复**：配合 `MemorySaver`，可以在任意节点暂停和恢复执行

### 2.2 旧版本状态管理（无显式状态）

```python
# 旧版 react_agent.py - 第145-151行
def _stream_response(self, messages: List):
    """提交消息给 Agent，以流式方式返回回答"""
    input_dict = {"messages": messages}
    for chunk in self.agent.stream(
        input_dict, stream_mode="values", context={"report": False}
    ):
        latest = chunk["messages"][-1]
        if latest.content:
            yield latest.content.strip() + "\n"
```

**分析**：旧版本只有 `messages` 这一个输入，状态全部封装在 LangChain 的 Agent 内部。开发者无法：
- 知道当前执行到了哪一步
- 中途修改执行计划
- 根据中间结果决定下一步
- 在某个节点暂停和恢复

### 2.3 新版本状态流

```python
# agent/react_agent.py - 第219-240行
async def execute_stream(self, query: str):
    """单轮对话：流式返回回答（异步生成器）"""
    initial_state: AgentState = {
        "messages": [],
        "query": query,
        "intent": "",
        "plan": [],
        "current_step": 0,
        "step_results": [],
        "retry_count": 0,
        "max_retries": self.max_retries,
        "memory_summary": "",
        "tool_result": None,
        "tool_error": None,
        "is_finished": False,
        "final_answer": None,
    }

    # 运行图
    async for state in self.graph.astream(initial_state, self.config):
        if "final_answer" in state and state["final_answer"]:
            yield state["final_answer"]
```

**关键点**：状态在节点间流转，每个节点都可以修改状态，下一个节点可以看到上一个节点的修改结果。

---

## 三、执行模式升级：从 ReAct 到 Plan-and-Execute

### 3.1 改了哪里

**新增节点文件**：
- `agent/nodes/planner.py` - 任务规划器
- `agent/nodes/executor.py` - 执行器（带重试）
- `agent/nodes/replanner.py` - 重规划器

**旧版本执行流程**：
```
用户问题 → Agent 思考 → 调用工具 → 观察结果 → 继续思考 → 输出回答
            (单步循环，无法分解复杂任务)
```

**新版本执行流程**：
```
用户问题 → 分类 → 规划（生成步骤列表） → 执行第1步 → 重规划 → 执行第2步 → ... → 结束
```

### 3.2 规划器节点（planner_node）

**文件**：`agent/nodes/planner.py`

```python
# 第14-77行
async def planner_node(state: AgentState) -> AgentState:
    """生成任务执行计划"""
    query = state["query"]

    # 加载规划提示词
    plan_prompt = load_prompts("plan_prompts")

    system_prompt = f"""{plan_prompt}

请为以下任务生成详细的执行计划。计划应该是JSON格式，包含以下字段：
- steps: 步骤列表
- 每个步骤包含: step(步骤序号), task(任务描述), tool(使用的工具名称，可选)
...
"""

    # 调用模型生成计划
    response = await chat_model.ainvoke(messages)
    plan_text = response.content.strip()

    # 解析JSON计划
    plan_data = json.loads(plan_text)

    if isinstance(plan_data, dict) and "steps" in plan_data:
        state["plan"] = plan_data["steps"]
    elif isinstance(plan_data, list):
        state["plan"] = plan_data

    state["current_step"] = 0
    return state
```

**为什么要改**：ReAct 模式是"边想边做"，复杂任务容易遗漏步骤或跑偏。例如用户说"帮我生成2025年1月的使用报告"，ReAct 模式可能：
1. 先调用 RAG 查询知识库
2. 发现信息不够，再查天气
3. 发现还缺用户数据，再查外部接口
4. 最后才生成报告——顺序混乱，可能做无用功

**不改会怎样**：复杂任务的执行结果完全依赖模型的"临场发挥"，没有规划就容易：
- 步骤遗漏（如忘记查用户信息）
- 顺序错误（如先生成报告再查数据，报告内容不完整）
- 重复劳动（多次查询同一信息源）

**这么做的好处**：

1. **计划先行**：模型先完整规划，再按计划执行，步骤清晰
2. **可验证**：可以在执行前检查计划是否合理
3. **可干预**：用户可以审核和修改计划
4. **可追溯**：执行过程中记录了每一步的结果

### 3.3 执行器节点（executor_node）

**文件**：`agent/nodes/executor.py`

```python
# 第27-111行
async def executor_node(state: AgentState) -> AgentState:
    """执行当前步骤"""
    current_step = state["current_step"]
    plan = state["plan"]

    # 检查是否已完成所有步骤
    if current_step >= len(plan):
        state["is_finished"] = True
        return state

    # 获取当前步骤
    step = plan[current_step]
    tool_name = step.get("tool")
    task = step.get("task", "")

    # 如果有工具，调用工具
    if tool_name and tool_name in TOOL_MAP:
        try:
            tool = TOOL_MAP[tool_name]
            # ... 根据工具类型调用
            result = tool.invoke(params)
            state["tool_result"] = result

        except Exception as e:
            # 重试逻辑
            if state["retry_count"] < state["max_retries"]:
                state["retry_count"] += 1
                return state  # 保持 current_step 不变，下次循环重试
            # 重试次数用尽，记录错误
            state["tool_error"] = str(e)

    # 进入下一步
    state["current_step"] += 1
    state["retry_count"] = 0  # 重置重试计数

    return state
```

**关键改进**：内置重试机制，`retry_count` < `max_retries` 时自动重试当前步骤。

**旧版本错误处理**（agent/tools/agent_tools.py）：
```python
# 假设工具调用失败
try:
    result = tool.invoke(...)
except Exception as e:
    return f"错误: {str(e)}"  # 直接返回错误字符串
```

**改后的好处**：
- 网络抖动不会立即失败，会自动重试
- 重试次数可配置（默认3次）
- 错误信息会记录到 `step_results` 供后续分析

### 3.4 重规划器节点（replanner_node）

**文件**：`agent/nodes/replanner.py`

```python
# 第13-70行
async def replanner_node(state: AgentState) -> AgentState:
    """评估执行结果，决定下一步"""
    plan = state["plan"]
    current_step = state["current_step"]
    step_results = state["step_results"]

    # 检查是否完成所有步骤
    if current_step >= len(plan):
        state["is_finished"] = True
        return state

    # 构建评估上下文
    results_summary = "\n".join([
        f"步骤 {r['step']}: {r['task']} - {r['status']}"
        for r in step_results
    ])

    # 调用模型评估
    response = await chat_model.ainvoke(messages)
    decision = response.content.strip().lower()

    # 根据决策设置状态
    if decision == "finish":
        state["is_finished"] = True
    elif decision == "revise":
        state["intent"] = "complex"
        state["current_step"] = 0  # 重置步骤
    # "continue" - 保持当前状态，继续执行

    return state
```

**作用**：每次执行完一个步骤后，评估是否需要：
- `continue`：继续执行下一步
- `revise`：修改计划（重新规划）
- `finish`：计划已完成，结束

**不改会怎样**：旧版 ReAct 需要模型自己判断是否"想清楚了"，容易陷入无限循环或过早结束。

---

## 四、记忆系统升级：摘要记忆 + 向量记忆

### 4.1 改了哪里

**新增文件**：`agent/memory.py`

```python
# agent/memory.py - 第17-113行
class MemoryService:
    """记忆服务：摘要记忆 + 向量长记忆"""

    def __init__(self):
        # 向量记忆集合
        memory_collection = chroma_conf.get("memory_collection_name", "agent_memory")

        self.vector_memory = Chroma(
            collection_name=memory_collection,
            embedding_function=embed_model,
            persist_directory=get_abs_path(chroma_conf["persist_directory"]),
        )

        # 摘要记忆
        self.summary: Optional[str] = None

    def add_to_vector_memory(self, content: str, metadata: dict = None):
        """添加到向量记忆"""
        doc = Document(page_content=content, metadata=metadata or {"type": "memory"})
        self.vector_memory.add_documents([doc])

    def search_vector_memory(self, query: str, k: int = 3) -> List[Document]:
        """检索向量记忆"""
        return self.vector_memory.similarity_search(query, k=k)

    async def generate_summary(self, messages: List[BaseMessage]) -> str:
        """生成对话摘要"""
        # 取最近 10 条消息，调用 LLM 生成摘要
        response = await chat_model.ainvoke(prompt)
        self.summary = response.content.strip()
        return self.summary
```

**新增节点**：`agent/nodes/summarize.py`

```python
# agent/nodes/summarize.py - 第13-51行
async def summarize_node(state: AgentState) -> AgentState:
    """生成对话摘要"""
    messages = state["messages"]
    recent_messages = messages[-10:]

    # 调用 LLM 生成摘要
    response = await chat_model.ainvoke(messages)
    summary = response.content.strip()

    state["memory_summary"] = summary
    return state
```

### 4.2 两种记忆机制

| 记忆类型 | 存储方式 | 用途 | 优点 | 缺点 |
|----------|----------|------|------|------|
| 摘要记忆 | 字符串 | 当前会话 | 轻量，快速 | 信息有损 |
| 向量记忆 | Chroma 向量库 | 跨会话 | 语义检索，信息完整 | 需要额外存储 |

**旧版本记忆**（agent/react_agent.py 第115-133行）：
```python
def _build_messages(self, history: List[Dict], current_query: str) -> List:
    """把历史记录和当前问题转换成消息格式"""
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=current_query))
    return messages
```

**问题**：所有历史消息都直接拼接，有两个严重问题：

1. **token 限制**：模型上下文窗口有限，历史消息超过限制后会被截断，丢失早期信息
2. **无长期记忆**：每次对话都是独立的，无法记住跨会话的用户偏好

**新版本解决方案**：
- 摘要记忆：每轮对话后用 LLM 生成摘要，压缩历史信息
- 向量记忆：将重要对话存入向量库，检索时召回相关历史

**不改会怎样**：
- 长对话超过模型上下文窗口时，回答质量断崖式下降
- 无法记住用户偏好（如户型、预算、使用习惯），每次都要重新问

---

## 五、意图分类与条件路由

### 5.1 改了哪里

**新增节点**：`agent/nodes/classify.py`

```python
# agent/nodes/classify.py - 第11-38行
async def classify_node(state: AgentState) -> AgentState:
    """分类用户意图"""
    query = state["query"]

    # 构建分类提示词
    system_prompt = """你是一个任务分类器。分析用户问题，判断属于哪一类：

1. chat - 闲聊、问候、简单问答（不需要检索知识库）
2. rag - 需要查询扫地机器人知识库的问题
3. complex - 复杂任务，需要多步骤执行（如生成报告、综合分析）

只返回分类结果，不要解释。"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"问题: {query}")
    ]

    # 调用模型分类
    response = await chat_model.ainvoke(messages)
    intent = response.content.strip().lower()

    # 验证意图有效性
    if intent not in ["chat", "rag", "complex"]:
        intent = "rag"  # 默认使用RAG

    state["intent"] = intent
    return state
```

### 5.2 条件路由实现

**文件**：`agent/graph.py` 第39-56行

```python
# 分类后分支
def route_after_classify(state: AgentState) -> str:
    intent = state.get("intent", "rag")
    logger.info(f"[Graph] 路由到：{intent}")

    if intent == "chat":
        return "chat"
    elif intent == "rag":
        return "rag"
    elif intent == "complex":
        return "planner"
    else:
        return "rag"

graph.add_conditional_edges(
    "classify",
    route_after_classify,
    ["chat", "rag", "planner"]
)
```

### 5.3 三种意图的处理

| 意图 | 路由节点 | 处理方式 | 适用场景 |
|------|----------|----------|----------|
| chat | chat_node | 直接对话，不检索知识库 | 问候、闲聊、简单问答 |
| rag | rag_node | RAG 检索后回答 | 事实性问题、产品查询 |
| complex | planner → executor → replanner | 规划→执行→重规划循环 | 报告生成、多步骤任务 |

**旧版本**：所有问题都走同一流程，先 RAG 检索，再决定是否调用工具。

**不改会怎样**：
- 用户说"你好"也要走 RAG 检索，浪费资源
- 闲聊类问题检索结果无意义，响应慢
- 复杂任务无法规划分解，执行混乱

---

## 六、图构建与工作流

### 6.1 改了哪里

**新增文件**：`agent/graph.py`

```python
# agent/graph.py - 第20-93行
def build_graph():
    """构建 StateGraph"""

    # 初始化图
    graph = StateGraph(AgentState)

    # 添加节点（7个）
    graph.add_node("classify", classify_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("replanner", replanner_node)
    graph.add_node("chat", chat_node)
    graph.add_node("rag", rag_node)
    graph.add_node("summarize", summarize_node)

    # 设置入口点
    graph.add_edge(START, "classify")

    # 分类后条件分支
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        ["chat", "rag", "planner"]
    )

    # 闲聊分支
    graph.add_edge("chat", "summarize")
    graph.add_edge("summarize", END)

    # RAG 分支
    graph.add_edge("rag", "summarize")
    graph.add_edge("summarize", END)

    # 复杂任务分支（Plan-and-Execute）
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "replanner")

    # 重规划器后条件分支
    graph.add_conditional_edges(
        "replanner",
        route_after_replan,
        ["summarize", "executor"]
    )

    # 编译图
    memory = MemorySaver()
    compiled_graph = graph.compile(checkpointer=memory)

    return compiled_graph
```

### 6.2 工作流图

```
                        ┌──────────────┐
                        │    START     │
                        └──────┬───────┘
                               ▼
                    ┌─────────────────────┐
                    │   classify_node     │ ─ 判断意图
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ chat_node│    │ rag_node │    │ planner  │
        └────┬─────┘    └────┬─────┘    └────┬─────┘
             │               │               │
             ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ summarize│    │ summarize│    │ executor │
        └────┬─────┘    └────┬─────┘    └────┬─────┘
             │               │               │
             └───────────────┼───────────────┘
                             ▼
                      ┌──────────┐
                      │ replanner│ ─ 评估决策
                      └────┬─────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        ┌──────────┐              ┌──────────┐
        │ summarize│              │ executor │ ─ 继续执行
        └────┬─────┘              └──────────┘
             │
             ▼
        ┌──────────┐
        │   END    │
        └──────────┘
```

### 6.3 关键设计点

1. **节点（Node）**：每个节点是一个 Python 异步函数，接收状态，返回修改后的状态
2. **边（Edge）**：控制流程，有普通边（固定跳转）和条件边（根据状态决定跳转）
3. **条件分支**：根据 `intent` 决定走哪个分支；根据 `is_finished` 决定是否继续循环

**旧版本工作流**：
```python
# 旧版 agent.stream() 内部
# 用户输入 → Agent 思考 → 工具调用 → 观察结果 → (重复) → 输出
```
完全封闭，无法干预。

**新版本工作流**：
- 每一步都可观测：可以打印每个节点的状态
- 每一步都可干预：可以在任意节点修改状态
- 支持断点恢复：MemorySaver 保存状态，可恢复

**不改会怎样**：
- 智能体是个黑盒，出了问题无法定位
- 无法中途修改执行计划
- 无法暂停和恢复执行

---

## 七、配置文件变更

### 7.1 agent.yml 新增配置

**文件**：`config/agent.yml`

```yaml
external_data_path: data/external/records.csv

# LangGraph Agent 配置（新增）
max_retries: 3              # 工具调用最大重试次数
max_iterations: 10          # 最大迭代次数（循环上限）
memory_type: summary        # 记忆类型：summary | vector | both
enable_plan_execute: true   # 是否启用规划执行
```

**各配置的作用**：

| 配置 | 作用 | 不配置的后果 |
|------|------|--------------|
| max_retries | 工具调用失败后重试次数 | 失败直接返回错误 |
| max_iterations | Plan-and-Execute 循环上限 | 可能无限循环 |
| memory_type | 记忆存储方式 | 使用默认摘要记忆 |
| enable_plan_execute | 是否启用规划模式 | 走默认 ReAct 模式 |

---

## 八、使用方式对比

### 8.1 初始化对比

**旧版**：
```python
from agent.react_agent import ReactAgent
agent = ReactAgent()
```

**新版**：
```python
from agent.react_agent import LangGraphAgent
agent = LangGraphAgent()
```

### 8.2 单轮对话对比

**旧版**：
```python
for chunk in agent.execute_stream("给我生成使用报告"):
    print(chunk, end="", flush=True)
```

**新版**：
```python
# 异步方式
for chunk in agent.execute_stream("给我生成使用报告"):
    print(chunk, end="", flush=True)

# 或同步方式
for chunk in agent.execute_stream_sync("给我生成使用报告"):
    print(chunk, end="", flush=True)
```

### 8.3 多轮对话对比

**旧版**：
```python
history = [{"role": "user", "content": "我家的户型是80平米"}]
for chunk in agent.execute_stream_with_history(history, "适合什么机器人"):
    print(chunk, end="", flush=True)
```

**新版**（带记忆）：
```python
history = [{"role": "user", "content": "我家的户型是80平米"}]
for chunk in agent.execute_stream_with_history(history, "适合什么机器人"):
    print(chunk, end="", flush=True)
# 新版会自动将对话存入向量记忆，供后续检索
```

---

## 九、新增/修改文件清单

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `agent/state.py` | 新建 | AgentState TypedDict 定义 |
| `agent/graph.py` | 新建 | StateGraph 构建（核心） |
| `agent/memory.py` | 新建 | 记忆服务（摘要+向量） |
| `agent/nodes/classify.py` | 新建 | 意图分类节点 |
| `agent/nodes/planner.py` | 新建 | 任务规划节点 |
| `agent/nodes/executor.py` | 新建 | 执行器节点（带重试） |
| `agent/nodes/replanner.py` | 新建 | 重规划节点 |
| `agent/nodes/summarize.py` | 新建 | 记忆摘要节点 |
| `agent/nodes/chat.py` | 新建 | 闲聊节点 |
| `agent/nodes/rag.py` | 新建 | RAG 检索节点 |
| `agent/react_agent.py` | 修改 | 添加 LangGraphAgent 类 |
| `prompts/plan_prompt.txt` | 新建 | 任务规划提示词 |
| `prompts/replan_prompt.txt` | 新建 | 重规划提示词 |
| `prompts/summary_prompt.txt` | 新建 | 记忆摘要提示词 |
| `config/agent.yml` | 修改 | 添加 LangGraph 配置项 |

---

## 十、依赖要求

```bash
# 必须安装
pip install langgraph

# LangGraph 依赖
# - langchain-core
# - langchain-openai（如使用 OpenAI 模型）
# - langchain-chroma（如使用向量记忆）
```

---

## 十一、注意事项

### 11.1 状态持久化

```python
# agent/graph.py - 第89-90行
memory = MemorySaver()
compiled_graph = graph.compile(checkpointer=memory)
```

**注意**：`MemorySaver` 是内存级别，重启后丢失。如需跨会话持久化：

```python
# 使用 SQLite 持久化
from langgraph.checkpoint.sqlite import SqliteSaver
memory = SqliteSaver.from_conn_string(":memory:")  # 或指定文件路径
```

### 11.2 异步调用

所有节点函数都是异步的，确保模型支持异步：

```python
# model/factory.py 返回的模型需要支持 ainvoke()
response = await chat_model.ainvoke(messages)
```

### 11.3 调试方法

运行时会输出日志：

| 日志前缀 | 来源 | 含义 |
|----------|------|------|
| `[Graph]` | graph.py | 图路由决策 |
| `[Planner]` | planner.py | 计划生成 |
| `[Executor]` | executor.py | 步骤执行 |
| `[Replanner]` | replanner.py | 重规划决策 |
| `[Summarize]` | summarize.py | 摘要生成 |
| `[Memory]` | memory.py | 记忆操作 |

---

## 十二、常见问题

### Q1：如何判断是否成功升级？

运行测试：
```python
from agent.react_agent import LangGraphAgent

agent = LangGraphAgent()
for chunk in agent.execute_stream("你好"):
    print(chunk, end="", flush=True)
```

### Q2：旧版 ReactAgent 还能用吗？

可以。`LangGraphAgent` 和 `ReactAgent` 是两个独立的类，通过配置选择使用哪个。

### Q3：如何调整重试次数？

修改 `config/agent.yml`：
```yaml
max_retries: 5  # 改为5次
```

### Q4：如何禁用 Plan-and-Execute？

修改 `config/agent.yml`：
```yaml
enable_plan_execute: false
```

### Q5：图结构支持自定义吗？

支持。修改 `agent/graph.py` 中的 `build_graph()` 函数即可增删节点和边。
