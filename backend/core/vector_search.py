"""
向量检索服务

提供基于 embedding 的语义检索功能。
不关心 embedding 如何生成，只负责存储和检索。
"""
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Callable
import numpy as np
from .database import get_connection
from ..logger import get_logger

logger = get_logger(__name__)


class VectorSearchService:
    """向量检索服务"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def add_embedding(
        self,
        message_id: int,
        embedding: List[float],
        created_at: str
    ) -> int:
        """
        添加 embedding

        Args:
            message_id: 消息 ID
            embedding: 向量（list of float）
            created_at: 创建时间

        Returns:
            embedding ID
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 序列化向量
        embedding_blob = self._serialize_embedding(embedding)

        cursor.execute("""
            INSERT INTO message_embeddings (message_id, embedding, created_at)
            VALUES (?, ?, ?)
        """, (message_id, embedding_blob, created_at))

        embedding_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return embedding_id

    def get_embedding(self, message_id: int) -> Optional[List[float]]:
        """
        获取消息的 embedding

        Args:
            message_id: 消息 ID

        Returns:
            向量或 None
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT embedding FROM message_embeddings
            WHERE message_id = ?
        """, (message_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._deserialize_embedding(row["embedding"])

    def delete_embedding(self, message_id: int):
        """删除消息的 embedding"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM message_embeddings WHERE message_id = ?
        """, (message_id,))

        conn.commit()
        conn.close()

    def search_similar(
        self,
        query_embedding: List[float],
        session_id: Optional[str] = None,
        limit: int = 5,
        threshold: float = 0.0,
        role: str = "user"
    ) -> List[Dict]:
        """
        搜索相似消息

        Args:
            query_embedding: 查询向量
            session_id: 限定会话 ID（None 表示全局搜索）
            limit: 返回结果数量
            threshold: 相似度阈值（0-1）
            role: 搜索的消息角色 ('user', 'assistant', 'all')

        Returns:
            [
                {
                    "message_id": int,
                    "session_id": str,
                    "role": str,
                    "content": str,
                    "similarity": float,
                    "timestamp": str
                },
                ...
            ]
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 构建 SQL 查询
        if session_id:
            if role == "all":
                sql = """
                    SELECT m.id, m.session_id, m.role, m.content, m.timestamp, e.embedding
                    FROM messages m
                    JOIN message_embeddings e ON m.id = e.message_id
                    WHERE m.session_id = ?
                """
                cursor.execute(sql, (session_id,))
            else:
                sql = """
                    SELECT m.id, m.session_id, m.role, m.content, m.timestamp, e.embedding
                    FROM messages m
                    JOIN message_embeddings e ON m.id = e.message_id
                    WHERE m.session_id = ? AND m.role = ?
                """
                cursor.execute(sql, (session_id, role))
        else:
            if role == "all":
                sql = """
                    SELECT m.id, m.session_id, m.role, m.content, m.timestamp, e.embedding
                    FROM messages m
                    JOIN message_embeddings e ON m.id = e.message_id
                """
                cursor.execute(sql)
            else:
                sql = """
                    SELECT m.id, m.session_id, m.role, m.content, m.timestamp, e.embedding
                    FROM messages m
                    JOIN message_embeddings e ON m.id = e.message_id
                    WHERE m.role = ?
                """
                cursor.execute(sql, (role,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

        # 计算相似度
        query_vec = np.array(query_embedding, dtype=np.float32)
        results = []

        for row in rows:
            embedding = self._deserialize_embedding(row["embedding"])
            embedding_vec = np.array(embedding, dtype=np.float32)

            # 余弦相似度
            similarity = self._cosine_similarity(query_vec, embedding_vec)

            if similarity >= threshold:
                results.append({
                    "message_id": row["id"],
                    "session_id": row["session_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "similarity": float(similarity),
                    "timestamp": row["timestamp"]
                })

        # 按相似度降序排序
        results.sort(key=lambda x: x["similarity"], reverse=True)

        return results[:limit]

    def rebuild_all(
        self,
        encode_func: Callable[[str], List[float]],
        batch_size: int = 100
    ) -> Dict[str, int]:
        """
        重建所有 embedding

        Args:
            encode_func: 编码函数 (text: str) -> List[float]
            batch_size: 批处理大小

        Returns:
            统计信息 {"total": int, "success": int, "failed": int}
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 1. 清空现有 embedding
        cursor.execute("DELETE FROM message_embeddings")
        logger.info("已清空现有 embedding")

        # 2. 查询所有需要生成 embedding 的消息
        cursor.execute("""
            SELECT id, content, timestamp
            FROM messages
            WHERE tool_execution_id IS NULL
              AND content IS NOT NULL
              AND content != ''
        """)

        messages = cursor.fetchall()
        total = len(messages)
        logger.info(f"找到 {total} 条消息需要生成 embedding")

        if total == 0:
            conn.close()
            return {"total": 0, "success": 0, "failed": 0}

        # 3. 批量生成 embedding
        success = 0
        failed = 0

        for i in range(0, total, batch_size):
            batch = messages[i:i + batch_size]
            logger.info(f"处理批次 {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}")

            for msg in batch:
                try:
                    # 调用外部提供的编码函数
                    embedding = encode_func(msg["content"])

                    # 存储
                    embedding_blob = self._serialize_embedding(embedding)
                    cursor.execute("""
                        INSERT INTO message_embeddings (message_id, embedding, created_at)
                        VALUES (?, ?, ?)
                    """, (msg["id"], embedding_blob, msg["timestamp"]))

                    success += 1
                except Exception as e:
                    logger.error(f"生成 embedding 失败 (message_id={msg['id']}): {e}")
                    failed += 1

            conn.commit()

        conn.close()

        logger.info(f"重建完成: 总计 {total}, 成功 {success}, 失败 {failed}")
        return {"total": total, "success": success, "failed": failed}

    def get_metadata(self, key: str) -> Optional[str]:
        """获取 embedding 元数据"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT value FROM embedding_metadata WHERE key = ?
        """, (key,))

        row = cursor.fetchone()
        conn.close()

        return row["value"] if row else None

    def set_metadata(self, key: str, value: str):
        """设置 embedding 元数据"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO embedding_metadata (key, value)
            VALUES (?, ?)
        """, (key, value))

        conn.commit()
        conn.close()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 总消息数
        cursor.execute("SELECT COUNT(*) as count FROM messages")
        total_messages = cursor.fetchone()["count"]

        # 有 embedding 的消息数
        cursor.execute("SELECT COUNT(*) as count FROM message_embeddings")
        total_embeddings = cursor.fetchone()["count"]

        # 应该有 embedding 的消息数（排除工具调用）
        cursor.execute("""
            SELECT COUNT(*) as count FROM messages
            WHERE tool_execution_id IS NULL
              AND content IS NOT NULL
              AND content != ''
        """)
        should_have_embeddings = cursor.fetchone()["count"]

        conn.close()

        return {
            "total_messages": total_messages,
            "total_embeddings": total_embeddings,
            "should_have_embeddings": should_have_embeddings,
            "missing_embeddings": should_have_embeddings - total_embeddings
        }

    @staticmethod
    def _serialize_embedding(embedding: List[float]) -> bytes:
        """序列化向量为 BLOB"""
        return pickle.dumps(np.array(embedding, dtype=np.float32))

    @staticmethod
    def _deserialize_embedding(blob: bytes) -> List[float]:
        """反序列化 BLOB 为向量"""
        return pickle.loads(blob).tolist()

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
