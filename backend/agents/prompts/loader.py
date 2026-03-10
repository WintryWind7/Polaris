"""
提示词文件加载器

提供统一的提示词文件加载逻辑：
- 优先从 data/prompts/ 加载用户自定义文件
- 回退到 backend/agents/prompts/templates/ 模板
- 首次使用时自动复制模板到 data 目录
"""
from pathlib import Path
from ...logger import get_logger

logger = get_logger(__name__)


def load_prompt_file(filename: str) -> str:
    """
    加载提示词文件

    Args:
        filename: 文件名（如 "soul.md"）

    Returns:
        文件内容

    Raises:
        FileNotFoundError: 文件不存在
    """
    user_path = Path("data/prompts") / filename
    template_path = Path("backend/agents/prompts/templates") / filename

    # 优先使用用户文件
    if user_path.exists():
        logger.debug(f"加载用户提示词: {user_path}")
        return user_path.read_text(encoding="utf-8")

    # 回退到模板
    if template_path.exists():
        logger.info(f"首次使用，从模板复制: {template_path} -> {user_path}")
        user_path.parent.mkdir(parents=True, exist_ok=True)
        content = template_path.read_text(encoding="utf-8")
        user_path.write_text(content, encoding="utf-8")
        return content

    raise FileNotFoundError(f"找不到提示词文件: {filename}")
