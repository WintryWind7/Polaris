"""
Soul Prompt Hook

注入 Polaris 的核心身份和使命
"""
from typing import Dict
from ..hooks.system_prompt_hook import system_prompt_hook
from .loader import load_prompt_file
from ...logger import get_logger

logger = get_logger(__name__)


@system_prompt_hook(priority=10)
def inject_soul(context: Dict) -> Dict:
    """
    注入核心身份

    Args:
        context: 上下文信息

    Returns:
        Hook 响应
    """
    try:
        content = load_prompt_file("soul.md")
        return {
            "hook_type": "system_prompt",
            "content": content
        }
    except Exception as e:
        logger.error(f"加载 soul.md 失败: {e}", exc_info=True)
        return {
            "hook_type": "system_prompt",
            "content": ""
        }
