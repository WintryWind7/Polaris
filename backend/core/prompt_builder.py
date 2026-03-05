"""
提示词构建器

负责：
- 动态构建 system prompt
- 组装完整的 messages 数组
- 提供 hook 机制（预留扩展点）
"""

from typing import List, Dict, Callable, Optional, Any
from datetime import datetime
from ..logger import get_logger

logger = get_logger(__name__)


class PromptBuilder:
    """提示词构建器"""

    def __init__(self):
        # Hook 注册表
        self._hooks: Dict[str, List[Callable]] = {
            "system_prompt": [],      # 修改 system prompt
            "before_messages": [],    # 在历史消息之前插入
            "after_messages": [],     # 在历史消息之后插入
        }
        logger.info("PromptBuilder 初始化完成")

    def register_hook(self, hook_name: str, func: Callable):
        """
        注册 hook

        Args:
            hook_name: hook 名称 ("system_prompt" | "before_messages" | "after_messages")
            func: hook 函数

        Example:
            def add_memory(prompt: str, context: Dict) -> str:
                memory = context.get("memory", "")
                return prompt + f"\n\n用户记忆：{memory}"

            builder.register_hook("system_prompt", add_memory)
        """
        if hook_name not in self._hooks:
            raise ValueError(f"Unknown hook: {hook_name}")
        self._hooks[hook_name].append(func)
        logger.info(f"注册 hook: {hook_name}")

    def build_messages(
        self,
        user_message: str,
        history: List[Dict],
        context: Optional[Dict[str, Any]] = None,
        max_history: int = 20
    ) -> List[Dict]:
        """
        构建完整的 messages 数组

        Args:
            user_message: 当前用户消息
            history: 历史消息 [{"role": "user", "content": "..."}, ...]
            context: 上下文数据（传递给 hooks）
            max_history: 最大历史消息数（滑动窗口）

        Returns:
            完整的 messages 数组
        """
        context = context or {}
        messages = []

        # 1. 构建 system prompt
        system_prompt = self._build_system_prompt(context)
        messages.append({"role": "system", "content": system_prompt})

        # 2. 应用 before_messages hooks
        before_messages = self._apply_hooks("before_messages", [], context)
        messages.extend(before_messages)

        # 3. 添加历史消息（滑动窗口）
        if history:
            windowed_history = history[-max_history:]
            messages.extend(windowed_history)
            logger.debug(f"添加历史消息: {len(windowed_history)} 条（窗口大小: {max_history}）")

        # 4. 应用 after_messages hooks
        after_messages = self._apply_hooks("after_messages", [], context)
        messages.extend(after_messages)

        # 5. 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        logger.debug(f"构建 messages 完成: 共 {len(messages)} 条")
        return messages

    def _build_system_prompt(self, context: Dict) -> str:
        """构建 system prompt"""
        from ..config.settings import get_settings
        settings = get_settings()
        
        # 从配置中获取基础提示词
        base_prompt = settings.system_prompt
        
        # 补充当前时间
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "{current_time}" in base_prompt:
            prompt = base_prompt.format(current_time=current_time_str)
        else:
            prompt = f"{base_prompt}\n\n当前时间：{current_time_str}"

        # 应用 system_prompt hooks
        prompt = self._apply_hooks("system_prompt", prompt, context)

        return prompt

    def _apply_hooks(
        self,
        hook_name: str,
        data: Any,
        context: Dict
    ) -> Any:
        """应用 hooks"""
        for hook_func in self._hooks[hook_name]:
            try:
                data = hook_func(data, context)
            except Exception as e:
                # Hook 失败不应该影响主流程
                logger.error(f"Hook '{hook_name}' 执行失败: {e}", exc_info=True)
        return data
