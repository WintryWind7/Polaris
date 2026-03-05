"""
心跳 Agent

后台常驻，定时检查系统状态，决定是否唤醒主 Agent。
使用最便宜的模型（qwen-turbo）。
"""
from typing import Optional, Dict, Any
from .base import Agent


class HeartbeatAgent(Agent):
    """心跳 Agent"""

    def __init__(self):
        super().__init__("heartbeat", "qwen-turbo")
        self.check_interval = 300  # 5 分钟检查一次

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行检查任务

        Args:
            task: 任务字典（心跳 Agent 通常不需要外部任务）

        Returns:
            检查结果
        """
        wake_reason = await self.check()

        if wake_reason:
            return {
                "should_wake": True,
                "reason": wake_reason["reason"],
                "context": wake_reason["context"]
            }
        else:
            return {"should_wake": False}

    async def check(self) -> Optional[Dict[str, Any]]:
        """
        检查系统状态

        Returns:
            如果需要唤醒主 Agent，返回原因和上下文；否则返回 None
        """
        # TODO: 实现检查逻辑
        # 1. 检测构建失败
        # 2. 检测内存占用过高
        # 3. 检测文件变化异常
        # 4. 其他需要主动提醒的情况

        # 示例：检测到异常
        # return {
        #     "reason": "构建失败",
        #     "context": {"log_path": "/path/to/build.log"}
        # }

        return None
