"""
技能注册表

管理技能的注册、查询和执行。
"""
from typing import Dict, Optional, List

from .base import Skill


class SkillRegistry:
    """技能注册表"""

    def __init__(self):
        """初始化技能注册表"""
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill):
        """
        注册技能

        Args:
            skill: 技能实例
        """
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        """
        获取技能

        Args:
            name: 技能名称

        Returns:
            技能实例或 None
        """
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        """
        列出所有技能

        Returns:
            技能名称列表
        """
        return list(self._skills.keys())

    def unregister(self, name: str) -> bool:
        """
        注销技能

        Args:
            name: 技能名称

        Returns:
            是否成功注销
        """
        if name in self._skills:
            del self._skills[name]
            return True
        return False
