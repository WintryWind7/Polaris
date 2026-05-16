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


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口（SSE）— LLM 后台处理，与 SSE 连接解耦"""
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

        queue: asyncio.Queue = asyncio.Queue()

        async def background_llm_task():
            """后台任务：独立执行 LLM 处理，通过队列传递事件"""
            try:
                async for event in agent.stream_chat({
                    "user_message": request.message,
                    "session_id": request.session_id,
                    "context": request.context or {}
                }):
                    await queue.put(event)
            except Exception as e:
                logger.error(f"后台 LLM 任务异常: {e}", exc_info=True)
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(None)

        # 启动后台任务（不受 SSE 连接生命周期影响）
        asyncio.create_task(background_llm_task())

        async def event_generator():
            """从队列读取事件并推送 SSE，客户端断连不影响后台任务"""
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
                        continue

                    if event is None:
                        break

                    yield f"data: {json_module.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.CancelledError:
                # 客户端断开，后台任务继续运行并自动保存到 DB
                logger.info(f"SSE 客户端断开: session={session_short}, 后台任务继续")
                return

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

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


@router.post("/chat/stream/resume")
async def resume_stream(request: ResumeRequest):
    """恢复中断的流式对话（SSE）"""
    from backend.api.server import session_manager

    session_short = request.session_id[:8]
    agent = session_manager.get(request.session_id)

    if not agent or agent._stream_buffer is None or agent._stream_done:
        return {"streaming": False}

    logger.info(f"流式恢复请求: session={session_short}, 已缓冲 {len(agent._stream_buffer)} 个事件")

    async def resume_generator():
        """重放已有事件 + 继续流式新事件"""
        try:
            # 1. 重放所有已缓冲的事件
            for event in agent._stream_buffer:
                yield f"data: {json_module.dumps(event, ensure_ascii=False)}\n\n"

            # 2. 等待新事件
            idx = len(agent._stream_buffer)
            while True:
                if agent._stream_done:
                    # 流式结束，发送剩余事件
                    while idx < len(agent._stream_buffer):
                        yield f"data: {json_module.dumps(agent._stream_buffer[idx], ensure_ascii=False)}\n\n"
                        idx += 1
                    break

                # 等待新事件通知
                agent._stream_event.clear()
                try:
                    await asyncio.wait_for(agent._stream_event.wait(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                # 发送新到达的事件
                while idx < len(agent._stream_buffer):
                    evt = agent._stream_buffer[idx]
                    yield f"data: {json_module.dumps(evt, ensure_ascii=False)}\n\n"
                    idx += 1

        except asyncio.CancelledError:
            logger.info(f"流式恢复客户端断开: session={session_short}")
            return

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        resume_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


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
