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

SYSTEM_PROMPT = """你是 Polaris 的文件系统专家。你的职责是处理所有与文件和目录相关的操作。

## 工作方式

1. 接收主 Agent 传递的任务描述
2. 使用你的工具完成任务
3. 用清晰、结构化的自然语言返回结果

## 输出规范

- 简洁准确地描述你找到的内容
- 如果文件较大，提取关键信息而非全部输出
- 如果操作失败，说明具体原因
- 用主 Agent 容易理解的方式组织信息
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
