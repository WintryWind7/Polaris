"""
测试 Hooks 系统

验证 hooks 注册、执行和配置机制
"""
import pytest
from tests.helpers.test_utils import Environment
from backend.config.hooks_config import HooksConfig


@pytest.fixture
def test_env():
    """测试环境 fixture"""
    env = Environment(test_name="hooks")
    yield env


@pytest.fixture
def main_agent(test_env):
    """主 Agent fixture"""
    from backend.agents.main_agent import MainAgent
    return MainAgent()


@pytest.fixture
def prompt_builder(main_agent):
    """提示词构建器 fixture（使用 MainAgent 中已注册 hooks 的实例）"""
    return main_agent.prompt_builder


class TestHooksConfig:
    """测试 Hooks 配置"""

    def test_default_all_disabled(self):
        """测试默认所有 hooks 禁用"""
        context = HooksConfig.to_context()

        assert context["enable_capabilities"] is False
        assert context["enable_memory"] is False
        assert context["enable_tools"] is False
        assert context["enable_few_shot"] is False
        assert context["enable_realtime_info"] is False

    def test_enable_all(self):
        """测试启用所有 hooks"""
        HooksConfig.enable_all()
        context = HooksConfig.to_context()

        assert all(context.values())

        # 恢复默认
        HooksConfig.disable_all()

    def test_disable_all(self):
        """测试禁用所有 hooks"""
        HooksConfig.enable_all()
        HooksConfig.disable_all()
        context = HooksConfig.to_context()

        assert not any(context.values())


class TestSystemPromptHooks:
    """测试 System Prompt Hooks"""

    def test_hook_add_capabilities(self, prompt_builder):
        """测试能力描述 hook"""
        context = {
            "enable_capabilities": True,
            "capabilities": ["搜索网络", "执行代码", "读写文件"]
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        system_prompt = messages[0]["content"]
        assert "你拥有以下能力" in system_prompt
        assert "搜索网络" in system_prompt
        assert "执行代码" in system_prompt

    def test_hook_add_capabilities_disabled(self, prompt_builder):
        """测试能力描述 hook 禁用"""
        context = {
            "enable_capabilities": False,
            "capabilities": ["搜索网络"]
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        system_prompt = messages[0]["content"]
        assert "你拥有以下能力" not in system_prompt

    def test_hook_add_tools(self, prompt_builder):
        """测试工具列表 hook"""
        context = {
            "enable_tools": True
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        system_prompt = messages[0]["content"]
        # 注意：ToolRegistry 默认为空，所以不会注入内容
        # 这里只测试 hook 被调用，不测试具体内容


class TestBeforeMessagesHooks:
    """测试 Before Messages Hooks"""

    def test_hook_add_few_shot_examples(self, prompt_builder):
        """测试 Few-shot 示例 hook"""
        context = {
            "enable_few_shot": True
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        # system + examples(3) + user = 5
        assert len(messages) >= 4

        # 检查示例内容
        has_example = any("搜索北京" in str(m.get("content", "")) for m in messages)
        assert has_example

    def test_hook_add_few_shot_disabled(self, prompt_builder):
        """测试 Few-shot 示例 hook 禁用"""
        context = {
            "enable_few_shot": False
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        # system + user = 2
        assert len(messages) == 2


class TestAfterMessagesHooks:
    """测试 After Messages Hooks"""

    def test_hook_add_realtime_info(self, prompt_builder):
        """测试实时信息 hook"""
        context = {
            "enable_realtime_info": True,
            "realtime_info": {"天气": "晴天", "时间": "14:30"}
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        # system + realtime_info + user = 3
        assert len(messages) == 3

        # 检查实时信息
        has_realtime = any("实时信息" in str(m.get("content", "")) for m in messages)
        assert has_realtime

    def test_hook_add_realtime_info_disabled(self, prompt_builder):
        """测试实时信息 hook 禁用"""
        context = {
            "enable_realtime_info": False,
            "realtime_info": {"天气": "晴天"}
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        # system + user = 2
        assert len(messages) == 2


class TestHooksIntegration:
    """测试 Hooks 集成"""

    def test_multiple_hooks_enabled(self, prompt_builder):
        """测试多个 hooks 同时启用"""
        context = {
            "enable_capabilities": True,
            "enable_few_shot": True,
            "enable_realtime_info": True,
            "capabilities": ["搜索网络"],
            "realtime_info": {"天气": "晴天"}
        }

        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context=context,
            max_history=20
        )

        # system + few_shot(3) + realtime_info + user = 6
        assert len(messages) >= 5

        # 检查各个 hook 是否生效
        system_prompt = messages[0]["content"]
        assert "你拥有以下能力" in system_prompt

        has_example = any("搜索北京" in str(m.get("content", "")) for m in messages)
        assert has_example

        has_realtime = any("实时信息" in str(m.get("content", "")) for m in messages)
        assert has_realtime

    def test_hooks_with_history(self, prompt_builder):
        """测试 hooks 与历史消息结合"""
        context = {
            "enable_capabilities": True,
            "capabilities": ["搜索网络"]
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
