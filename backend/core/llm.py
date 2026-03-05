"""
LLM 抽象层

封装不同 LLM 提供商的 API 调用，支持阿里云百炼、Claude 等。
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Optional
from enum import Enum
import httpx
from ..logger import get_logger

logger = get_logger(__name__)


class ModelType(Enum):
    """模型类型"""
    # 阿里云百炼模型
    QWEN_PLUS = "qwen3.5-plus"
    QWEN_TURBO = "qwen-turbo"
    QWEN_MAX = "qwen-max"

    # Claude 模型（预留）
    OPUS = "claude-opus-4-20250514"
    SONNET = "claude-sonnet-4-20250514"
    HAIKU = "claude-haiku-4-20250514"


class LLMProvider(ABC):
    """LLM 提供商基类"""

    @abstractmethod
    async def complete(self, messages: List[Dict[str, str]]) -> str:
        """
        文本补全

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]

        Returns:
            LLM 响应文本
        """
        pass

    @abstractmethod
    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """
        流式响应

        Args:
            messages: 消息列表

        Yields:
            响应文本片段
        """
        pass


class DashScopeProvider(LLMProvider):
    """阿里云百炼 API 提供商（兼容 OpenAI 格式）"""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen3.5-plus",
        api_base: str = "https://coding.dashscope.aliyuncs.com/v1"
    ):
        """
        初始化阿里云百炼提供商

        Args:
            api_key: API Key
            model: 模型名称
            api_base: API 基础地址
        """
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")

    async def complete(self, messages: List[Dict[str, str]]) -> str:
        """
        调用阿里云百炼 API

        Args:
            messages: 消息列表

        Returns:
            LLM 响应
        """
        logger.debug(f"调用 DashScope API: model={self.model}, messages={len(messages)}条")
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages
                    }
                )
                response.raise_for_status()
                data = response.json()
                result = data["choices"][0]["message"]["content"]
                logger.debug(f"API 调用成功: 返回 {len(result)} 字符")
                return result
        except httpx.HTTPStatusError as e:
            logger.error(f"API 请求失败: status={e.response.status_code}, body={e.response.text}")
            raise
        except Exception as e:
            logger.error(f"API 调用异常: {e}", exc_info=True)
            raise

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """
        流式调用阿里云百炼 API

        Args:
            messages: 消息列表

        Yields:
            响应片段
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            import json
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue


class ClaudeProvider(LLMProvider):
    """Claude API 提供商（预留）"""

    def __init__(self, api_key: str, model: ModelType = ModelType.OPUS):
        """
        初始化 Claude 提供商

        Args:
            api_key: Anthropic API Key
            model: 使用的模型
        """
        self.api_key = api_key
        self.model = model

    async def complete(self, messages: List[Dict[str, str]]) -> str:
        """
        调用 Claude API

        Args:
            messages: 消息列表

        Returns:
            Claude 响应
        """
        # TODO: 实现 Claude API 调用
        raise NotImplementedError("Claude API 暂未实现")

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """
        流式调用 Claude API

        Args:
            messages: 消息列表

        Yields:
            响应片段
        """
        # TODO: 实现流式调用
        raise NotImplementedError("Claude API 暂未实现")


class LLMFactory:
    """LLM 工厂类"""

    @staticmethod
    def create_provider(
        model: str,
        api_key: str,
        api_base: Optional[str] = None
    ) -> LLMProvider:
        """
        创建 LLM 提供商

        Args:
            model: 模型名称 ("qwen-plus", "opus", "sonnet", "haiku")
            api_key: API Key
            api_base: API 基础地址（可选）

        Returns:
            LLM 提供商实例
        """
        logger.debug(f"创建 LLM Provider: model={model}")

        # 阿里云百炼模型
        if model in ["qwen-plus", "qwen-turbo", "qwen-max"]:
            model_map = {
                "qwen-plus": "qwen3.5-plus",
                "qwen-turbo": "qwen-turbo",
                "qwen-max": "qwen-max"
            }
            provider = DashScopeProvider(
                api_key=api_key,
                model=model_map[model],
                api_base=api_base or "https://coding.dashscope.aliyuncs.com/v1"
            )
            logger.info(f"创建 DashScope Provider: {model_map[model]}")
            return provider

        # Claude 模型
        elif model in ["opus", "sonnet", "haiku"]:
            model_map = {
                "opus": ModelType.OPUS,
                "sonnet": ModelType.SONNET,
                "haiku": ModelType.HAIKU
            }
            logger.info(f"创建 Claude Provider: {model}")
            return ClaudeProvider(api_key, model_map[model])

        else:
            logger.error(f"不支持的模型: {model}")
            raise ValueError(f"Unsupported model: {model}")
