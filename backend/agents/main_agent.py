"""
主 Agent

负责理解用户意图、调度子 Agent 执行任务。
不直接执行任何工具，只通过 subagent 工具进行分发。
"""
import json
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from .base import Agent
from .subagents.filesystem import FilesystemAgent
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
        "description": "当用户请求需要执行具体操作时，调用对应子 Agent。可用的子 Agent: filesystem（文件操作）、web（搜索和抓取网页）、memory（检索历史记忆）。纯对话、闲聊、表达观点时不要调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["filesystem", "web", "memory"],
                    "description": "要调用的子 Agent 类型"
                },
                "task": {
                    "type": "string",
                    "description": "任务描述。包含：用户要做什么、涉及的具体路径或关键词。不要包含无关上下文。"
                }
            },
            "required": ["agent_type", "task"]
        }
    }
}


class MainAgent(Agent):
    """主 Agent"""

    def __init__(self):
        super().__init__("main")

        # 初始化对话管理
        settings = get_settings()
        self.conversation_manager = ConversationManager(settings.data_dir)
        self.prompt_builder = PromptBuilder()

        # 初始化核心组件
        self.memory_system = MemorySystem(settings.data_dir)
        self.state_manager = StateManager(settings.data_dir / "state.json")

        # 子 Agent 注册表（类型 → 类）
        self._subagent_classes = {
            "filesystem": FilesystemAgent,
            "web": WebAgent,
            "memory": MemoryAgent,
        }
        # 当前会话 ID（_handle_chat / stream_chat 设置）
        self._current_session_id: Optional[str] = None
        # 子 Agent 实例缓存（类型 → 实例），session 生命周期内复用
        self._active_subagents: Dict[str, Agent] = {}

        logger.info("MainAgent 初始化完成，无工具，仅通过 subagent 调度")

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

        # 1. 获取或创建会话
        if not session_id:
            session_id = self.conversation_manager.create_session()
        self._current_session_id = session_id

        # 2. 获取历史消息
        history = self.conversation_manager.get_messages(session_id, limit=20)

        # 3. 构建 hooks context
        hooks_context = {
            "enable_skills": False,
            "session_id": session_id,
            "skills": [],
        }
        hooks_context.update(context)

        # 注入 workspace 信息
        session_info = self.conversation_manager.get_session(session_id)
        if session_info and session_info.get("workspace_id"):
            from ..core.workspace import WorkspaceManager
            wm = WorkspaceManager(get_settings().data_dir)
            ws = wm.get_workspace(session_info["workspace_id"])
            if ws:
                hooks_context["workspace_path"] = ws["path"]
                hooks_context["workspace_name"] = ws["name"]

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
            steps = []

            for iteration in range(max_iterations):
                response = await self.call_llm(messages, tools)

                tool_calls = response.get("tool_calls", [])

                if not tool_calls:
                    final_response = response.get("content")
                    break

                # 将 assistant 的 tool_calls 加入 messages
                messages.append({
                    "role": "assistant",
                    "content": response.get("content"),
                    "tool_calls": tool_calls
                })

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
                        tool_execution_id=None
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

            self.conversation_manager.add_message(session_id, "assistant", final_response)

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

        # 1. Workspace 信息
        session_info = self.conversation_manager.get_session(session_id)
        if session_info and session_info.get("workspace_id"):
            from ..core.workspace import WorkspaceManager
            wm = WorkspaceManager(get_settings().data_dir)
            ws = wm.get_workspace(session_info["workspace_id"])
            if ws:
                context["workspace_path"] = ws["path"]
                context["workspace_name"] = ws["name"]

        # 2. 最近历史（精简，仅 user/assistant 文本）
        recent = self.conversation_manager.get_messages(session_id, limit=10)
        context["recent_history"] = [
            {"role": m["role"], "content": (m.get("content") or "")[:200]}
            for m in recent[-6:]
            if m.get("content") and not isinstance(m.get("content"), list)
        ]

        # 3. 用户偏好
        context["user_preferences"] = self.state_manager.get_all()

        # 4. 相关记忆
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

        decision_prompt = f"""子 Agent（{agent_type}）在执行任务时向你提出了问题：

【问题】
{question}

【相关记忆】
{memory_text or '无相关记忆'}

请判断：
1. 如果你能从上下文或记忆中确定答案，返回 {{"action": "answer", "content": "你的回答"}}
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

    async def _dispatch_subagent(self, tool_call: Dict[str, Any]) -> str:
        """
        根据工具调用分发到对应子 Agent，注入上下文，处理反问循环。
        """
        arguments = json.loads(tool_call["function"]["arguments"])
        agent_type = arguments.get("agent_type", "")
        task_description = arguments.get("task", "")

        agent_class = self._subagent_classes.get(agent_type)
        if not agent_class:
            return json.dumps(
                {"success": False, "error": f"未知子 Agent 类型: {agent_type}"},
                ensure_ascii=False
            )

        logger.info(f"调度子 Agent: {agent_type}, 任务: {task_description[:50]}")

        try:
            # 复用已存在的子 Agent 实例
            agent = self._active_subagents.get(agent_type)
            if not agent:
                agent = agent_class()
                self._active_subagents[agent_type] = agent
                logger.info(f"创建子 Agent 实例: {agent_type}")

            # 构建上下文
            context = {}
            if self._current_session_id:
                context = self._build_subagent_context(
                    self._current_session_id, task_description
                )

            result = await agent.execute({
                "task": task_description,
                "context": context
            })

            # 反问循环
            ask_count = 0
            max_asks = getattr(agent, "max_ask_rounds", 3)
            while result.get("status") == "ask" and ask_count < max_asks:
                question = result.get("question", "")
                logger.info(f"子 Agent ({agent_type}) 反问: {question[:80]}")
                decision = await self._handle_subagent_ask(
                    question, self._current_session_id or "", agent_type
                )
                if decision["action"] == "answer":
                    logger.info(f"自动替答: {decision['content'][:60]}")
                    result = await agent.resume({"answer": decision["content"]})
                    ask_count += 1
                else:
                    # 升级给用户
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"需要用户确认: {question}",
                            "needs_user_input": True,
                            "question": decision["content"],
                        },
                        ensure_ascii=False
                    )

            if result.get("status") == "complete":
                response = result.get("response", "")
                return json.dumps(
                    {"success": True, "response": response},
                    ensure_ascii=False
                )
            return json.dumps(
                {"success": False, "error": result.get("error", "执行失败")},
                ensure_ascii=False
            )
        except Exception as e:
            logger.error(f"子 Agent 执行失败: {e}", exc_info=True)
            return json.dumps(
                {"success": False, "error": str(e)},
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
        task_description = arguments.get("task", "")

        agent_class = self._subagent_classes.get(agent_type)
        if not agent_class:
            yield {
                "type": "tool_result",
                "tool_name": "subagent",
                "result": f"未知子 Agent 类型: {agent_type}",
                "status": "error"
            }
            return

        # 获取或创建实例
        agent = self._active_subagents.get(agent_type)
        if not agent:
            agent = agent_class()
            self._active_subagents[agent_type] = agent
            logger.info(f"创建子 Agent 实例: {agent_type}")

        context = {}
        if self._current_session_id:
            context = self._build_subagent_context(
                self._current_session_id, task_description
            )

        logger.info(f"流式调度子 Agent: {agent_type}, 任务: {task_description[:50]}")

        try:
            # 开启子 Agent 流式执行
            stream = agent.execute_stream({
                "task": task_description,
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
                    logger.info(f"子 Agent ({agent_type}) 反问: {question[:80]}")
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
                            "question": decision["content"]
                        }
                        return

                yield event

        except Exception as e:
            logger.error(f"子 Agent 流式执行失败: {e}", exc_info=True)
            yield {
                "type": "tool_result",
                "tool_name": "subagent",
                "result": str(e),
                "status": "error"
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

        if not session_id:
            session_id = self.conversation_manager.create_session()
        self._current_session_id = session_id

        yield {"type": "session", "session_id": session_id}

        history = self.conversation_manager.get_messages(session_id, limit=20)

        hooks_context = {
            "enable_skills": False,
            "session_id": session_id,
            "skills": [],
        }
        hooks_context.update(context)

        session_info = self.conversation_manager.get_session(session_id)
        if session_info and session_info.get("workspace_id"):
            from ..core.workspace import WorkspaceManager
            wm = WorkspaceManager(get_settings().data_dir)
            ws = wm.get_workspace(session_info["workspace_id"])
            if ws:
                hooks_context["workspace_path"] = ws["path"]
                hooks_context["workspace_name"] = ws["name"]

        messages = self.prompt_builder.build_messages(
            user_message=user_message,
            history=history,
            context=hooks_context,
            max_history=20
        )

        try:
            provider = LLMFactory.get_provider(
                model=self.model,
                api_key=self.api_key,
                api_base=self.api_base,
                api_format=self.api_format,
                thinking=self.thinking,
                reasoning_effort=self.reasoning_effort
            )
            tools = [SUBAGENT_TOOL_SCHEMA]
            max_iterations = 5
            steps = []

            for iteration in range(max_iterations):
                full_content = ""
                full_reasoning = ""
                received_tool_calls = []

                # 真流式调用 LLM，token 边生成边推送
                async for chunk in provider.stream(messages, tools):
                    if chunk["type"] == "reasoning":
                        full_reasoning += chunk["content"]
                        yield {"type": "reasoning", "content": chunk["content"]}
                    elif chunk["type"] == "text":
                        full_content += chunk["content"]
                        yield {"type": "text", "content": chunk["content"]}
                    elif chunk["type"] == "tool_call":
                        tc = chunk["tool_call"]
                        fn = tc["function"]
                        received_tool_calls.append(tc)

                        try:
                            arguments = json.loads(fn["arguments"])
                        except json.JSONDecodeError:
                            arguments = {}

                        yield {
                            "type": "tool_call",
                            "tool_name": fn["name"],
                            "arguments": arguments,
                            "status": "assembling"
                        }
                        await asyncio.sleep(0.05)

                        if fn["name"] == "subagent":
                            # 流式分发子 Agent，透传内部事件
                            sub_text = ""
                            sub_tool_result = ""
                            async for sub_event in self._dispatch_subagent_stream(tc):
                                if sub_event.get("type") == "escalate":
                                    sub_text = sub_event.get("question", "")
                                elif sub_event.get("type") == "text":
                                    sub_text += sub_event.get("content", "")
                                elif sub_event.get("type") == "tool_result":
                                    sub_tool_result = sub_event.get("result", "")
                                else:
                                    pass
                                yield sub_event
                            # 优先用子 Agent LLM 的文本总结，而非原始工具结果
                            result = json.dumps(
                                {"success": True, "response": sub_text or sub_tool_result},
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

                        yield {"type": "tool_result", **step}

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": fn["name"],
                            "content": result
                        })

                if not received_tool_calls:
                    # 纯文本回答，已在流式中推送完毕
                    msg = {"role": "assistant", "content": full_content or ""}
                    if full_reasoning:
                        msg["reasoning_content"] = full_reasoning
                    messages.append(msg)
                    break

                # 有工具调用：把 assistant 消息（含 tool_calls）加入对话
                msg = {
                    "role": "assistant",
                    "content": full_content or None,
                    "tool_calls": received_tool_calls
                }
                if full_reasoning:
                    msg["reasoning_content"] = full_reasoning
                messages.append(msg)
            else:
                yield {"type": "text", "content": "抱歉，处理超出限制"}
                logger.warning(f"Function Calling 超过最大轮数: {max_iterations}")
                messages.append({
                    "role": "assistant",
                    "content": "抱歉，处理超出限制"
                })

            # 保存对话
            self.conversation_manager.add_message(session_id, "user", user_message)

            # 合并所有 tool_calls 为一条消息，再存最终文本回复
            all_tool_calls = []
            all_tool_results = []
            final_text = ""

            history_start_idx = len(history) + 1
            for i in range(history_start_idx, len(messages)):
                msg = messages[i]
                if msg["role"] == "assistant" and "tool_calls" in msg:
                    all_tool_calls.extend(msg["tool_calls"])
                    for j in range(i + 1, len(messages)):
                        if messages[j]["role"] == "tool":
                            all_tool_results.append(messages[j])
                        elif messages[j]["role"] == "assistant":
                            break
                elif msg["role"] == "assistant" and "tool_calls" not in msg:
                    final_text = msg.get("content", "")

            # 存工具调用（合并为一条）
            if all_tool_calls:
                tool_calls_json = json.dumps(all_tool_calls, ensure_ascii=False)
                message_id = self.conversation_manager.add_message(
                    session_id, "assistant",
                    content=tool_calls_json,
                    tool_execution_id=None
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

            # 存最终文本回复
            if final_text:
                self.conversation_manager.add_message(
                    session_id, "assistant",
                    content=final_text,
                )

            yield {"type": "done", "session_id": session_id}

        except Exception as e:
            logger.error(f"流式对话处理失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}
