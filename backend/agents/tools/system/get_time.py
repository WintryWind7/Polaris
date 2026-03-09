"""
获取当前时间工具
"""
from datetime import datetime
from ..base import Tool, ToolParameter, RiskLevel


class GetTimeTool(Tool):
    """获取当前时间"""

    name = "get_time"
    description = "获取当前系统时间，支持多种格式"
    category = "system"
    risk_level = RiskLevel.SAFE

    parameters = {
        "format": ToolParameter(
            type="string",
            description="时间格式，默认为 'datetime'",
            enum=["datetime", "date", "time", "timestamp"]
        )
    }
    required_params = []

    async def execute(self, format: str = "datetime", **kwargs) -> dict:
        """执行获取时间"""
        try:
            now = datetime.now()

            if format == "date":
                result = now.strftime("%Y-%m-%d")
            elif format == "time":
                result = now.strftime("%H:%M:%S")
            elif format == "timestamp":
                result = str(int(now.timestamp()))
            else:  # datetime
                result = now.strftime("%Y-%m-%d %H:%M:%S")

            return {
                "success": True,
                "time": result,
                "format": format
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
