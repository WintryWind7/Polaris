"""
测试环境管理

提供测试数据隔离和管理功能
"""
import shutil
from pathlib import Path
from typing import Optional
from backend.core.conversation import ConversationManager
from backend.core.prompt_builder import PromptBuilder


class Environment:
    """
    测试环境管理器

    用法：
        # 在 pytest fixture 中使用
        @pytest.fixture
        def test_env():
            env = Environment(test_name="my_test")
            yield env
            env.cleanup()  # 可选：测试后清理
    """

    def __init__(self, test_name: Optional[str] = None):
        """
        初始化测试环境

        Args:
            test_name: 测试名称，用于创建独立的测试目录
                      例如：Environment("conversation")
                      数据会写入 data/test/conversation/
        """
        # 项目根目录（tests/helpers/ -> tests/ -> 项目根）
        self.project_root = Path(__file__).parent.parent.parent
        self.test_data_root = self.project_root / "data" / "test"

        if test_name:
            self.test_data_dir = self.test_data_root / test_name
        else:
            self.test_data_dir = self.test_data_root

        # 确保测试目录存在
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

    def get_conversation_manager(self) -> ConversationManager:
        """获取测试用的 ConversationManager"""
        return ConversationManager(self.test_data_dir)

    def get_prompt_builder(self) -> PromptBuilder:
        """获取测试用的 PromptBuilder"""
        return PromptBuilder()

    def cleanup(self):
        """
        清理当前测试的数据

        注意：通常不需要调用，测试数据可以保留用于调试
        """
        if self.test_data_dir.exists():
            shutil.rmtree(self.test_data_dir)
