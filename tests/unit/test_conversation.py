"""
测试对话系统

验证多轮对话和 hook 机制
"""
import pytest
from tests.helpers.test_utils import Environment


@pytest.fixture
def test_env():
    """测试环境 fixture"""
    env = Environment(test_name="conversation")
    yield env
    # 测试后清理（可选）
    # env.cleanup()


@pytest.fixture
def conv_manager(test_env):
    """会话管理器 fixture"""
    return test_env.get_conversation_manager()


@pytest.fixture
def prompt_builder(test_env):
    """提示词构建器 fixture"""
    return test_env.get_prompt_builder()


class TestConversationManager:
    """测试会话管理器"""

    def test_create_session(self, conv_manager):
        """测试创建会话"""
        session_id = conv_manager.create_session(metadata={"user": "test_user"})

        assert session_id is not None
        assert len(session_id) > 0

        # 验证会话可以被获取
        session = conv_manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
        assert session.metadata["user"] == "test_user"

    def test_add_message(self, conv_manager):
        """测试添加消息"""
        session_id = conv_manager.create_session()

        # 添加用户消息
        conv_manager.add_message(session_id, "user", "你好")

        # 获取消息
        messages = conv_manager.get_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "你好"

    def test_multi_turn_conversation(self, conv_manager):
        """测试多轮对话"""
        session_id = conv_manager.create_session()

        # 第一轮
        conv_manager.add_message(session_id, "user", "你好")
        conv_manager.add_message(session_id, "assistant", "你好！我是 Polaris。")

        # 第二轮
        conv_manager.add_message(session_id, "user", "我叫张三")
        conv_manager.add_message(session_id, "assistant", "很高兴认识你，张三！")

        # 验证消息数量
        messages = conv_manager.get_messages(session_id)
        assert len(messages) == 4

        # 验证消息顺序
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "你好"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[3]["role"] == "assistant"

    def test_get_messages_with_limit(self, conv_manager):
        """测试获取消息（带限制）"""
        session_id = conv_manager.create_session()

        # 添加多条消息
        for i in range(10):
            conv_manager.add_message(session_id, "user", f"消息 {i}")

        # 获取最近 3 条
        messages = conv_manager.get_messages(session_id, limit=3)
        assert len(messages) == 3
        assert messages[0]["content"] == "消息 7"
        assert messages[2]["content"] == "消息 9"

    def test_delete_session(self, conv_manager):
        """测试删除会话"""
        session_id = conv_manager.create_session()
        conv_manager.add_message(session_id, "user", "测试")

        # 删除会话
        conv_manager.delete_session(session_id)

        # 验证会话不存在
        session = conv_manager.get_session(session_id)
        assert session is None


class TestPromptBuilder:
    """测试提示词构建器"""

    def test_build_messages_basic(self, prompt_builder):
        """测试基础 messages 构建"""
        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context={},
            max_history=10
        )

        # 应该有 system + user
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "你好"

    def test_build_messages_with_history(self, prompt_builder):
        """测试带历史的 messages 构建"""
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]

        messages = prompt_builder.build_messages(
            user_message="我叫张三",
            history=history,
            context={},
            max_history=10
        )

        # system + 历史(2) + 当前用户消息
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "你好"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "我叫张三"

    def test_sliding_window(self, prompt_builder):
        """测试滑动窗口"""
        # 创建 10 条历史消息
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"消息 {i}"})

        # 只保留最近 3 条
        messages = prompt_builder.build_messages(
            user_message="当前消息",
            history=history,
            context={},
            max_history=3
        )

        # system + 历史(3) + 当前
        assert len(messages) == 5
        assert messages[1]["content"] == "消息 7"
        assert messages[2]["content"] == "消息 8"
        assert messages[3]["content"] == "消息 9"

    def test_hook_system_prompt(self, prompt_builder):
        """测试 system prompt hook"""
        # 注册 hook
        def add_test_info(prompt: str, context: dict) -> str:
            return prompt + "\n\n测试信息：这是一个测试"

        prompt_builder.register_hook("system_prompt", add_test_info)

        messages = prompt_builder.build_messages(
            user_message="测试",
            history=[],
            context={},
            max_history=10
        )

        # 验证 hook 生效
        system_prompt = messages[0]["content"]
        assert "测试信息：这是一个测试" in system_prompt

    def test_hook_with_context(self, prompt_builder):
        """测试带上下文的 hook"""
        # 注册 hook
        def add_capabilities(prompt: str, context: dict) -> str:
            capabilities = context.get("capabilities", [])
            if capabilities:
                cap_text = "\n".join(f"- {cap}" for cap in capabilities)
                return prompt + f"\n\n你拥有以下能力：\n{cap_text}"
            return prompt

        prompt_builder.register_hook("system_prompt", add_capabilities)

        messages = prompt_builder.build_messages(
            user_message="测试",
            history=[],
            context={"capabilities": ["文件操作", "网络搜索"]},
            max_history=10
        )

        system_prompt = messages[0]["content"]
        assert "文件操作" in system_prompt
        assert "网络搜索" in system_prompt


class TestIntegration:
    """集成测试"""

    def test_full_conversation_flow(self, conv_manager, prompt_builder):
        """测试完整的对话流程"""
        # 1. 创建会话
        session_id = conv_manager.create_session()

        # 2. 第一轮对话
        messages = prompt_builder.build_messages(
            user_message="你好",
            history=[],
            context={},
            max_history=10
        )
        assert len(messages) == 2

        # 模拟 LLM 回复
        conv_manager.add_message(session_id, "user", "你好")
        conv_manager.add_message(session_id, "assistant", "你好！我是 Polaris。")

        # 3. 第二轮对话（带历史）
        history = conv_manager.get_messages(session_id)
        messages = prompt_builder.build_messages(
            user_message="我叫张三",
            history=history,
            context={},
            max_history=10
        )

        # system + 历史(2) + 当前
        assert len(messages) == 4
        assert messages[1]["content"] == "你好"
        assert messages[2]["content"] == "你好！我是 Polaris。"
        assert messages[3]["content"] == "我叫张三"
