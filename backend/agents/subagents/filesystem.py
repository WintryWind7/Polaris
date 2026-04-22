"""
Filesystem 子 Agent

负责文件读取和目录浏览。
拥有自己的 LLM 调用循环和工具集。
"""
from typing import Dict, Any, List
from pathlib import Path
from ..base import Agent
from ..tools import ToolRegistry, ToolExecutor, ToolLoader
from ...logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是 Polaris 的文件系统子 Agent。你接收主 Agent 派发的任务，使用工具完成文件读取和目录浏览操作，然后向主 Agent 返回结果。

## 你的角色

你不是在和用户对话，而是在和主 Agent 交流。主 Agent 会把用户的请求转换成具体的任务描述发给你，你需要：
1. 理解任务要求
2. 调用合适的工具完成操作
3. 把结果整理成主 Agent 能直接使用的形式返回

## 可用工具

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
"""


class FilesystemAgent(Agent):
    """文件系统子 Agent"""

    def __init__(self):
        super().__init__("filesystem", "qwen-plus")
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)

        # 只加载 filesystem 工具
        tools_dir = Path(__file__).parent.parent / "tools"
        count = ToolLoader.load_from_directory(
            tools_dir, self.tool_registry, categories=["filesystem"]
        )
        logger.info(f"FilesystemAgent 初始化，加载了 {count} 个工具")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行文件系统任务

        Args:
            task: {"task": str} 主 Agent 传递的任务描述

        Returns:
            {"response": str} 自然语言结果
        """
        task_description = task.get("task", "")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task_description}
        ]

        tools = self.tool_registry.get_schemas()

        max_iterations = 5
        final_response = None

        for _ in range(max_iterations):
            response = await self.call_llm(messages, tools)
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                final_response = response.get("content")
                break

            tool_names = [tc["function"]["name"] for tc in tool_calls]
            logger.info(f"FilesystemAgent 调用工具: {', '.join(tool_names)}")

            messages.append({
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": tool_calls
            })

            for tool_call in tool_calls:
                tool_message = await self.tool_executor.execute_tool_call(tool_call)
                messages.append(tool_message)

        if final_response is None:
            final_response = "文件操作未能完成"

        return {"response": final_response}
