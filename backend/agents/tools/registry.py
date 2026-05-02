"""
工具注册表

管理工具的注册、查询和执行。
"""
from typing import Dict, Any, List, Optional

from .base import Tool


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = {}
        self._schemas: Dict[str, Dict] = {}  # 伪工具的原始 schema（不通过 Tool 类）

    def register(self, tool: Tool):
        """
        注册工具

        Args:
            tool: 工具实例
        """
        self._tools[tool.name] = tool

        # 按分类索引
        if tool.category not in self._categories:
            self._categories[tool.category] = []
        self._categories[tool.category].append(tool.name)

    def get(self, name: str) -> Optional[Tool]:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            工具实例或 None
        """
        return self._tools.get(name)

    def list_all(self) -> List[str]:
        """
        列出所有工具名称

        Returns:
            工具名称列表
        """
        return list(self._tools.keys())

    def list_by_category(self, category: str) -> List[str]:
        """
        按分类列出工具

        Args:
            category: 分类名称

        Returns:
            工具名称列表
        """
        return self._categories.get(category, [])

    def get_categories(self) -> List[str]:
        """
        获取所有分类

        Returns:
            分类列表
        """
        return list(self._categories.keys())

    def register_schema(self, name: str, schema: Dict):
        """注册原始 schema（用于非 Tool 子类的伪工具，如 ask_main_agent）"""
        self._schemas[name] = schema

    def get_schemas(self, enabled_tools: Optional[List[str]] = None) -> List[Dict]:
        """
        获取所有工具和伪工具的 function schema

        Args:
            enabled_tools: 启用的工具列表（None 表示全部）

        Returns:
            [{"type": "function", "function": {...}}, ...]
        """
        schemas = []
        for name, tool in self._tools.items():
            if enabled_tools is None or name in enabled_tools:
                schemas.append(tool.to_function_schema())
        # 追加伪工具 schema
        for name, schema in self._schemas.items():
            if enabled_tools is None or name in enabled_tools:
                schemas.append(schema)
        return schemas
