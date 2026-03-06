"""
配置管理

管理 API keys、用户偏好等配置。
使用 ConfigManager 和 ProviderManager 分离管理。
"""
from pathlib import Path
from backend.config.manager import ConfigManager
from backend.config.provider_manager import ProviderManager

# 全局配置管理器实例
config_manager = ConfigManager()
provider_manager = ProviderManager()


class Settings:
    """应用配置"""

    @property
    def data_dir(self) -> Path:
        """数据目录"""
        return config_manager.data_dir

    @property
    def host(self) -> str:
        """服务器主机"""
        return config_manager.get("server.host")

    @property
    def port(self) -> int:
        """服务器端口"""
        return config_manager.get("server.port")

    @property
    def system_prompt(self) -> str:
        """系统提示词"""
        return config_manager.get("agent.system_prompt")

    # ===== 临时兼容方法（等 Agent 重构后删除）=====
    @property
    def dashscope_api_key(self) -> str:
        """临时兼容：返回第一个 provider 的 api_key（实时从文件读取）"""
        providers = provider_manager.load_providers()
        if providers:
            first_provider = next(iter(providers.values()))
            return first_provider.api_key
        return ""

    @property
    def dashscope_api_base(self) -> str:
        """临时兼容：返回第一个 provider 的 api_base_url（实时从文件读取）"""
        providers = provider_manager.load_providers()
        if providers:
            first_provider = next(iter(providers.values()))
            return first_provider.api_base_url
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
