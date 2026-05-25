# MCP 多服务器使用指南

##  概述

本项目现在支持三种 MCP 模式：
1. **仅本地工具** - 只使用项目内置的本地工具
2. **单服务器模式** - 连接一个 MCP 服务器
3. **多服务器模式** - 同时连接多个 MCP 服务器

## 🚀 快速开始

### 1️⃣ 配置服务器

编辑 `mcp/mcp_config.py` 文件，在配置区域添加或修改服务器：

```python
# 示例：添加阿里云百炼 MCP 服务器
ALIYUN_BAILIAN_MCP: Dict[str, Any] = {
    'name': '阿里云百炼',
    'url': f'https://dashscope.aliyuncs.com/api/v1/mcp/sse?Authorization=Bearer {ALIYUN_API_KEY}',
    'transport': 'sse',
    'description': '阿里云百炼平台提供的 MCP 服务',
    'enabled': True,  # 设置为 True 启用
}
```

### 2️⃣ 设置 API Key（可选）

如果使用需要 API Key 的服务，设置环境变量：

**Windows PowerShell:**
```powershell
$env:ALIYUN_API_KEY="your-api-key-here"
```

**Linux/Mac:**
```bash
export ALIYUN_API_KEY="your-api-key-here"
```

### 3️⃣ 运行项目

```bash
# 启动 Web 应用
streamlit run app.py
```

##  添加新服务器

在 `mcp/mcp_config.py` 中：

```python
# 1. 定义新服务器配置
NEW_SERVICE_MCP: Dict[str, Any] = {
    'name': '新服务名称',
    'url': 'https://your-server-url/sse',
    'transport': 'sse',  # 或 'streamable_http'
    'description': '服务描述',
    'enabled': False,  # 默认关闭
}

# 2. 注册到 ALL_MCP_SERVERS
ALL_MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    'local_python': LOCAL_PYTHON_MCP,
    'java': JAVA_MCP,
    'aliyun_bailian': ALIYUN_BAILIAN_MCP,
    'zhipuai': ZHIPUAI_MCP,
    'new_service': NEW_SERVICE_MCP,  # 添加这里
}
```

## 🧪 测试多服务器

运行测试脚本验证连接：

```bash
python mcp/test_multi_server.py
```

##  Web 界面使用

1. 打开 http://localhost:8501
2. 在侧边栏选择 MCP 模式
3. 多服务器模式会自动加载所有启用的服务器
4. 开始对话，Agent 会自动调用最合适的工具

## 📝 配置文件说明

### mcp/mcp_config.py

集中管理所有服务器配置：

- **API Keys 区域** - 设置各平台的 API Key
- **服务器配置区域** - 定义每个服务器的连接信息
- **配置管理区域** - 自动管理已启用的服务器列表

### mcp/multi_server_client.py

多服务器 MCP 客户端实现：

- 自动连接所有配置的服务器
- 为工具添加服务器前缀避免冲突
- 完全对应老师演示的代码风格

## ⚙️ 模式对比

| 特性 | 仅本地工具 | 单服务器模式 | 多服务器模式 |
|------|----------|------------|------------|
| 工具来源 | 本地代码 | 单个远程服务器 | 多个远程服务器 |
| 配置方式 | 无需配置 | 输入 URL | 编辑配置文件 |
| 适用场景 | 快速测试 | 单一服务集成 | 多服务集成 |
| 工具前缀 | 无 | 无 | server_name_ |

## 🔧 故障排除

### 连接失败

1. 检查服务器地址是否正确
2. 确认服务器正在运行
3. 检查网络连接
4. 查看控制台错误信息

### API Key 问题

1. 确认环境变量已设置
2. 检查 API Key 是否有效
3. 查看服务文档确认 URL 格式

### 工具冲突

多服务器模式下，工具会自动添加前缀：
- `local_python_search_robot_knowledge`
- `aliyun_bailian_code_interpreter`

## 📚 代码示例

### Python 代码中使用

```python
from mcp.mcp_config import get_enabled_servers
from agent.react_agent import ReactAgent

# 方式 1: 使用配置文件中的服务器
enabled_servers = get_enabled_servers()
agent = ReactAgent(mcp_server_configs=enabled_servers)

# 方式 2: 自定义服务器配置
custom_servers = {
    'my_server': {
        'name': '我的服务',
        'url': 'http://localhost:8001/sse',
        'transport': 'sse',
        'description': '描述',
        'enabled': True,
    }
}
agent = ReactAgent(mcp_server_configs=custom_servers)

# 方式 3: 单服务器模式
agent = ReactAgent(mcp_server_url="http://localhost:8001/sse")
```

## 🎉 完成！

现在你可以：
- ✅ 集中管理所有 MCP 服务器配置
- ✅ 轻松添加新的远程服务
- ✅ 在 Web 界面直观选择模式
- ✅ 同时使用多个服务器的工具
