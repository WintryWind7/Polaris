"""
Agent 基类定义

所有 Agent（主 Agent、心跳 Agent、子 Agent）的基类。
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from ..core.llm import LLMFactory, LLMProvider
from ..config.settings import get_settings
from ..logger import get_logger

logger = get_logger(__name__)


class Agent(ABC):
    """Agent 基类"""

    def __init__(self, name: str):
        """
        初始化 Agent

        Args:
            name: Agent 名称（用于匹配模型配置，如 "main"、"filesystem"）
        """
        self.name = name
        self.model = None
        self.api_key = None
        self.api_base = None
        self.state: Dict[str, Any] = {}
        self.created_at = datetime.now()

        settings = get_settings()
        try:
            model, api_key, api_base = settings.resolve_agent_model(name)
            self.model = model
            self.api_key = api_key
            self.api_base = api_base
        except ValueError:
            logger.warning(f"Agent '{name}' 无可用模型配置，请在设置中配置模型")

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

    async def call_llm(
        self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        调用 LLM (使用单例 Provider)

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            tools: 工具定义列表

        Returns:
            {"content": str, "tool_calls": List[Dict]}
        """
        if not self.model:
            raise RuntimeError(f"Agent '{self.name}' 无可用模型，请在设置中配置模型")

        provider = LLMFactory.get_provider(
            model=self.model,
            api_key=self.api_key,
            api_base=self.api_base
        )
        return await provider.complete(messages, tools)

    def get_state(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        return {
            "name": self.name,
            "model": self.model,
            "state": self.state,
            "created_at": self.created_at.isoformat()
        }
