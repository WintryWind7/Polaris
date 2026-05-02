"""
Chat 会话路由

提供 /api/chat/sessions 等会话管理接口
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any

from backend.core.conversation import ConversationManager
from backend.config.settings import get_settings

router = APIRouter(prefix="/api/chat", tags=["chat"])

def get_conversation_manager() -> ConversationManager:
    """依赖注入 ConversationManager"""
    settings = get_settings()
    return ConversationManager(settings.data_dir)


@router.get("/sessions")
async def get_sessions(manager: ConversationManager = Depends(get_conversation_manager)):
    """获取所有会话列表"""
    try:
        sessions = manager.list_sessions()
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load sessions: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session_history(session_id: str, manager: ConversationManager = Depends(get_conversation_manager)):
    """获取指定会话的历史消息和元数据"""
    try:
        session = manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        messages = manager.get_session_messages(session_id)
        return {
            "session": {
                "id": session.get("id"),
                "workspace_id": session.get("workspace_id"),
                "title": session.get("title"),
                "created_at": session.get("created_at"),
                "updated_at": session.get("updated_at"),
            },
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load history: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, manager: ConversationManager = Depends(get_conversation_manager)):
    """删除指定的会话"""
    try:
        manager.delete_session(session_id)
        # 同步清理 SessionManager 中的 MainAgent
        from backend.api.server import session_manager
        session_manager.delete(session_id)
        return {"success": True, "message": f"Session {session_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")
