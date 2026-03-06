"""
配置管理 API 路由

提供配置的读取、更新、重载等接口。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.config.manager import ConfigManager
from utils.launcher_utils import write_restart_signal

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


class PortsConfig(BaseModel):
    """端口配置请求体"""
    backend_port: int = Field(ge=1024, le=65535, description="后端端口")
    frontend_port: int = Field(ge=1024, le=65535, description="前端端口")


@router.post("/ports")
async def update_ports(ports: PortsConfig):
    """
    更新前后端端口配置并持久化到 config.json

    Args:
        ports: { backend_port, frontend_port }

    Returns:
        更新状态和新端口值
    """
    try:
        config_manager.update({
            "server": {
                "port": ports.backend_port,
                "frontend_port": ports.frontend_port
            }
        })
        return {
            "status": "success",
            "message": "端口配置已保存，重启后生效",
            "backend_port": ports.backend_port,
            "frontend_port": ports.frontend_port
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"保存端口配置失败: {str(e)}")


@router.post("/restart")
async def restart_services(ports: PortsConfig):
    """
    保存端口配置并触发服务重启。

    流程：保存 config.json → 写入 .restart 信号文件 → main.py 主循环检测到后重启前后端

    Returns:
        { status, new_frontend_port } —— 前端用 new_frontend_port 决定是否跳转
    """
    try:
        # 1. 保存新端口到 config.json
        config_manager.update({
            "server": {
                "port": ports.backend_port,
                "frontend_port": ports.frontend_port
            }
        })
        # 2. 写入重启信号文件，触发 main.py 主循环重启
        write_restart_signal()
        return {
            "status": "restarting",
            "message": "配置已保存，服务即将重启",
            "new_frontend_port": ports.frontend_port
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重启失败: {str(e)}")
