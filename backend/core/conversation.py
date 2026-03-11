"""
对话会话管理（SQLite 版本）

负责：
- 会话的创建、获取、删除
- 消息的添加和查询
- 会话持久化（SQLite）
- 记忆检索功能
"""
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from .database import init_database, get_connection
from ..logger import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """对话会话管理器（单例模式）"""

    _instance = None
    _initialized = False

    def __new__(cls, data_dir: Path):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, data_dir: Path):
        # 避免重复初始化
        if self._initialized:
            return

        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / "conversations.db"

        # 初始化数据库
        init_database(self.db_path)
        logger.info(f"ConversationManager 初始化完成: {self.db_path}")

        self._initialized = True

    def create_session(self, metadata: Optional[Dict] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (id, created_at, updated_at, title, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            now,
            now,
            None,
            json.dumps(metadata or {})
        ))

        conn.commit()
        conn.close()

        logger.info(f"创建新会话: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM sessions WHERE id = ?
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.warning(f"会话不存在: {session_id}")
            return None

        return dict(row)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict] = None
    ):
        """添加消息到会话"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 获取当前会话的最大 sequence
        cursor.execute("""
            SELECT COALESCE(MAX(sequence), 0) FROM messages
            WHERE session_id = ?
        """, (session_id,))
        max_seq = cursor.fetchone()[0]

        # 插入消息
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO messages
            (session_id, role, content, tool_name, tool_args, timestamp, sequence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            role,
            content,
            tool_name,
            json.dumps(tool_args) if tool_args else None,
            now,
            max_seq + 1
        ))

        # 更新会话的 updated_at 和 title
        cursor.execute("""
            UPDATE sessions
            SET updated_at = ?,
                title = COALESCE(title, ?)
            WHERE id = ?
        """, (
            now,
            content[:50] + "..." if len(content) > 50 else content if role == "user" else None,
            session_id
        ))

        conn.commit()
        conn.close()

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
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        if limit:
            sql = """
                SELECT role, content, tool_name, tool_args
                FROM messages
                WHERE session_id = ?
                ORDER BY sequence DESC
                LIMIT ?
            """
            cursor.execute(sql, (session_id, limit))
        else:
            sql = """
                SELECT role, content, tool_name, tool_args
                FROM messages
                WHERE session_id = ?
                ORDER BY sequence
            """
            cursor.execute(sql, (session_id,))

        rows = cursor.fetchall()
        conn.close()

        messages = [dict(row) for row in rows]

        # 如果有 limit，需要反转顺序（因为用了 DESC）
        if limit:
            messages.reverse()

        # 转换为 LLM 格式
        result = []
        for msg in messages:
            # 保持原始 role，不做转换
            # tool 消息应该保持为 tool，这是 Function Calling 的标准格式
            result.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return result

    def get_session_messages(self, session_id: str) -> List[Dict]:
        """获取特定会话的全部消息历史详情"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY sequence
        """, (session_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def list_sessions(self) -> List[Dict]:
        """获取所有会话列表并按更新时间降序排列"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, created_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            session = dict(row)
            # 如果没有 title，用默认值
            if not session["title"]:
                session["title"] = f"新对话 ({session['created_at'][:10]})"
            sessions.append(session)

        return sessions

    def delete_session(self, session_id: str):
        """删除会话"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 因为有 ON DELETE CASCADE，删除 session 会自动删除相关 messages
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

        conn.commit()
        conn.close()

        logger.info(f"删除会话: {session_id}")

    def search_memory(self, query: str, limit: int = 5) -> List[Dict]:
        """
        记忆检索：根据关键词搜索历史对话

        Args:
            query: 搜索关键词
            limit: 返回结果数量

        Returns:
            [
                {
                    "session_id": "...",
                    "title": "...",
                    "matched_content": "...",
                    "sequence": 1,
                    "updated_at": "..."
                },
                ...
            ]
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 使用 LIKE 查询（支持中文，但性能较 FTS5 差）
        cursor.execute("""
            SELECT DISTINCT
                m.session_id,
                m.content as matched_content,
                m.sequence,
                s.title,
                s.updated_at
            FROM messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE m.content LIKE ?
              AND m.role = 'user'
            ORDER BY s.updated_at DESC
            LIMIT ?
        """, (f"%{query}%", limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_context(
        self,
        session_id: str,
        around_sequence: int,
        context_size: int = 5
    ) -> List[Dict]:
        """
        获取某条消息的上下文

        Args:
            session_id: 会话 ID
            around_sequence: 目标消息的 sequence
            context_size: 前后各取几条

        Returns:
            消息列表
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM messages
            WHERE session_id = ?
              AND sequence BETWEEN ? AND ?
            ORDER BY sequence
        """, (
            session_id,
            max(1, around_sequence - context_size),
            around_sequence + context_size
        ))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
