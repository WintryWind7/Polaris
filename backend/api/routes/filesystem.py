"""
文件系统 API 路由
"""
import os
import sys
from fastapi import APIRouter, Query
from pathlib import Path

from backend.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/filesystem", tags=["filesystem"])


@router.get("/list-dir")
async def list_dir(path: str = Query("", description="要列出的目录路径")):
    """列出指定路径下的子目录（不含普通文件）"""
    # 无路径时返回根级入口
    if not path:
        if sys.platform == "win32":
            drives = []
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append({"name": drive, "path": drive, "type": "drive"})
            return {"current_path": "", "parent": None, "dirs": drives}
        else:
            path = "/"

    path = os.path.normpath(path)

    if not os.path.isdir(path):
        return {"current_path": path, "parent": None, "dirs": [], "error": "路径不存在"}

    # 计算上级目录
    parent = str(Path(path).parent)
    if parent == path:
        parent = None

    dirs = []
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return {"current_path": path, "parent": parent, "dirs": [], "error": "无权限访问"}

    for name in entries:
        full = os.path.join(path, name)
        if os.path.isdir(full):
            dirs.append({"name": name, "path": full})

    return {"current_path": path, "parent": parent, "dirs": dirs}

