"""
会话管理器

管理 session_id → MainAgent 的映射。
每个会话拥有独立的 Main Agent 实例及其子 Agent。
"""
from typing import Dict, Optional
from ..agents.main_agent import MainAgent
from ..logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """会话级 Agent 管理器"""

    def __init__(self):
        self._agents: Dict[str, MainAgent] = {}

    def get_or_create(self, session_id: str) -> MainAgent:
        """
        获取或创建会话对应的 MainAgent

        Args:
            session_id: 会话 ID

        Returns:
            MainAgent 实例
        """
        if session_id not in self._agents:
            self._agents[session_id] = MainAgent()
            logger.info(f"创建会话 Agent: session={session_id[:8]}")
        return self._agents[session_id]

    def get(self, session_id: str) -> Optional[MainAgent]:
        """获取已有会话的 MainAgent，不存在返回 None"""
        return self._agents.get(session_id)

    def delete(self, session_id: str):
        """删除会话及其 MainAgent"""
        if session_id in self._agents:
            del self._agents[session_id]
            logger.info(f"销毁会话 Agent: session={session_id[:8]}")

    def list_sessions(self) -> list:
        """列出所有活跃会话"""
        return list(self._agents.keys())

    @property
    def active_count(self) -> int:
        """当前活跃会话数"""
        return len(self._agents)
