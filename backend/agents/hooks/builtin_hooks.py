"""
内置 System Prompt Hooks

使用装饰器声明式注册，返回 JSON 格式
"""

from typing import Dict
from .system_prompt_hook import system_prompt_hook
from ...logger import get_logger

logger = get_logger(__name__)


@system_prompt_hook(
    priority=10,
    enabled_by=lambda ctx: ctx.get("enable_skills", False)
)
def inject_skills(context: Dict) -> Dict:
    """
    添加技能描述到 system prompt

    启用条件: context.get("enable_skills") == True
    依赖数据: context["skills"] (List[str])
    """
    skills = context.get("skills", [])
    if not skills:
        return {"hook_type": "system_prompt", "content": ""}

    skills_text = "\n".join(f"- {skill}" for skill in skills)
    content = f"\n\n## 你拥有以下技能\n{skills_text}"

    logger.debug(f"[Hook] 添加技能描述: {len(skills)} 项")
    return {"hook_type": "system_prompt", "content": content}
