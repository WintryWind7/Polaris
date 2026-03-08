"""
技能基类

定义技能的抽象接口。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class Skill(ABC):
    """技能基类"""

    def __init__(self, name: str, description: str):
        """
        初始化技能

        Args:
            name: 技能名称
            description: 技能描述
        """
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行技能

        Args:
            context: 执行上下文

        Returns:
            执行结果
        """
        pass

    def validate(self, context: Dict[str, Any]) -> bool:
        """
        验证上下文是否满足执行条件

        Args:
            context: 执行上下文

        Returns:
            是否有效
        """
        return True
