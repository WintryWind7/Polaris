"""
配置管理

管理 API keys、用户偏好等配置。
使用 ConfigManager 和 ProviderManager 分离管理。
"""
from pathlib import Path
from typing import Dict, Optional, Tuple
from backend.config.manager import ConfigManager
from backend.config.provider_manager import ProviderManager
from backend.logger import get_logger

logger = get_logger(__name__)

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

    def resolve_agent_model(self, agent_name: str) -> Tuple[str, str, str, str, bool, str]:
        """
        按 agent_name 解析模型配置（含降级链）。

        降级链：
        - 子 Agent: subagent_models[name] → main_model → fallback_model → 报错
        - 主 Agent: main_model → fallback_model → 报错

        Returns:
            (model_id, api_key, api_base_url, api_format, thinking, reasoning_effort)

        Raises:
            ValueError: 无可用模型配置
        """
        agent_config = config_manager.get("agent")
        is_main = (agent_name == "main")

        # 1. 查 agent 自己的配置
        if is_main:
            own_ref = agent_config.get("main_model")
        else:
            own_ref = agent_config.get("subagent_models", {}).get(agent_name)

        if own_ref:
            result = self._resolve_ref(own_ref)
            if result:
                return result
            logger.warning(f"Agent '{agent_name}' 的模型配置无效，开始降级")

        # 2. 子 Agent 降级到 main_model
        if not is_main:
            main_ref = agent_config.get("main_model")
            if main_ref:
                result = self._resolve_ref(main_ref)
                if result:
                    logger.warning(f"Agent '{agent_name}' 降级到主 Agent 模型")
                    return result

        # 3. 降级到 fallback_model
        fallback_ref = agent_config.get("fallback_model")
        if fallback_ref:
            result = self._resolve_ref(fallback_ref)
            if result:
                logger.warning(f"Agent '{agent_name}' 降级到备选模型")
                return result

        # 4. 无可用配置
        raise ValueError(f"Agent '{agent_name}' 无可用模型配置，请在设置中配置模型")

    def _resolve_ref(self, ref: Dict) -> Optional[Tuple[str, str, str, str, bool, str]]:
        """
        从 provider_manager 查找模型配置。

        Returns:
            (model_id, api_key, api_base_url, api_format, thinking, reasoning_effort) 或 None
        """
        provider_id = ref.get("provider_id", "")
        model_id = ref.get("model_id", "")

        if not provider_id or not model_id:
            return None

        provider = provider_manager.get_provider(provider_id)
        if not provider:
            logger.warning(f"Provider '{provider_id}' 不存在")
            return None

        model_config = next((m for m in provider.models if m.model_id == model_id), None)
        if not model_config:
            logger.warning(f"Model '{model_id}' 不在 Provider '{provider_id}' 中")
            return None

        return (
            model_id, provider.api_key, provider.api_base_url, provider.api_format,
            model_config.thinking, model_config.reasoning_effort
        )


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
