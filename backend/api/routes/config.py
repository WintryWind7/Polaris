"""
配置管理 API 路由

提供配置的读取、更新、重载等接口。
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.config.manager import ConfigManager

_RESTART_FILE = Path(__file__).parent.parent.parent / "data" / ".restart"


def _write_restart_signal():
    """写入重启信号文件"""
    _RESTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RESTART_FILE.touch()

router = APIRouter(prefix="/api/config", tags=["config"])
config_manager = ConfigManager()


@router.get("")
async def get_config():
    """
    获取配置（API Key 脱敏）
    """
    try:
        return config_manager.get_masked_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("")
async def update_config(updates: dict):
    """
    更新配置
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
    """
    try:
        config_manager.reload()
        return {"status": "success", "message": "配置已重新加载"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新加载配置失败: {str(e)}")


@router.get("/providers")
async def get_providers():
    """获取支持的 LLM 提供商列表"""
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
    """更新前后端端口配置"""
    try:
        config_manager.update({
            "server": {
                "port": ports.backend_port,
                "frontend_port": ports.frontend_port
            }
        })
        return {"status": "success", "message": "端口配置已保存"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"保存失败: {str(e)}")


@router.post("/restart")
async def restart_services(ports: PortsConfig):
    """保存端口并触发重启"""
    try:
        config_manager.update({
            "server": {
                "port": ports.backend_port,
                "frontend_port": ports.frontend_port
            }
        })
        _write_restart_signal()
        return {
            "status": "restarting",
            "message": "服务即将重启",
            "new_frontend_port": ports.frontend_port
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重启失败: {str(e)}")
