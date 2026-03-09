"""
工具基类

定义工具的抽象接口和风险等级。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel


class RiskLevel(Enum):
    """风险等级"""
    SAFE = "safe"           # 安全操作（读取文件）
    LOW = "low"             # 低风险（创建文件）
    MEDIUM = "medium"       # 中风险（修改文件）
    HIGH = "high"           # 高风险（删除文件）
    CRITICAL = "critical"   # 严重风险（系统调用）


class ToolParameter(BaseModel):
    """工具参数定义"""
    type: str  # string, integer, boolean, array, object
    description: str
    enum: Optional[list] = None  # 枚举值
    items: Optional[Dict] = None  # array 类型的元素定义
    properties: Optional[Dict] = None  # object 类型的属性定义


class Tool(ABC):
    """工具基类"""

    # 子类必须定义这些类属性
    name: str = ""
    description: str = ""
    category: str = "general"
    risk_level: RiskLevel = RiskLevel.SAFE

    # 参数定义（子类覆盖）
    parameters: Dict[str, ToolParameter] = {}
    required_params: list = []

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具

        Args:
            **kwargs: 参数（从 arguments 解析而来）

        Returns:
            执行结果字典，格式：{"success": bool, "data": Any, "error": str}
        """
        pass

    def to_function_schema(self) -> Dict[str, Any]:
        """
        转换为 OpenAI Function Calling 格式

        Returns:
            {
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "...",
                    "parameters": {...}
                }
            }
        """
        properties = {}
        for param_name, param_def in self.parameters.items():
            prop = {
                "type": param_def.type,
                "description": param_def.description
            }
            if param_def.enum:
                prop["enum"] = param_def.enum
            if param_def.items:
                prop["items"] = param_def.items
            if param_def.properties:
                prop["properties"] = param_def.properties
            properties[param_name] = prop

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": self.required_params
                }
            }
        }

    def validate_params(self, **kwargs) -> bool:
        """
        参数校验

        Args:
            **kwargs: 参数

        Returns:
            是否有效
        """
        # 检查必需参数
        for required in self.required_params:
            if required not in kwargs:
                return False
        return True
