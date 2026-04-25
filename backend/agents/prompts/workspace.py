"""
Workspace Prompt Hook

将当前工作空间信息注入 system prompt
"""
from typing import Dict
from ..hooks.system_prompt_hook import system_prompt_hook
from ...logger import get_logger

logger = get_logger(__name__)


@system_prompt_hook(priority=15)
def inject_workspace(context: Dict) -> Dict:
    workspace_path = context.get("workspace_path")
    workspace_name = context.get("workspace_name")

    if not workspace_path:
        return {"hook_type": "system_prompt", "content": ""}

    name_part = f"（{workspace_name}）" if workspace_name else ""
    content = f"""

## 当前工作空间

你正在工作空间{name_part}中工作，工作目录为：`{workspace_path}`

- 用户的所有文件操作请求都应基于此目录
- 理解路径时优先以工作目录为基准
- 如需访问工作目录外的文件，应向用户确认"""

    return {"hook_type": "system_prompt", "content": content}
