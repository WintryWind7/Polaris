"""
对话会话管理

负责：
- 会话的创建、获取、删除
- 消息的添加和查询
- 会话持久化（JSON）
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import json
import uuid
from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class Message:
    """单条消息"""
    role: str  # "user" | "assistant"
    content: str
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Conversation:
    """对话会话"""
    session_id: str
    created_at: str
    updated_at: str
    messages: List[Message]
    metadata: Dict  # 预留：可以存储用户偏好、主题等

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata
        }


class ConversationManager:
    """对话会话管理器"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.sessions_dir = data_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ConversationManager 初始化完成: {self.sessions_dir}")

    def create_session(self, metadata: Optional[Dict] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conversation = Conversation(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            messages=[],
            metadata=metadata or {}
        )

        self._save_session(conversation)
        logger.info(f"创建新会话: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[Conversation]:
        """获取会话"""
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            logger.warning(f"会话不存在: {session_id}")
            return None

        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 重建 Message 对象
        messages = [Message(**m) for m in data["messages"]]
        data["messages"] = messages

        return Conversation(**data)

    def add_message(self, session_id: str, role: str, content: str):
        """添加消息到会话"""
        conversation = self.get_session(session_id)
        if not conversation:
            raise ValueError(f"Session {session_id} not found")

        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat()
        )

        conversation.messages.append(message)
        conversation.updated_at = datetime.now().isoformat()

        self._save_session(conversation)
        logger.debug(f"添加消息到会话 {session_id}: role={role}, content={content[:50]}...")

    def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        获取会话消息（转换为 LLM 格式）

        Returns:
            [{"role": "user", "content": "..."}, ...]
        """
        conversation = self.get_session(session_id)
        if not conversation:
            return []

        messages = conversation.messages
        if limit:
            messages = messages[-limit:]

        return [{"role": m.role, "content": m.content} for m in messages]

    def get_session_messages(self, session_id: str) -> List[Dict]:
        """获取特定会话的全部消息历史详情"""
        conversation = self.get_session(session_id)
        if not conversation:
            return []
        return [m.to_dict() for m in conversation.messages]

    def list_sessions(self) -> List[Dict]:
        """获取所有会话列表并按更新时间降序排列"""
        sessions = []
        if not self.sessions_dir.exists():
            return sessions

        for file_path in self.sessions_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 提取标题
                title = data.get("metadata", {}).get("title")
                if not title:
                    messages = data.get("messages", [])
                    for msg in messages:
                        if msg["role"] == "user":
                            content = msg["content"]
                            title = content[:20] + "..." if len(content) > 20 else content
                            break
                if not title:
                    title = f"新对话 ({data.get('created_at', '')[:10]})"

                sessions.append({
                    "id": data["session_id"],
                    "title": title,
                    "created_at": data["created_at"],
                    "updated_at": data["updated_at"]
                })
            except Exception as e:
                logger.error(f"加载会话文件失败 {file_path}: {e}")

        # 按更新时间倒序
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions

    def delete_session(self, session_id: str):
        """删除会话"""
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            logger.info(f"删除会话: {session_id}")

    def _save_session(self, conversation: Conversation):
        """保存会话到文件"""
        session_file = self.sessions_dir / f"{conversation.session_id}.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(conversation.to_dict(), f, ensure_ascii=False, indent=2)
