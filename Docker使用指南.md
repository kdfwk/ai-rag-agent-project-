# 🐳 Docker 使用指南

## 📋 前置条件

- ✅ 已安装 Docker Desktop
- ✅ Docker Desktop 正在运行

## 🚀 快速开始

### 方式一：使用启动脚本（推荐）

```powershell
# 1. 允许执行脚本（首次需要）
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 2. 运行启动脚本
.\docker-start.ps1
```

脚本会自动：
- 检查 Docker 是否运行
- 创建 .env 配置文件
- 构建 Docker 镜像
- 启动所有服务
- 打开浏览器访问应用

### 方式二：手动命令

#### 1️⃣ 配置 API Key

```powershell
# 复制环境变量模板
Copy-Item .env.example .env

# 编辑 .env 文件，填入你的 API Key
notepad .env
```

在 `.env` 文件中修改：
```bash
OPEMAO_API_KEY=sk-your-real-api-key-here
```

#### 2️⃣ 准备知识库数据

确保 `data/` 目录下有文档文件（PDF、Word、TXT、图片等）。

#### 3️⃣ 构建并启动服务

```powershell
# 首次构建并启动
docker compose up -d --build
```

这会启动两个服务：
- **app**: Streamlit Web 应用（端口 8501）
- **mcp-server**: MCP 服务器（端口 8001）

#### 4️⃣ 构建向量知识库

```powershell
# 运行知识库构建服务
docker compose --profile tools up vector-store-builder
```

看到类似输出表示成功：
```
[知识库] 发现 5 个文件待处理
[知识库] ✓ data/扫地机器人100问.pdf (23个片段)
[知识库] ✓ data/故障排除.txt (15个片段)
```

#### 5️⃣ 访问应用

- **Web 界面**: http://localhost:8501
- **MCP 服务器**: http://localhost:8001

## 📊 常用命令

### 查看服务状态

```powershell
# 查看所有容器
docker compose ps

# 查看实时日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f app
docker compose logs -f mcp-server
```

### 管理服务

```powershell
# 停止所有服务
docker compose down

# 重启服务
docker compose restart

# 重新构建并启动（代码修改后）
docker compose up -d --build

# 进入容器内部调试
docker compose exec app bash
```

### 资源管理

```powershell
# 查看容器资源使用情况
docker stats

# 清理未使用的镜像和缓存
docker system prune -a
```

## 🔧 Docker Desktop GUI 使用

### 1. 查看容器

1. 打开 Docker Desktop 应用
2. 点击左侧 "Containers" 标签
3. 可以看到：
   - `zhiSaoTong-app` - Web 应用
   - `zhiSaoTong-mcp` - MCP 服务器

### 2. 查看日志

1. 点击容器名称
2. 切换到 "Logs" 标签页
3. 实时查看日志输出

### 3. 管理容器

- ▶️ 启动容器
- ⏹️ 停止容器
- 🗑️ 删除容器
- 📋 复制容器信息

### 4. 查看镜像

1. 点击左侧 "Images" 标签
2. 可以看到构建的镜像
3. 右键可以删除或查看详情

## 🎯 使用场景

### 场景一：日常开发

```powershell
# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f app

# 修改代码后重新构建
docker compose up -d --build
```

### 场景二：更新知识库

```powershell
# 1. 添加新文档到 data/ 目录
Copy-Item "新文档.pdf" .\data\

# 2. 重新构建向量库
docker compose --profile tools up vector-store-builder

# 3. 重启应用
docker compose restart app
```

### 场景三：备份数据

```powershell
# 停止服务
docker compose down

# 备份向量数据库
tar -czf chroma_db_backup.tar.gz .\chroma_db\

# 备份日志
tar -czf logs_backup.tar.gz .\logs\

# 恢复数据
tar -xzf chroma_db_backup.tar.gz
```

### 场景四：完全清理

```powershell
# 停止并删除所有容器、网络
docker compose down

# 删除数据卷（谨慎！会删除所有数据）
docker compose down -v

# 删除镜像
docker rmi zhisao-tong-app
```

