"""
API 集成测试

测试完整的对话 API 流程
需要先启动服务：python main.py --dev
"""
import pytest
import httpx


BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture
async def client():
    """HTTP 客户端 fixture"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.mark.asyncio
class TestHealthAPI:
    """测试健康检查 API"""

    async def test_health_check(self, client):
        """测试健康检查端点"""
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "pid" in data


@pytest.mark.asyncio
class TestChatAPI:
    """测试对话 API"""

    async def test_chat_without_session(self, client):
        """测试不带 session_id 的对话（创建新会话）"""
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "你好"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert "timestamp" in data
        assert "session_id" in data
        assert data["session_id"] is not None

    async def test_chat_with_session(self, client):
        """测试带 session_id 的对话（多轮对话）"""
        # 第一轮：创建会话
        response1 = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "你好"}
        )
        data1 = response1.json()
        session_id = data1["session_id"]

        # 第二轮：使用相同会话
        response2 = await client.post(
            f"{BASE_URL}/chat",
            json={
                "message": "我叫张三",
                "session_id": session_id
            }
        )

        assert response2.status_code == 200
        data2 = response2.json()

        # 验证返回相同的 session_id
        assert data2["session_id"] == session_id
        assert "message" in data2

    async def test_multi_turn_conversation(self, client):
        """测试多轮对话上下文"""
        # 第一轮
        response1 = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "你好"}
        )
        session_id = response1.json()["session_id"]

        # 第二轮
        response2 = await client.post(
            f"{BASE_URL}/chat",
            json={
                "message": "我叫张三",
                "session_id": session_id
            }
        )
        assert response2.status_code == 200

        # 第三轮：测试上下文记忆
        response3 = await client.post(
            f"{BASE_URL}/chat",
            json={
                "message": "我叫什么名字？",
                "session_id": session_id
            }
        )

        assert response3.status_code == 200
        data3 = response3.json()

        # 注意：这里只验证 API 正常工作
        # 是否真的记住名字取决于 LLM 的回复
        assert "message" in data3
        assert data3["session_id"] == session_id

    async def test_session_isolation(self, client):
        """测试会话隔离"""
        # 创建第一个会话
        response1 = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "我是用户A"}
        )
        session_id_1 = response1.json()["session_id"]

        # 创建第二个会话
        response2 = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "我是用户B"}
        )
        session_id_2 = response2.json()["session_id"]

        # 验证两个会话 ID 不同
        assert session_id_1 != session_id_2

    async def test_invalid_message(self, client):
        """测试无效消息"""
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": ""}  # 空消息
        )

        # 应该返回错误或处理空消息
        # 具体行为取决于后端实现
        assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
class TestTimelineAPI:
    """测试时间线 API"""

    async def test_get_timeline(self, client):
        """测试获取时间线"""
        response = await client.get(f"{BASE_URL}/timeline?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert "events" in data
        assert isinstance(data["events"], list)
