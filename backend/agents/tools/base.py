"""
工具基类

定义工具的抽象接口和风险等级。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    SAFE = "safe"           # 安全操作（读取文件）
    LOW = "low"             # 低风险（创建文件）
    MEDIUM = "medium"       # 中风险（修改文件）
    HIGH = "high"           # 高风险（删除文件）
    CRITICAL = "critical"   # 严重风险（系统调用）


class Tool(ABC):
    """工具基类"""

    def __init__(self, name: str, description: str):
        """
        初始化工具

        Args:
            name: 工具名称
            description: 工具描述
        """
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具

        Args:
            params: 参数字典

        Returns:
            执行结果
        """
        pass

    def validate(self, params: Dict[str, Any]) -> bool:
        """
        参数校验

        Args:
            params: 参数字典

        Returns:
            是否有效
        """
        return True

    def estimate_risk(self, params: Dict[str, Any]) -> RiskLevel:
        """
        风险评估

        Args:
            params: 参数字典

        Returns:
            风险等级
        """
        return RiskLevel.SAFE
