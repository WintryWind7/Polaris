"""
共享状态管理

使用 JSON 文件存储共享状态（测试阶段），后续迁移到 SQLite。
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional
from threading import Lock


class StateManager:
    """状态管理器"""

    def __init__(self, state_file: Path):
        """
        初始化状态管理器

        Args:
            state_file: 状态文件路径
        """
        self.state_file = state_file
        self.state: Dict[str, Any] = {}
        self.lock = Lock()

        # 确保父目录存在
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # 加载状态
        self._load()

    def _load(self):
        """从文件加载状态"""
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                self.state = json.load(f)

    def _save(self):
        """保存状态到文件"""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取状态值

        Args:
            key: 键
            default: 默认值

        Returns:
            状态值
        """
        with self.lock:
            return self.state.get(key, default)

    def set(self, key: str, value: Any):
        """
        设置状态值

        Args:
            key: 键
            value: 值
        """
        with self.lock:
            self.state[key] = value
            self._save()

    def update(self, data: Dict[str, Any]):
        """
        批量更新状态

        Args:
            data: 要更新的数据
        """
        with self.lock:
            self.state.update(data)
            self._save()

    def delete(self, key: str):
        """
        删除状态值

        Args:
            key: 键
        """
        with self.lock:
            if key in self.state:
                del self.state[key]
                self._save()

    def clear(self):
        """清空所有状态"""
        with self.lock:
            self.state = {}
            self._save()

    def get_all(self) -> Dict[str, Any]:
        """
        获取所有状态

        Returns:
            状态字典
        """
        with self.lock:
            return self.state.copy()
