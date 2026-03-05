"""
使用 TestClient 测试 Provider API

不需要启动真实的服务器，直接测试 FastAPI 应用
"""
import pytest
from fastapi.testclient import TestClient
from backend.api.server import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.mark.integration
class TestProviderAPI:
    """Provider API 集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """设置测试环境"""
        self.client = client
        self.provider_id = "test_provider_123"

        yield

        # 清理：删除测试 Provider
        try:
            self.client.delete(f"/api/providers/{self.provider_id}")
        except:
            pass

    def test_add_provider(self):
        """测试添加 Provider"""
        payload = {
            "provider_id": self.provider_id,
            "api_key": "sk-test-key-12345",
            "api_base_url": "https://api.test.com",
            "models": [
                {
                    "model_id": "test-model-1",
                    "display_name": "测试模型 1"
                }
            ]
        }

        response = self.client.post("/api/providers", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["provider_id"] == self.provider_id

    def test_get_provider(self):
        """测试获取 Provider"""
        # 先添加
        payload = {
            "provider_id": self.provider_id,
            "api_key": "sk-test-key-12345",
            "api_base_url": "https://api.test.com",
            "models": []
        }
        self.client.post("/api/providers", json=payload)

        # 获取
        response = self.client.get(f"/api/providers/{self.provider_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["provider_id"] == self.provider_id
        # API Key 应该被脱敏
        assert "***" in data["api_key"]
        assert data["api_key"] != "sk-test-key-12345"

    def test_update_provider(self):
        """测试更新 Provider"""
        # 先添加
        payload = {
            "provider_id": self.provider_id,
            "api_key": "sk-old-key",
            "api_base_url": "https://api.old.com",
            "models": []
        }
        self.client.post("/api/providers", json=payload)

        # 更新
        update_payload = {
            "api_key": "sk-new-key-67890",
            "api_base_url": "https://api.new.com",
            "models": [
                {
                    "model_id": "new-model",
                    "display_name": "新模型"
                }
            ]
        }
        response = self.client.put(
            f"/api/providers/{self.provider_id}",
            json=update_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # 验证更新
        get_response = self.client.get(f"/api/providers/{self.provider_id}")
        updated_data = get_response.json()
        assert updated_data["api_base_url"] == "https://api.new.com"
        assert len(updated_data["models"]) == 1
        assert updated_data["models"][0]["model_id"] == "new-model"

    def test_delete_provider(self):
        """测试删除 Provider"""
        # 先添加
        payload = {
            "provider_id": self.provider_id,
            "api_key": "sk-test-key",
            "api_base_url": "https://api.test.com",
            "models": []
        }
        self.client.post("/api/providers", json=payload)

        # 删除
        response = self.client.delete(f"/api/providers/{self.provider_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # 验证已删除
        get_response = self.client.get(f"/api/providers/{self.provider_id}")
        assert get_response.status_code == 404

    def test_get_all_providers(self):
        """测试获取所有 Providers"""
        response = self.client.get("/api/providers")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
