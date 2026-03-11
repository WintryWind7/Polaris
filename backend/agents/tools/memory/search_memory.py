"""
记忆检索工具

允许 AI 搜索历史对话记忆
"""
from typing import Dict, Any
from ..base import Tool, RiskLevel, ToolParameter
from ....core.conversation import ConversationManager
from ....config.settings import settings


class SearchMemoryTool(Tool):
    """搜索历史对话记忆"""

    name = "search_memory"
    description = "搜索历史对话记忆，查找用户之前说过的内容。当用户询问历史信息时（如'我之前说的'、'上次讨论'、'我是谁'、'我叫什么'），必须使用此工具查询，不要凭空猜测或说不知道"
    category = "memory"
    risk_level = RiskLevel.SAFE

    parameters = {
        "query": ToolParameter(
            type="string",
            description="要搜索的关键词或主题（从用户输入和上下文中提取）"
        ),
        "limit": ToolParameter(
            type="integer",
            description="返回结果数量，默认 5"
        )
    }
    required_params = ["query"]

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行记忆检索

        Args:
            query: 搜索关键词
            limit: 返回结果数量

        Returns:
            {
                "success": True,
                "data": [
                    {
                        "session_id": "...",
                        "title": "...",
                        "matched_content": "...",
                        "time": "..."
                    }
                ]
            }
        """
        try:
            query = kwargs.get("query")
            limit = kwargs.get("limit", 5)

            # 获取 ConversationManager
            manager = ConversationManager(settings.data_dir)

            # 搜索记忆
            results = manager.search_memory(query, limit=limit)

            # 格式化结果
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "session_id": r["session_id"],
                    "title": r["title"],
                    "matched_content": r["matched_content"],
                    "time": r["updated_at"]
                })

            return {
                "success": True,
                "data": formatted_results
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class GetContextTool(Tool):
    """获取某条消息的上下文"""

    name = "get_context"
    description = "获取历史对话中某条消息的上下文（前后几条消息）。当需要查看完整对话时使用"
    category = "memory"
    risk_level = RiskLevel.SAFE

    parameters = {
        "session_id": ToolParameter(
            type="string",
            description="会话 ID（从 search_memory 结果中获取）"
        ),
        "sequence": ToolParameter(
            type="integer",
            description="目标消息的序号"
        ),
        "context_size": ToolParameter(
            type="integer",
            description="前后各取几条消息，默认 5"
        )
    }
    required_params = ["session_id", "sequence"]

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行上下文获取

        Args:
            session_id: 会话 ID
            sequence: 目标消息序号
            context_size: 前后各取几条

        Returns:
            {
                "success": True,
                "data": [
                    {
                        "role": "user",
                        "content": "...",
                        "sequence": 1
                    }
                ]
            }
        """
        try:
            session_id = kwargs.get("session_id")
            sequence = kwargs.get("sequence")
            context_size = kwargs.get("context_size", 5)

            # 获取 ConversationManager
            manager = ConversationManager(settings.data_dir)

            # 获取上下文
            context = manager.get_context(session_id, sequence, context_size)

            # 格式化结果
            formatted_context = []
            for msg in context:
                formatted_context.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "sequence": msg["sequence"],
                    "timestamp": msg["timestamp"]
                })

            return {
                "success": True,
                "data": formatted_context
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
