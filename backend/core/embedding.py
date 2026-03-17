"""
Embedding 服务

负责加载和使用 embedding 模型生成向量
"""
from typing import List, Dict, Optional
from pathlib import Path
from sentence_transformers import SentenceTransformer
from ..config.embedding_manager import EmbeddingManager
from ..logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Embedding 服务"""

    def __init__(self, model_path: str, embedding_id: str):
        """
        初始化 Embedding 服务

        Args:
            model_path: 模型路径
            embedding_id: Embedding ID
        """
        self.model_path = model_path
        self.embedding_id = embedding_id
        self.model: Optional[SentenceTransformer] = None
        self._load_model()

    def _load_model(self):
        """加载模型"""
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"模型路径不存在: {self.model_path}")

        logger.info(f"正在加载 embedding 模型: {self.model_path}")
        self.model = SentenceTransformer(self.model_path)
        logger.info(f"模型加载完成: {self.embedding_id}")

    def encode(self, text: str) -> List[float]:
        """
        编码文本为向量

        Args:
            text: 输入文本

        Returns:
            向量（list of float）
        """
        if not self.model:
            raise RuntimeError("模型未加载")

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量编码文本

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not self.model:
            raise RuntimeError("模型未加载")

        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def get_model_info(self) -> Dict:
        """
        获取模型信息

        Returns:
            {
                "provider": "local",
                "model_name": "bge-small-zh-v1.5",
                "dimension": 384
            }
        """
        if not self.model:
            raise RuntimeError("模型未加载")

        dimension = self.model.get_sentence_embedding_dimension()

        return {
            "provider": "local",
            "model_name": self.embedding_id,
            "dimension": dimension
        }


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    获取全局 Embedding 服务实例（单例）

    Returns:
        EmbeddingService 实例

    Raises:
        RuntimeError: 如果没有启用的 embedding 模型
    """
    global _embedding_service

    if _embedding_service is not None:
        return _embedding_service

    # 从配置中获取启用的模型
    manager = EmbeddingManager()
    active = manager.get_active_embedding()

    if not active:
        raise RuntimeError("未配置启用的 Embedding 模型")

    if active.model_type != "local":
        raise RuntimeError(f"不支持的模型类型: {active.model_type}")

    # 创建服务实例
    _embedding_service = EmbeddingService(
        model_path=active.model_path,
        embedding_id=active.embedding_id
    )

    return _embedding_service


def reset_embedding_service():
    """重置 Embedding 服务（用于切换模型）"""
    global _embedding_service
    _embedding_service = None
