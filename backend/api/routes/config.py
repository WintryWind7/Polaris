"""
配置管理 API 路由

提供配置的读取、更新、重载等接口。
"""
from fastapi import APIRouter, HTTPException
from backend.config.manager import ConfigManager

router = APIRouter(prefix="/api/config", tags=["config"])
config_manager = ConfigManager()


@router.get("")
async def get_config():
    """
    获取配置（API Key 脱敏）

    Returns:
        脱敏后的配置数据
    """
    try:
        return config_manager.get_masked_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("")
async def update_config(updates: dict):
    """
    更新配置

    Args:
        updates: 要更新的配置项（支持部分更新）

    Returns:
        更新状态
    """
    try:
        config_manager.update(updates)
        return {"status": "success", "message": "配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新配置失败: {str(e)}")


@router.post("/reload")
async def reload_config():
    """
    重新加载配置

    Returns:
        重载状态
    """
    try:
        config_manager.reload()
        return {"status": "success", "message": "配置已重新加载"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新加载配置失败: {str(e)}")


@router.get("/providers")
async def get_providers():
    """
    获取支持的 LLM 提供商列表

    Returns:
        提供商配置（API Key 脱敏）
    """
    try:
        masked_config = config_manager.get_masked_config()
        return masked_config.get("llm", {}).get("providers", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取提供商列表失败: {str(e)}")
