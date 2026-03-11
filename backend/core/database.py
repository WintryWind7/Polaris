"""
数据库初始化和连接管理
"""
import sqlite3
from pathlib import Path
from ..logger import get_logger

logger = get_logger(__name__)


def init_database(db_path: Path):
    """初始化数据库表结构"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 会话表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            title TEXT,
            metadata TEXT
        )
    """)

    # 消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_name TEXT,
            tool_args TEXT,
            timestamp TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)

    # 全文检索虚拟表
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content,
            content=messages,
            content_rowid=id
        )
    """)

    # 索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_sequence
        ON messages(session_id, sequence)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON messages(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_role
        ON messages(role)
    """)

    # 触发器：自动同步 messages_fts
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
            DELETE FROM messages_fts WHERE rowid = old.id;
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
            UPDATE messages_fts SET content = new.content WHERE rowid = new.id;
        END
    """)

    conn.commit()
    conn.close()

    logger.info(f"数据库初始化完成: {db_path}")


def get_connection(db_path: Path) -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 返回字典格式
    # 确保使用 UTF-8 编码
    conn.text_factory = str
    return conn
