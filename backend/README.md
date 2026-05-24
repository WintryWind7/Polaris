# Polaris 后端

Python + FastAPI 驱动的 AI Agent 后端服务。

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式（支持热重载）
$env:POLARIS_RELOAD="1"; $env:POLARIS_DEV="1"; python -m backend.api.server

# 调整日志级别
$env:POLARIS_LOG_LEVEL="DEBUG"  # PowerShell
export POLARIS_LOG_LEVEL=DEBUG   # bash
```

启动后访问 http://127.0.0.1:6547

## 目录结构

```
backend/
├── agents/            # Agent 系统
│   ├── main_agent.py  # 主 Agent（对话调度）
│   ├── heartbeat_agent.py  # 心跳 Agent（后台监控）
│   ├── base.py        # Agent 基类
│   ├── subagents/     # 子 Agent（文件系统、技能学习等）
│   ├── tools/         # 工具系统（文件、内存、系统、网页）
│   ├── hooks/         # System prompt 扩展钩子
│   └── prompts/       # 提示词模板
├── api/               # HTTP API
│   ├── server.py      # FastAPI 入口
│   └── routes/        # 路由（chat, agent, config, embeddings 等）
├── config/            # 配置管理
│   ├── settings.py    # 全局设置
│   ├── manager.py     # 配置读写
│   ├── provider_manager.py  # LLM Provider 管理
│   └── embedding_manager.py # Embedding 模型管理
├── core/              # 核心模块
│   ├── llm/             # LLM 适配层（base -> factory -> provider）
│   ├── conversation.py # 对话持久化（SQLite）
│   ├── session_manager.py  # 会话管理
│   ├── embedding.py   # Embedding 服务
│   └── vector_search.py    # 向量检索
├── logger/            # 日志系统（含 WebSocket 实时推送）
└── data/              # 运行时数据（gitignore）
    ├── conversations.db
    ├── config.json
    └── logs/
```

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **LLM 调用**: HTTP API（通过 LLM 适配层 `core/llm/` 对接多厂商）
- **向量检索**: sentence-transformers + SQLite
- **日志**: Python logging + WebSocket 实时推送
