"""按文件名模式搜索文件（glob）"""
from pathlib import Path
from ..base import Tool, ToolParameter, RiskLevel


class SearchFilesTool(Tool):
    """按 glob 模式查找文件"""

    name = "search_files"
    description = "在当前目录下按 glob 模式搜索文件，如 '**/*.py' 或 '*.vue'"
    category = "coding"
    risk_level = RiskLevel.SAFE

    parameters = {
        "pattern": ToolParameter(
            type="string",
            description="glob 匹配模式，如 '**/*.py'、'*.md'、'src/**/*.ts'"
        ),
        "directory": ToolParameter(
            type="string",
            description="搜索目录路径，默认为当前工作目录"
        ),
    }
    required_params = ["pattern"]

    async def execute(self, pattern: str, directory: str = ".", **kwargs) -> dict:
        try:
            dir_path = Path(directory).resolve()
            if not dir_path.is_dir():
                return {"success": False, "error": f"目录不存在: {directory}"}

            results = []
            for file_path in dir_path.glob(pattern):
                if file_path.is_file():
                    parts = set(file_path.parts)
                    if parts & {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}:
                        continue
                    try:
                        rel = str(file_path.relative_to(dir_path))
                    except ValueError:
                        rel = str(file_path)
                    results.append({
                        "path": rel,
                        "size": file_path.stat().st_size
                    })
                if len(results) >= 100:
                    break

            return {
                "success": True,
                "pattern": pattern,
                "directory": str(dir_path),
                "count": len(results),
                "files": results[:100],
                "truncated": len(results) >= 100
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
