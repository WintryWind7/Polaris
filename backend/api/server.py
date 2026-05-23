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
from ..core.session_manager import SessionManager
from ..agents.tools import ToolRegistry
from ..config.settings import get_settings
from .routes import config, providers, chat, agent, health, embeddings, workspace, filesystem
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
session_manager = SessionManager()
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
app.include_router(embeddings.router)
app.include_router(filesystem.router)
app.include_router(workspace.router)
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


if __name__ == "__main__":
    import uvicorn
    import subprocess
    import re
    import sys

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
            print("💡 可能是其他程序占用，请检查或运行 python scripts/start_backend.py --clean")
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
            reload_delay=1.0,  # 等文件稳定后再重载，避免编辑器原子保存导致重载失败
            reload_dirs=[
                str(Path(__file__).parent.parent),  # backend 目录
            ],
            reload_excludes=[
                "__pycache__",
                "*.pyc",
                "*.pyo",
                ".git",
                ".pytest_cache",
                "backend/data/*",    # 排除 data 目录下所有文件
                "*.db",             # 排除数据库文件
                "*.db-journal",     # 排除数据库 journal 文件
                "*.log",            # 排除日志文件
            ],
            log_config=None,
            h11_max_incomplete_event_size=65536  # 增加 header 大小限制到 64KB
        )
    else:
        # 生产模式
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_config=None,
            h11_max_incomplete_event_size=65536  # 增加 header 大小限制到 64KB
        )
