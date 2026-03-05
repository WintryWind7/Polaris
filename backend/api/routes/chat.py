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
    """获取指定会话的历史消息"""
    try:
        messages = manager.get_session_messages(session_id)
        if not messages and not manager.get_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load history: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, manager: ConversationManager = Depends(get_conversation_manager)):
    """删除指定的会话"""
    try:
        manager.delete_session(session_id)
        return {"success": True, "message": f"Session {session_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")
