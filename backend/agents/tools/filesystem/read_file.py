"""
读取文件工具
"""
from pathlib import Path
from ..base import Tool, ToolParameter, RiskLevel


class ReadFileTool(Tool):
    """读取文件内容"""

    name = "read_file"
    description = "读取指定路径的文件内容"
    category = "filesystem"
    risk_level = RiskLevel.SAFE

    parameters = {
        "path": ToolParameter(
            type="string",
            description="文件的绝对路径或相对路径"
        )
    }
    required_params = ["path"]

    async def execute(self, path: str, **kwargs) -> dict:
        """执行文件读取"""
        try:
            file_path = Path(path)
            if not file_path.exists():
                return {"success": False, "error": "文件不存在"}

            if not file_path.is_file():
                return {"success": False, "error": "路径不是文件"}

            content = file_path.read_text(encoding="utf-8")
            return {
                "success": True,
                "path": str(file_path.absolute()),
                "content": content,
                "size": len(content)
            }
        except UnicodeDecodeError:
            return {"success": False, "error": "文件编码不是 UTF-8"}
        except Exception as e:
            return {"success": False, "error": str(e)}
