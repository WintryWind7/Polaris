"""
API 健康检查测试

测试后端服务是否正常运行并响应
"""
import pytest
import httpx
from backend.config.settings import get_settings


@pytest.mark.integration
class TestAPIHealth:
    """API 健康检查测试"""

    def test_api_server_responds(self):
        """测试后端服务是否响应（需要先启动后端）"""
        settings = get_settings()
        url = f"http://{settings.host}:{settings.port}/api/health"

        try:
            response = httpx.get(url, timeout=5)
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
        except httpx.ConnectError:
            pytest.skip("后端服务未启动，跳过测试")
