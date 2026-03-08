"""
内置 Hooks

提供默认的 hook 实现，用于扩展 prompt 构建逻辑。
外部插件可以参考这些实现来编写自己的 hooks。
"""
from typing import Dict, List, Any
from ..logger import get_logger

logger = get_logger(__name__)


# ========== System Prompt Hooks ==========

def add_capabilities_hook(prompt: str, context: Dict) -> str:
    """
    添加能力描述到 system prompt

    启用条件: context.get("enable_capabilities") == True
    依赖数据: context["capabilities"] (List[str])

    Example:
        context = {
            "enable_capabilities": True,
            "capabilities": ["文件操作", "网络搜索", "代码执行"]
        }
    """
    if not context.get("enable_capabilities", False):
        return prompt

    capabilities = context.get("capabilities", [])
    if not capabilities:
        return prompt

    cap_text = "\n".join(f"- {cap}" for cap in capabilities)
    prompt += f"\n\n## 你拥有以下能力\n{cap_text}"

    logger.debug(f"[Hook] 添加能力描述: {len(capabilities)} 项")
    return prompt


def add_memory_hook(prompt: str, context: Dict) -> str:
    """
    添加长期记忆到 system prompt

    启用条件: context.get("enable_memory") == True
    依赖数据: context["memory_system"]

    Example:
        context = {
            "enable_memory": True,
            "memory_system": memory_system_instance
        }
    """
    if not context.get("enable_memory", False):
        return prompt

    memory_system = context.get("memory_system")
    if not memory_system:
        return prompt

    # 获取最近的对话记忆
    recent_chats = memory_system.get_recent_chats(limit=5)
    if not recent_chats:
        return prompt

    memory_lines = []
    for event in recent_chats:
        user_msg = event.data.get("user", "")[:50]
        assistant_msg = event.data.get("assistant", "")[:50]
        memory_lines.append(f"- 用户: {user_msg}... → 你: {assistant_msg}...")

    memory_text = "\n".join(memory_lines)
    prompt += f"\n\n## 最近的对话记忆\n{memory_text}"

    logger.debug(f"[Hook] 添加记忆: {len(recent_chats)} 条")
    return prompt


def add_tools_hook(prompt: str, context: Dict) -> str:
    """
    添加工具列表到 system prompt

    启用条件: context.get("enable_tools") == True
    依赖数据: context["tool_registry"]

    Example:
        context = {
            "enable_tools": True,
            "tool_registry": tool_registry_instance
        }
    """
    if not context.get("enable_tools", False):
        return prompt

    tool_registry = context.get("tool_registry")
    if not tool_registry:
        return prompt

    tools = tool_registry.list_tools()
    if not tools:
        return prompt

    tool_text = "\n".join(f"- {tool}" for tool in tools)
    prompt += f"\n\n## 可用工具\n{tool_text}"
    prompt += "\n\n使用格式: [TOOL: tool_name(params)]"

    logger.debug(f"[Hook] 添加工具列表: {len(tools)} 个")
    return prompt


# ========== Before Messages Hooks ==========

def add_few_shot_examples_hook(messages: List, context: Dict) -> List:
    """
    添加 Few-shot 示例到历史消息之前

    启用条件: context.get("enable_few_shot") == True
    依赖数据: context["few_shot_examples"] (可选，使用默认示例)

    Example:
        context = {
            "enable_few_shot": True,
            "few_shot_examples": [  # 可选
                {"role": "user", "content": "示例问题"},
                {"role": "assistant", "content": "示例回答"}
            ]
        }
    """
    if not context.get("enable_few_shot", False):
        return messages

    # 使用自定义示例或默认示例
    examples = context.get("few_shot_examples", [
        {"role": "user", "content": "搜索北京今天的天气"},
        {"role": "assistant", "content": "[TOOL: search(\"北京天气\")]\n结果：晴天，15-25度"},
        {"role": "system", "content": "--- 以上是示例，以下是真实对话 ---"}
    ])

    logger.debug(f"[Hook] 添加 Few-shot 示例: {len(examples)} 条")
    return examples


# ========== After Messages Hooks ==========

def add_realtime_info_hook(messages: List, context: Dict) -> List:
    """
    添加实时信息到历史消息之后

    启用条件: context.get("enable_realtime_info") == True
    依赖数据: context["realtime_info"] (Dict)

    Example:
        context = {
            "enable_realtime_info": True,
            "realtime_info": {
                "weather": "晴天 25°C",
                "time": "2024-03-08 14:30",
                "location": "北京"
            }
        }
    """
    if not context.get("enable_realtime_info", False):
        return messages

    realtime_info = context.get("realtime_info", {})
    if not realtime_info:
        return messages

    info_text = "\n".join(f"- {k}: {v}" for k, v in realtime_info.items())

    logger.debug(f"[Hook] 添加实时信息: {len(realtime_info)} 项")
    return [
        {"role": "system", "content": f"实时信息：\n{info_text}"}
    ]


# ========== 辅助函数 ==========

def register_builtin_hooks(prompt_builder):
    """
    注册所有内置 hooks

    Args:
        prompt_builder: PromptBuilder 实例

    Usage:
        from backend.core.hooks import register_builtin_hooks

        builder = PromptBuilder()
        register_builtin_hooks(builder)
    """
    # System Prompt Hooks
    prompt_builder.register_hook("system_prompt", add_capabilities_hook)
    prompt_builder.register_hook("system_prompt", add_memory_hook)
    prompt_builder.register_hook("system_prompt", add_tools_hook)

    # Before Messages Hooks
    prompt_builder.register_hook("before_messages", add_few_shot_examples_hook)

    # After Messages Hooks
    prompt_builder.register_hook("after_messages", add_realtime_info_hook)

    logger.info("内置 hooks 注册完成")
