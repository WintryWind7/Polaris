"""
Memory 子 Agent

负责检索历史对话和用户信息。
提示词模板：prompts/templates/subagent_memory.md
"""
from .base_subagent import BaseSubAgent


class MemoryAgent(BaseSubAgent):
    """Memory 子 Agent"""

    agent_type = "memory"
    categories = ["memory"]
    prompt_file = "subagent_memory.md"
    max_iterations = 3
