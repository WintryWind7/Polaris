"""
主 Agent

负责理解用户意图、调度子 Agent 执行任务。
不直接执行任何工具，只通过 subagent 工具进行分发。
"""
import json
import asyncio
from typing import Dict, Any, Optional, List
from .base import Agent
from .subagents.coding_agent import CodingAgent
from .subagents.web_agent import WebAgent
from .subagents.memory_agent import MemoryAgent
from ..logger import get_logger
from ..core.conversation import ConversationManager
from ..core.prompt_builder import PromptBuilder
from ..core.llm import LLMFactory
from .memory import MemorySystem
from ..core.state import StateManager
from ..config.settings import get_settings

logger = get_logger(__name__)

# 主 Agent 唯一的工具：调用子 Agent
SUBAGENT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "subagent",
        "description": "与子 Agent 通信的唯一方式。可用的子 Agent: coding（代码读写和搜索）、web（搜索和抓取网页）、memory（检索历史记忆）。同一 instance_id 可多次调用，子 Agent 会记住之前的对话。",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["coding", "web", "memory"],
                    "description": "要通信的子 Agent 类型"
                },
                "message": {
                    "type": "string",
                    "description": "发送给子 Agent 的消息。可以是指令（\"读取 auth.py\"）、问题（\"这个模块现在什么结构？\"）、讨论（\"如果要加 OAuth，你觉得该改哪里？\"）。子 Agent 执行后会回复。"
                },
                "instance_id": {
                    "type": "string",
                    "description": "子 Agent 实例标识，必填。同一 instance_id 的多次调用共享上下文（已读文件、工具历史、之前的对话）。不同 instance_id 完全隔离。用有意义的名字命名，如 'explore-auth'、'refactor-login'。并行任务用不同 instance_id。"
                }
            },
            "required": ["agent_type", "message", "instance_id"]
        }
    }
}


class StreamContext:
    """per-session 流式上下文，隔离并发请求"""
    def __init__(self):
        self.buffer: list = []
        self.done: bool = False
        self.waiter: asyncio.Event = asyncio.Event()


