"""
Agent 业务路由

提供对话、技能学习、时间线、心跳等接口。
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import asyncio
import json as json_module

from backend.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])


# 请求/响应模型
class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ToolCallStep(BaseModel):
    """工具调用步骤"""
    tool_name: str
    arguments: dict
    result: str = ""
    status: str = "completed"


class ChatResponse(BaseModel):
    """对话响应"""
    message: str
    timestamp: str
    session_id: Optional[str] = None
    steps: List[ToolCallStep] = Field(default_factory=list)


class SkillLearningRequest(BaseModel):
    """技能学习请求"""
    description: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话接口"""
    from backend.api.server import session_manager

    # 截短 session ID 和 message
    session_short = request.session_id[:8] if request.session_id else "new"
    message_preview = request.message if len(request.message) <= 15 else f"{request.message[:15]}..."

    logger.info(f"收到对话请求: session={session_short}, message={message_preview}")
    try:
        # 如果没有 session_id，先创建会话以确定 ID
        if not request.session_id:
            from backend.config.settings import get_settings
            from backend.core.conversation import ConversationManager
            settings = get_settings()
            conv_manager = ConversationManager(settings.data_dir)
            request.session_id = conv_manager.create_session(workspace_id=request.workspace_id)

        # 按 session_id 获取或创建 MainAgent
        agent = session_manager.get_or_create(request.session_id)

        result = await agent.execute({
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
            session_id=result.get("session_id"),
            steps=result.get("steps", [])
        )
    except Exception as e:
        logger.error(f"对话处理失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _sse_response(agent, label=""):
    """从 session 订阅者生成 SSE 响应，多客户端共享同一 buffer"""

    async def generator():
        try:
            async for event in agent.subscribe_stream():
                if event.get("type") == "heartbeat":
                    yield ": heartbeat\n\n"
                else:
                    yield f"data: {json_module.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            if label:
                logger.info(f"SSE 客户端断开: {label}")
            return
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话（SSE）— 发送消息并订阅 session 事件流"""
    from backend.api.server import session_manager

    session_short = request.session_id[:8] if request.session_id else "new"
    message_preview = request.message if len(request.message) <= 15 else f"{request.message[:15]}..."
    logger.info(f"收到流式对话请求: session={session_short}, message={message_preview}")

    try:
        if not request.session_id:
            from backend.config.settings import get_settings
            from backend.core.conversation import ConversationManager
            settings = get_settings()
            conv_manager = ConversationManager(settings.data_dir)
            request.session_id = conv_manager.create_session(workspace_id=request.workspace_id)

        agent = session_manager.get_or_create(request.session_id)

        if agent._stream_buffer is not None and not agent._stream_done:
            raise HTTPException(status_code=409, detail="Session is busy, try watching instead")

        # 预初始化缓冲区，确保 subscribe_stream 可立即进入（stream_chat 会重新赋值）
        agent._stream_buffer = []
        agent._stream_done = False

        # 后台启动 LLM（stream_chat 内部会调用 _buffer_event 写入共享缓冲区）
        async def _drain():
            try:
                async for _event in agent.stream_chat({
                    "user_message": request.message,
                    "session_id": request.session_id,
                    "context": request.context or {},
                }):
                    pass  # 事件已通过 _buffer_event 写入共享缓冲区
            except Exception as e:
                logger.error(f"LLM 任务异常: {e}", exc_info=True)

        asyncio.create_task(_drain())

        return _sse_response(agent, label=f"chat:{session_short}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"流式对话启动失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ResumeRequest(BaseModel):
    """流式恢复请求"""
    session_id: str


@router.get("/chat/stream/status/{session_id}")
async def stream_status(session_id: str):
    """查询会话是否有正在进行的流式生成"""
    from backend.api.server import session_manager

    agent = session_manager.get(session_id)
    streaming = (
        agent is not None
        and agent._stream_buffer is not None
        and not agent._stream_done
    )
    return {"streaming": streaming}


@router.get("/chat/stream/watch/{session_id}")
async def watch_stream(session_id: str):
    """观察会话流式事件（纯订阅，不发送消息）"""
    from backend.api.server import session_manager

    agent = session_manager.get(session_id)
    if not agent or agent._stream_buffer is None or agent._stream_done:
        return {"streaming": False}

    logger.info(f"流式观察请求: session={session_id[:8]}")
    return _sse_response(agent, label=f"watch:{session_id[:8]}")


@router.post("/chat/stream/resume")
async def resume_stream(request: ResumeRequest):
    """恢复/加入流式对话（SSE），与 watch 等价"""
    from backend.api.server import session_manager

    session_short = request.session_id[:8]
    agent = session_manager.get(request.session_id)

    if not agent or agent._stream_buffer is None or agent._stream_done:
        return {"streaming": False}

    logger.info(f"流式恢复请求: session={session_short}, 已缓冲 {len(agent._stream_buffer)} 个事件")
    return _sse_response(agent, label=f"resume:{session_short}")


@router.post("/learn-skill")
async def learn_skill(request: SkillLearningRequest):
    """学习技能接口"""
    from backend.agents.main_agent import MainAgent

    logger.info(f"收到技能学习请求: {request.description[:50]}...")
    try:
        agent = MainAgent()
        result = await agent.execute({
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


# ===== 开发测试接口 =====

class SubagentTestRequest(BaseModel):
    """子 Agent 测试请求"""
    agent_type: str
    task: str


# 子 Agent 注册表：类型 → 类
_SUBAGENT_CLASSES = None


def _get_subagent_classes():
    """延迟加载子 Agent 类"""
    global _SUBAGENT_CLASSES
    if _SUBAGENT_CLASSES is None:
        from backend.agents.subagents.filesystem import FilesystemAgent
        from backend.agents.subagents.skill_learner import SkillLearnerAgent
        _SUBAGENT_CLASSES = {
            "filesystem": FilesystemAgent,
            "skill_learner": SkillLearnerAgent,
        }
    return _SUBAGENT_CLASSES


@router.post("/test-subagent")
async def test_subagent(request: SubagentTestRequest):
    """直接测试子 Agent（开发用，跳过主 Agent 调度）"""
    classes = _get_subagent_classes()

    if request.agent_type not in classes:
        raise HTTPException(
            status_code=400,
            detail=f"未知子 Agent: {request.agent_type}，可用: {list(classes.keys())}"
        )

    logger.info(f"测试子 Agent: {request.agent_type}, 任务: {request.task[:50]}")
    try:
        agent = classes[request.agent_type]()
        result = await agent.execute({"task": request.task})
        return {"agent_type": request.agent_type, "response": result.get("response", "")}
    except Exception as e:
        logger.error(f"子 Agent 测试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
