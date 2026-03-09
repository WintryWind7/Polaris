"""
工具自动加载器

扫描 tools 目录，自动发现并注册工具。
"""
import importlib
import inspect
from pathlib import Path
from typing import List
from .base import Tool
from .registry import ToolRegistry
from ...logger import get_logger

logger = get_logger(__name__)


class ToolLoader:
    """工具自动加载器"""

    @staticmethod
    def load_from_directory(tools_dir: Path, registry: ToolRegistry) -> int:
        """
        从目录加载所有工具

        Args:
            tools_dir: tools 目录路径
            registry: 工具注册表

        Returns:
            加载的工具数量
        """
        count = 0

        # 遍历所有子目录（分类）
        for category_dir in tools_dir.iterdir():
            if not category_dir.is_dir():
                continue
            if category_dir.name.startswith("_"):
                continue

            category = category_dir.name
            logger.debug(f"扫描工具分类: {category}")

            # 遍历分类下的所有 .py 文件
            for tool_file in category_dir.glob("*.py"):
                if tool_file.name.startswith("_"):
                    continue

                try:
                    # 动态导入模块
                    module_path = f"backend.agents.tools.{category}.{tool_file.stem}"
                    module = importlib.import_module(module_path)

                    # 查找 Tool 子类
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, Tool) and obj is not Tool:
                            tool_instance = obj()
                            registry.register(tool_instance)
                            count += 1
                            logger.info(f"加载工具: {tool_instance.name} ({category})")

                except Exception as e:
                    logger.error(f"加载工具失败: {tool_file}, 错误: {e}")

        return count
