"""
Web 子 Agent

负责搜索互联网和抓取网页内容。
提示词模板：prompts/templates/subagent_web.md
"""
from .base_subagent import BaseSubAgent


class WebAgent(BaseSubAgent):
    """Web 子 Agent"""

    agent_type = "web"
    categories = ["web"]
    prompt_file = "subagent_web.md"
    max_iterations = 5
