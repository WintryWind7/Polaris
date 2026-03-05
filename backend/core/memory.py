"""
记忆系统

基于时间线的记忆管理，支持对话历史、知识图谱、工作模式等。
初期使用 JSON 存储，后续迁移到 SQLite。
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from ..logger import get_logger

logger = get_logger(__name__)


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


class MemorySystem:
    """记忆系统"""

    def __init__(self, data_dir: Path):
        """
        初始化记忆系统

        Args:
            data_dir: 数据目录
        """
        self.data_dir = data_dir
        self.timeline_file = data_dir / "timeline.json"
        self.timeline: List[TimelineEvent] = []

        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 加载时间线
        self._load_timeline()
        logger.info(f"MemorySystem 初始化完成: 加载了 {len(self.timeline)} 条事件")

    def _load_timeline(self):
        """从文件加载时间线"""
        if self.timeline_file.exists():
            try:
                with open(self.timeline_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.timeline = [TimelineEvent.from_dict(item) for item in data]
                logger.debug(f"从文件加载了 {len(self.timeline)} 条时间线事件")
            except Exception as e:
                logger.error(f"加载时间线失败: {e}", exc_info=True)
                self.timeline = []

    def _save_timeline(self):
        """保存时间线到文件"""
        with open(self.timeline_file, "w", encoding="utf-8") as f:
            data = [event.to_dict() for event in self.timeline]
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_event(self, event: TimelineEvent):
        """
        添加事件到时间线

        Args:
            event: 时间线事件
        """
        self.timeline.append(event)
        self._save_timeline()

    def add_chat(self, user_message: str, assistant_message: str):
        """
        添加对话记录

        Args:
            user_message: 用户消息
            assistant_message: 助手回复
        """
        event = TimelineEvent(
            event_type="chat",
            data={
                "user": user_message,
                "assistant": assistant_message
            }
        )
        self.add_event(event)
        logger.debug(f"添加对话记录: user={user_message[:30]}...")

    def query_timeline(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None
    ) -> List[TimelineEvent]:
        """
        查询时间线

        Args:
            start_time: 开始时间
            end_time: 结束时间
            event_type: 事件类型过滤

        Returns:
            符合条件的事件列表
        """
        results = self.timeline

        if start_time:
            results = [e for e in results if e.timestamp >= start_time]

        if end_time:
            results = [e for e in results if e.timestamp <= end_time]

        if event_type:
            results = [e for e in results if e.event_type == event_type]

        return results

    def get_recent_chats(self, limit: int = 10) -> List[TimelineEvent]:
        """
        获取最近的对话记录

        Args:
            limit: 返回数量

        Returns:
            最近的对话事件
        """
        chat_events = [e for e in self.timeline if e.event_type == "chat"]
        return chat_events[-limit:]
