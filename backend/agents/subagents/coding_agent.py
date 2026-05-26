"""
Coding 子 Agent

通用编码 Agent，负责文件读写、代码搜索、代码理解和修改。
"""
from .base_subagent import BaseSubAgent

SYSTEM_PROMPT = """## 可用工具

- **read_file**：读取文件内容
- **write_file**：写入文件（创建或覆盖）
- **list_directory**：列出目录下的文件和子目录
- **search_content**：在文件中搜索关键词或正则表达式
- **search_files**：按文件名模式搜索（glob）

## 工作方式

收到任务后，按以下步骤独立完成：

1. **理解任务**：明确要做什么。不确定路径或文件名时，先用 search_files / list_directory 定位。
2. **收集信息**：用 search_content 找到相关代码，用 read_file 阅读关键文件。要确保理解上下文后再动手。
3. **执行修改**：用 write_file 写入改动。改完之后读一遍确认正确。
4. **总结汇报**：列出改了哪些文件、做了什么改动、为什么这样改。

## 注意事项

- 写文件前先读文件，理解现有逻辑再改
- 一次改完，不要分多次无意义的操作
- 不确定的事情用 ask_main_agent 确认，不要猜测
- task 中给的 workspace_path 作为所有路径的基准目录"""


class CodingAgent(BaseSubAgent):
    """通用编码子 Agent"""

    agent_type = "coding"
    categories = ["filesystem", "coding"]
    system_prompt = SYSTEM_PROMPT
    max_iterations = 8
