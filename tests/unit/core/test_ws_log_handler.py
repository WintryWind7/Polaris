"""
WebSocketLogHandler 单元测试

覆盖以下场景：
1. 日志条目格式是否正确（timestamp / level / name / message）
2. buffer 是否正确存储日志
3. buffer 满时是否按 FIFO 淘汰旧条目
4. 新连接是否收到完整的历史 buffer
5. 新连接后产生的日志是否实时推送到 WebSocket
6. 历史 buffer 不会被重复推送（connect 先历史后注册）
7. 客户端断开后不再接收消息
8. setup_logging() 后 get_ws_log_handler() 可正常访问
"""
import asyncio
import json
import logging
import pytest

from backend.logger import WebSocketLogHandler, setup_logging, get_ws_log_handler


# ── 辅助：模拟 WebSocket 连接 ─────────────────────────────────────────────────

class FakeWebSocket:
    """模拟 FastAPI WebSocket，记录所有 send_text 调用。"""

    def __init__(self, fail_on_send: bool = False):
        self.received: list[dict] = []
        self.fail_on_send = fail_on_send

    async def send_text(self, text: str):
        if self.fail_on_send:
            raise RuntimeError("连接已断开")
        self.received.append(json.loads(text))


def make_record(message: str, level: int = logging.INFO, name: str = "test.module") -> logging.LogRecord:
    """构造一条日志 record。"""
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )
    return record


# ── 1. 日志条目格式 ────────────────────────────────────────────────────────────

class TestLogEntryFormat:

    def test_record_to_dict_has_required_fields(self):
        """序列化后必须包含 timestamp / level / name / message 四个字段。"""
        handler = WebSocketLogHandler()
        record = make_record("hello world")
        data = handler._record_to_dict(record)

        assert "timestamp" in data
        assert "level" in data
        assert "name" in data
        assert "message" in data

    def test_level_name_is_correct(self):
        """level 字段应与 record 的 levelname 一致。"""
        handler = WebSocketLogHandler()
        for level, name in [(logging.DEBUG, "DEBUG"), (logging.WARNING, "WARNING"), (logging.ERROR, "ERROR")]:
            record = make_record("msg", level=level)
            data = handler._record_to_dict(record)
            assert data["level"] == name

    def test_message_content_is_correct(self):
        """message 字段应与原始日志文本完全一致。"""
        handler = WebSocketLogHandler()
        text = "这是一条中文日志消息 with unicode 🚀"
        record = make_record(text)
        data = handler._record_to_dict(record)
        assert data["message"] == text

    def test_name_reflects_logger_name(self):
        """name 字段应与 logger name 一致。"""
        handler = WebSocketLogHandler()
        record = make_record("msg", name="api.server")
        data = handler._record_to_dict(record)
        assert data["name"] == "api.server"


# ── 2. 内存 buffer ────────────────────────────────────────────────────────────

class TestBuffer:

    def test_emit_stores_to_buffer(self):
        """emit 调用后日志应进入 buffer。"""
        handler = WebSocketLogHandler(max_buffer=10)
        handler.emit(make_record("msg1"))
        handler.emit(make_record("msg2"))

        assert len(handler._buffer) == 2
        assert handler._buffer[0]["message"] == "msg1"
        assert handler._buffer[1]["message"] == "msg2"

    def test_buffer_respects_max_size(self):
        """buffer 满后，最旧的条目应被淘汰（FIFO）。"""
        handler = WebSocketLogHandler(max_buffer=3)
        for i in range(5):
            handler.emit(make_record(f"msg{i}"))

        assert len(handler._buffer) == 3
        # buffer 中只保留最后 3 条
        messages = [item["message"] for item in handler._buffer]
        assert messages == ["msg2", "msg3", "msg4"]

    def test_buffer_is_empty_initially(self):
        """新 handler 的 buffer 初始应为空。"""
        handler = WebSocketLogHandler()
        assert len(handler._buffer) == 0


# ── 3. 历史回放（connect 时推送 buffer）─────────────────────────────────────────

class TestHistoryReplay:

    @pytest.mark.asyncio
    async def test_new_connection_receives_history(self):
        """连接建立时，应立即收到 buffer 中的所有历史日志。"""
        handler = WebSocketLogHandler(max_buffer=10)
        # 产生 3 条"历史"日志（此时无连接）
        for i in range(3):
            handler.emit(make_record(f"history_{i}"))

        ws = FakeWebSocket()
        await handler.connect(ws)

        # 应收到全部 3 条历史
        assert len(ws.received) == 3
        for i, item in enumerate(ws.received):
            assert item["message"] == f"history_{i}"

    @pytest.mark.asyncio
    async def test_empty_buffer_sends_nothing_on_connect(self):
        """buffer 为空时，connect 不应推送任何消息。"""
        handler = WebSocketLogHandler()
        ws = FakeWebSocket()
        await handler.connect(ws)
        assert ws.received == []

    @pytest.mark.asyncio
    async def test_connection_registered_after_history(self):
        """connect 结束后，websocket 应在 connections 集合中。"""
        handler = WebSocketLogHandler()
        ws = FakeWebSocket()
        await handler.connect(ws)
        assert ws in handler._connections


