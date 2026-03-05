"""
pytest 全局配置和共享 fixtures
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    """FastAPI 测试客户端"""
    from backend.api.server import app
    return TestClient(app)
