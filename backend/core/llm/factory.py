"""
LLM 工厂类
"""
from typing import Dict, Optional
from .base import LLMProvider
from .provider import OpenAICompatibleProvider
from ...logger import get_logger

logger = get_logger(__name__)


class LLMFactory:
    """LLM 工厂类（支持单例缓存）"""

    _cache: Dict[str, LLMProvider] = {}
    _cache_keys: Dict[str, tuple] = {}

    @classmethod
    def get_provider(
        cls,
        model: str,
        api_key: str,
        api_base: Optional[str] = None,
        api_format: str = "openai",
        thinking: bool = False,
        reasoning_effort: str = "",
        preserve_reasoning: bool = False
    ) -> LLMProvider:
        """
        获取 LLM 提供商（单例模式，配置变更时自动重建）

        Args:
            model: 模型名称（直接传给 API，如 "qwen3.5-plus"、"deepseek-v4"）
            api_key: API Key
            api_base: API 基础地址
            api_format: API 格式，"openai" 或 "anthropic"
            thinking: 是否启用思考模式
            reasoning_effort: 推理强度
            preserve_reasoning: 多轮历史中是否保留 reasoning_content

        Returns:
            LLM 提供商实例
        """
        config_key = (model, api_key, api_base, api_format, thinking, reasoning_effort, preserve_reasoning)

        if model in cls._cache:
            if cls._cache_keys.get(model) == config_key:
                return cls._cache[model]
            else:
                logger.info(f"配置变更，重建 Provider: model={model}")

        provider = cls._create_provider(model, api_key, api_base, api_format, thinking, reasoning_effort, preserve_reasoning)
        cls._cache[model] = provider
        cls._cache_keys[model] = config_key

        return provider

    @staticmethod
    def _create_provider(
        model: str,
        api_key: str,
        api_base: Optional[str] = None,
        api_format: str = "openai",
        thinking: bool = False,
        reasoning_effort: str = "",
        preserve_reasoning: bool = False
    ) -> LLMProvider:
        """根据 api_format 创建对应 Provider 实例"""
        if api_format == "anthropic":
            raise NotImplementedError("Anthropic 格式 Provider 尚未实现")

        logger.info(f"创建 OpenAI 兼容 Provider: model={model}, api_base={api_base}, thinking={thinking}")
        return OpenAICompatibleProvider(
            api_key=api_key,
            model=model,
            api_base=api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            thinking=thinking,
            reasoning_effort=reasoning_effort,
            preserve_reasoning=preserve_reasoning
        )

    @classmethod
    def clear_cache(cls):
        """清空缓存（用于测试或强制重建）"""
        logger.debug("清空 Provider 缓存")
        cls._cache.clear()
        cls._cache_keys.clear()
