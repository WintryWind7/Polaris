"""
Hooks 配置

控制各个 hook 的启用/禁用状态。
默认全部禁用，需要时手动开启。
"""
from typing import Dict, Any


class HooksConfig:
    """Hooks 配置类"""

    # ========== System Prompt Hooks ==========
    ENABLE_CAPABILITIES = False  # 能力描述
    ENABLE_MEMORY = False        # 长期记忆
    ENABLE_TOOLS = False         # 工具列表

    # ========== Before Messages Hooks ==========
    ENABLE_FEW_SHOT = False      # Few-shot 示例

    # ========== After Messages Hooks ==========
    ENABLE_REALTIME_INFO = False # 实时信息

    @classmethod
    def to_context(cls) -> Dict[str, Any]:
        """
        转换为 context 字典

        Returns:
            包含所有 hook 开关的字典
        """
        return {
            "enable_capabilities": cls.ENABLE_CAPABILITIES,
            "enable_memory": cls.ENABLE_MEMORY,
            "enable_tools": cls.ENABLE_TOOLS,
            "enable_few_shot": cls.ENABLE_FEW_SHOT,
            "enable_realtime_info": cls.ENABLE_REALTIME_INFO,
        }

    @classmethod
    def enable_all(cls):
        """启用所有 hooks（调试用）"""
        cls.ENABLE_CAPABILITIES = True
        cls.ENABLE_MEMORY = True
        cls.ENABLE_TOOLS = True
        cls.ENABLE_FEW_SHOT = True
        cls.ENABLE_REALTIME_INFO = True

    @classmethod
    def disable_all(cls):
        """禁用所有 hooks（默认状态）"""
        cls.ENABLE_CAPABILITIES = False
        cls.ENABLE_MEMORY = False
        cls.ENABLE_TOOLS = False
        cls.ENABLE_FEW_SHOT = False
        cls.ENABLE_REALTIME_INFO = False
