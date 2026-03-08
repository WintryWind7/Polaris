"""
工具注册表

管理工具的注册、查询和执行。
"""
from typing import Dict, Any, List, Optional

from .base import Tool, RiskLevel


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """
        注册工具

        Args:
            tool: 工具实例
        """
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            工具实例或 None
        """
        return self.tools.get(name)

    def list_tools(self) -> List[str]:
        """
        列出所有工具

        Returns:
            工具名称列表
        """
        return list(self.tools.keys())

    async def execute(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具

        Args:
            name: 工具名称
            params: 参数

        Returns:
            执行结果
        """
        tool = self.get(name)
        if not tool:
            return {"error": f"Tool not found: {name}"}

        if not tool.validate(params):
            return {"error": "Invalid parameters"}

        # TODO: 在沙箱中执行（如果是高风险操作）
        risk = tool.estimate_risk(params)
        if risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            # 需要用户授权
            pass

        return await tool.execute(params)
