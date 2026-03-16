"""
日志 WebSocket 路由

提供 ws://host/ws/logs 端点，客户端连接后：
1. 立即接收内存 buffer 中的历史日志（回放启动以来的日志）
2. 之后实时接收后端产生的新日志
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .logger import get_ws_log_handler, get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/api/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket 日志流端点。"""
    await websocket.accept()
    handler = get_ws_log_handler()

    # logger.debug(f"日志 WebSocket 客户端连接: {websocket.client}")
    await handler.connect(websocket)

    try:
        # 保持连接活跃，日志会通过 handler._broadcast() 自动推送
        while True:
            await asyncio.sleep(3600)  # 每小时检查一次连接状态
    except WebSocketDisconnect:
        pass
        # logger.debug(f"日志 WebSocket 客户端断开: {websocket.client}")
    finally:
        await handler.disconnect(websocket)