# ── 4. 实时推送（emit 后广播）────────────────────────────────────────────────────

class TestRealtimeBroadcast:

    @pytest.mark.asyncio
    async def test_new_log_is_pushed_to_connected_client(self):
        """连接建立后，新产生的日志应实时推送到客户端。"""
        handler = WebSocketLogHandler()
        ws = FakeWebSocket()
        await handler.connect(ws)

        # 直接调用 _broadcast（模拟 emit 在事件循环中的行为）
        data = handler._record_to_dict(make_record("realtime_msg"))
        await handler._broadcast(data)

        assert len(ws.received) == 1
        assert ws.received[0]["message"] == "realtime_msg"

    @pytest.mark.asyncio
    async def test_broadcast_reaches_multiple_clients(self):
        """广播应推送到所有连接的客户端。"""
        handler = WebSocketLogHandler()
        ws1, ws2, ws3 = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
        for ws in (ws1, ws2, ws3):
            await handler.connect(ws)

        data = handler._record_to_dict(make_record("broadcast_test"))
        await handler._broadcast(data)

        for ws in (ws1, ws2, ws3):
            assert any(item["message"] == "broadcast_test" for item in ws.received)

    @pytest.mark.asyncio
    async def test_no_duplicate_history_after_connect(self):
        """connect 后的实时广播，不应让已连接的客户端再次收到历史日志。"""
        handler = WebSocketLogHandler()
        handler.emit(make_record("old_msg"))

        ws = FakeWebSocket()
        await handler.connect(ws)  # 收到 1 条历史

        # 再 broadcast 一条新消息
        data = handler._record_to_dict(make_record("new_msg"))
        await handler._broadcast(data)

        # 总共 2 条：1 条历史 + 1 条新消息
        assert len(ws.received) == 2
        assert ws.received[0]["message"] == "old_msg"
        assert ws.received[1]["message"] == "new_msg"


# ── 5. 断开连接 ───────────────────────────────────────────────────────────────

class TestDisconnect:

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self):
        """disconnect 后，websocket 应从 connections 集合中移除。"""
        handler = WebSocketLogHandler()
        ws = FakeWebSocket()
        await handler.connect(ws)
        assert ws in handler._connections

        await handler.disconnect(ws)
        assert ws not in handler._connections

    @pytest.mark.asyncio
    async def test_broadcast_skips_dead_connection(self):
        """已断开的客户端在广播时抛出异常，应从 connections 中静默移除。"""
        handler = WebSocketLogHandler()
        dead_ws = FakeWebSocket(fail_on_send=True)
        live_ws = FakeWebSocket()

        await handler.connect(dead_ws)
        await handler.connect(live_ws)

        data = handler._record_to_dict(make_record("msg"))
        await handler._broadcast(data)

        # 死亡连接被移除，存活连接收到消息
        assert dead_ws not in handler._connections
        assert len(live_ws.received) == 1

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_is_safe(self):
        """对不存在的 ws 调用 disconnect 不应抛出异常。"""
        handler = WebSocketLogHandler()
        ws = FakeWebSocket()
        await handler.disconnect(ws)  # 不在集合中，应静默


# ── 6. setup_logging 集成 ────────────────────────────────────────────────────

class TestSetupLogging:

    def test_get_ws_log_handler_after_setup(self):
        """调用 setup_logging() 后，get_ws_log_handler() 应返回有效实例。"""
        setup_logging(enable_file=False, enable_console=False)
        handler = get_ws_log_handler()
        assert isinstance(handler, WebSocketLogHandler)

    def test_handler_registered_in_root_logger(self):
        """WebSocketLogHandler 应被注册到 root logger 的 handlers 中。"""
        setup_logging(enable_file=False, enable_console=False)
        root_logger = logging.getLogger()
        ws_handlers = [h for h in root_logger.handlers if isinstance(h, WebSocketLogHandler)]
        assert len(ws_handlers) == 1

    def test_log_via_logger_enters_buffer(self):
        """通过标准 logger 写日志后，应能在 buffer 中找到对应记录。"""
        setup_logging(enable_file=False, enable_console=False)
        handler = get_ws_log_handler()
        handler._buffer.clear()  # 清空旧数据，确保干净

        logger = logging.getLogger("test.integration")
        logger.info("integration_test_message")

        messages = [item["message"] for item in handler._buffer]
        assert "integration_test_message" in messages
