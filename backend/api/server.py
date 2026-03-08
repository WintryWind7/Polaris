"""
FastAPI 服务器

提供 HTTP API 供前端（Electron、QQ Bot 等）调用。
生产模式下也提供前端静态文件服务。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import os

from ..agents.main_agent import MainAgent
from ..agents.heartbeat_agent import HeartbeatAgent
from ..agents.memory import MemorySystem
from ..core.state import StateManager
from ..agents.tools import ToolRegistry
from ..config.settings import get_settings
from .routes import config, providers, chat, agent, health
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
app.include_router(agent.router)
app.include_router(health.router)

# 前端静态文件路径
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@app.get("/")
async def root():
    """根路径"""
    return {"message": "Polaris API is running"}


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
