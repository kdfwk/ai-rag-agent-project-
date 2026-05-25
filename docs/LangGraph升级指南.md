# LangGraph 智能体升级指南

## 一、升级了哪些功能

### 1. 状态管理（StateGraph）
**旧版**：使用 LangChain 的 `create_agent`，线性执行，无法暂停恢复。

**新版**：使用 LangGraph 的 `StateGraph`，状态在节点间流转，支持条件分支和循环。

- **文件**：`agent/state.py` - 定义 AgentState TypedDict
- **字段**：messages, query, intent, plan, current_step, step_results, retry_count, memory_summary, tool_result, is_finished, final_answer

### 2. 任务规划（Plan-and-Execute）
**旧版**：ReAct 模式单步执行，复杂任务无法分解。

**新版**：
- `planner_node`：接收任务，调用 LLM 生成 JSON 格式的执行计划
- `executor_node`：按顺序执行计划中的每步，调用工具
- `replanner_node`：评估执行结果，决定继续/修改/结束

- **文件**：`agent/nodes/planner.py`, `executor.py`, `replanner.py`

### 3. 记忆系统
**旧版**：简单消息列表，无摘要无长期记忆。

**新版**：
- **摘要记忆**：`summarize_node` 每轮对话后调用 LLM 摘要，存入 `memory_summary`
- **向量记忆**：`memory_service` 把重要对话存入 Chroma 向量库，检索时召回

- **文件**：`agent/memory.py`, `agent/nodes/summarize.py`

### 4. 意图分类与分支
**旧版**：所有问题走同一流程。

**新版**：`classify_node` 先判断意图：
- `chat`：闲聊 → chat_node
- `rag`：知识库查询 → rag_node
- `complex`：复杂任务 → planner_node → executor → replanner（循环）

- **文件**：`agent/nodes/classify.py`, `chat.py`, `rag.py`

### 5. 工具重试与容错
**旧版**：工具调用失败直接返回错误字符串。

**新版**：
- `executor_node` 内置重试逻辑：`retry_count` < `max_retries` 时自动重试
- 失败达到上限，记录错误，继续执行下一步

## 二、为什么这么做

### 1. 状态管理 → 可控性
LangGraph 的 StateGraph 把整个执行过程变成**可观测、可干预、可恢复**的。状态在节点间流转，每步可检查、可修改、可回滚。

**不这么做**：Agent 行为是个黑盒，出了问题无法定位。

### 2. 任务规划 → 复杂任务处理
ReAct 单步执行无法处理需要多步骤协调的任务。Plan-and-Execute 把任务拆解为有序步骤，每步可单独评估。

**不这么做**：复杂问题只能靠模型自己"思考"，容易遗漏步骤或跑偏。

### 3. 记忆系统 → 上下文扩展
短消息列表有 token 限制，长对话会丢失早期信息。摘要记忆压缩历史，向量记忆跨会话存储。

**不这么做**：长对话超过模型上下文窗口，回答质量下降。

### 4. 意图分类 → 效率与资源
闲聊不需要 RAG，天气查询不需要知识库。分类后走不同分支，避免无谓的检索和计算。

**不这么做**：所有问题都走 RAG，响应慢且浪费资源。

### 5. 重试机制 → 可靠性
网络不稳定、API 波动是常态。重试机制提高工具调用成功率。

**不这么做**：一次失败就返回错误，用户体验差。

