"""
Agent 业务路由

提供对话、技能学习、时间线、心跳等接口。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])


# 请求/响应模型
class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """对话响应"""
    message: str
    timestamp: str
    session_id: Optional[str] = None


class SkillLearningRequest(BaseModel):
    """技能学习请求"""
    description: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话接口"""
    from backend.api.server import main_agent

    # 截短 session ID 和 message
    session_short = request.session_id[:8] if request.session_id else "new"
    message_preview = request.message if len(request.message) <= 15 else f"{request.message[:15]}..."

    logger.info(f"收到对话请求: session={session_short}, message={message_preview}")
    try:
        result = await main_agent.execute({
            "type": "chat",
            "data": {
                "user_message": request.message,
                "session_id": request.session_id,
                "context": request.context or {}
            }
        })

        session_result = result.get('session_id', '')[:8] if result.get('session_id') else ''
        response_msg = result["assistant_message"]
        response_preview = response_msg if len(response_msg) <= 15 else f"{response_msg[:15]}..."
        logger.info(f"对话处理完成: session={session_result}, response={response_preview}")
        return ChatResponse(
            message=result["assistant_message"],
            timestamp=result["timestamp"],
            session_id=result.get("session_id")
        )
    except Exception as e:
        logger.error(f"对话处理失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learn-skill")
async def learn_skill(request: SkillLearningRequest):
    """学习技能接口"""
    from backend.api.server import main_agent

    logger.info(f"收到技能学习请求: {request.description[:50]}...")
    try:
        result = await main_agent.execute({
            "type": "learn_skill",
            "data": {"description": request.description}
        })
        logger.info("技能学习完成")
        return result
    except Exception as e:
        logger.error(f"技能学习失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline")
async def get_timeline(limit: int = 10):
    """获取时间线"""
    from backend.api.server import memory_system

    events = memory_system.get_recent_chats(limit)
    return {
        "events": [event.to_dict() for event in events]
    }


@router.get("/heartbeat")
async def heartbeat_check():
    """心跳检查接口"""
    from backend.api.server import heartbeat_agent

    logger.debug("[heartbeat] 开始执行心跳检查")
    result = await heartbeat_agent.execute({})
    logger.debug(f"[heartbeat] 检查完成: should_wake={result.get('should_wake')}")
    return result
