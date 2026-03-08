"""
技能系统

可扩展的技能注册和管理框架。
"""
from .base import Skill
from .registry import SkillRegistry

__all__ = ["Skill", "SkillRegistry"]
