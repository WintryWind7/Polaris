"""
获取环境变量工具
"""
import os
from ..base import Tool, ToolParameter, RiskLevel


class GetEnvTool(Tool):
    """获取环境变量"""

    name = "get_env"
    description = "获取指定的环境变量值"
    category = "system"
    risk_level = RiskLevel.LOW

    parameters = {
        "name": ToolParameter(
            type="string",
            description="环境变量名称"
        )
    }
    required_params = ["name"]

    async def execute(self, name: str, **kwargs) -> dict:
        """执行获取环境变量"""
        try:
            value = os.environ.get(name)
            if value is None:
                return {
                    "success": False,
                    "error": f"环境变量 '{name}' 不存在"
                }

            return {
                "success": True,
                "name": name,
                "value": value
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
