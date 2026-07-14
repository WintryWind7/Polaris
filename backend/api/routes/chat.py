"""
Chat 对话路由

单一对话线程模型：只有一个默认会话，仅提供历史消息查询。
"""
from fastapi import APIRouter, Depends

from backend.core.conversation import ConversationManager
from backend.config.settings import get_settings

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_conversation_manager() -> ConversationManager:
    """依赖注入 ConversationManager"""
    settings = get_settings()
    return ConversationManager(settings.data_dir)


@router.get("/history")
async def get_history(manager: ConversationManager = Depends(get_conversation_manager)):
    """获取对话历史"""
    sid = manager.DEFAULT_SESSION_ID
    messages = manager.get_session_messages(sid)
    return {"messages": messages}
