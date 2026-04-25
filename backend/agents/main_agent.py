"""
主 Agent

负责理解用户意图、调度子 Agent 执行任务。
不直接执行任何工具，只通过 subagent 工具进行分发。
"""
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from .base import Agent
from .subagents.filesystem import FilesystemAgent
from ..logger import get_logger
from ..core.conversation import ConversationManager
from ..core.prompt_builder import PromptBuilder
from .memory import MemorySystem
from ..core.state import StateManager
from ..config.settings import get_settings

logger = get_logger(__name__)

# 主 Agent 唯一的工具：调用子 Agent
SUBAGENT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "subagent",
        "description": "当用户请求需要执行具体操作（读文件、查目录等）时，调用对应子 Agent。纯对话、闲聊、表达观点时不要调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["filesystem"],
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
        }
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

                    if function_name == "subagent":
                        result = await self._dispatch_subagent(tool_call)
                    else:
                        result = json.dumps(
                            {"success": False, "error": f"未知工具: {function_name}"},
                            ensure_ascii=False
                        )

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
                "timestamp": self.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"对话处理失败: {e}", exc_info=True)
            return {
                "assistant_message": f"抱歉，处理消息时出错: {str(e)}",
                "session_id": session_id,
                "timestamp": self.created_at.isoformat(),
                "error": str(e)
            }

    async def _dispatch_subagent(self, tool_call: Dict[str, Any]) -> str:
        """
        根据工具调用分发到对应子 Agent

        Args:
            tool_call: Function Calling 的 tool_call 对象

        Returns:
            子 Agent 的自然语言响应（JSON 字符串）
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

            result = await agent.execute({"task": task_description})
            response = result.get("response", "")

            return json.dumps(
                {"success": True, "response": response},
                ensure_ascii=False
            )
        except Exception as e:
            logger.error(f"子 Agent 执行失败: {e}", exc_info=True)
            return json.dumps(
                {"success": False, "error": str(e)},
                ensure_ascii=False
            )

    async def _delegate_skill_learning(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        委派技能学习任务给子 Agent
        """
        from .subagents.skill_learner import SkillLearnerAgent
        agent = SkillLearnerAgent()
        return await agent.execute(data)
