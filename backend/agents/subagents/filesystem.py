"""
Filesystem 子 Agent

负责文件读取和目录浏览。拥有自己的 LLM 调用循环和工具集。
"""
from .base_subagent import BaseSubAgent


SYSTEM_PROMPT = """## 可用工具

- **read_file**：读取指定路径的文件内容
- **list_directory**：列出指定目录下的文件和子目录

## 输出规范

根据不同场景组织输出：

- **读文件**：先说明文件是什么（类型、用途），再给出关键内容。文件很长时，提取重要部分，告诉主 Agent 总行数和大小。
- **列目录**：列出文件和子目录，按类型分组（目录在前、文件在后），标注文件大小。
- **操作失败**：说明具体原因（路径不存在、权限不足等），不要只说"失败了"。
- **多步操作**：如果需要先列目录再读文件，自己完成所有步骤，返回最终结果。

## 注意事项

- 只做读操作，不修改任何文件
- 路径不明确时，先用 list_directory 确认结构再读取
- 返回内容要精炼，不要输出无用的元信息
- 如果 task 中给出了 workspace_path，文件和目录路径以它为基础"""


class FilesystemAgent(BaseSubAgent):
    """文件系统子 Agent"""

    agent_type = "filesystem"
    categories = ["filesystem"]
    system_prompt = SYSTEM_PROMPT
    max_iterations = 5
