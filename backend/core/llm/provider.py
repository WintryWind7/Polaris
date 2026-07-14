"""
OpenAI 兼容格式 Provider

适用于所有 OpenAI 兼容 API（DashScope、DeepSeek 等）。
"""
from typing import AsyncIterator, List, Dict, Any, Optional
import httpx
from .base import LLMProvider
from ...logger import get_logger

logger = get_logger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容格式提供商"""

    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        thinking: bool = False,
        reasoning_effort: str = "",
        preserve_reasoning: bool = False
    ):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.thinking = thinking
        self.reasoning_effort = reasoning_effort
        self.preserve_reasoning = preserve_reasoning

    async def complete(
        self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        调用 OpenAI 兼容 API

        Args:
            messages: 消息列表
            tools: 工具定义列表

        Returns:
            {"content": str, "tool_calls": List[Dict], "reasoning_content": Optional[str]}
        """
        try:
            request_body = {
                "model": self.model,
                "messages": messages
            }
            if tools:
                request_body["tools"] = tools
            if self.thinking:
                request_body["thinking"] = {"type": "enabled"}
            if self.reasoning_effort:
                request_body["reasoning_effort"] = self.reasoning_effort

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
                reasoning_content = message.get("reasoning_content")

                usage = data.get("usage", {})
                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "reasoning_content": reasoning_content,
                    "usage": usage
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
            {"type": "reasoning", "content": "..."}
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
            if self.thinking:
                request_body["thinking"] = {"type": "enabled"}
            if self.reasoning_effort:
                request_body["reasoning_effort"] = self.reasoning_effort

            async with client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_body
            ) as response:
                if not response.is_success:
                    error_body = await response.aread()
                    logger.error(f"流式 API 错误: status={response.status_code}, body={error_body.decode('utf-8', errors='replace')[:500]}")
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

                    # DeepSeek: usage 和 finish_reason 在最后一个 chunk 一起返回，choices 非空
                    if "usage" in data and data["usage"]:
                        yield {"type": "usage", "usage": data["usage"]}

                    if not data.get("choices"):
                        continue
                    delta = data["choices"][0].get("delta", {})
                    if not delta:
                        continue

                    # 思维链内容
                    if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                        yield {"type": "reasoning", "content": delta["reasoning_content"]}
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
