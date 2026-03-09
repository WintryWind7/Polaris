"""
提示词构建器

负责：
- 动态构建 system prompt
- 组装完整的 messages 数组
- 自动加载全局 hook 注册表
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from ..logger import get_logger

logger = get_logger(__name__)


class PromptBuilder:
    """提示词构建器"""

    def __init__(self):
        # 导入 hooks 模块，确保装饰器被执行（自动注册）
        from ..agents.hooks import builtin_hooks
        logger.info("PromptBuilder 初始化完成")

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

        # 1. 构建 system prompt（自动应用 hooks）
        system_prompt = self._build_system_prompt(context)
        messages.append({"role": "system", "content": system_prompt})

        # 2. 添加历史消息（滑动窗口）
        if history:
            windowed_history = history[-max_history:]
            messages.extend(windowed_history)
            logger.debug(f"添加历史消息: {len(windowed_history)} 条（窗口大小: {max_history}）")

        # 3. 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        logger.debug(f"构建 messages 完成: 共 {len(messages)} 条")
        return messages

    def _build_system_prompt(self, context: Dict) -> str:
        """构建 system prompt（自动应用全局注册的 hooks）"""
        from ..config.settings import get_settings
        from ..agents.hooks import SystemPromptRegistry

        settings = get_settings()

        # 从配置中获取基础提示词
        base_prompt = settings.system_prompt

        # 补充当前时间
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "{current_time}" in base_prompt:
            prompt = base_prompt.format(current_time=current_time_str)
        else:
            prompt = f"{base_prompt}\n\n当前时间：{current_time_str}"

        # 获取全局注册的 hooks
        registry = SystemPromptRegistry.get_instance()
        hooks = registry.get_hooks()

        # 按 priority 顺序执行 hooks
        for hook in hooks:
            try:
                # 检查启用条件
                if hook.enabled_by and not hook.enabled_by(context):
                    continue

                # 执行 hook
                result = hook.func(context)

                # 校验返回格式
                if not isinstance(result, dict):
                    logger.error(f"Hook '{hook.name}' 返回值必须是 dict")
                    continue

                if result.get("hook_type") != "system_prompt":
                    logger.error(f"Hook '{hook.name}' 返回的 hook_type 必须是 'system_prompt'")
                    continue

                # 拼接 content
                content = result.get("content", "")
                if content:
                    prompt += content

            except Exception as e:
                # Hook 失败不影响主流程
                logger.error(f"Hook '{hook.name}' 执行失败: {e}", exc_info=True)

        return prompt
