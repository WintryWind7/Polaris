"""
写入文件工具
"""
from pathlib import Path
from ..base import Tool, ToolParameter, RiskLevel


class WriteFileTool(Tool):
    """写入文件内容"""

    name = "write_file"
    description = "写入内容到指定文件，支持覆盖或追加模式"
    category = "filesystem"
    risk_level = RiskLevel.MEDIUM

    parameters = {
        "path": ToolParameter(
            type="string",
            description="文件的绝对路径或相对路径"
        ),
        "content": ToolParameter(
            type="string",
            description="要写入的内容"
        ),
        "mode": ToolParameter(
            type="string",
            description="写入模式：overwrite（覆盖）或 append（追加）",
            enum=["overwrite", "append"]
        )
    }
    required_params = ["path", "content"]

    async def execute(self, path: str, content: str, mode: str = "overwrite", **kwargs) -> dict:
        """执行文件写入"""
        try:
            file_path = Path(path)

            # 确保父目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if mode == "append":
                file_path.write_text(
                    file_path.read_text(encoding="utf-8") + content if file_path.exists() else content,
                    encoding="utf-8"
                )
            else:  # overwrite
                file_path.write_text(content, encoding="utf-8")

            return {
                "success": True,
                "path": str(file_path.absolute()),
                "mode": mode,
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
