"""
搜索文件内容工具（grep）
"""
import re
from pathlib import Path
from ..base import Tool, ToolParameter, RiskLevel


class SearchContentTool(Tool):
    """在目录下搜索文件内容"""

    name = "search_content"
    description = "在指定目录下搜索文件内容，支持正则表达式和文件类型过滤"
    category = "coding"
    risk_level = RiskLevel.SAFE

    parameters = {
        "pattern": ToolParameter(
            type="string",
            description="搜索关键词或正则表达式"
        ),
        "directory": ToolParameter(
            type="string",
            description="搜索目录路径，默认为当前工作目录"
        ),
        "file_glob": ToolParameter(
            type="string",
            description="文件类型过滤，如 '*.py' 或 '*.{py,js}'"
        ),
    }
    required_params = ["pattern"]

    async def execute(self, pattern: str, directory: str = ".", file_glob: str = "*", **kwargs) -> dict:
        try:
            dir_path = Path(directory).resolve()
            if not dir_path.is_dir():
                return {"success": False, "error": f"目录不存在: {directory}"}

            results = []
            compiled = re.compile(pattern)

            for file_path in dir_path.rglob(file_glob):
                if not file_path.is_file():
                    continue
                # 跳过常见忽略目录
                parts = set(file_path.parts)
                if parts & {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}:
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, PermissionError):
                    continue

                for lineno, line in enumerate(content.splitlines(), 1):
                    if compiled.search(line):
                        results.append({
                            "file": str(file_path.relative_to(dir_path)),
                            "line": lineno,
                            "content": line.strip()[:200]
                        })
                        if len(results) >= 50:
                            break
                if len(results) >= 50:
                    break

            return {
                "success": True,
                "pattern": pattern,
                "directory": str(dir_path),
                "matches": len(results),
                "results": results[:50],
                "truncated": len(results) >= 50
            }
        except re.error as e:
            return {"success": False, "error": f"正则表达式错误: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
