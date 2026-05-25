# 🚀 Docker 快速启动指南

## ✅ 已完成的配置

- ✅ Docker Desktop 已安装并运行（版本 29.4.3）
- ✅ Docker 配置文件已创建：
  - `Dockerfile` - Docker 镜像配置
  - `docker-compose.yml` - 服务编排配置
  - `.dockerignore` - Docker 忽略文件
  - `requirements.txt` - Python 依赖
  - `.env.example` - 环境变量模板
  - `.env` - 环境变量文件（需配置 API Key）
  - `docker-start.ps1` - 一键启动脚本
  - `check-docker.ps1` - Docker 检查脚本

## 📋 下一步操作

### 第 1 步：配置 API Key（必须）

在刚打开的记事本中，将这一行：
```
OPEMAO_API_KEY=sk-your-api-key-here
```

修改为你的真实 API Key：
```
OPEMAO_API_KEY=sk-你的真实API密钥
```

然后保存并关闭记事本。

### 第 2 步：启动 Docker 服务

#### 方式 A：使用启动脚本（推荐）

```powershell
.\docker-start.ps1
```

脚本会自动：
- 检查 Docker 状态
- 构建 Docker 镜像
- 启动所有服务
- 显示访问地址

#### 方式 B：手动命令

```powershell
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f
```

### 第 3 步：构建向量知识库

```powershell
# 运行知识库构建服务
docker compose --profile tools up vector-store-builder
```

这会处理 data/ 目录下的所有文档：
- 扫地机器人100问.pdf
- 扫地机器人100问2.txt
- 扫拖一体机器人100问.txt
- 故障排除.txt
- 维护保养.txt
- 选购指南.txt

### 第 4 步：访问应用

浏览器打开：
- **Web 界面**: http://localhost:8501
- **MCP 服务器**: http://localhost:8001

## 📊 常用命令速查

```powershell
# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 重新构建（代码修改后）
docker compose up -d --build

# 进入容器调试
docker compose exec app bash
```

## 🎯 完整流程示例

```powershell
# 1. 确保 API Key 已配置
notepad .env

# 2. 启动所有服务
.\docker-start.ps1

# 3. 等待服务启动（约 1-2 分钟）

# 4. 构建知识库
docker compose --profile tools up vector-store-builder

# 5. 访问 http://localhost:8501 开始使用
```

## ⚠️ 注意事项

1. **首次构建较慢**：首次运行需要下载基础镜像和安装依赖，可能需要 5-10 分钟
2. **端口占用**：确保 8501 和 8001 端口未被占用
3. **磁盘空间**：确保至少有 5GB 可用磁盘空间
4. **内存建议**：Docker Desktop 建议分配 8GB+ 内存

## 🔧 故障排查

### 问题 1：端口被占用

```powershell
# 查看占用端口的进程
netstat -ano | findstr :8501

# 修改 docker-compose.yml 中的端口映射
# 例如改为 8502:8501
```

### 问题 2：构建失败

```powershell
# 清理缓存重新构建
docker compose build --no-cache

# 查看详细日志
docker compose logs
```

### 问题 3：服务无法启动

```powershell
# 查看详细错误
docker compose logs app
docker compose logs mcp-server

# 检查 .env 配置
Get-Content .env
```

## 📁 数据持久化

以下目录会通过 Docker Volume 持久化：
- `./data` - 知识库文档
- `./chroma_db` - 向量数据库
- `./logs` - 日志文件
- `./.uploads` - 上传文件

即使删除容器，这些数据也会保留。

## 🎉 成功标志

当你看到以下输出时，表示启动成功：

```
✅ zhiSaoTong-app    Running    0.0.0.0:8501->8501/tcp
✅ zhiSaoTong-mcp    Running    0.0.0.0:8001->8001/tcp
```

然后在浏览器访问 http://localhost:8501 即可开始使用智扫通智能客服系统！

---

**提示**: 遇到问题先查看日志 `docker compose logs -f`，大部分问题都能从日志中找到答案。
