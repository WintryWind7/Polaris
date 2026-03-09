"""
测试 System Prompt Hook 系统

验证装饰器注册、优先级排序、条件启用和 JSON 格式校验
"""
import pytest
from tests.helpers.test_utils import Environment


@pytest.fixture
def test_env():
    """测试环境 fixture"""
    env = Environment(test_name="hooks")
    yield env


@pytest.fixture
def clear_registry():
    """清空注册表并重新加载 builtin hooks"""
    from backend.agents.hooks import SystemPromptRegistry
    import importlib
    import backend.agents.hooks.builtin_hooks

    registry = SystemPromptRegistry.get_instance()
    registry.clear()

    # 重新加载 builtin_hooks 模块以重新注册装饰器
    importlib.reload(backend.agents.hooks.builtin_hooks)

    yield registry


@pytest.fixture
def prompt_builder():
    """提示词构建器 fixture（会自动加载 builtin hooks）"""
    from backend.core.prompt_builder import PromptBuilder
    # 每次创建新的 PromptBuilder 会重新加载 builtin hooks
    return PromptBuilder()


class TestSystemPromptHooks:
    """测试 System Prompt Hooks"""

    def test_hook_inject_skills(self, prompt_builder):
        """测试技能描述 hook"""
        context = {
            "enable_skills": True,
            "skills": ["搜索网络", "执行代码", "读写文件"]
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        system_prompt = messages[0]["content"]
        assert "你拥有以下技能" in system_prompt
        assert "搜索网络" in system_prompt
        assert "执行代码" in system_prompt

    def test_hook_inject_skills_disabled(self, prompt_builder):
        """测试技能描述 hook 禁用"""
        context = {
            "enable_skills": False,
            "skills": ["搜索网络"]
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        system_prompt = messages[0]["content"]
        assert "你拥有以下技能" not in system_prompt


class TestHookPriority:
    """测试 Hook 优先级"""

    def test_hooks_execute_in_priority_order(self, clear_registry):
        """测试 hooks 按 priority 顺序执行"""
        from backend.agents.hooks import system_prompt_hook, SystemPromptRegistry
        from backend.core.prompt_builder import PromptBuilder

        execution_order = []

        @system_prompt_hook(priority=30)
        def hook_c(context):
            execution_order.append("C")
            return {"hook_type": "system_prompt", "content": "\nC"}

        @system_prompt_hook(priority=10)
        def hook_a(context):
            execution_order.append("A")
            return {"hook_type": "system_prompt", "content": "\nA"}

        @system_prompt_hook(priority=20)
        def hook_b(context):
            execution_order.append("B")
            return {"hook_type": "system_prompt", "content": "\nB"}

        builder = PromptBuilder()
        messages = builder.build_messages("test", [], {})

        # 验证执行顺序
        assert execution_order == ["A", "B", "C"]

        # 验证内容顺序
        system_prompt = messages[0]["content"]
        assert system_prompt.index("A") < system_prompt.index("B")
        assert system_prompt.index("B") < system_prompt.index("C")


class TestHookValidation:
    """测试 Hook 校验"""

    def test_hook_returns_invalid_type(self, clear_registry):
        """测试 hook 返回非 dict 类型"""
        from backend.agents.hooks import system_prompt_hook
        from backend.core.prompt_builder import PromptBuilder

        @system_prompt_hook(priority=10)
        def invalid_hook(context):
            return "invalid"  # 应该返回 dict

        builder = PromptBuilder()
        messages = builder.build_messages("test", [], {})

        # 不应该崩溃，只是不注入内容
        assert len(messages) == 2  # system + user

    def test_hook_returns_wrong_hook_type(self, clear_registry):
        """测试 hook 返回错误的 hook_type"""
        from backend.agents.hooks import system_prompt_hook
        from backend.core.prompt_builder import PromptBuilder

        @system_prompt_hook(priority=10)
        def wrong_type_hook(context):
            return {"hook_type": "wrong_type", "content": "test"}

        builder = PromptBuilder()
        messages = builder.build_messages("test", [], {})

        # 不应该注入内容
        system_prompt = messages[0]["content"]
        assert "test" not in system_prompt


class TestHookAutoRegistration:
    """测试 Hook 自动注册"""

    def test_hook_name_auto_generated(self, clear_registry):
        """测试 hook name 自动生成"""
        from backend.agents.hooks import system_prompt_hook, SystemPromptRegistry

        @system_prompt_hook(priority=10)
        def my_test_hook(context):
            return {"hook_type": "system_prompt", "content": ""}

        registry = SystemPromptRegistry.get_instance()
        hooks = registry.get_hooks()

        # 验证 name 格式（应该包含 builtin hooks + 测试 hook）
        test_hook = [h for h in hooks if "my_test_hook" in h.name]
        assert len(test_hook) == 1
        assert test_hook[0].name.endswith(".my_test_hook")


class TestHooksIntegration:
    """测试 Hooks 集成"""

    def test_multiple_hooks_enabled(self, prompt_builder):
        """测试多个 hooks 同时启用"""
        context = {
            "enable_skills": True,
            "skills": ["搜索网络"],
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        # system + user = 2
        assert len(messages) == 2

        # 检查 system prompt 包含技能描述
        system_prompt = messages[0]["content"]
        assert "你拥有以下技能" in system_prompt

    def test_hooks_with_history(self, prompt_builder):
        """测试 hooks 与历史消息结合"""
        context = {
            "enable_skills": True,
            "skills": ["搜索网络"]
        }

        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"}
        ]

        messages = prompt_builder.build_messages(
            user_message="我叫张三",
            history=history,
            context=context,
            max_history=20
        )

        # system + history(2) + user = 4
        assert len(messages) == 4
        assert messages[1]["content"] == "你好"
        assert messages[2]["content"] == "你好！"
        assert messages[3]["content"] == "我叫张三"

    def test_hook_error_isolation(self, clear_registry):
        """测试 hook 错误隔离"""
        from backend.agents.hooks import system_prompt_hook
        from backend.core.prompt_builder import PromptBuilder

        @system_prompt_hook(priority=10)
        def failing_hook(context):
            raise Exception("Hook failed")

        @system_prompt_hook(priority=20)
        def working_hook(context):
            return {"hook_type": "system_prompt", "content": "\nWorking"}

        builder = PromptBuilder()
        messages = builder.build_messages("test", [], {})

        # 失败的 hook 不应该影响其他 hooks
        system_prompt = messages[0]["content"]
        assert "Working" in system_prompt
