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
from ..core.memory import MemorySystem
from ..core.state import StateManager
from ..core.tools import ToolRegistry
from ..config.settings import get_settings
from ..config.hooks_config import HooksConfig

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

        # 初始化核心组件（用于 hooks）
        self.memory_system = MemorySystem(settings.data_dir)
        self.state_manager = StateManager(settings.data_dir / "state.json")
        self.tool_registry = ToolRegistry()

        # 注册 hooks（默认不启用，通过配置控制）
        self._register_hooks()

        logger.info("MainAgent 初始化完成")

    def _register_hooks(self):
        """
        注册所有 hooks

        Hook 架构说明：
        - system_prompt: 修改 system prompt 内容（记忆、能力、工具列表等）
        - before_messages: 在历史消息之前插入（Few-shot 示例）
        - after_messages: 在历史消息之后插入（实时信息、知识库检索结果）

        默认所有 hooks 都已注册，但通过 context 控制是否启用
        """
        # === System Prompt Hooks ===
        self.prompt_builder.register_hook("system_prompt", self._hook_add_capabilities)
        self.prompt_builder.register_hook("system_prompt", self._hook_add_memory)
        self.prompt_builder.register_hook("system_prompt", self._hook_add_tools)

        # === Before Messages Hooks ===
        self.prompt_builder.register_hook("before_messages", self._hook_add_few_shot_examples)

        # === After Messages Hooks ===
        self.prompt_builder.register_hook("after_messages", self._hook_add_realtime_info)

        logger.info("Hooks 注册完成（默认不启用，通过 context 控制）")

    # ========== System Prompt Hooks ==========

    def _hook_add_capabilities(self, prompt: str, context: Dict) -> str:
        """
        Hook: 添加能力描述

        启用条件: context.get("enable_capabilities") == True
        数据来源: context.get("capabilities", [])
        """
        if not context.get("enable_capabilities", False):
            return prompt

        capabilities = context.get("capabilities", [])
        if not capabilities:
            return prompt

        cap_text = "\n".join(f"- {cap}" for cap in capabilities)
        prompt += f"\n\n## 你拥有以下能力\n{cap_text}"

        logger.debug(f"[Hook] 添加能力描述: {len(capabilities)} 项")
        return prompt

    def _hook_add_memory(self, prompt: str, context: Dict) -> str:
        """
        Hook: 添加长期记忆

        启用条件: context.get("enable_memory") == True
        数据来源: MemorySystem.get_recent_chats()
        """
        if not context.get("enable_memory", False):
            return prompt

        # 获取最近的对话记忆
        recent_chats = self.memory_system.get_recent_chats(limit=5)
        if not recent_chats:
            return prompt

        memory_lines = []
        for event in recent_chats:
            user_msg = event.data.get("user", "")[:50]
            assistant_msg = event.data.get("assistant", "")[:50]
            memory_lines.append(f"- 用户: {user_msg}... → 你: {assistant_msg}...")

        memory_text = "\n".join(memory_lines)
        prompt += f"\n\n## 最近的对话记忆\n{memory_text}"

        logger.debug(f"[Hook] 添加记忆: {len(recent_chats)} 条")
        return prompt

    def _hook_add_tools(self, prompt: str, context: Dict) -> str:
        """
        Hook: 添加工具列表

        启用条件: context.get("enable_tools") == True
        数据来源: ToolRegistry.list_tools()
        """
        if not context.get("enable_tools", False):
            return prompt

        tools = self.tool_registry.list_tools()
        if not tools:
            return prompt

        tool_text = "\n".join(f"- {tool}" for tool in tools)
        prompt += f"\n\n## 可用工具\n{tool_text}"
        prompt += "\n\n使用格式: [TOOL: tool_name(params)]"

        logger.debug(f"[Hook] 添加工具列表: {len(tools)} 个")
        return prompt

    # ========== Before Messages Hooks ==========

    def _hook_add_few_shot_examples(self, messages: List, context: Dict) -> List:
        """
        Hook: 添加 Few-shot 示例

        启用条件: context.get("enable_few_shot") == True
        数据来源: 预定义示例
        """
        if not context.get("enable_few_shot", False):
            return messages

        examples = [
            {"role": "user", "content": "搜索北京今天的天气"},
            {"role": "assistant", "content": "[TOOL: search(\"北京天气\")]\n结果：晴天，15-25度"},
            {"role": "system", "content": "--- 以上是示例，以下是真实对话 ---"}
        ]

        logger.debug(f"[Hook] 添加 Few-shot 示例: {len(examples)} 条")
        return examples

    # ========== After Messages Hooks ==========

    def _hook_add_realtime_info(self, messages: List, context: Dict) -> List:
        """
        Hook: 添加实时信息

        启用条件: context.get("enable_realtime_info") == True
        数据来源: context.get("realtime_info", {})
        """
        if not context.get("enable_realtime_info", False):
            return messages

        realtime_info = context.get("realtime_info", {})
        if not realtime_info:
            return messages

        info_text = "\n".join(f"- {k}: {v}" for k, v in realtime_info.items())

        logger.debug(f"[Hook] 添加实时信息: {len(realtime_info)} 项")
        return [
            {"role": "system", "content": f"实时信息：\n{info_text}"}
        ]

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

        # 3. 合并 hooks 配置到 context
        # 从全局配置读取 hook 开关，但允许 context 覆盖
        hooks_context = HooksConfig.to_context()
        hooks_context.update(context)  # context 优先级更高

        # 补充额外数据（供 hooks 使用）
        hooks_context.update({
            "session_id": session_id,
            "capabilities": ["搜索网络", "执行代码", "读写文件"],  # 示例数据
            "realtime_info": {},  # 示例数据
        })

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

            # 7. 保存到长期记忆（如果启用了记忆 hook）
            if hooks_context.get("enable_memory"):
                self.memory_system.add_chat(user_message, response)

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
