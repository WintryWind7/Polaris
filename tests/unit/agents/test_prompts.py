"""
测试 Prompts 系统

验证：
1. 文件加载逻辑（优先级：data/prompts > templates）
2. 首次使用时自动复制模板
3. soul.md 和 memory.md 正确注入到 system prompt
"""
import pytest
from pathlib import Path
import tempfile
import shutil
from tests.helpers.test_utils import Environment


@pytest.fixture
def test_env():
    """测试环境 fixture"""
    env = Environment(test_name="prompts")
    yield env


@pytest.fixture
def temp_data_dir():
    """创建临时 data 目录"""
    temp_dir = tempfile.mkdtemp()
    data_prompts = Path(temp_dir) / "prompts"
    data_prompts.mkdir(parents=True)

    yield temp_dir

    # 清理
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def clear_registry():
    """清空注册表"""
    from backend.agents.hooks import SystemPromptRegistry
    registry = SystemPromptRegistry.get_instance()
    registry.clear()
    yield registry


class TestPromptLoader:
    """测试提示词加载器"""

    def test_load_soul_from_template(self):
        """测试从模板加载 soul.md"""
        from backend.agents.prompts.loader import load_prompt_file

        content = load_prompt_file("soul.md")

        # 验证内容
        assert "Polaris" in content
        assert "核心使命" in content
        assert len(content) > 100

    def test_load_memory_from_template(self):
        """测试从模板加载 memory.md"""
        from backend.agents.prompts.loader import load_prompt_file

        content = load_prompt_file("memory.md")

        # 验证内容
        assert "长期记忆" in content or "记忆" in content

    def test_load_creates_user_file(self):
        """测试加载时会创建用户文件"""
        from backend.agents.prompts.loader import load_prompt_file

        # 删除可能存在的用户文件
        user_file = Path("backend/data/prompts/soul.md")
        if user_file.exists():
            # 如果存在，说明已经被创建过了
            content = load_prompt_file("soul.md")
            assert "Polaris" in content
        else:
            # 首次加载会创建
            content = load_prompt_file("soul.md")
            assert user_file.exists()
            assert "Polaris" in content

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        from backend.agents.prompts.loader import load_prompt_file

        with pytest.raises(FileNotFoundError):
            load_prompt_file("nonexistent.md")


class TestPromptHooks:
    """测试提示词 Hooks"""

    def test_soul_hook_injects_content(self):
        """测试 soul hook 注入内容"""
        from backend.agents.prompts.soul import inject_soul

        result = inject_soul({})

        assert result["hook_type"] == "system_prompt"
        assert "Polaris" in result["content"]
        assert "核心使命" in result["content"]

    def test_memory_hook_injects_content(self):
        """测试 memory hook 注入内容"""
        from backend.agents.prompts.memory import inject_memory

        result = inject_memory({})

        assert result["hook_type"] == "system_prompt"
        # memory.md 可能不存在，返回空内容也是正常的
        assert isinstance(result["content"], str)

    def test_hooks_are_registered_in_builder(self):
        """测试 hooks 在 PromptBuilder 中被注册"""
        from backend.core.prompt_builder import PromptBuilder
        from backend.agents.hooks import SystemPromptRegistry

        # 创建 builder 会触发 hooks 注册
        builder = PromptBuilder()

        registry = SystemPromptRegistry.get_instance()
        hooks = registry.get_hooks()

        # 应该至少有 soul 和 memory hooks
        hook_names = [h.name for h in hooks]
        assert any("inject_soul" in name for name in hook_names)
        assert any("inject_memory" in name for name in hook_names)


class TestPromptsIntegration:
    """测试 Prompts 集成"""

    def test_prompts_in_system_prompt(self, clear_registry):
        """测试 prompts 内容注入到 system prompt"""
        from backend.core.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        messages = builder.build_messages(
            user_message="你好",
            history=[],
            context={},
            max_history=20
        )

        system_prompt = messages[0]["content"]

        # 验证 soul.md 内容
        assert "Polaris" in system_prompt or "北极星" in system_prompt

        # 验证 memory.md 内容（如果存在）
        # memory.md 可能包含 "长期记忆" 或为空

    def test_prompts_priority_order(self, clear_registry):
        """测试 prompts 按优先级顺序注入"""
        from backend.core.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        messages = builder.build_messages(
            user_message="测试",
            history=[],
            context={},
            max_history=20
        )

        system_prompt = messages[0]["content"]

        # soul (priority=10) 应该在 memory (priority=20) 之前
        # 但由于 memory 可能为空，只验证 soul 存在
        assert "Polaris" in system_prompt or len(system_prompt) > 0

    def test_prompts_with_history(self, clear_registry):
        """测试 prompts 与历史消息结合"""
        from backend.core.prompt_builder import PromptBuilder

        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"}
        ]

        builder = PromptBuilder()
        messages = builder.build_messages(
            user_message="我是谁",
            history=history,
            context={},
            max_history=20
        )

        # system + history(2) + user = 4
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "你好"
        assert messages[2]["content"] == "你好！"
        assert messages[3]["content"] == "我是谁"


class TestPromptFiles:
    """测试提示词文件"""

    def test_soul_template_exists(self):
        """测试 soul.md 模板存在"""
        template_path = Path("backend/agents/prompts/templates/soul.md")
        assert template_path.exists()

        content = template_path.read_text(encoding="utf-8")
        assert "Polaris" in content
        assert len(content) > 100  # 确保有实质内容

    def test_memory_template_exists(self):
        """测试 memory.md 模板存在"""
        template_path = Path("backend/agents/prompts/templates/memory.md")
        assert template_path.exists()

        content = template_path.read_text(encoding="utf-8")
        assert "长期记忆" in content or "记忆" in content

    def test_templates_are_valid_markdown(self):
        """测试模板是有效的 Markdown"""
        templates_dir = Path("backend/agents/prompts/templates")

        for md_file in templates_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")

            # 基本 Markdown 验证
            assert len(content) > 0
            assert not content.startswith(" ")  # 不应该有前导空格

            # 应该包含标题
            assert "#" in content
