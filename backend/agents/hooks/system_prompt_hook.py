"""
System Prompt Hook 系统

提供声明式的 Hook 注册机制：
- 使用装饰器自动注册 hooks
- 全局单例注册表
- 返回 JSON 格式，便于校验和调试
"""

import threading
from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional, List
from functools import wraps
from ...logger import get_logger

logger = get_logger(__name__)


@dataclass
class SystemPromptHook:
    """System Prompt Hook 描述符"""
    name: str
    func: Callable[[Dict], Dict]
    priority: int
    enabled_by: Optional[Callable[[Dict], bool]]
    hook_type: str = "system_prompt"


class SystemPromptRegistry:
    """全局 Hook 注册表（单例）"""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._hooks: List[SystemPromptHook] = []
        self._hooks_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "SystemPromptRegistry":
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, hook: SystemPromptHook):
        """注册 hook"""
        with self._hooks_lock:
            self._hooks.append(hook)
            logger.info(f"注册 hook: {hook.name} (priority={hook.priority})")

    def get_hooks(self) -> List[SystemPromptHook]:
        """获取所有 hooks（按 priority 排序）"""
        with self._hooks_lock:
            return sorted(self._hooks, key=lambda h: h.priority)

    def clear(self):
        """清空注册表（用于测试）"""
        with self._hooks_lock:
            self._hooks.clear()
            logger.debug("清空 hook 注册表")


def system_prompt_hook(
    priority: int = 50,
    enabled_by: Optional[Callable[[Dict], bool]] = None
):
    """
    System Prompt Hook 装饰器

    Args:
        priority: 优先级（数字越小越先执行）
        enabled_by: 启用条件函数，接收 context，返回 bool

    Example:
        @system_prompt_hook(priority=10, enabled_by=lambda ctx: ctx.get("enable_memory"))
        def inject_memory(context: Dict) -> Dict:
            memory = context["memory_system"].get_recent_chats(limit=5)
            return {
                "hook_type": "system_prompt",
                "content": f"\\n\\n## 记忆\\n{memory}"
            }
    """
    def decorator(func: Callable[[Dict], Dict]) -> Callable[[Dict], Dict]:
        # 自动生成 hook name
        hook_name = f"{func.__module__}.{func.__name__}"

        # 创建 hook 描述符
        hook = SystemPromptHook(
            name=hook_name,
            func=func,
            priority=priority,
            enabled_by=enabled_by
        )

        # 注册到全局注册表
        registry = SystemPromptRegistry.get_instance()
        registry.register(hook)

        @wraps(func)
        def wrapper(context: Dict) -> Dict:
            # 检查启用条件
            if enabled_by and not enabled_by(context):
                return {"hook_type": "system_prompt", "content": ""}

            # 执行 hook
            try:
                result = func(context)

                # 校验返回格式
                if not isinstance(result, dict):
                    logger.error(f"Hook '{hook_name}' 返回值必须是 dict，实际: {type(result)}")
                    return {"hook_type": "system_prompt", "content": ""}

                if result.get("hook_type") != "system_prompt":
                    logger.error(f"Hook '{hook_name}' 返回的 hook_type 必须是 'system_prompt'，实际: {result.get('hook_type')}")
                    return {"hook_type": "system_prompt", "content": ""}

                return result
            except Exception as e:
                logger.error(f"Hook '{hook_name}' 执行失败: {e}", exc_info=True)
                return {"hook_type": "system_prompt", "content": ""}

        return wrapper

    return decorator