## ⚙️ 高级配置

### 修改端口

如果端口冲突，编辑 `docker-compose.yml`：

```yaml
services:
  app:
    ports:
      - "8502:8501"  # 改为 8502 端口
```

### 增加资源限制

编辑 `docker-compose.yml`：

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

### 开发模式（热重载）

创建 `docker-compose.dev.yml`：

```yaml
version: '3.8'

services:
  app:
    build: .
    container_name: zhiSaoTong-dev
    ports:
      - "8501:8501"
    environment:
      - OPEMAO_API_KEY=${OPEMAO_API_KEY}
    volumes:
      - .:/app
      - /app/__pycache__
    command: >
      streamlit run app.py
      --server.port=8501
      --server.address=0.0.0.0
      --server.runOnSave=true
    networks:
      - zhiSaoTong-network

networks:
  zhiSaoTong-network:
    driver: bridge
```

使用：
```powershell
docker compose -f docker-compose.dev.yml up -d
```

## ❓ 常见问题

### Q1: 端口被占用

```powershell
# 查看哪个程序占用了端口
netstat -ano | findstr :8501
netstat -ano | findstr :8001

# 杀死进程（替换 PID）
taskkill /F /PID <PID>

# 或者修改 docker-compose.yml 中的端口映射
```

### Q2: 构建失败

```powershell
# 清理缓存重新构建
docker compose build --no-cache

# 查看详细构建日志
docker compose build --progress=plain
```

### Q3: 容器无法启动

```powershell
# 查看详细错误日志
docker compose logs app
docker compose logs mcp-server

# 检查环境变量
docker compose config

# 检查 .env 文件是否正确
Get-Content .env
```

### Q4: 数据持久化问题

```powershell
# 确认 volume 挂载正确
docker inspect zhiSaoTong-app | Select-String "Mounts" -Context 10

# 检查本地目录
Get-ChildItem .\data\
Get-ChildItem .\chroma_db\
```

### Q5: 网络连接问题

```powershell
# 重启 Docker Desktop
# 或者重置网络
docker network prune

# 重建网络
docker compose down
docker compose up -d
```

### Q6: 内存不足

在 Docker Desktop 中调整：
1. Settings → Resources → Advanced
2. 增加 Memory 分配（建议 8GB+）
3. Apply & Restart

## 📁 项目结构

```
项目根目录/
├── Dockerfile              # Docker 镜像配置
├── docker-compose.yml      # Docker Compose 配置
├── .dockerignore           # Docker 忽略文件
├── .env                    # 环境变量（需自行创建）
├── .env.example            # 环境变量模板
├── requirements.txt        # Python 依赖
├── docker-start.ps1        # 启动脚本
├── data/                   # 知识库数据（持久化）
├── chroma_db/             # 向量数据库（持久化）
├── logs/                  # 日志文件（持久化）
└── ...
```

## 🔐 安全建议

1. **不要提交 .env 文件到 Git**
   - `.env` 已在 `.gitignore` 中
   - 只提交 `.env.example` 作为模板

2. **定期更新镜像**
   ```powershell
   docker compose pull
   docker compose up -d --build
   ```

3. **备份重要数据**
   - 定期备份 `chroma_db/` 目录
   - 备份 `data/` 目录的知识库文档

## 📈 性能优化

### Docker Desktop 设置

1. **启用 WSL 2 后端**
   - Settings → General
   - 勾选 "Use the WSL 2 based engine"

2. **增加资源分配**
   - Settings → Resources → Advanced
   - CPU: 4核
   - Memory: 8GB
   - Swap: 2GB

3. **配置镜像加速器**
   - Settings → Docker Engine
   - 添加国内镜像源（如阿里云、腾讯云）

### 镜像优化

```powershell
# 定期清理未使用的资源
docker system prune -a --volumes

# 查看磁盘使用情况
docker system df
```

## 🎓 学习资源

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Docker Desktop 文档](https://docs.docker.com/desktop/)

---

**提示**: 遇到问题先查看日志 `docker compose logs -f`，大部分问题都能从日志中找到线索。
