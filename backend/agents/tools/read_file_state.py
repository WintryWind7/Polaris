"""
ReadFileState — per-subagent 文件读取状态追踪

确保子 Agent 在 write_file 之前已经 read_file 过目标文件，
防止 LLM 基于过期认知或凭空猜测修改文件。

参照 Claude Code 的 readFileState 机制，简化版：
- 规则 1: read_file 成功后登记
- 规则 2: write_file 前必须查表（新文件豁免）
- 规则 3: write_file 成功后自动续期（连续写入无需重读）
- 规则 4: LRU 容量控制（默认 100 条目）
"""
import os
from pathlib import Path
from typing import Optional, Tuple


class ReadFileState:
    """per-subagent 文件读取状态追踪（LRU）"""

    def __init__(self, max_entries: int = 100):
        self._max_entries = max_entries
        # Python 3.7+ dict 保序；每次 register 时把 key 移到最后 → LRU
        self._entries: dict[str, dict] = {}

    # ---- public API ----

    def register(self, path: str, content: str) -> None:
        """登记一次读取或写入"""
        abs_path = self._resolve(path)
        if not abs_path:
            return

        mtime = self._get_mtime(abs_path)
        # 删除旧 key（如果存在），后面新插入保证排到末尾
        self._entries.pop(abs_path, None)
        self._entries[abs_path] = {
            "content": content,
            "mtime": mtime,
        }
        # 超出容量时淘汰最久未用的（dict 第一个 key）
        while len(self._entries) > self._max_entries:
            oldest = next(iter(self._entries))
            del self._entries[oldest]

    def can_write(self, path: str) -> Tuple[bool, str]:
        """
        检查是否可以写入。
        返回 (allowed, reason)。
        """
        abs_path = self._resolve(path)
        if not abs_path:
            return False, f"无法解析路径: {path}"

        # 新文件豁免
        if not os.path.exists(abs_path):
            return True, ""

        # 查表
        if abs_path in self._entries:
            return True, ""

        return False, "File has not been read yet. Read it first before writing to it."

    def clear(self) -> None:
        """清空状态（测试用）"""
        self._entries.clear()

    # ---- internal ----

    @staticmethod
    def _resolve(path: str) -> Optional[str]:
        try:
            return str(Path(path).resolve())
        except Exception:
            return None

    @staticmethod
    def _get_mtime(file_path: str) -> Optional[int]:
        """获取文件 mtime（毫秒级），为后续并发保护预留"""
        try:
            return int(os.path.getmtime(file_path) * 1000)
        except OSError:
            return None
