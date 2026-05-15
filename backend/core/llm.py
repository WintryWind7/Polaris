"""
LLM 抽象层

封装不同 LLM 提供商的 API 调用，支持 OpenAI 兼容格式和 Anthropic 格式。
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Optional
import httpx
from ..logger import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """LLM 提供商基类"""

    @abstractmethod
    async def complete(
        self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        文本补全

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            tools: 工具定义列表（OpenAI Function Calling 格式）

        Returns:
            {
                "content": str,  # 文本响应（可能为 None）
                "tool_calls": List[Dict]  # 工具调用列表（可能为空）
            }
        """
        pass

    @abstractmethod
    async def stream(
        self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式响应

        Args:
            messages: 消息列表
            tools: 工具定义列表（可选）

        Yields:
            {"type": "text", "content": "..."}  或
            {"type": "tool_call", "tool_call": {...}}  (完整的 tool_call 对象)
        """
        pass


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容格式提供商（适用于 DashScope、DeepSeek 等所有 OpenAI 兼容 API）"""

    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")

    async def complete(
        self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        调用 OpenAI 兼容 API

        Args:
            messages: 消息列表
            tools: 工具定义列表

        Returns:
            {"content": str, "tool_calls": List[Dict]}
        """
        try:
            request_body = {
                "model": self.model,
                "messages": messages
            }
            if tools:
                request_body["tools"] = tools

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=request_body
                )
                response.raise_for_status()
                data = response.json()

                message = data["choices"][0]["message"]
                content = message.get("content")
                tool_calls = message.get("tool_calls", [])

                return {
                    "content": content,
                    "tool_calls": tool_calls
                }
        except httpx.HTTPStatusError as e:
            logger.error(f"API 请求失败: status={e.response.status_code}, body={e.response.text}")
            raise
        except Exception as e:
            logger.error(f"API 异常: {e}", exc_info=True)
            raise

    async def stream(
        self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式调用 OpenAI 兼容 API，支持工具调用。

        Args:
            messages: 消息列表
            tools: 工具定义列表（可选）

        Yields:
            {"type": "text", "content": "..."}
            {"type": "tool_call", "tool_call": {"id": ..., "function": {"name": ..., "arguments": "..."}}}
        """
        import json as json_mod

        async with httpx.AsyncClient(timeout=120.0) as client:
            request_body = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools:
                request_body["tools"] = tools

            async with client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_body
            ) as response:
                response.raise_for_status()

                # 按 index 聚合 tool_call delta
                tc_buf: Dict[int, Dict] = {}

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json_mod.loads(data_str)
                    except json_mod.JSONDecodeError:
                        continue

                    if not data.get("choices"):
                        continue
                    delta = data["choices"][0].get("delta", {})
                    if not delta:
                        continue

                    # 文本内容
                    if "content" in delta and delta["content"] is not None:
                        yield {"type": "text", "content": delta["content"]}
                        continue

                    # 工具调用 delta
                    tc_deltas = delta.get("tool_calls")
                    if not tc_deltas:
                        continue

                    for tc in tc_deltas:
                        idx = tc.get("index", 0)
                        if idx not in tc_buf:
                            tc_buf[idx] = {
                                "index": idx,
                                "id": tc.get("id") or "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            }

                        entry = tc_buf[idx]
                        if "id" in tc and tc["id"]:
                            entry["id"] = tc["id"]
                        if tc.get("type"):
                            entry["type"] = tc["type"]
                        fn = tc.get("function")
                        if fn:
                            if fn.get("name"):
                                entry["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                entry["function"]["arguments"] += fn["arguments"]

                        # 当 arguments 是完整 JSON 时，视为 tool_call 已完整
                        args = entry["function"]["arguments"]
                        if args and entry["id"]:
                            try:
                                json_mod.loads(args)
                                # 是完整 JSON → yield 完整 tool_call
                                yield {"type": "tool_call", "tool_call": dict(entry)}
                                del tc_buf[idx]
                            except json_mod.JSONDecodeError:
                                pass  # 还在收 arguments 中


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
        api_format: str = "openai"
    ) -> LLMProvider:
        """
        获取 LLM 提供商（单例模式，配置变更时自动重建）

        Args:
            model: 模型名称（直接传给 API，如 "qwen3.5-plus"、"deepseek-v4"）
            api_key: API Key
            api_base: API 基础地址
            api_format: API 格式，"openai" 或 "anthropic"

        Returns:
            LLM 提供商实例
        """
        config_key = (model, api_key, api_base, api_format)

        if model in cls._cache:
            if cls._cache_keys.get(model) == config_key:
                return cls._cache[model]
            else:
                logger.info(f"配置变更，重建 Provider: model={model}")

        provider = cls._create_provider(model, api_key, api_base, api_format)
        cls._cache[model] = provider
        cls._cache_keys[model] = config_key

        return provider

    @staticmethod
    def _create_provider(
        model: str,
        api_key: str,
        api_base: Optional[str] = None,
        api_format: str = "openai"
    ) -> LLMProvider:
        """根据 api_format 创建对应 Provider 实例"""
        if api_format == "anthropic":
            raise NotImplementedError("Anthropic 格式 Provider 尚未实现")

        logger.info(f"创建 OpenAI 兼容 Provider: model={model}, api_base={api_base}")
        return OpenAICompatibleProvider(
            api_key=api_key,
            model=model,
            api_base=api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    @classmethod
    def clear_cache(cls):
        """清空缓存（用于测试或强制重建）"""
        logger.debug("清空 Provider 缓存")
        cls._cache.clear()
        cls._cache_keys.clear()
