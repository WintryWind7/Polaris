"""
Embedding 配置 API 路由

提供本地 Embedding 模型的检测和配置接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import List
from backend.core.embedding_detector import scan_local_models, EmbeddingDetector
from backend.config.embedding_manager import EmbeddingManager
from backend.config.models import EmbeddingConfig

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])
embedding_manager = EmbeddingManager()


class AddEmbeddingRequest(BaseModel):
    """添加 Embedding 请求"""
    embedding_id: str  # Embedding ID
    model_type: str = "local"  # 模型类型
    model_path: str = ""  # 模型路径（绝对路径）


class UpdateEmbeddingRequest(BaseModel):
    """更新 Embedding 请求"""
    model_path: str | None = None
    enabled: bool | None = None


@router.get("")
async def get_all_embeddings():
    """
    获取所有 Embeddings

    Returns:
        所有 Embeddings 配置
    """
    try:
        embeddings = embedding_manager.get_all_embeddings()
        return {eid: e.model_dump() for eid, e in embeddings.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Embeddings 失败: {str(e)}")


@router.get("/active")
async def get_active_embedding():
    """
    获取当前启用的 Embedding

    Returns:
        当前启用的 Embedding 配置，如果没有则返回 null
    """
    try:
        active = embedding_manager.get_active_embedding()
        if active:
            return active.model_dump()
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取活跃 Embedding 失败: {str(e)}")


@router.get("/compatibility")
async def check_compatibility():
    """
    检查当前配置的模型和数据库中的模型是否兼容

    Returns:
        {
            "compatible": true/false,
            "current_model": "bge-small-zh-v1.5",
            "current_dimension": 384,
            "db_model": "bge-small-zh-v1.5",
            "db_dimension": 384,
            "message": "模型兼容"
        }
    """
    try:
        result = embedding_manager.check_compatibility()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查兼容性失败: {str(e)}")


@router.get("/{embedding_id}")
async def get_embedding(embedding_id: str):
    """
    获取指定 Embedding

    Args:
        embedding_id: Embedding ID

    Returns:
        Embedding 配置
    """
    try:
        embedding = embedding_manager.get_embedding(embedding_id)
        if not embedding:
            raise HTTPException(status_code=404, detail=f"Embedding '{embedding_id}' 不存在")
        return embedding.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Embedding 失败: {str(e)}")


@router.post("")
async def add_embedding(request: AddEmbeddingRequest):
    """
    添加 Embedding

    Args:
        request: 添加 Embedding 请求

    Returns:
        添加结果
    """
    try:
        # 生成唯一的 embedding_id（如果重复则自动添加 _1, _2 后缀）
        unique_id = embedding_manager.generate_unique_id(request.embedding_id)

        # 创建 Embedding
        embedding = EmbeddingConfig(
            embedding_id=unique_id,
            model_type=request.model_type,
            model_path=request.model_path
        )

        embedding_manager.add_embedding(embedding)

        return {
            "status": "success",
            "message": "Embedding 添加成功",
            "embedding_id": unique_id
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加 Embedding 失败: {str(e)}")


@router.put("/{embedding_id}")
async def update_embedding(embedding_id: str, request: UpdateEmbeddingRequest):
    """
    更新 Embedding

    Args:
        embedding_id: Embedding ID
        request: 更新请求

    Returns:
        更新结果
    """
    try:
        # 构建更新数据（只包含非 None 的字段）
        updates = {}
        if request.model_path is not None:
            updates["model_path"] = request.model_path
        if request.enabled is not None:
            updates["enabled"] = request.enabled

        embedding_manager.update_embedding(embedding_id, updates)

        return {
            "status": "success",
            "message": "Embedding 更新成功"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新 Embedding 失败: {str(e)}")


@router.delete("/{embedding_id}")
async def delete_embedding(embedding_id: str):
    """
    删除 Embedding

    Args:
        embedding_id: Embedding ID

    Returns:
        删除结果
    """
    try:
        embedding_manager.delete_embedding(embedding_id)

        return {
            "status": "success",
            "message": "Embedding 删除成功"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Embedding 失败: {str(e)}")


@router.post("/rebuild")
async def rebuild_embeddings():
    """
    重建向量数据库

    从消息表中重新生成所有 embedding

    Returns:
        {
            "status": "success",
            "total": 100,
            "success": 98,
            "failed": 2
        }
    """
    try:
        from backend.core.vector_search import VectorSearchService
        from backend.core.embedding import get_embedding_service
        from backend.config.settings import get_settings

        # 获取配置
        settings = get_settings()
        db_path = settings.data_dir / "conversations.db"

        if not db_path.exists():
            raise HTTPException(status_code=404, detail="数据库不存在")

        # 初始化服务
        embedding_service = get_embedding_service()
        model_info = embedding_service.get_model_info()

        vector_search = VectorSearchService(db_path)

        # 定义编码函数
        def encode_func(text: str) -> list:
            return embedding_service.encode(text)

        # 重建
        result = vector_search.rebuild_all(encode_func, batch_size=100)

        # 保存模型信息
        vector_search.set_metadata("model_provider", model_info["provider"])
        vector_search.set_metadata("model_name", model_info["model_name"])
        vector_search.set_metadata("dimension", str(model_info["dimension"]))

        return {
            "status": "success",
            "total": result["total"],
            "success": result["success"],
            "failed": result["failed"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重建失败: {str(e)}")


@router.get("/scan/local")
async def scan_embeddings():
    """
    扫描本地 Embedding 模型

    Returns:
        {
            "models": [
                {
                    "model_id": "bge-small-zh-v1.5",
                    "model_path": "data/models/embeddings/bge-small-zh-v1.5",
                    "dimension": 384,
                    "model_type": "bert",
                    "weight_format": "safetensors",
                    "weight_size_mb": 95.2,
                    "valid": true,
                    "error": null
                },
                ...
            ],
            "total": 2,
            "valid": 2,
            "invalid": 0
        }
    """
    try:
        models = scan_local_models()

        valid_count = sum(1 for m in models if m['valid'])
        invalid_count = len(models) - valid_count

        return {
            "models": models,
            "total": len(models),
            "valid": valid_count,
            "invalid": invalid_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描失败: {str(e)}")


@router.get("/scan/{model_id}")
async def get_embedding_info(model_id: str):
    """
    获取指定模型的详细信息

    Args:
        model_id: 模型 ID（目录名）

    Returns:
        模型详细信息
    """
    try:
        base_dir = Path(__file__).parent.parent.parent  # backend/
        models_dir = base_dir / "data" / "models" / "embeddings"
        detector = EmbeddingDetector(models_dir)

        model_info = detector.get_model_info(model_id)

        if model_info is None:
            raise HTTPException(status_code=404, detail=f"模型 '{model_id}' 不存在")

        return model_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型信息失败: {str(e)}")


@router.get("/directory/info")
async def get_embeddings_directory():
    """
    获取 Embedding 模型目录路径

    Returns:
        {
            "path": "data/models/embeddings",
            "absolute_path": "C:/Users/.../data/models/embeddings",
            "exists": true
        }
    """
    try:
        backend_dir = Path(__file__).parent.parent.parent  # backend/
        models_dir = backend_dir / "data" / "models" / "embeddings"

        return {
            "path": str(models_dir.relative_to(backend_dir)),
            "absolute_path": str(models_dir.absolute()),
            "exists": models_dir.exists()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取目录信息失败: {str(e)}")


@router.post("/directory/browse")
async def browse_directory(path: str = ""):
    """
    浏览文件系统目录

    Args:
        path: 目录路径（空字符串表示默认目录）

    Returns:
        {
            "current_path": "C:/Users/...",
            "parent_path": "C:/Users",
            "folders": ["folder1", "folder2", ...],
            "is_valid_model": false
        }
    """
    try:
        # 如果没有提供路径，使用默认的 embeddings 目录
        if not path:
            base_dir = Path(__file__).parent.parent.parent  # backend/
            target_path = base_dir / "data" / "models" / "embeddings"
        else:
            target_path = Path(path)

        # 安全检查：确保路径存在且是目录
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="路径不存在")

        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="不是有效的目录")

        # 获取父目录
        parent_path = str(target_path.parent) if target_path.parent != target_path else None

        # 列出所有子文件夹
        folders = []
        try:
            for item in target_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    folders.append(item.name)
        except PermissionError:
            pass

        folders.sort()

        # 检查当前目录是否是有效的模型目录
        detector = EmbeddingDetector(target_path.parent)
        model_info = detector.get_model_info(target_path.name)
        is_valid_model = model_info and model_info.get("valid", False)

        return {
            "current_path": str(target_path.absolute()),
            "parent_path": parent_path,
            "folders": folders,
            "is_valid_model": is_valid_model
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"浏览目录失败: {str(e)}")

