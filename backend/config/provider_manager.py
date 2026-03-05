"""
Provider 配置管理器

管理 LLM 提供商的增删改查，配置存储在 data/providers.json
"""
import json
import threading
from pathlib import Path
from typing import Optional
from backend.config.models import ProviderConfig, ModelConfig


class ProviderManager:
    """Provider 配置管理器（单例）"""

    _instance: Optional["ProviderManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self.project_root = Path(__file__).parent.parent.parent
        self.data_dir = self.project_root / "data"
        self.providers_file = self.data_dir / "providers.json"

        self._providers: dict[str, ProviderConfig] = {}
        self._operation_lock = threading.Lock()

        # 确保配置文件存在并加载
        self._ensure_file_exists()
        self.load_providers()

        self._initialized = True

    def _ensure_file_exists(self) -> None:
        """确保配置文件存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.providers_file.exists():
            # 创建空的 providers 配置
            with open(self.providers_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
            print(f"[ProviderManager] 已创建 providers 配置文件: {self.providers_file}")

    def load_providers(self) -> dict[str, ProviderConfig]:
        """加载所有 providers"""
        with self._operation_lock:
            with open(self.providers_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._providers = {}
            for provider_id, provider_data in data.items():
                # 兼容旧字段名：api_base -> api_base_url
                if "api_base" in provider_data and "api_base_url" not in provider_data:
                    provider_data["api_base_url"] = provider_data.pop("api_base")

                # 删除已废弃的字段
                provider_data.pop("provider_type", None)
                provider_data.pop("display_name", None)

                # 转换 models 列表
                if "models" in provider_data:
                    provider_data["models"] = [
                        ModelConfig(**m) if isinstance(m, dict) else m
                        for m in provider_data["models"]
                    ]
                self._providers[provider_id] = ProviderConfig(**provider_data)

            return self._providers

    def save_providers(self) -> None:
        """保存所有 providers"""
        with self._operation_lock:
            self._save_providers_unsafe()

    def _save_providers_unsafe(self) -> None:
        """保存所有 providers（不加锁，内部使用）"""
        data = {}
        for provider_id, provider in self._providers.items():
            data[provider_id] = provider.model_dump()

        with open(self.providers_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_all_providers(self) -> dict[str, ProviderConfig]:
        """获取所有 providers"""
        return self._providers.copy()

    def get_provider(self, provider_id: str) -> Optional[ProviderConfig]:
        """获取指定 provider"""
        return self._providers.get(provider_id)

    def add_provider(self, provider: ProviderConfig) -> None:
        """添加 provider"""
        with self._operation_lock:
            if provider.provider_id in self._providers:
                raise ValueError(f"Provider ID '{provider.provider_id}' 已存在")

            self._providers[provider.provider_id] = provider
            self._save_providers_unsafe()

    def generate_unique_id(self, base_id: str) -> str:
        """
        生成唯一的 provider_id

        如果 base_id 已存在，自动添加 _1, _2, ... 后缀
        """
        if base_id not in self._providers:
            return base_id

        counter = 1
        while f"{base_id}_{counter}" in self._providers:
            counter += 1

        return f"{base_id}_{counter}"

    def update_provider(self, provider_id: str, updates: dict) -> None:
        """更新 provider"""
        with self._operation_lock:
            if provider_id not in self._providers:
                raise ValueError(f"Provider ID '{provider_id}' 不存在")

            provider = self._providers[provider_id]
            provider_data = provider.model_dump()

            # 深度合并更新
            self._deep_merge(provider_data, updates)

            # 转换 models
            if "models" in provider_data:
                provider_data["models"] = [
                    ModelConfig(**m) if isinstance(m, dict) else m
                    for m in provider_data["models"]
                ]

            self._providers[provider_id] = ProviderConfig(**provider_data)
            self._save_providers_unsafe()

    def delete_provider(self, provider_id: str) -> None:
        """删除 provider"""
        with self._operation_lock:
            if provider_id not in self._providers:
                raise ValueError(f"Provider ID '{provider_id}' 不存在")

            del self._providers[provider_id]
            self._save_providers_unsafe()


    @staticmethod
    def _deep_merge(target: dict, source: dict) -> None:
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                ProviderManager._deep_merge(target[key], value)
            else:
                target[key] = value
