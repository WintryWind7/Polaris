"""
时间线事件

定义时间线事件的数据结构和序列化方法。
"""
from datetime import datetime
from typing import Dict, Any, Optional


class TimelineEvent:
    """时间线事件"""

    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化时间线事件

        Args:
            event_type: 事件类型 ("chat", "file_edit", "app_launch" 等)
            data: 事件数据
            timestamp: 时间戳（默认当前时间）
            context: 上下文信息（预留字段）
        """
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.now()
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineEvent":
        """从字典创建"""
        return cls(
            event_type=data["event_type"],
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            context=data.get("context", {})
        )
