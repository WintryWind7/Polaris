"""
配置管理器

单例模式的配置管理类，负责：
- 配置文件的加载、保存、热更新
- 配置完整性检查和自动补全
- API Key 脱敏
- 线程安全的配置访问
"""
import json
import shutil
import threading
from pathlib import Path
from typing import Any, Optional

from backend.config.models import AppConfig, ProviderConfig


class ConfigManager:
    """配置管理器（单例）"""

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        if hasattr(self, "_initialized"):
            return

        self.project_root = Path(__file__).parent.parent.parent
        self.data_dir = self.project_root / "data"
        self.config_file = self.data_dir / "config.json"
        self.template_file = self.project_root / "backend" / "config" / "templates" / "config.template.json"

        self._config: Optional[AppConfig] = None
        self._config_lock = threading.Lock()

        # 确保配置文件存在并加载
        self._ensure_config_exists()
        self.load_config()

        self._initialized = True

    def _ensure_config_exists(self) -> None:
        """确保配置文件存在，不存在则从模板创建"""
        # 确保 data 目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 如果配置文件不存在，从模板复制
        if not self.config_file.exists():
            if not self.template_file.exists():
                raise FileNotFoundError(f"配置模板文件不存在: {self.template_file}")

            shutil.copy(self.template_file, self.config_file)
            print(f"[ConfigManager] 首次运行：已从模板创建配置文件 {self.config_file}")

    def _load_template(self) -> dict:
        """加载配置模板"""
        with open(self.template_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_config(self) -> AppConfig:
        """从文件加载配置"""
        with self._config_lock:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # 配置完整性检查
            template_data = self._load_template()
            has_changes = self._check_integrity(config_data, template_data)

            if has_changes:
                # 自动补全缺失项并保存
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                print("[ConfigManager] 配置完整性检查：已自动补全缺失项")

            # 验证并加载配置
            self._config = AppConfig(**config_data)
            return self._config

    def _check_integrity(self, user_config: dict, template_config: dict) -> bool:
        """
        检查配置完整性，自动补全缺失项

        Args:
            user_config: 用户配置（会被修改）
            template_config: 模板配置

        Returns:
            是否有变更
        """
        has_changes = False

        for key, default_value in template_config.items():
            if key not in user_config:
                # 缺失项：插入默认值
                user_config[key] = default_value
                has_changes = True
            elif isinstance(default_value, dict):
                # 递归检查嵌套字典
                if not isinstance(user_config[key], dict):
                    user_config[key] = default_value
                    has_changes = True
                else:
                    has_changes |= self._check_integrity(user_config[key], default_value)

        return has_changes

    def save_config(self) -> None:
        """保存配置到文件"""
        with self._config_lock:
            if self._config is None:
                raise RuntimeError("配置未加载")

            config_data = self._config.model_dump()
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

    def get(self, key_path: str) -> Any:
        """
        获取配置项（支持点号路径）

        Args:
            key_path: 配置路径，如 "llm.default_model"

        Returns:
            配置值
        """
        if self._config is None:
            raise RuntimeError("配置未加载")

        keys = key_path.split(".")
        value = self._config.model_dump()

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                raise KeyError(f"无效的配置路径: {key_path}")

        return value

    def update(self, updates: dict) -> None:
        """
        更新配置项（支持部分更新）

        Args:
            updates: 要更新的配置项
        """
        with self._config_lock:
            if self._config is None:
                raise RuntimeError("配置未加载")

            # 获取当前配置
            config_data = self._config.model_dump()

            # 深度合并更新
            self._deep_merge(config_data, updates)

            # 验证并保存
            self._config = AppConfig(**config_data)
            self.save_config()

    def _deep_merge(self, target: dict, source: dict) -> None:
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def reload(self) -> None:
        """重新加载配置"""
        self.load_config()
        print("[ConfigManager] 配置已重新加载")

    def get_masked_config(self) -> dict:
        """获取脱敏配置（API Key 显示为 ***...***）"""
        if self._config is None:
            raise RuntimeError("配置未加载")

        config_data = self._config.model_dump()

        # 脱敏所有 provider 的 API Key
        if "llm" in config_data and "providers" in config_data["llm"]:
            for provider_name, provider_config in config_data["llm"]["providers"].items():
                if "api_key" in provider_config:
                    provider_config["api_key"] = self._mask_api_key(provider_config["api_key"])

        return config_data

    @staticmethod
    def _mask_api_key(key: str) -> str:
        """
        脱敏 API Key

        - 空字符串 → ""
        - 短于 8 字符 → "***"
        - 正常长度 → "sk-***...***e1"（保留前3后2）
        """
        if not key:
            return ""
        if len(key) < 8:
            return "***"
        return f"{key[:3]}***...***{key[-2:]}"
