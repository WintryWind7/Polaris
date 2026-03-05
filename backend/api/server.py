"""
FastAPI 服务器

提供 HTTP API 供前端（Electron、QQ Bot 等）调用。
生产模式下也提供前端静态文件服务。
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import os
import sys
import logging

from ..agents.main_agent import MainAgent
from ..agents.heartbeat_agent import HeartbeatAgent
from ..core.memory import MemorySystem
from ..core.state import StateManager
from ..core.tools import ToolRegistry
from ..config.settings import get_settings
from .routes import config, providers, chat
from ..logger import setup_logging, get_logger, logger_router

# 初始化日志系统
log_level = os.environ.get("POLARIS_LOG_LEVEL", "INFO")
is_dev = os.environ.get("POLARIS_RELOAD") == "1"
setup_logging(
    level=log_level,
    enable_console=True,
    enable_file=True,
    enable_color=is_dev  # 开发模式启用颜色
)

logger = get_logger(__name__)

# 初始化配置
settings = get_settings()
logger.info(f"配置加载完成: host={settings.host}, port={settings.port}")

# 初始化核心组件
logger.info("初始化核心组件...")
memory_system = MemorySystem(settings.data_dir)
state_manager = StateManager(settings.data_dir / "state.json")
tool_registry = ToolRegistry()
logger.info("核心组件初始化完成")

# 初始化 Agent
logger.info("初始化 Agent...")
main_agent = MainAgent()
heartbeat_agent = HeartbeatAgent()
logger.info("Agent 初始化完成")

# 创建 FastAPI 应用
app = FastAPI(title="Polaris API", version="0.1.0")
logger.info("FastAPI 应用创建完成")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(config.router)
app.include_router(providers.router)
app.include_router(logger_router)
app.include_router(chat.router)

# 前端静态文件路径
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


# 请求模型
class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: Optional[str] = None  # 会话 ID
    context: Optional[Dict[str, Any]] = None  # 上下文（预留）


class ChatResponse(BaseModel):
    """对话响应"""
    message: str
    timestamp: str
    session_id: Optional[str] = None  # 返回会话 ID


class SkillLearningRequest(BaseModel):
    """技能学习请求"""
    description: str


# API 路由
@app.get("/")
async def root():
    """根路径"""
    return {"message": "Polaris API is running"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    对话接口

    Args:
        request: 对话请求

    Returns:
        对话响应
    """
    logger.info(f"收到对话请求: session={request.session_id}, message={request.message[:50]}...")
    try:
        # 调用主 Agent
        result = await main_agent.execute({
            "type": "chat",
            "data": {
                "user_message": request.message,
                "session_id": request.session_id,
                "context": request.context or {}
            }
        })

        # 注意：不再需要手动调用 memory_system.add_chat()
        # 因为 ConversationManager 已经处理了消息保存

        logger.info(f"对话处理完成: session={result.get('session_id')}")
        return ChatResponse(
            message=result["assistant_message"],
            timestamp=result["timestamp"],
            session_id=result.get("session_id")
        )
    except Exception as e:
        logger.error(f"对话处理失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/learn-skill")
async def learn_skill(request: SkillLearningRequest):
    """
    学习技能接口

    Args:
        request: 技能学习请求

    Returns:
        学习结果
    """
    logger.info(f"收到技能学习请求: {request.description[:50]}...")
    try:
        result = await main_agent.execute({
            "type": "learn_skill",
            "data": {"description": request.description}
        })
        logger.info("技能学习完成")
        return result
    except Exception as e:
        logger.error(f"技能学习失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/timeline")
async def get_timeline(limit: int = 10):
    """
    获取时间线

    Args:
        limit: 返回数量

    Returns:
        时间线事件列表
    """
    events = memory_system.get_recent_chats(limit)
    return {
        "events": [event.to_dict() for event in events]
    }


@app.get("/api/heartbeat")
async def heartbeat_check():
    """
    心跳检查接口

    Returns:
        心跳状态
    """
    logger.debug("[heartbeat] 开始执行心跳检查")
    result = await heartbeat_agent.execute({})
    logger.debug(f"[heartbeat] 检查完成: should_wake={result.get('should_wake')}")
    return result


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "reload": os.environ.get("POLARIS_RELOAD") == "1",
        "dev": os.environ.get("POLARIS_DEV") == "1"
    }


# 生产模式：提供前端静态文件
if FRONTEND_DIST.exists():
    # 挂载静态文件目录
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/app")
    async def serve_frontend():
        """提供前端页面"""
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/app/{full_path:path}")
    async def serve_frontend_routes(full_path: str):
        """处理前端路由（SPA）"""
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # 如果文件不存在，返回 index.html（SPA 路由）
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn
    import subprocess
    import re

    # 检查端口是否已被占用
    def check_port_occupied(port):
        """检查端口是否被占用"""
        try:
            if sys.platform == 'win32':
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True,
                    encoding='gbk',
                    errors='ignore'
                )
                pattern = rf'[:\s]{port}\s+.*LISTENING\s+(\d+)'
                match = re.search(pattern, result.stdout)
                if match:
                    return True, int(match.group(1))
            else:
                result = subprocess.run(
                    ['lsof', '-i', f':{port}', '-t'],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    return True, int(result.stdout.strip().split()[0])
        except Exception:
            pass
        return False, None

    def check_backend_alive(port):
        """通过 API 检查后端是否存活"""
        try:
            import urllib.request
            import json
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    if data.get("status") == "healthy":
                        return True, data.get("pid"), data.get("reload", False), data.get("dev", False)
        except Exception:
            pass
        return False, None, False, False

    # 检查端口
    is_occupied, pid = check_port_occupied(settings.port)
    if is_occupied:
        # 尝试通过 API 确认是否是 Polaris 后端
        b_alive, b_pid, b_hot, b_dev = check_backend_alive(settings.port)
        if b_alive:
            hot_tag = " (热重载)" if b_hot else ""
            mode_tag = " [开发模式]" if b_dev else " [生产模式]"
            print(f"⚠️  后端已在运行{hot_tag}{mode_tag}")
            print(f"    http://127.0.0.1:{settings.port}")
            print(f"    PID: {b_pid}")
            print("💡 后端支持热重载，无需重启")
        else:
            print(f"⚠️  端口 {settings.port} 已被占用 (PID: {pid})")
            print("💡 可能是其他程序占用，请检查或运行 python main.py --clean")
        sys.exit(1)

    # 检查是否开启热重载（通过环境变量）
    reload_enabled = os.environ.get("POLARIS_RELOAD") == "1"

    logger.info(f"启动 Polaris 服务器: {settings.host}:{settings.port} (热重载={'开启' if reload_enabled else '关闭'})")

    if reload_enabled:
        # 热重载模式：必须使用字符串导入路径
        # 仅监听 backend 目录
        uvicorn.run(
            "backend.api.server:app",
            host=settings.host,
            port=settings.port,
            reload=True,
            reload_dirs=[
                str(Path(__file__).parent.parent),  # backend 目录
            ],
            reload_excludes=[
                "__pycache__",
                "*.pyc",
                "*.pyo",
                ".git",
                ".pytest_cache",
                "data"
            ],
            log_config=None
        )
    else:
        # 生产模式
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_config=None
        )
