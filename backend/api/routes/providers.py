"""
Provider 配置 API 路由

提供 Provider 的增删改查接口。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from backend.config.provider_manager import ProviderManager
from backend.config.models import ProviderConfig, ModelConfig

router = APIRouter(prefix="/api/providers", tags=["providers"])
provider_manager = ProviderManager()


class AddProviderRequest(BaseModel):
    """添加 Provider 请求"""
    provider_id: str  # Provider ID（也是显示名称）
    api_key: str = ""
    api_base_url: str = ""
    models: List[ModelConfig] = []


class UpdateProviderRequest(BaseModel):
    """更新 Provider 请求"""
    api_key: str | None = None
    api_base_url: str | None = None
    models: List[ModelConfig] | None = None


@router.get("")
async def get_all_providers():
    """
    获取所有 Providers

    Returns:
        所有 Providers 配置
    """
    try:
        providers = provider_manager.get_all_providers()
        return {pid: p.model_dump() for pid, p in providers.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Providers 失败: {str(e)}")


@router.get("/{provider_id}")
async def get_provider(provider_id: str):
    """
    获取指定 Provider

    Args:
        provider_id: Provider ID

    Returns:
        Provider 配置
    """
    try:
        provider = provider_manager.get_provider(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' 不存在")
        return provider.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Provider 失败: {str(e)}")


@router.post("")
async def add_provider(request: AddProviderRequest):
    """
    添加 Provider

    Args:
        request: 添加 Provider 请求

    Returns:
        添加结果
    """
    try:
        # 生成唯一的 provider_id（如果重复则自动添加 _1, _2 后缀）
        unique_id = provider_manager.generate_unique_id(request.provider_id)

        # 创建 Provider
        provider = ProviderConfig(
            provider_id=unique_id,
            api_key=request.api_key,
            api_base_url=request.api_base_url,
            models=request.models
        )

        provider_manager.add_provider(provider)

        return {
            "status": "success",
            "message": "Provider 添加成功",
            "provider_id": unique_id
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加 Provider 失败: {str(e)}")


@router.put("/{provider_id}")
async def update_provider(provider_id: str, request: UpdateProviderRequest):
    """
    更新 Provider

    Args:
        provider_id: Provider ID
        request: 更新请求

    Returns:
        更新结果
    """
    try:
        # 构建更新数据（只包含非 None 的字段）
        updates = {}
        if request.api_key is not None:
            updates["api_key"] = request.api_key
        if request.api_base_url is not None:
            updates["api_base_url"] = request.api_base_url
        if request.models is not None:
            updates["models"] = [m.model_dump() for m in request.models]

        provider_manager.update_provider(provider_id, updates)

        return {
            "status": "success",
            "message": "Provider 更新成功"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新 Provider 失败: {str(e)}")


@router.delete("/{provider_id}")
async def delete_provider(provider_id: str):
    """
    删除 Provider

    Args:
        provider_id: Provider ID

    Returns:
        删除结果
    """
    try:
        provider_manager.delete_provider(provider_id)

        return {
            "status": "success",
            "message": "Provider 删除成功"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Provider 失败: {str(e)}")
