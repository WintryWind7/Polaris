"""
列出目录工具
"""
from pathlib import Path
from ..base import Tool, ToolParameter, RiskLevel


class ListDirectoryTool(Tool):
    """列出目录内容"""

    name = "list_directory"
    description = "列出指定目录下的文件和子目录"
    category = "filesystem"
    risk_level = RiskLevel.SAFE

    parameters = {
        "path": ToolParameter(
            type="string",
            description="目录的绝对路径或相对路径"
        )
    }
    required_params = ["path"]

    async def execute(self, path: str, **kwargs) -> dict:
        """执行目录列表"""
        try:
            dir_path = Path(path)
            if not dir_path.exists():
                return {"success": False, "error": "目录不存在"}

            if not dir_path.is_dir():
                return {"success": False, "error": "路径不是目录"}

            items = []
            for item in dir_path.iterdir():
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })

            return {
                "success": True,
                "path": str(dir_path.absolute()),
                "items": items,
                "count": len(items)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
