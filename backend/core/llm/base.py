"""
LLM Provider 基类
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Optional


class LLMProvider(ABC):
    """LLM 提供商基类"""

    def __init__(self):
        self.preserve_reasoning = False

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

    def build_message(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        reasoning: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        构建 assistant 消息 dict

        Args:
            content: 文本内容
            tool_calls: 工具调用列表
            reasoning: 思维链内容

        Returns:
            API 格式的 assistant 消息
        """
        msg: Dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning and self.preserve_reasoning:
            msg["reasoning_content"] = reasoning
        return msg
