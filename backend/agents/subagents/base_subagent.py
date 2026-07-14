"""
BaseSubAgent — 可复用的 LLM+Tool 子 Agent 基类

子类只需声明 agent_type、categories、system_prompt 即可得到一个完整的
LLM 驱动子 Agent，包含 Function Calling 循环和反问主 Agent 的能力。
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
from ..base import Agent
from ..tools import ToolRegistry, ToolExecutor, ToolLoader
from ..tools.read_file_state import ReadFileState
from ...logger import get_logger

logger = get_logger(__name__)

ASK_MAIN_AGENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_main_agent",
        "description": "向主 Agent 提问。当你需要确认信息、查询上下文或请求决策时调用。主 Agent 能访问用户记忆和偏好信息。问题应具体明确，一次只问一个问题。",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "要询问的问题"
                }
            },
            "required": ["question"]
        }
    }
}


class BaseSubAgent(Agent):
    """可复用的 LLM+Tool 子 Agent 基类"""

    # ---- 子类覆盖的类属性 ----
    agent_type: str = ""
    categories: List[str] = []
    prompt_file: str = ""       # 提示词模板文件名（如 "subagent_coding.md"），优先级高于 system_prompt
    system_prompt: str = ""     # 后备：直接写死的提示词（prompt_file 为空时使用）
    max_iterations: int = 5
    max_ask_rounds: int = 3

    def __init__(self):
        super().__init__(self.agent_type)
        self.tool_registry = ToolRegistry()
        self._read_file_state = ReadFileState()
        self.tool_executor = ToolExecutor(
            self.tool_registry, read_file_state=self._read_file_state
        )
        self._load_tools()

        # 如果指定了 prompt_file，从模板加载，否则使用硬编码 system_prompt
        if self.prompt_file:
            from ..prompts.loader import load_prompt_file
            self.system_prompt = load_prompt_file(self.prompt_file)

        # 实例状态
        self._messages: List[Dict] = []    # session 内累积，不重置
        self._pending_ask: Optional[str] = None
        self._ask_count: int = 0
        self._iteration_count: int = 0

    # ---- 工具加载 ----

    def _load_tools(self) -> None:
        """注册 ask_main_agent schema + 按 categories 加载工具"""
        # 注册反问工具
        self.tool_registry.register_schema("ask_main_agent", ASK_MAIN_AGENT_SCHEMA)

        # 加载业务工具
        tools_dir = Path(__file__).parent.parent / "tools"
        count = ToolLoader.load_from_directory(
            tools_dir, self.tool_registry, categories=self.categories
        )
        logger.info(f"[{self.agent_type}] 初始化完成，加载了 {count} 个工具")

    # ---- System Prompt 构建 ----

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """拼接完整 system prompt：角色声明 + 上下文块 + 业务指令 + 反问工具说明"""
        parts = []

        # 1. 角色声明
        parts.append(
            f"你是 Polaris 的 **{self.agent_type}** 子 Agent。\n"
            f"你不是在和用户对话，而是在和主 Agent 交流。\n"
            f"主 Agent 也是 AI——和你的对话直接高效即可，不需要为用户格式化输出。\n"
            f"收到消息后调用合适的工具完成操作，自然地回复。"
        )

        # 2. 上下文块
        ctx_lines = []
        if context.get("user_preferences"):
            prefs = context["user_preferences"]
            if isinstance(prefs, dict) and prefs:
                pref_items = [f"{k}: {v}" for k, v in prefs.items() if v]
                if pref_items:
                    ctx_lines.append(f"- 用户偏好: {'; '.join(pref_items)}")
        if context.get("relevant_memories"):
            memories = context["relevant_memories"]
            if memories:
                ctx_lines.append("- 相关记忆:")
                for m in memories[:3]:
                    ctx_lines.append(f"  [{m.get('time', '?')}] {m.get('content', '')[:200]}")
        if ctx_lines:
            parts.append("## 当前上下文\n" + "\n".join(ctx_lines))

        # 3. 业务指令
        parts.append(self.system_prompt.strip())

        # 4. 反问工具说明
        parts.append(
            "## 反问主 Agent\n\n"
            "如果你遇到需要确认才能继续的问题（例如需要知道用户的偏好、"
            "需要在多个方案中选择、需要确认信息），先调 `ask_main_agent` 工具，"
            "主 Agent 有更完整的上下文和用户记忆，能为你做出决策。\n"
            "每次只能问一个问题，问完后等待回复。"
        )

        return "\n\n".join(parts)

    # ---- 核心执行 ----

    # 上下文窗口上限，超出时保留 system prompt + 最近 N 条
    MAX_MESSAGES: int = 40

    def _setup_task(self, task: Dict[str, Any]) -> None:
        """追加新任务到对话上下文，重置调用级计数器"""
        task_description = task.get("message", task.get("task", ""))
        context = task.get("context", {})

        if not self._messages:
            # 首次调用：设置 system prompt
            system_prompt = self._build_system_prompt(context)
            self._messages = [{"role": "system", "content": system_prompt}]

        # 截断：防止跨多次 dispatch 后 _messages 无限增长
        if len(self._messages) >= self.MAX_MESSAGES:
            self._messages = [self._messages[0]] + self._messages[-(self.MAX_MESSAGES - 1):]
            logger.info(f"[{self.agent_type}] _messages 截断至 {len(self._messages)} 条")

        self._messages.append({"role": "user", "content": task_description})
        self._ask_count = 0
        self._iteration_count = 0

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务（非流式，内部仍用 call_llm）"""
        self._setup_task(task)
        return await self._run_loop()

    async def execute_stream(self, task: Dict[str, Any]):
        """流式执行任务，逐步 yield 事件"""
        import json as json_mod
        from ...core.llm import LLMFactory

        self._setup_task(task)
        tools = self.tool_registry.get_schemas()
        provider = LLMFactory.get_provider(
            model=self.model,
            api_key=self.api_key,
            api_base=self.api_base,
            api_format=self.api_format,
            thinking=self.thinking,
            reasoning_effort=self.reasoning_effort,
            preserve_reasoning=self.preserve_reasoning
        )

        while self._iteration_count < self.max_iterations:
            self._iteration_count += 1
            full_content = ""
            full_reasoning = ""
            received_tcs = []
            pending_tool_results = []  # 缓冲工具结果，等 assistant 消息插入后再追加

            async for chunk in provider.stream(self._messages, tools):
                if chunk["type"] == "reasoning":
                    full_reasoning += (chunk["content"] or "")
                    yield {"type": "reasoning", "content": chunk["content"] or ""}

                elif chunk["type"] == "text":
                    full_content += (chunk["content"] or "")
                    yield {"type": "text", "content": chunk["content"] or ""}

                elif chunk["type"] == "tool_call":
                    tc = chunk["tool_call"]
                    fn = tc["function"]
                    received_tcs.append(tc)

                    try:
                        arguments = json_mod.loads(fn["arguments"])
                    except (json_mod.JSONDecodeError, KeyError):
                        arguments = {}

                    yield {
                        "type": "tool_call",
                        "tool_name": fn["name"],
                        "arguments": arguments
                    }

                    if fn["name"] == "ask_main_agent":
                        self._pending_ask = tc["id"]
                        self._ask_count += 1
                        if self._ask_count > self.max_ask_rounds:
                            yield {"type": "text", "content": "已超过反问次数限制"}
                            return
                        yield {
                            "type": "ask",
                            "question": arguments.get("question", ""),
                            "tool_call_id": tc["id"]
                        }
                        # 保存当前轮状态到 messages，等待 resume
                        if received_tcs:
                            msg = provider.build_message(
                                content=full_content or None,
                                tool_calls=received_tcs,
                                reasoning=full_reasoning
                            )
                            self._messages.append(msg)
                        return

                    # 执行工具
                    tool_msg = await self.tool_executor.execute_tool_call(tc)
                    pending_tool_results.append(tool_msg)
                    result_data = json_mod.loads(tool_msg["content"])
                    if result_data.get("success"):
                        display = {k: v for k, v in result_data.items() if k != "success"}
                        result_str = json_mod.dumps(display, ensure_ascii=False) if display else ""
                    else:
                        result_str = result_data.get("error", "执行失败")
                    yield {
                        "type": "tool_result",
                        "tool_name": fn["name"],
                        "result": result_str,
                        "status": "completed" if result_data.get("success") else "error"
                    }

            # 本轮流式结束，保存 assistant 消息
            if received_tcs:
                msg = provider.build_message(
                    content=full_content or None,
                    tool_calls=received_tcs,
                    reasoning=full_reasoning
                )
                self._messages.append(msg)
                self._messages.extend(pending_tool_results)
            else:
                msg = provider.build_message(content=full_content or "", reasoning=full_reasoning)
                self._messages.append(msg)
                return  # 纯文本，完成

    async def resume(self, answer: Dict[str, Any]) -> Dict[str, Any]:
        """收到主 Agent 回答后从断点继续（非流式）"""
        answer_text = answer.get("answer", "")
        tc_id = self._pending_ask or "ask_unknown"
        self._messages.append({
            "role": "tool",
            "tool_call_id": tc_id,
            "name": "ask_main_agent",
            "content": answer_text
        })
        self._pending_ask = None
        return await self._run_loop()

    async def resume_stream(self, answer: Dict[str, Any]):
        """收到主 Agent 回答后从断点继续（流式）"""
        answer_text = answer.get("answer", "")
        tc_id = self._pending_ask or "ask_unknown"
        self._messages.append({
            "role": "tool",
            "tool_call_id": tc_id,
            "name": "ask_main_agent",
            "content": answer_text
        })
        self._pending_ask = None
        # 继续流式循环
        async for event in self.execute_stream({"message": "", "context": {}}):
            yield event

    async def _run_loop(self) -> Dict[str, Any]:
        """LLM+Tool 循环（非流式），拦截 ask_main_agent"""
        tools = self.tool_registry.get_schemas()

        while self._iteration_count < self.max_iterations:
            self._iteration_count += 1
            response = await self.call_llm(self._messages, tools)
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                return {
                    "status": "complete",
                    "response": response.get("content") or ""
                }

            tool_names = [tc["function"]["name"] for tc in tool_calls]
            logger.info(f"[{self.agent_type}] 调用工具: {', '.join(tool_names)}")

            assistant_msg = {
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": tool_calls
            }
            self._messages.append(assistant_msg)

            for tool_call in tool_calls:
                fn_name = tool_call["function"]["name"]

                if fn_name == "ask_main_agent":
                    self._pending_ask = tool_call["id"]
                    self._ask_count += 1
                    if self._ask_count > self.max_ask_rounds:
                        return {
                            "status": "complete",
                            "response": response.get("content") or "已超过反问次数限制"
                        }
                    import json as json_mod
                    try:
                        args = json_mod.loads(tool_call["function"]["arguments"])
                        question = args.get("question", "")
                    except (json_mod.JSONDecodeError, KeyError):
                        question = str(tool_call["function"].get("arguments", ""))
                    return {
                        "status": "ask",
                        "question": question,
                        "tool_call_id": tool_call["id"]
                    }

                tool_msg = await self.tool_executor.execute_tool_call(tool_call)
                self._messages.append(tool_msg)

        return {
            "status": "complete",
            "response": "已超出最大执行轮数，返回当前结果"
        }
