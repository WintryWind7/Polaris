"""
主 Agent

负责核心决策、对话、任务规划和子 Agent 调度。
使用最强的模型（qwen-plus）。
"""
from typing import Dict, Any, Optional, List
from .base import Agent
from .subagents.skill_learner import SkillLearnerAgent
from ..logger import get_logger
from ..core.conversation import ConversationManager
from ..core.prompt_builder import PromptBuilder
from .memory import MemorySystem
from ..core.state import StateManager
from .tools import ToolRegistry
from ..config.settings import get_settings

logger = get_logger(__name__)


class MainAgent(Agent):
    """主 Agent"""

    def __init__(self):
        super().__init__("main", "qwen-plus")
        self.subagents: Dict[str, Agent] = {}

        # 初始化对话管理
        settings = get_settings()
        self.conversation_manager = ConversationManager(settings.data_dir)
        self.prompt_builder = PromptBuilder()

        # 初始化核心组件
        self.memory_system = MemorySystem(settings.data_dir)
        self.state_manager = StateManager(settings.data_dir / "state.json")
        self.tool_registry = ToolRegistry()

        logger.info("MainAgent 初始化完成")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 包含 type 和 data 的任务字典

        Returns:
            执行结果
        """
        task_type = task.get("type")
        logger.debug(f"执行任务: type={task_type}")

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
                "context": Optional[Dict]  # 传递给 hooks
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
            logger.info(f"创建新会话: {session_id}")

        # 2. 获取历史消息
        history = self.conversation_manager.get_messages(session_id, limit=20)
        logger.debug(f"获取历史消息: {len(history)} 条")

        # 3. 构建 hooks context
        hooks_context = {
            # Hook 开关（默认禁用，按需启用）
            "enable_skills": False,

            # Hook 依赖数据
            "session_id": session_id,
            "skills": ["搜索网络", "执行代码", "读写文件"],
        }

        # 合并用户传入的 context（允许覆盖）
        hooks_context.update(context)

        # 4. 构建 messages（hooks 会根据 context 自动应用）
        messages = self.prompt_builder.build_messages(
            user_message=user_message,
            history=history,
            context=hooks_context,
            max_history=20
        )

        logger.debug(f"构建 messages: 共 {len(messages)} 条")

        try:
            # 5. 调用 LLM
            response = await self.call_llm(messages)

            # 6. 保存到会话
            self.conversation_manager.add_message(session_id, "user", user_message)
            self.conversation_manager.add_message(session_id, "assistant", response)

            # 7. 保存到长期记忆（如果需要）
            # 注：记忆功能暂未实现

            logger.info(f"对话完成: session={session_id}")

            return {
                "assistant_message": response,
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

    async def _delegate_skill_learning(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        委派技能学习任务给子 Agent

        Args:
            data: 技能学习任务数据

        Returns:
            学习结果
        """
        return await self.spawn_subagent("skill_learner", data)

    async def spawn_subagent(self, agent_type: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建并执行子 Agent

        Args:
            agent_type: 子 Agent 类型
            task: 任务数据

        Returns:
            子 Agent 执行结果
        """
        if agent_type == "skill_learner":
            agent = SkillLearnerAgent()
        else:
            return {"error": f"Unknown subagent type: {agent_type}"}

        # 执行子 Agent 任务
        result = await agent.execute(task)

        # 子 Agent 执行完毕后销毁（不保存引用）
        return result
