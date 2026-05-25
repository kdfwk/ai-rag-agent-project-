# 智扫通 - 快速开始指南

> **版本**: 3.0 (优化重构版)  
> **阅读时间**: 5分钟

---

## 🚀 5分钟快速上手

### 第1步：安装依赖

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 安装核心依赖
pip install langchain langchain-chroma langchain-community streamlit fastmcp

# 安装OCR相关依赖
pip install pdf2image Pillow python-docx dashscope
```

**Windows用户额外步骤：**
1. 下载poppler：http://blog.alivate.com.au/poppler-windows/
2. 解压后将`bin/`目录添加到系统PATH

### 第2步：配置API Key

```powershell
# Windows PowerShell
$env:OPEMAO_API_KEY="sk-your-api-key-here"
```

或者在代码中设置（不推荐）：
```python
# mcp/mcp_config.py
ALIYUN_API_KEY = "sk-your-api-key-here"
```

### 第3步：准备知识库文件

将文档放入 `data/` 目录：
- ✅ PDF文件（产品手册、故障排除指南）
- ✅ Word文件（.docx格式）
- ✅ 图片文件（jpg/png，会自动OCR识别）
- ✅ TXT文件（纯文本）

**示例：**
```
data/
├── 扫地机器人100问.pdf
├── 故障排除指南.docx
├── 产品结构图.jpg
└── 维护保养.txt
```

### 第4步：构建知识库

```bash
python rag/vector_store.py
```

**输出示例：**
```
[知识库] 发现 4 个文件待处理
[知识库] ✓ data/扫地机器人100问.pdf (45个片段)
[知识库] ✓ data/故障排除指南.docx (32个片段)
[知识库] ✓ data/产品结构图.jpg (1个片段)
[知识库] ✓ data/维护保养.txt (18个片段)
```

### 第5步：启动Web应用

```bash
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`

**开始对话：**
```
用户：扫地机器人如何清理主刷？
AI：根据产品手册，清理主刷的步骤如下...
```

---

## 🎯 常用场景

### 场景1：产品咨询

```
问：小户型适合哪些扫地机器人？
问：X500和X600有什么区别？
问：电池续航时间是多久？
```

### 场景2：故障排查

```
问：机器人显示错误代码E3怎么办？
问：为什么机器人总是卡在沙发底下？
问：充电座指示灯闪烁红色是什么意思？
```

### 场景3：维护建议

```
问：滤网多久更换一次？
问：如何清洁悬崖传感器？
问：边刷磨损了怎么判断？
```

### 场景4：生成报告

```
问：给我生成我的使用报告
```

Agent会自动：
1. 获取你的用户ID
2. 获取当前月份
3. 检索使用记录
4. 生成详细分析报告

---

## 🔌 MCP扩展（可选）

### 启用远程工具

**终端1：启动MCP服务器**
```bash
python mcp/start_robot_mcp_server.py
```

**终端2：启动Web应用**
```bash
streamlit run app.py
```

**在Web界面：**
1. 侧边栏选择"MCP模式"
2. 选择"单服务器模式"或"多服务器模式"
3. 开始使用远程工具

---

## 📚 了解更多

### 完整文档

- 📖 [项目架构与代码详解.md](file:///E:/AI大模型RAG与智能体开发_Agent项目/项目架构与代码详解.md) - 完整技术文档
- 📝 [优化总结报告.md](file:///E:/AI大模型RAG与智能体开发_Agent项目/优化总结报告.md) - 优化内容说明
- 🔌 [MCP使用指南.md](file:///E:/AI大模型RAG与智能体开发_Agent项目/MCP使用指南.md) - MCP协议详解

### 项目结构

```
项目根目录/
├── app.py                      # Web应用入口
├── agent/                      # Agent核心
│   ├── react_agent.py          # ReAct Agent
│   └── tools/                  # 工具和中间件
├── rag/                        # RAG检索
│   ├── vector_store.py         # 向量存储
│   ├── rag_service.py          # RAG服务
│   └── multimodal_ocr.py       # OCR服务
├── mcp/                        # MCP协议
├── utils/                      # 工具类
│   ├── file_utils.py           # 文件工具
│   ├── document_loader.py      # 文档加载器
│   └── loader_factory.py       # 加载器工厂
├── config/                     # 配置文件
├── prompts/                    # 提示词模板
└── data/                       # 知识库数据
```

---

## ❓ 常见问题

### Q1: 如何提高检索准确率？

**A:** 修改 `config/chroma.yml`：
```yaml
k: 5  # 增加检索数量（默认3）
chunk_size: 300  # 调整分片大小（默认200）
```

### Q2: PDF图片OCR很慢？

**A:** 
- 减少PDF页数
- 降低图片分辨率
- 使用GPU加速

### Q3: 如何清空知识库？

**A:**
```bash
# 删除向量库和MD5记录
rm -rf chroma_db/
rm md5.text

# 重新加载
python rag/vector_store.py
```

### Q4: 添加新文件格式？

**A:** 
1. 在 `utils/document_loader.py` 中添加加载函数
2. 在 `utils/loader_factory.py` 中添加映射
3. 在 `config/chroma.yml` 中添加扩展名

示例（添加Excel支持）：
```python
# document_loader.py
def load_excel(filepath: str) -> list[Document]:
    # 实现Excel加载逻辑
    ...

# loader_factory.py
LOADER_MAP = {
    '.xlsx': load_excel,
    ...
}
```

### Q5: API Key在哪里获取？

**A:** 
- 通义千问：https://dashscope.console.aliyun.com/
- 注册账号 → 创建API Key → 复制粘贴

---

## 🎉 开始使用

现在你已经准备好了！

```bash
# 1. 构建知识库
python rag/vector_store.py

# 2. 启动应用
streamlit run app.py

# 3. 在浏览器中开始对话
# http://localhost:8501
```

**祝你使用愉快！** 🤖✨

---

**需要帮助？**
- 查看 [项目架构与代码详解.md](file:///E:/AI大模型RAG与智能体开发_Agent项目/项目架构与代码详解.md)
- 查看日志文件：`logs/agent_*.log`
- 检查配置文件：`config/*.yml`
