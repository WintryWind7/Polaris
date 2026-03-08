"""
健康检查路由
"""
import os
import sys

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "reload": os.environ.get("POLARIS_RELOAD") == "1",
        "dev": os.environ.get("POLARIS_DEV") == "1"
    }
