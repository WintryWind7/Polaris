"""
Memory Prompt Hook

注入长期记忆内容
"""
from typing import Dict
from ..hooks.system_prompt_hook import system_prompt_hook
from .loader import load_prompt_file
from ...logger import get_logger

logger = get_logger(__name__)


@system_prompt_hook(priority=20)
def inject_memory(context: Dict) -> Dict:
    """
    注入长期记忆

    Args:
        context: 上下文信息

    Returns:
        Hook 响应
    """
    try:
        content = load_prompt_file("memory.md")
        return {
            "hook_type": "system_prompt",
            "content": content
        }
    except FileNotFoundError:
        # memory.md 可能不存在（首次运行），返回空内容
        logger.debug("memory.md 不存在，跳过记忆注入")
        return {
            "hook_type": "system_prompt",
            "content": ""
        }
    except Exception as e:
        logger.error(f"加载 memory.md 失败: {e}", exc_info=True)
        return {
            "hook_type": "system_prompt",
            "content": ""
        }
