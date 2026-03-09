"""
Hooks 模块

导出装饰器和注册表，方便外部使用
"""

from .system_prompt_hook import (
    system_prompt_hook,
    SystemPromptRegistry,
    SystemPromptHook
)

# 导入 builtin_hooks 确保装饰器被执行（自动注册）
from . import builtin_hooks

__all__ = [
    "system_prompt_hook",
    "SystemPromptRegistry",
    "SystemPromptHook",
    "builtin_hooks"
]
