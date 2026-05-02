"""
Web 子 Agent

负责搜索互联网和抓取网页内容。
"""
from .base_subagent import BaseSubAgent


SYSTEM_PROMPT = """## 可用工具

- **web_search**：搜索互联网（DuckDuckGo），返回结果标题、摘要和链接
- **web_fetch**：抓取指定 URL 的网页正文内容

## 输出规范

- **搜索结果**：列出关键结果（标题、摘要、链接），标注信息来源
- **网页抓取**：提取核心信息，标注 URL 和抓取时间
- **信息整合**：多个来源的信息要交叉对比，指出矛盾或一致之处
- **操作失败**：说明具体原因（无法访问、解析失败等）

## 注意事项

- 搜索结果不等于事实，在回答中适当标注可信度
- 优先使用权威来源
- 搜索结果未返回有用信息时，尝试换关键词重新搜索"""


class WebAgent(BaseSubAgent):
    """Web 子 Agent"""

    agent_type = "web"
    categories = ["web"]
    system_prompt = SYSTEM_PROMPT
    max_iterations = 5