## 三、新增/修改的文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent/state.py` | 新建 | AgentState TypedDict 定义 |
| `agent/nodes/classify.py` | 新建 | 意图分类节点 |
| `agent/nodes/planner.py` | 新建 | 任务规划节点 |
| `agent/nodes/executor.py` | 新建 | 执行器节点（带重试） |
| `agent/nodes/replanner.py` | 新建 | 重规划节点 |
| `agent/nodes/summarize.py` | 新建 | 记忆摘要节点 |
| `agent/nodes/chat.py` | 新建 | 闲聊节点 |
| `agent/nodes/rag.py` | 新建 | RAG 检索节点 |
| `agent/nodes/tools.py` | 新建 | 工具调用节点 |
| `agent/memory.py` | 新建 | 记忆服务（摘要+向量） |
| `agent/graph.py` | 新建 | StateGraph 构建 |
| `agent/react_agent.py` | 修改 | 添加 LangGraphAgent 类 |
| `rag/rag_service.py` | 修改 | 添加 arag_summarize 异步方法 |
| `utils/prompt_loader.py` | 修改 | 添加 plan/replan/summary 加载函数 |
| `config/agent.yml` | 修改 | 添加 max_retries, max_iterations 等配置 |
| `config/chroma.yml` | 修改 | 添加 memory_collection_name |
| `config/prompts.yml` | 修改 | 添加 plan/replan/summary 路径配置 |
| `prompts/plan_prompt.txt` | 新建 | 任务规划提示词 |
| `prompts/replan_prompt.txt` | 新建 | 重规划提示词 |
| `prompts/summary_prompt.txt` | 新建 | 记忆摘要提示词 |

## 四、使用方式

### 1. 启用 LangGraph Agent
修改 `app.py` 中的 Agent 初始化：

```python
# 旧版（ReAct）
from agent.react_agent import ReactAgent
agent = ReactAgent()

# 新版（LangGraph）
from agent.react_agent import LangGraphAgent
agent = LangGraphAgent()
```

### 2. 配置参数
`config/agent.yml`：
```yaml
max_retries: 3           # 工具调用最大重试次数
max_iterations: 10       # 最大迭代次数
memory_type: summary     # 记忆类型：summary | vector | both
enable_plan_execute: true  # 是否启用规划执行
```

`config/chroma.yml`：
```yaml
memory_collection_name: agent_memory  # 向量记忆集合名
```

### 3. 测试
```bash
# 测试单轮对话
python -c "
from agent.react_agent import LangGraphAgent
agent = LangGraphAgent()
for chunk in agent.execute_stream('给我生成2025年1月的使用报告'):
    print(chunk, end='', flush=True)
"

# 测试多轮对话
python -c "
from agent.react_agent import LangGraphAgent
agent = LangGraphAgent()
history = [{'role': 'user', 'content': '我家的户型是80平米'}]
for chunk in agent.execute_stream_with_history(history, '适合什么机器人'):
    print(chunk, end='', flush=True)
"
```

## 五、工作流程图

```
用户输入
    │
    ▼
┌─────────────────┐
│ classify_node   │ ─── 判断意图
└────────┬────────┘
         │
    ┌────┼────┐
    ▼    ▼    ▼
  chat  rag  complex
    │    │    │
    ▼    ▼    ▼
┌───────────────┐
│ chat_node     │ → 闲聊
│ rag_node      │ → RAG检索
│ planner_node  │ → 生成计划
└───────┬───────┘
        │
        ▼
┌─────────────────┐
│ executor_node   │ → 执行步骤 + 重试
└────────┬────────┘
        │
        ▼
┌─────────────────┐
│ replanner_node  │ → 评估决策
└────────┬────────┘
        │
   ┌────┴────┐
   ▼         ▼
 继续      结束
   │         │
   └────┬────┘
        ▼
┌─────────────────┐
│ summarize_node  │ → 生成摘要
└────────┬────────┘
        │
        ▼
    最终回答
```

## 六、注意事项

1. **依赖**：需要安装 `langgraph` 包（`pip install langgraph`）

2. **模型调用**：所有节点使用 `await chat_model.ainvoke()` 异步调用，确保 `model/factory.py` 返回的模型支持异步

3. **状态持久化**：`MemorySaver` 是内存级别，重启后丢失。如需跨会话持久化，可换用 `SqliteSaver` 或 `RedisSaver`

4. **兼容性**：`LangGraphAgent` 与原 `ReactAgent` 并存，可通过配置切换

5. **调试**：运行时会输出 `[Graph]`, `[Planner]`, `[Executor]`, `[Replanner]` 等日志，方便定位问题
