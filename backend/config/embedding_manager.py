"""
Embedding 配置管理器

管理 Embedding 模型的增删改查，配置存储在 data/embeddings.json
"""
import json
import threading
from pathlib import Path
from typing import Optional
from backend.config.models import EmbeddingConfig
from backend.core.embedding_detector import EmbeddingDetector


class EmbeddingManager:
    """Embedding 配置管理器（单例）"""

    _instance: Optional["EmbeddingManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self.project_root = Path(__file__).parent.parent.parent
        self.data_dir = Path(__file__).parent.parent / "data"
        self.embeddings_file = self.data_dir / "embeddings.json"
        self.models_dir = self.data_dir / "models" / "embeddings"

        self._embeddings: dict[str, EmbeddingConfig] = {}
        self._operation_lock = threading.Lock()

        # 确保配置文件存在并加载
        self._ensure_file_exists()
        self.load_embeddings()

        self._initialized = True

    def _ensure_file_exists(self) -> None:
        """确保配置文件存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        if not self.embeddings_file.exists():
            # 创建空的 embeddings 配置
            with open(self.embeddings_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
            print(f"[EmbeddingManager] 已创建 embeddings 配置文件: {self.embeddings_file}")

    def load_embeddings(self) -> dict[str, EmbeddingConfig]:
        """加载所有 embeddings"""
        with self._operation_lock:
            with open(self.embeddings_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._embeddings = {}
            for embedding_id, embedding_data in data.items():
                self._embeddings[embedding_id] = EmbeddingConfig(**embedding_data)

            return self._embeddings

    def save_embeddings(self) -> None:
        """保存所有 embeddings"""
        with self._operation_lock:
            self._save_embeddings_unsafe()

    def _save_embeddings_unsafe(self) -> None:
        """保存所有 embeddings（不加锁，内部使用）"""
        data = {}
        for embedding_id, embedding in self._embeddings.items():
            data[embedding_id] = embedding.model_dump()

        with open(self.embeddings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_all_embeddings(self) -> dict[str, EmbeddingConfig]:
        """获取所有 embeddings"""
        return self._embeddings.copy()

    def get_embedding(self, embedding_id: str) -> Optional[EmbeddingConfig]:
        """获取指定 embedding"""
        return self._embeddings.get(embedding_id)

    def get_active_embedding(self) -> Optional[EmbeddingConfig]:
        """
        获取当前启用的 embedding 模型

        Returns:
            当前启用的 embedding，如果没有启用的模型则返回 None
        """
        for embedding in self._embeddings.values():
            if embedding.enabled:
                return embedding
        return None

    def check_compatibility(self) -> dict:
        """
        检查当前配置的模型和数据库中的模型是否兼容

        Returns:
            {
                "compatible": bool,  # 是否兼容
                "current_model": str,  # 当前配置的模型
                "current_dimension": int,  # 当前模型维度
                "db_model": str,  # 数据库中的模型
                "db_dimension": int,  # 数据库中的维度
                "message": str  # 提示信息
            }
        """
        from backend.core.vector_search import VectorSearchService
        from backend.config.settings import get_settings

        result = {
            "compatible": False,
            "current_model": None,
            "current_dimension": None,
            "db_model": None,
            "db_dimension": None,
            "message": ""
        }

        # 获取当前启用的模型
        active = self.get_active_embedding()
        if not active:
            result["message"] = "未配置 Embedding 模型"
            return result

        result["current_model"] = active.embedding_id
        result["current_dimension"] = active.dimension

        # 检查数据库
        try:
            settings = get_settings()
            db_path = settings.data_dir / "conversations.db"

            if not db_path.exists():
                result["message"] = "数据库不存在"
                return result

            vector_search = VectorSearchService(db_path)

            db_model = vector_search.get_metadata("model_name")
            db_dimension = vector_search.get_metadata("dimension")

            if not db_model:
                result["message"] = "向量数据库为空，需要初始化"
                return result

            result["db_model"] = db_model
            result["db_dimension"] = int(db_dimension) if db_dimension else None

            # 检查兼容性
            if result["current_model"] == db_model and result["current_dimension"] == result["db_dimension"]:
                result["compatible"] = True
                result["message"] = "模型兼容"
            else:
                result["compatible"] = False
                result["message"] = f"模型不兼容：当前使用 {result['current_model']}({result['current_dimension']}维)，但数据库是 {db_model}({result['db_dimension']}维)"

        except Exception as e:
            result["message"] = f"检查失败: {str(e)}"

        return result

    def add_embedding(self, embedding: EmbeddingConfig) -> None:
        """添加 embedding"""
        with self._operation_lock:
            if embedding.embedding_id in self._embeddings:
                raise ValueError(f"Embedding ID '{embedding.embedding_id}' 已存在")

            # 验证模型路径
            if embedding.model_type == "local":
                model_path = Path(embedding.model_path)
                if not model_path.exists():
                    raise ValueError(f"模型路径不存在: {embedding.model_path}")

                # 自动检测维度
                detector = EmbeddingDetector(model_path.parent)
                model_info = detector.get_model_info(model_path.name)

                if not model_info or not model_info.get("valid"):
                    error = model_info.get("error") if model_info else "未知错误"
                    raise ValueError(f"模型验证失败: {error}")

                # 更新维度信息
                embedding.dimension = model_info["dimension"]

            # 如果新模型启用，禁用其他所有模型（单选模式）
            if embedding.enabled:
                for existing_embedding in self._embeddings.values():
                    existing_embedding.enabled = False

            self._embeddings[embedding.embedding_id] = embedding
            self._save_embeddings_unsafe()

    def generate_unique_id(self, base_id: str) -> str:
        """
        生成唯一的 embedding_id

        如果 base_id 已存在，自动添加 _1, _2, ... 后缀
        """
        if base_id not in self._embeddings:
            return base_id

        counter = 1
        while f"{base_id}_{counter}" in self._embeddings:
            counter += 1

        return f"{base_id}_{counter}"

    def update_embedding(self, embedding_id: str, updates: dict) -> None:
        """更新 embedding"""
        with self._operation_lock:
            if embedding_id not in self._embeddings:
                raise ValueError(f"Embedding ID '{embedding_id}' 不存在")

            embedding = self._embeddings[embedding_id]
            embedding_data = embedding.model_dump()

            # 深度合并更新
            self._deep_merge(embedding_data, updates)

            # 如果更新了路径，重新验证
            if "model_path" in updates and embedding_data["model_type"] == "local":
                model_path = Path(embedding_data["model_path"])
                if not model_path.exists():
                    raise ValueError(f"模型路径不存在: {embedding_data['model_path']}")

                detector = EmbeddingDetector(model_path.parent)
                model_info = detector.get_model_info(model_path.name)

                if not model_info or not model_info.get("valid"):
                    error = model_info.get("error") if model_info else "未知错误"
                    raise ValueError(f"模型验证失败: {error}")

                embedding_data["dimension"] = model_info["dimension"]

            # 如果启用此模型，禁用其他所有模型（单选模式）
            if "enabled" in updates and updates["enabled"]:
                for eid, existing_embedding in self._embeddings.items():
                    if eid != embedding_id:
                        existing_embedding.enabled = False

            self._embeddings[embedding_id] = EmbeddingConfig(**embedding_data)
            self._save_embeddings_unsafe()

    def delete_embedding(self, embedding_id: str) -> None:
        """删除 embedding"""
        with self._operation_lock:
            if embedding_id not in self._embeddings:
                raise ValueError(f"Embedding ID '{embedding_id}' 不存在")

            del self._embeddings[embedding_id]
            self._save_embeddings_unsafe()

    @staticmethod
    def _deep_merge(target: dict, source: dict) -> None:
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                EmbeddingManager._deep_merge(target[key], value)
            else:
                target[key] = value
