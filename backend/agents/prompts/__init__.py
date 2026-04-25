"""
Prompts 模块

导入所有 prompt hooks 以触发自动注册
"""
from . import soul
from . import memory
from . import workspace

__all__ = ["soul", "memory", "workspace"]