class MainAgent(Agent):
    """主 Agent（全局单例）"""

    def __init__(self, state_manager=None, memory_system=None):
        super().__init__("main")

        # 初始化对话管理
        settings = get_settings()
        self.conversation_manager = ConversationManager(settings.data_dir)
        self.prompt_builder = PromptBuilder()

        # 核心组件（接受外部注入，未注入时自动创建）
        self.memory_system = memory_system or MemorySystem(settings.data_dir)
        self.state_manager = state_manager or StateManager(settings.data_dir / "state.json")

        # 子 Agent 注册表（类型 → 类）
        self._subagent_classes = {
            "coding": CodingAgent,
            "web": WebAgent,
            "memory": MemoryAgent,
        }
        # 当前会话 ID（_handle_chat / stream_chat 设置）
        self._current_session_id: Optional[str] = None
        # 子 Agent 实例缓存（"{agent_type}:{instance_id}" → 实例），全局共享
        self._active_subagents: Dict[str, Agent] = {}

        # 流式上下文（per-session，并发隔离）
        self._streams: Dict[str, StreamContext] = {}

        # Token 统计（全局累计）
        self._token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        logger.info("MainAgent 初始化完成（全局单例），无工具，仅通过 subagent 调度")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 包含 type 和 data 的任务字典

        Returns:
            执行结果
        """
        task_type = task.get("type")

        if task_type == "chat":
            return await self._handle_chat(task["data"])
        elif task_type == "learn_skill":
            return await self._delegate_skill_learning(task["data"])
        else:
            logger.warning(f"未知任务类型: {task_type}")
            return {"error": f"Unknown task type: {task_type}"}

    async def _handle_chat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理对话

        Args:
            data: {
                "user_message": str,
                "session_id": Optional[str],
                "context": Optional[Dict]
            }

        Returns:
            包含 assistant_message 的字典
        """
        user_message = data["user_message"]
        session_id = data.get("session_id")
        context = data.get("context", {})

        # 重置本轮 token 统计
        self._token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # 1. 获取或创建会话
        self._current_session_id = session_id

        # 2. 获取历史消息
        history = self.conversation_manager.get_messages(
            session_id, limit=20, preserve_reasoning=self.preserve_reasoning
        )

        # 3. 构建 hooks context
        hooks_context = {
            "enable_skills": False,
            "session_id": session_id,
            "skills": [],
        }
        hooks_context.update(context)

        # 4. 构建 messages
        messages = self.prompt_builder.build_messages(
            user_message=user_message,
            history=history,
            context=hooks_context,
            max_history=20
        )

        try:
            # 5. 主 Agent 只有一个工具：subagent
            tools = [SUBAGENT_TOOL_SCHEMA]

            # 6. Function Calling 循环（最多 5 轮）
            max_iterations = 5
            final_response = None
            final_reasoning = None
            steps = []

            for iteration in range(max_iterations):
                response = await self.call_llm(messages, tools)

                # 记录本轮 token 用量（替换而非累加，反映当前上下文占用量）
                usage = response.get("usage", {})
                if usage:
                    self._token_usage["prompt_tokens"] = usage.get("prompt_tokens", 0)
                    self._token_usage["completion_tokens"] = usage.get("completion_tokens", 0)
                    self._token_usage["total_tokens"] = usage.get("total_tokens", 0)

                tool_calls = response.get("tool_calls", [])
                reasoning = response.get("reasoning_content")

                if not tool_calls:
                    final_response = response.get("content")
                    final_reasoning = reasoning
                    break

                # 将 assistant 的 tool_calls 加入 messages
                msg = {
                    "role": "assistant",
                    "content": response.get("content"),
                    "tool_calls": tool_calls
                }
                if reasoning:
                    msg["reasoning_content"] = reasoning
                messages.append(msg)

                # 处理 subagent 工具调用
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])

                    if function_name == "subagent":
                        result = await self._dispatch_subagent(tool_call)
                    else:
                        result = json.dumps(
                            {"success": False, "error": f"未知工具: {function_name}"},
                            ensure_ascii=False
                        )

                    result_data = json.loads(result)
                    steps.append({
                        "tool_name": function_name,
                        "arguments": arguments,
                        "result": result_data.get("response", "") if result_data.get("success") else result_data.get("error", ""),
                        "status": "completed" if result_data.get("success") else "error"
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": result
                    })

            if final_response is None:
                final_response = "抱歉，处理超出限制"
                logger.warning(f"Function Calling 超过最大轮数: {max_iterations}")

            # 7. 保存到会话
            self.conversation_manager.add_message(session_id, "user", user_message)

            # 保存工具调用历史
            history_start_idx = len(history) + 1
            for i in range(history_start_idx, len(messages)):
                msg = messages[i]
                if msg["role"] == "assistant" and "tool_calls" in msg:
                    tool_calls_json = json.dumps(msg["tool_calls"], ensure_ascii=False)
                    message_id = self.conversation_manager.add_message(
                        session_id, "assistant",
                        content=tool_calls_json,
                        tool_execution_id=None,
                        reasoning_content=msg.get("reasoning_content")
                    )
                    tool_results = []
                    for j in range(i + 1, len(messages)):
                        if messages[j]["role"] == "tool":
                            tool_results.append(messages[j])
                        elif messages[j]["role"] == "assistant":
                            break
                    if tool_results:
                        tool_execution_id = self.conversation_manager.add_tool_execution(
                            session_id, message_id, tool_results
                        )
                        from ..core.database import get_connection
                        conn = get_connection(self.conversation_manager.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE messages SET tool_execution_id = ? WHERE id = ?",
                            (tool_execution_id, message_id)
                        )
                        conn.commit()
                        conn.close()

            self.conversation_manager.add_message(
                session_id, "assistant", final_response,
                reasoning_content=final_reasoning
            )

            return {
                "assistant_message": final_response,
                "session_id": session_id,
                "timestamp": self.created_at.isoformat(),
                "steps": steps
            }
        except Exception as e:
            logger.error(f"对话处理失败: {e}", exc_info=True)
            return {
                "assistant_message": f"抱歉，处理消息时出错: {str(e)}",
                "session_id": session_id,
                "timestamp": self.created_at.isoformat(),
                "error": str(e)
            }

    def _build_subagent_context(
        self, session_id: str, task_description: str
    ) -> Dict[str, Any]:
        """为子 Agent 构建注入上下文"""
        context: Dict[str, Any] = {}

        # 1. 最近历史（精简，仅 user/assistant 文本）
        recent = self.conversation_manager.get_messages(
            session_id, limit=10, preserve_reasoning=self.preserve_reasoning
        )
        context["recent_history"] = [
            {"role": m["role"], "content": (m.get("content") or "")[:200]}
            for m in recent[-6:]
            if m.get("content") and not isinstance(m.get("content"), list)
        ]

        # 2. 用户偏好
        context["user_preferences"] = self.state_manager.get_all()

        # 3. 相关记忆
        if task_description:
            try:
                memories = self.conversation_manager.search_memory(
                    task_description[:200], limit=3, role="user"
                )
                context["relevant_memories"] = [
                    {
                        "content": m["matched_content"][:300],
                        "time": m.get("updated_at", ""),
                    }
                    for m in (memories or [])
                ]
            except Exception:
                context["relevant_memories"] = []

        context["session_id"] = session_id
        return context

    async def _handle_subagent_ask(
        self, question: str, session_id: str, agent_type: str
    ) -> Dict[str, str]:
        """
        Auto-reply 决策：查记忆后用主 LLM 判断是替答还是升级给用户。

        Returns:
            {"action": "answer", "content": str}
            {"action": "escalate", "content": str}
        """
        # 检索相关记忆
        memories = []
        try:
            memories = self.conversation_manager.search_memory(
                question[:200], limit=3, role="all"
            ) or []
        except Exception:
            pass

        memory_text = ""
        if memories:
            items = []
            for m in memories[:3]:
                items.append(f"- [{m.get('updated_at', '?')}] {m.get('matched_content', '')[:300]}")
            memory_text = "\n".join(items)

        # 同时查用户偏好（StateManager），与对话记忆互补
        preferences = self.state_manager.get_all()
        pref_text = ""
        if preferences:
            pref_items = [f"- {k}: {v}" for k, v in preferences.items() if v]
            if pref_items:
                pref_text = "\n".join(pref_items)

        decision_prompt = f"""子 Agent（{agent_type}）在执行任务时向你提出了问题：

【问题】
{question}

【用户偏好】
{pref_text or '无已知偏好'}

【相关对话记忆】
{memory_text or '无相关记忆'}

请判断：
1. 如果你能从用户偏好或记忆中确定答案，返回 {{"action": "answer", "content": "你的回答"}}
2. 如果必须用户确认（涉及主观偏好、安全决策、信息完全缺失），返回 {{"action": "escalate", "content": "需向用户提问的内容"}}

只返回 JSON，无其他文字。"""

        try:
            decision = await self.call_llm([
                {"role": "user", "content": decision_prompt}
            ])
            content = decision.get("content", "").strip()
            # 提取 JSON
            if "{" in content:
                content = content[content.index("{"):content.rindex("}") + 1]
            result = json.loads(content)
            return {"action": result.get("action", "escalate"), "content": result.get("content", question)}
        except Exception:
            return {"action": "escalate", "content": question}

    def _resolve_subagent(self, agent_type: str, instance_id: str):
        """获取或创建子 Agent 实例。instance_id 相同的调用共享上下文。instance_id 必填，缺了返回错误。"""
        if not instance_id:
            return None, "缺少 instance_id——请指定要使用哪个子 Agent 实例（如 'refactor-auth'、'search-docs'）。每次调用 subagent 工具时必须显式提供 instance_id。"

        cache_key = f"{agent_type}:{instance_id}"

        agent = self._active_subagents.get(cache_key)
        if not agent:
            agent_class = self._subagent_classes.get(agent_type)
            if not agent_class:
                return None, f"未知子 Agent 类型: {agent_type}"
            agent = agent_class()
            self._active_subagents[cache_key] = agent
            logger.info(f"创建子 Agent 实例: {cache_key}")

        return agent, cache_key

    async def _dispatch_subagent(self, tool_call: Dict[str, Any]) -> str:
        """
        根据工具调用分发到对应子 Agent，注入上下文，处理反问循环。
        """
        arguments = json.loads(tool_call["function"]["arguments"])
        agent_type = arguments.get("agent_type", "")
        task_description = arguments.get("message", "")
        instance_id = arguments.get("instance_id", "")

        agent, cache_key = self._resolve_subagent(agent_type, instance_id)
        if not agent:
            return json.dumps(
                {"success": False, "error": cache_key, "instance_id": instance_id},
                ensure_ascii=False
            )

        logger.info(f"调度子 Agent [{instance_id}]: {agent_type}, 任务: {task_description[:50]}")

        try:
            context = {}
            if self._current_session_id:
                context = self._build_subagent_context(
                    self._current_session_id, task_description
                )

            result = await agent.execute({
                "message": task_description,
                "context": context
            })

            # 反问循环
            ask_count = 0
            max_asks = getattr(agent, "max_ask_rounds", 3)
            while result.get("status") == "ask" and ask_count < max_asks:
                question = result.get("question", "")
                logger.info(f"子 Agent [{instance_id}] 反问: {question[:80]}")
                decision = await self._handle_subagent_ask(
                    question, self._current_session_id or "", agent_type
                )
                if decision["action"] == "answer":
                    logger.info(f"自动替答: {decision['content'][:60]}")
                    result = await agent.resume({"answer": decision["content"]})
                    ask_count += 1
                else:
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"需要用户确认: {question}",
                            "needs_user_input": True,
                            "question": decision["content"],
                            "instance_id": instance_id,
                        },
                        ensure_ascii=False
                    )

            if result.get("status") == "complete":
                response = result.get("response", "")
                return json.dumps(
                    {"success": True, "response": response, "instance_id": instance_id},
                    ensure_ascii=False
                )
            return json.dumps(
                {"success": False, "error": result.get("error", "执行失败"), "instance_id": instance_id},
                ensure_ascii=False
            )
        except Exception as e:
            logger.error(f"子 Agent 执行失败: {e}", exc_info=True)
            return json.dumps(
                {"success": False, "error": str(e), "instance_id": instance_id},
                ensure_ascii=False
            )

    async def _dispatch_subagent_stream(self, tool_call: Dict[str, Any]):
        """
        流式分发子 Agent，透传子 Agent 内部事件给前端。

        Yields:
            {"type": "text", "content": "..."}          子 Agent LLM 逐 token 输出
            {"type": "tool_call", "tool_name": "...", ...}  子 Agent 调用工具
            {"type": "tool_result", "result": "...", ...}   工具执行结果
            {"type": "escalate", "question": "..."}         反问升级给用户
        """
        arguments = json.loads(tool_call["function"]["arguments"])
        agent_type = arguments.get("agent_type", "")
        task_description = arguments.get("message", "")
        instance_id = arguments.get("instance_id", "")

        agent, cache_key = self._resolve_subagent(agent_type, instance_id)
        if not agent:
            yield {
                "type": "tool_result",
                "tool_name": "subagent",
                "result": cache_key,
                "status": "error",
                "instance_id": instance_id,
            }
            return

        context = {}
        if self._current_session_id:
            context = self._build_subagent_context(
                self._current_session_id, task_description
            )

        logger.info(f"流式调度子 Agent [{instance_id}]: {agent_type}, 任务: {task_description[:50]}")

        try:
            # 开启子 Agent 流式执行
            stream = agent.execute_stream({
                "message": task_description,
                "context": context
            })

            ask_count = 0
            max_asks = getattr(agent, "max_ask_rounds", 3)

            while True:
                try:
                    event = await stream.__anext__()
                except StopAsyncIteration:
                    break

                if event.get("type") == "ask":
                    question = event.get("question", "")
                    logger.info(f"子 Agent [{instance_id}] 反问: {question[:80]}")
                    decision = await self._handle_subagent_ask(
                        question, self._current_session_id or "", agent_type
                    )
                    if decision["action"] == "answer":
                        logger.info(f"自动替答: {decision['content'][:60]}")
                        ask_count += 1
                        if ask_count < max_asks:
                            stream = agent.resume_stream({"answer": decision["content"]})
                            continue
                    else:
                        yield {
                            "type": "escalate",
                            "question": decision["content"],
                            "instance_id": instance_id,
                        }
                        return

                # 注入 instance_id 到每个事件
                event["instance_id"] = instance_id
                yield event

        except Exception as e:
            logger.error(f"子 Agent 流式执行失败: {e}", exc_info=True)
            yield {
                "type": "tool_result",
                "tool_name": "subagent",
                "result": str(e),
                "status": "error",
                "instance_id": instance_id,
            }

    async def _delegate_skill_learning(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        委派技能学习任务给子 Agent
        """
        from .subagents.skill_learner import SkillLearnerAgent
        agent = SkillLearnerAgent()
        return await agent.execute(data)

    async def stream_chat(self, data: Dict[str, Any]):
        """
        流式对话处理，逐步 yield SSE 事件。

        事件类型：
        - session: {session_id}
        - tool_call: {tool_name, arguments}
        - tool_result: {tool_name, arguments, result, status}
        - text: {content}（逐块推送）
        - done: {session_id}
        - error: {message}
        """
        user_message = data["user_message"]
        session_id = data.get("session_id")
        context = data.get("context", {})

        # 重置本轮 token 统计
        self._token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        self._current_session_id = session_id

        # 初始化 per-session 流式上下文
        ctx = StreamContext()
        self._streams[session_id] = ctx

        evt = {"type": "session", "session_id": session_id}
        self._buffer_event(evt)
        yield evt

        history = self.conversation_manager.get_messages(
            session_id, limit=20, preserve_reasoning=self.preserve_reasoning
        )

        hooks_context = {
            "enable_skills": False,
            "session_id": session_id,
            "skills": [],
        }
        hooks_context.update(context)

        messages = self.prompt_builder.build_messages(
            user_message=user_message,
            history=history,
            context=hooks_context,
            max_history=20
        )

        try:
            user_msg_seq = 0

            provider = LLMFactory.get_provider(
                model=self.model,
                api_key=self.api_key,
                api_base=self.api_base,
                api_format=self.api_format,
                thinking=self.thinking,
                reasoning_effort=self.reasoning_effort,
                preserve_reasoning=self.preserve_reasoning
            )
            tools = [SUBAGENT_TOOL_SCHEMA]
            max_iterations = 5
            steps = []

            # 立即保存用户消息
            user_msg_id = self.conversation_manager.add_message(session_id, "user", user_message)
            # 记录用户消息的 sequence，后续增量保存时清除这之后的记录
            user_msg_seq = self._get_message_sequence(user_msg_id)

            for iteration in range(max_iterations):
                full_content = ""
                full_reasoning = ""
                received_tool_calls = []
                pending_tool_results = []  # 缓冲工具结果，等 assistant 消息插入后再追加

                # 真流式调用 LLM，token 边生成边推送
                async for chunk in provider.stream(messages, tools):
                    if chunk["type"] == "usage":
                        u = chunk["usage"]
                        self._token_usage["prompt_tokens"] = u.get("prompt_tokens", 0)
                        self._token_usage["completion_tokens"] = u.get("completion_tokens", 0)
                        self._token_usage["total_tokens"] = u.get("total_tokens", 0)
                        evt = {"type": "usage", "usage": dict(self._token_usage)}
                        self._buffer_event(evt)
                        yield evt
                    elif chunk["type"] == "reasoning":
                        full_reasoning += chunk["content"]
                        evt = {"type": "reasoning", "content": chunk["content"]}
                        self._buffer_event(evt)
                        yield evt
                    elif chunk["type"] == "text":
                        full_content += chunk["content"]
                        evt = {"type": "text", "content": chunk["content"]}
                        self._buffer_event(evt)
                        yield evt
                    elif chunk["type"] == "tool_call":
                        tc = chunk["tool_call"]
                        fn = tc["function"]
                        received_tool_calls.append(tc)

                        try:
                            arguments = json.loads(fn["arguments"])
                        except json.JSONDecodeError:
                            arguments = {}

                        evt = {
                            "type": "tool_call",
                            "tool_name": fn["name"],
                            "arguments": arguments,
                            "status": "assembling"
                        }
                        self._buffer_event(evt)
                        yield evt
                        await asyncio.sleep(0.05)

                        if fn["name"] == "subagent":
                            # 流式分发子 Agent，透传内部事件并累积 conversation
                            sub_text = ""
                            sub_tool_result = ""
                            sub_conversation = []
                            async for sub_event in self._dispatch_subagent_stream(tc):
                                if sub_event.get("type") == "escalate":
                                    sub_text = sub_event.get("question", "")
                                elif sub_event.get("type") == "text":
                                    sub_text += sub_event.get("content", "")
                                elif sub_event.get("type") == "tool_result":
                                    sub_tool_result = sub_event.get("result", "")
                                else:
                                    pass
                                # 累积子 Agent 内部交互用于持久化
                                conv_entry = {"type": sub_event.get("type")}
                                for k in ("tool_name", "arguments", "content", "result", "status"):
                                    if sub_event.get(k) is not None:
                                        conv_entry[k] = sub_event[k]
                                sub_conversation.append(conv_entry)
                                self._buffer_event(sub_event)
                                yield sub_event
                            # 优先用子 Agent LLM 的文本总结，而非原始工具结果
                            result = json.dumps(
                                {"success": True, "response": sub_text or sub_tool_result, "conversation": sub_conversation},
                                ensure_ascii=False
                            )
                        else:
                            result = json.dumps(
                                {"success": False, "error": f"未知工具: {fn['name']}"},
                                ensure_ascii=False
                            )

                        result_data = json.loads(result)
                        step = {
                            "tool_name": fn["name"],
                            "arguments": arguments,
                            "result": result_data.get("response", "") if result_data.get("success") else result_data.get("error", ""),
                            "status": "completed" if result_data.get("success") else "error"
                        }
                        steps.append(step)

                        evt = {"type": "tool_result", **step}
                        self._buffer_event(evt)
                        yield evt

                        pending_tool_results.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": fn["name"],
                            "content": result
                        })

                if not received_tool_calls:
                    # 纯文本回答，已在流式中推送完毕
                    msg = provider.build_message(content=full_content or "", reasoning=full_reasoning)
                    messages.append(msg)
                    # 最终保存
                    self._save_stream_state(session_id, messages, len(history), user_msg_seq)
                    break

                # 有工具调用：先把 assistant 消息（含 tool_calls）加入对话，再追加工具结果
                msg = provider.build_message(
                    content=full_content or None,
                    tool_calls=received_tool_calls,
                    reasoning=full_reasoning
                )
                messages.append(msg)
                messages.extend(pending_tool_results)
                # 每轮迭代后增量保存
                self._save_stream_state(session_id, messages, len(history), user_msg_seq)
            else:
                evt = {"type": "text", "content": "抱歉，处理超出限制"}
                self._buffer_event(evt)
                yield evt
                logger.warning(f"Function Calling 超过最大轮数: {max_iterations}")
                messages.append({
                    "role": "assistant",
                    "content": "抱歉，处理超出限制"
                })
                self._save_stream_state(session_id, messages, len(history), user_msg_seq)

            evt = {"type": "done", "session_id": session_id}
            self._buffer_event(evt)
            yield evt

        except Exception as e:
            logger.error(f"流式对话处理失败: {e}", exc_info=True)
            evt = {"type": "error", "message": str(e)}
            self._buffer_event(evt)
            yield evt
        finally:
            # 标记流式结束，唤醒所有订阅者，清理 per-session 上下文
            ctx = self._streams.get(session_id)
            if ctx:
                ctx.done = True
                old = ctx.waiter
                ctx.waiter = asyncio.Event()
                old.set()
            # 无论正常结束、异常还是客户端断连，都保存已有内容
            # 如果流式内容还在累积中（generator 被中断），手动追加到 messages
            try:
                has_text = any(
                    m.get("role") == "assistant" and "tool_calls" not in m
                    for m in messages[len(history) + 1:]
                )
                if not has_text and (full_content or full_reasoning):
                    msg = provider.build_message(content=full_content or "", reasoning=full_reasoning)
                    messages.append(msg)
                    logger.info(f"finally 追加未完成的流式内容: text={len(full_content)}, reasoning={len(full_reasoning)}")
            except NameError:
                pass
            if user_msg_seq:
                self._save_stream_state(session_id, messages, len(history), user_msg_seq)

    def _buffer_event(self, event: dict):
        """追加事件到当前 session 的缓冲区，唤醒所有订阅者"""
        if self._current_session_id is None:
            return
        ctx = self._streams.get(self._current_session_id)
        if ctx is not None:
            ctx.buffer.append(event)
            old = ctx.waiter
            ctx.waiter = asyncio.Event()
            old.set()

    async def subscribe_stream(self, session_id: str):
        """订阅指定 session 的流式事件，多客户端可同时调用"""
        ctx = self._streams.get(session_id)
        if ctx is None:
            yield {"type": "error", "message": "No active stream for this session"}
            return
        pos = 0
        while True:
            while pos < len(ctx.buffer):
                yield ctx.buffer[pos]
                pos += 1
            if ctx.done:
                break
            waiter = ctx.waiter
            try:
                await asyncio.wait_for(waiter.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"type": "heartbeat"}

    def _get_message_sequence(self, message_id: int) -> int:
        """获取消息的 sequence 编号"""
        from ..core.database import get_connection
        conn = get_connection(self.conversation_manager.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT sequence FROM messages WHERE id = ?", (message_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row)["sequence"] if row else 0

    def _save_stream_state(
        self, session_id: str, messages: list, history_len: int, user_msg_seq: int
    ) -> None:
        """
        增量保存流式对话状态。
        先删除用户消息之后的所有记录，再根据当前 messages 重新写入。
        """

        # 1. 清除之前的 assistant 记录
        self.conversation_manager.delete_messages_after_sequence(session_id, user_msg_seq)

        # 2. 从 messages 中提取本轮新增的 assistant 内容
        # messages[0..history_len] 是历史+system+user，之后是本轮新增
        history_start_idx = history_len + 1
        all_tool_calls = []
        all_tool_results = []
        tool_reasoning_parts = []  # 每轮工具调用的 reasoning
        final_text = ""
        final_reasoning = None

        for i in range(history_start_idx, len(messages)):
            msg = messages[i]
            if msg["role"] == "assistant" and "tool_calls" in msg:
                all_tool_calls.extend(msg["tool_calls"])
                if msg.get("reasoning_content"):
                    tool_reasoning_parts.append(msg["reasoning_content"])
                for j in range(i + 1, len(messages)):
                    if messages[j]["role"] == "tool":
                        all_tool_results.append(messages[j])
                    elif messages[j]["role"] == "assistant":
                        break
            elif msg["role"] == "assistant" and "tool_calls" not in msg:
                final_text = msg.get("content", "")
                final_reasoning = msg.get("reasoning_content")

        # 3. 存工具调用（合并为一条）
        if all_tool_calls:
            tool_calls_json = json.dumps(all_tool_calls, ensure_ascii=False)
            tool_reasoning = "\n".join(tool_reasoning_parts) if tool_reasoning_parts else None
            message_id = self.conversation_manager.add_message(
                session_id, "assistant",
                content=tool_calls_json,
                tool_execution_id=None,
                reasoning_content=tool_reasoning
            )
            if all_tool_results:
                tool_execution_id = self.conversation_manager.add_tool_execution(
                    session_id, message_id, all_tool_results
                )
                from ..core.database import get_connection
                conn = get_connection(self.conversation_manager.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE messages SET tool_execution_id = ? WHERE id = ?",
                    (tool_execution_id, message_id)
                )
                conn.commit()
                conn.close()

        # 4. 存最终文本回复
        if final_text:
            self.conversation_manager.add_message(
                session_id, "assistant",
                content=final_text,
                reasoning_content=final_reasoning,
            )
            logger.info(f"已保存文本回复: len={len(final_text)}, has_reasoning={final_reasoning is not None}")
        else:
            logger.warning(f"final_text 为空，未保存! all_tool_calls={len(all_tool_calls)}, "
                          f"history_start_idx={history_start_idx}, msg_count={len(messages)}")
