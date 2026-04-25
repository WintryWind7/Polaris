"""
工作空间管理

负责工作空间的 CRUD 和会话关联。
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from .database import get_connection
from ..logger import get_logger

logger = get_logger(__name__)


class WorkspaceManager:

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.db_path = data_dir / "conversations.db"

    def create_workspace(self, name: str, path: str) -> str:
        workspace_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workspaces (id, name, path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (workspace_id, name, path, now, now))
        conn.commit()
        conn.close()

        logger.info(f"创建工作空间: {name} ({workspace_id[:8]})")
        return workspace_id

    def get_workspace(self, workspace_id: str) -> Optional[Dict]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_workspaces(self) -> List[Dict]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT w.*, COUNT(s.id) as session_count
            FROM workspaces w
            LEFT JOIN sessions s ON w.id = s.workspace_id
            GROUP BY w.id
            ORDER BY w.updated_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_workspace(self, workspace_id: str, updates: Dict):
        fields = []
        values = []
        for key in ("name", "path"):
            if key in updates and updates[key] is not None:
                fields.append(f"{key} = ?")
                values.append(updates[key])

        if not fields:
            return

        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(workspace_id)

        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE workspaces SET {', '.join(fields)} WHERE id = ?",
            values
        )
        conn.commit()
        conn.close()

        logger.info(f"更新工作空间: {workspace_id[:8]}")

    def delete_workspace(self, workspace_id: str):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        # 手动断开关联会话（SQLite 默认不启用外键约束）
        cursor.execute("UPDATE sessions SET workspace_id = NULL WHERE workspace_id = ?", (workspace_id,))
        cursor.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
        conn.commit()
        conn.close()

        logger.info(f"删除工作空间: {workspace_id[:8]}")

    def get_workspace_by_path(self, path: str) -> Optional[Dict]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workspaces WHERE path = ?", (path,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_workspace_sessions(self, workspace_id: str) -> List[Dict]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, created_at, updated_at
            FROM sessions
            WHERE workspace_id = ?
            ORDER BY updated_at DESC
        """, (workspace_id,))
        rows = cursor.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            session = dict(row)
            if not session["title"]:
                session["title"] = f"新对话 ({session['created_at'][:10]})"
            sessions.append(session)
        return sessions
