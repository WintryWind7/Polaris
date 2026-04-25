"""
工作空间 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict

from backend.core.workspace import WorkspaceManager
from backend.config.settings import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def get_workspace_manager() -> WorkspaceManager:
    settings = get_settings()
    return WorkspaceManager(settings.data_dir)


class CreateWorkspaceRequest(BaseModel):
    name: str
    path: str


class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None


@router.get("")
async def list_workspaces():
    try:
        manager = get_workspace_manager()
        return {"workspaces": manager.list_workspaces()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取工作空间列表失败: {str(e)}")


@router.post("")
async def create_workspace(request: CreateWorkspaceRequest):
    try:
        manager = get_workspace_manager()

        # 检查路径是否已存在
        existing = manager.get_workspace_by_path(request.path)
        if existing:
            raise HTTPException(status_code=409, detail=f"路径已绑定到工作空间: {existing['name']}")

        workspace_id = manager.create_workspace(request.name, request.path)
        return {"status": "success", "workspace_id": workspace_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建工作空间失败: {str(e)}")


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str):
    try:
        manager = get_workspace_manager()
        workspace = manager.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="工作空间不存在")
        return workspace
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取工作空间失败: {str(e)}")


@router.put("/{workspace_id}")
async def update_workspace(workspace_id: str, request: UpdateWorkspaceRequest):
    try:
        manager = get_workspace_manager()
        workspace = manager.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.path is not None:
            updates["path"] = request.path

        manager.update_workspace(workspace_id, updates)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新工作空间失败: {str(e)}")


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str):
    try:
        manager = get_workspace_manager()
        workspace = manager.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        manager.delete_workspace(workspace_id)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除工作空间失败: {str(e)}")


@router.get("/{workspace_id}/sessions")
async def get_workspace_sessions(workspace_id: str):
    try:
        manager = get_workspace_manager()
        workspace = manager.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        sessions = manager.get_workspace_sessions(workspace_id)
        return {"sessions": sessions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")
