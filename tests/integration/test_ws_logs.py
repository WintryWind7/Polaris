"""
WebSocket 日志集成测试

需要后端服务已启动。若服务器未运行，所有用例自动 skip。

使用方式：
    1. 启动后端: python -m backend
    2. 打开前端日志页并开启 DEBUG 级别过滤
    3. 在编辑器中运行此文件
    → 测试执行时，前端日志页会实时显示 /health 和 /heartbeat 产生的 DEBUG 日志
"""
import asyncio
import json

import httpx
import pytest
import websockets
from websockets.exceptions import InvalidStatus

from backend.config.settings import get_settings

settings = get_settings()
HTTP_BASE = f"http://{settings.host}:{settings.port}"
WS_URL    = f"ws://{settings.host}:{settings.port}/api/ws/logs"


# ── 服务器可用性检查 ────────────────────────────────────────────────────────────

def _check_server() -> str | None:
    """返回 None 表示服务器可用，否则返回 skip 原因。"""
    try:
        httpx.get(f"{HTTP_BASE}/api/health", timeout=3)
    except (httpx.ConnectError, httpx.TimeoutException):
        return "后端服务器未启动，需先运行: python -m backend"
    return None


_SKIP_REASON = _check_server()
requires_server = pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "")


# ── WebSocket / HTTP 辅助函数 ──────────────────────────────────────────────────

async def _drain(ws, timeout: float = 0.8) -> list[dict]:
    """耗尽 WS 当前已缓冲的所有历史消息。"""
    msgs = []
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msgs.append(json.loads(raw))
    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
        pass
    return msgs


async def _collect(ws, count: int = 30, timeout: float = 3.0) -> list[dict]:
    """收集接下来最多 count 条消息，最多等待 timeout 秒。"""
    msgs = []
    deadline = asyncio.get_event_loop().time() + timeout
    while len(msgs) < count:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            msgs.append(json.loads(raw))
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
            break
    return msgs


async def _get(path: str, timeout: float = 10.0) -> httpx.Response:
    """异步 HTTP GET，避免在 async 上下文中阻塞事件循环。"""
    async with httpx.AsyncClient() as client:
        return await client.get(f"{HTTP_BASE}{path}", timeout=timeout)


def _ws_skip_on_404(e: InvalidStatus):
    """遇到 404（路由未加载）时 skip，其他错误直接 raise。"""
    if "404" in str(e):
        pytest.skip("后端 /api/ws/logs 返回 404，请重启后端以加载新路由。")
    raise e


# ── 集成测试用例 ───────────────────────────────────────────────────────────────

@requires_server
class TestWebSocketLogsIntegration:
    """
    通过真实后端服务器验证 WebSocket 日志流。

    每个 test_ws_receives_* 测试在前端日志页（开启 DEBUG）都能实时看到对应的日志条目。
    """

    @pytest.mark.asyncio
    async def test_ws_connection_and_history(self):
        """连接 /ws/logs 后，应立即收到服务器启动以来的历史日志（buffer 回放）。"""
        try:
            async with websockets.connect(WS_URL) as ws:
                history = await _drain(ws)
        except InvalidStatus as e:
            _ws_skip_on_404(e)

        assert len(history) > 0, "未收到历史日志，buffer 可能为空或路由未正确注册"
        for msg in history:
            for field in ("timestamp", "level", "name", "message"):
                assert field in msg, f"消息缺少字段 {field!r}: {msg}"

    @pytest.mark.asyncio
    async def test_ws_receives_debug_on_health(self):
        """
        调用 GET /health，后端产生一条 DEBUG 日志：
            [DEBUG][health] pid=xxxx python=3.11.x handlers=3

        ✅ 前端日志页开启 DEBUG 过滤后可实时看到这条消息。
        """
        try:
            async with websockets.connect(WS_URL) as ws:
                await _drain(ws)                  # 清空历史，只看新消息
                await _get("/api/health")             # 触发后端 DEBUG 日志
                new_msgs = await _collect(ws)
        except InvalidStatus as e:
            _ws_skip_on_404(e)

        messages_text = [m.get("message", "") for m in new_msgs]
        assert any("[health]" in t for t in messages_text), (
            f"未找到 /health 的 DEBUG 日志\n收到的消息: {messages_text}"
        )

    @pytest.mark.asyncio
    async def test_ws_receives_debug_on_heartbeat(self):
        """
        调用 GET /heartbeat，后端产生两条 DEBUG 日志：
            [DEBUG][heartbeat] 开始执行心跳检查
            [DEBUG][heartbeat] 检查完成: should_wake=False

        ✅ 前端日志页开启 DEBUG 过滤后可实时看到这两条消息。
        """
        try:
            async with websockets.connect(WS_URL) as ws:
                await _drain(ws)
                resp = await _get("/api/heartbeat")
                assert resp.status_code == 200
                new_msgs = await _collect(ws, timeout=5.0)
        except InvalidStatus as e:
            _ws_skip_on_404(e)

        heartbeat_msgs = [m for m in new_msgs if "[heartbeat]" in m.get("message", "")]
        assert len(heartbeat_msgs) >= 2, (
            f"期望至少 2 条 heartbeat DEBUG 日志，实际收到:\n"
            + "\n".join(f"  {m['message']}" for m in new_msgs)
        )

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self):
        """同一条日志应被广播到所有已连接的前端客户端（验证多客户端广播）。"""
        try:
            async with websockets.connect(WS_URL) as ws1:
                async with websockets.connect(WS_URL) as ws2:
                    await _drain(ws1)
                    await _drain(ws2)
                    await _get("/api/heartbeat")
                    msgs1 = await _collect(ws1, timeout=5.0)
                    msgs2 = await _collect(ws2, timeout=5.0)
        except InvalidStatus as e:
            _ws_skip_on_404(e)

        assert len(msgs1) > 0, "客户端 1 未收到任何日志"
        assert len(msgs2) > 0, "客户端 2 未收到任何日志"
        assert {m["message"] for m in msgs1} == {m["message"] for m in msgs2}, (
            "两个客户端收到的日志内容不一致"
        )
