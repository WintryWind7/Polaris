"""
Agent 基类定义

所有 Agent（主 Agent、心跳 Agent、子 Agent）的基类。
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from ..core.llm import LLMFactory, LLMProvider
from ..config.settings import get_settings


class Agent(ABC):
    """Agent 基类"""

    def __init__(self, name: str, model: str):
        """
        初始化 Agent

        Args:
            name: Agent 名称
            model: 使用的模型 ("qwen-plus", "qwen-turbo", "qwen-max")
        """
        self.name = name
        self.model = model
        self.state: Dict[str, Any] = {}
        self.created_at = datetime.now()


    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 任务描述字典

        Returns:
            执行结果字典
        """
        pass

    async def call_llm(self, messages: List[Dict[str, str]]) -> str:
        """
        调用 LLM (实时获取最新配置)

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]

        Returns:
            LLM 响应
        """
        # 实时获取最新配置并创建 Provider
        settings = get_settings()
        provider = LLMFactory.create_provider(
            model=self.model,
            api_key=settings.dashscope_api_key,
            api_base=settings.dashscope_api_base
        )
        return await provider.complete(messages)

    def get_state(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        return {
            "name": self.name,
            "model": self.model,
            "state": self.state,
            "created_at": self.created_at.isoformat()
        }
