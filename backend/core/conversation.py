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

    def create_session(self, metadata: Optional[Dict] = None, workspace_id: Optional[str] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (id, created_at, updated_at, title, metadata, workspace_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            now,
            now,
            None,
            json.dumps(metadata or {}),
            workspace_id
        ))

        conn.commit()
        conn.close()

        logger.info(f"创建新会话: {session_id[:8]}")
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
            logger.warning(f"会话不存在: {session_id[:8]}")
            return None

        return dict(row)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: Optional[str] = None,
        tool_execution_id: Optional[int] = None
    ) -> int:
        """
        添加消息到会话

        Args:
            session_id: 会话ID
            role: 角色 ('user' | 'assistant')
            content: 消息内容（普通消息）或 tool_calls JSON（工具调用）
            tool_execution_id: 关联的工具执行ID

        Returns:
            插入的消息ID
        """
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
            (session_id, role, content, tool_execution_id, timestamp, sequence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            role,
            content,
            tool_execution_id,
            now,
            max_seq + 1
        ))

        message_id = cursor.lastrowid

        # 更新会话的 updated_at 和 title
        cursor.execute("""
            UPDATE sessions
            SET updated_at = ?,
                title = COALESCE(title, ?)
            WHERE id = ?
        """, (
            now,
            content[:50] + "..." if content and len(content) > 50 else content if role == "user" and content else None,
            session_id
        ))

        conn.commit()
        conn.close()

        return message_id

    def add_tool_execution(
        self,
        session_id: str,
        message_id: int,
        tool_results: List[Dict]
    ) -> int:
        """
        添加工具执行记录

        Args:
            session_id: 会话ID
            message_id: 关联的消息ID
            tool_results: 工具返回结果列表 [{"role": "tool", "content": "...", "tool_call_id": "..."}]

        Returns:
            插入的工具执行ID
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO tool_executions
            (session_id, message_id, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            session_id,
            message_id,
            json.dumps(tool_results, ensure_ascii=False),
            now
        ))

        tool_execution_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return tool_execution_id

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
                SELECT id, role, content, tool_execution_id
                FROM messages
                WHERE session_id = ?
                ORDER BY sequence DESC
                LIMIT ?
            """
            cursor.execute(sql, (session_id, limit))
        else:
            sql = """
                SELECT id, role, content, tool_execution_id
                FROM messages
                WHERE session_id = ?
                ORDER BY sequence
            """
            cursor.execute(sql, (session_id,))

        rows = cursor.fetchall()
        messages = [dict(row) for row in rows]

        # 如果有 limit，需要反转顺序（因为用了 DESC）
        if limit:
            messages.reverse()

        # 转换为 LLM 格式
        result = []
        for msg in messages:
            if msg["tool_execution_id"]:
                # assistant 调用工具
                tool_calls = json.loads(msg["content"]) if msg["content"] else []
                result.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls
                })

                # 查询工具返回结果
                cursor.execute("""
                    SELECT content FROM tool_executions WHERE id = ?
                """, (msg["tool_execution_id"],))
                tool_exec_row = cursor.fetchone()
                if tool_exec_row:
                    tool_results = json.loads(tool_exec_row["content"])
                    result.extend(tool_results)
            else:
                # 普通消息
                result.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        conn.close()
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
            SELECT id, title, created_at, updated_at, workspace_id
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

        logger.info(f"删除会话: {session_id[:8]}")

    def search_memory(self, query: str, limit: int = 5, role: str = "user") -> List[Dict]:
        """
        记忆检索：优先使用向量检索，失败时回退到关键词检索

        Args:
            query: 搜索关键词
            limit: 返回结果数量
            role: 搜索的消息角色 ('user', 'assistant', 'all')

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
        # 尝试向量检索
        try:
            from .vector_search import VectorSearchService
            from .embedding import get_embedding_service
            from ..config.embedding_manager import EmbeddingManager

            # 检查兼容性
            manager_emb = EmbeddingManager()
            compatibility = manager_emb.check_compatibility()

            if compatibility["compatible"]:
                # 向量检索
                embedding_service = get_embedding_service()
                query_embedding = embedding_service.encode(query)

                vector_search = VectorSearchService(self.db_path)
                results = vector_search.search_similar(
                    query_embedding=query_embedding,
                    limit=limit,
                    threshold=0.3,
                    role=role
                )

                if results:
                    # 补充会话标题
                    conn = get_connection(self.db_path)
                    cursor = conn.cursor()

                    formatted_results = []
                    for r in results:
                        cursor.execute("""
                            SELECT title, updated_at FROM sessions WHERE id = ?
                        """, (r["session_id"],))

                        session = cursor.fetchone()
                        if session:
                            formatted_results.append({
                                "session_id": r["session_id"],
                                "title": session["title"],
                                "matched_content": r["content"],
                                "sequence": r.get("sequence", 0),
                                "updated_at": session["updated_at"]
                            })

                    conn.close()

                    if formatted_results:
                        logger.info(f"向量检索成功: {len(formatted_results)} 条结果")
                        return formatted_results
        except Exception as e:
            logger.warning(f"向量检索失败，回退到关键词检索: {e}")

        # 回退到关键词检索
        logger.info("使用关键词检索")
        return self._search_memory_by_keyword(query, limit, role)

    def _search_memory_by_keyword(self, query: str, limit: int = 5, role: str = "user") -> List[Dict]:
        """
        关键词检索（回退方案）

        使用 LIKE 查询或 FTS5 全文搜索

        Args:
            query: 搜索关键词
            limit: 返回结果数量
            role: 搜索的消息角色 ('user', 'assistant', 'all')

        Returns:
            搜索结果列表
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 构建 WHERE 条件
        if role == "all":
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
                  AND m.tool_execution_id IS NULL
                ORDER BY s.updated_at DESC
                LIMIT ?
            """, (f"%{query}%", limit))
        else:
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
                  AND m.role = ?
                  AND m.tool_execution_id IS NULL
                ORDER BY s.updated_at DESC
                LIMIT ?
            """, (f"%{query}%", role, limit))

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
