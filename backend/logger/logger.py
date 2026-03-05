"""
日志系统

统一的日志配置，支持：
- 自动去除 backend. 前缀
- 按日期轮转
- 控制台 + 文件双输出
- 开发/生产环境不同级别
- WebSocket 实时日志推送
"""
import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from typing import Optional


class ModuleNameFilter(logging.Filter):
    """过滤器：去除模块名中的 backend. / tests. 前缀"""

    def filter(self, record):
        if record.name.startswith('backend.'):
            record.name = record.name[8:]  # 去掉 'backend.'
        elif record.name.startswith('tests.'):
            record.name = record.name[6:]  # 去掉 'tests.'
        return True


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台格式化器（仅开发环境）"""

    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'

    def format(self, record):
        # 添加颜色
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        result = super().format(record)

        # 恢复原始 levelname（避免影响其他 handler）
        record.levelname = levelname
        return result


def setup_logging(
    log_dir: Optional[Path] = None,
    level: str = "INFO",
    enable_console: bool = True,
    enable_file: bool = True,
    enable_color: bool = True,
    max_ws_buffer: int = 500,
):
    """
    配置全局日志系统

    Args:
        log_dir: 日志文件目录（默认为 data/logs）
        level: 日志级别（DEBUG/INFO/WARNING/ERROR）
        enable_console: 是否输出到控制台
        enable_file: 是否输出到文件
        enable_color: 是否启用控制台颜色（仅开发环境）
        max_ws_buffer: WebSocket 内存 buffer 上限（条数）
    """
    # 获取根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 根 logger 设为最低级别

    # 清除已有的 handlers
    root_logger.handlers.clear()

    # 添加模块名过滤器
    module_filter = ModuleNameFilter()

    # 日志格式
    console_format = '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
    file_format = '[%(asctime)s][%(name)s][%(levelname)s][%(funcName)s:%(lineno)d] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # 控制台 Handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.addFilter(module_filter)

        if enable_color:
            console_formatter = ColoredFormatter(console_format, datefmt=date_format)
        else:
            console_formatter = logging.Formatter(console_format, datefmt=date_format)

        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # 文件 Handler（按天轮转）
    if enable_file:
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / "data" / "logs"

        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "polaris.log"

        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',      # 每天午夜轮转
            interval=1,           # 间隔 1 天
            backupCount=30,       # 保留 30 天
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
        file_handler.addFilter(module_filter)
        file_handler.setFormatter(logging.Formatter(file_format, datefmt=date_format))

        root_logger.addHandler(file_handler)

    # WebSocket Handler（始终注册，捕获所有日志到内存 buffer）
    global _ws_log_handler
    _ws_log_handler = WebSocketLogHandler(max_buffer=max_ws_buffer)
    _ws_log_handler.setLevel(logging.DEBUG)
    _ws_log_handler.addFilter(module_filter)
    root_logger.addHandler(_ws_log_handler)

    # 设置第三方库的日志级别（避免过多噪音）
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取 logger 实例

    Args:
        name: 模块名（通常使用 __name__）

    Returns:
        Logger 实例

    Example:
        logger = get_logger(__name__)
        logger.info("这是一条日志")
    """
    return logging.getLogger(name)


# 便捷函数：直接使用模块名创建 logger
def create_logger(module_name: str) -> logging.Logger:
    """
    创建 logger（别名函数）

    Args:
        module_name: 模块名

    Returns:
        Logger 实例
    """
    return get_logger(module_name)


# ── WebSocket 日志推送 ─────────────────────────────────────────────────────────

import asyncio
import json
from collections import deque
from typing import Set


class WebSocketLogHandler(logging.Handler):
    """
    将日志实时推送到所有已连接的 WebSocket 客户端。

    - 内部维护一个大小为 max_buffer 的循环队列，用于缓存最近的日志。
    - 新 WebSocket 连接接入时，先批量推送 buffer 中的历史日志。
    - 之后每条新日志都会实时广播给所有连接。
    """

    def __init__(self, max_buffer: int = 500):
        super().__init__()
        self._buffer: deque = deque(maxlen=max_buffer)
        self._connections: Set = set()
        self._lock = asyncio.Lock()
        # 格式化器（和文件 handler 保持一致）
        fmt = '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
        self.setFormatter(logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S'))

    def _record_to_dict(self, record: logging.LogRecord) -> dict:
        """将 LogRecord 序列化为可 JSON 化的 dict。"""
        return {
            "timestamp": self.formatter.formatTime(record, '%Y-%m-%d %H:%M:%S'),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

    def emit(self, record: logging.LogRecord):
        """同步调用（logging 框架入口），存 buffer 并异步广播。"""
        try:
            data = self._record_to_dict(record)
            self._buffer.append(data)
            # 尝试在当前事件循环中异步广播
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._broadcast(data))
            except RuntimeError:
                pass  # 没有运行中的事件循环（启动阶段），仅存 buffer
        except Exception:
            self.handleError(record)

    async def _broadcast(self, data: dict):
        """向所有已连接的 WebSocket 推送一条日志。"""
        if not self._connections:
            return
        message = json.dumps(data, ensure_ascii=False)
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        # 清理断开的连接
        if dead:
            async with self._lock:
                self._connections -= dead

    async def connect(self, websocket) -> None:
        """
        新客户端连接时调用：
        1. 先批量推送 buffer 中的历史日志（初始化回放）。
        2. 再注册到广播集合。
        """
        # 先推历史，再注册，避免 emit 和 connect 竞态导致重复
        history = list(self._buffer)
        try:
            for item in history:
                await websocket.send_text(json.dumps(item, ensure_ascii=False))
        except Exception:
            return
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket) -> None:
        """客户端断开时调用。"""
        async with self._lock:
            self._connections.discard(websocket)


# 全局单例
_ws_log_handler: WebSocketLogHandler | None = None


def get_ws_log_handler() -> WebSocketLogHandler:
    """返回全局 WebSocketLogHandler 单例（需先调用 setup_logging）。"""
    global _ws_log_handler
    if _ws_log_handler is None:
        raise RuntimeError("WebSocketLogHandler 尚未初始化，请先调用 setup_logging()。")
    return _ws_log_handler
