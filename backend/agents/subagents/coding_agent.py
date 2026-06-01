"""
Coding 子 Agent

通用编码 Agent，负责文件读写、代码搜索、代码理解和修改。
提示词模板：prompts/templates/subagent_coding.md
"""
from .base_subagent import BaseSubAgent


class CodingAgent(BaseSubAgent):
    """通用编码子 Agent"""

    agent_type = "coding"
    categories = ["filesystem", "coding"]
    prompt_file = "subagent_coding.md"
    max_iterations = 8
