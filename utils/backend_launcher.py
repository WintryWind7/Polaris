import sys
import subprocess
import time
import os
from pathlib import Path

# 添加项目根目录到路径，确保能导入 backend
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.launcher_utils import BACKEND_PORT, setup_log_file, clean_port

def start_backend(dev_mode=True, interactive=True, quiet=False):
    """启动后端服务"""
    if interactive:
        clean_port(BACKEND_PORT, "后端")

    if not quiet:
        print(f"🚀 正在启动后端服务 (端口: {BACKEND_PORT})...")

    env = os.environ.copy()
    env['NO_COLOR'] = '1'
    env['PYTHONUNBUFFERED'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'   # 强制子进程 stdout/stderr 使用 UTF-8
    env['PYTHONUTF8'] = '1'             # Python 3.7+ UTF-8 模式
    env['POLARIS_PORT'] = str(BACKEND_PORT)
    if dev_mode:
        env['POLARIS_RELOAD'] = '1'  # 仅在开发模式开启热重载
        env['POLARIS_DEV'] = '1'     # 标识当前为开发模式

    log_f = setup_log_file("backend_server")

    # 创建启动参数，隔离子进程
    popen_kwargs = {
        'cwd': ROOT_DIR,
        'env': env,
        'stdout': log_f,
        'stderr': log_f,
    }

    # Windows: 创建新的进程组，防止终端状态污染
    if sys.platform == 'win32':
        popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # Unix: 创建新的会话，完全隔离终端
        popen_kwargs['start_new_session'] = True

    process = subprocess.Popen(
        [sys.executable, "-m", "backend.api.server"],
        **popen_kwargs
    )

    # 简单检查是否立刻崩溃
    time.sleep(2)
    if process.poll() is not None:
        print("[错误] 后端启动失败，请检查 data/logs/backend_server.log")
        if interactive:
            sys.exit(1)
        return None

    if not quiet:
        print(f"✓ 后端服务已启动: http://127.0.0.1:{BACKEND_PORT}{' (热重载)' if dev_mode else ''}")
    return process

if __name__ == "__main__":
    from utils.launcher_utils import check_backend_alive, check_port_occupied

    # 检查端口是否已被占用
    is_occupied, pid = check_port_occupied(BACKEND_PORT)
    if is_occupied:
        # 尝试通过 API 确认是否是 Polaris 后端
        b_alive, b_pid, b_hot, b_dev = check_backend_alive(BACKEND_PORT)
        if b_alive:
            hot_tag = " (热重载)" if b_hot else ""
            mode_tag = " [开发模式]" if b_dev else " [生产模式]"
            print(f"⚠️  后端已在运行{hot_tag}{mode_tag}")
            print(f"    http://127.0.0.1:{BACKEND_PORT}")
            print(f"    PID: {b_pid}")
            print("💡 后端支持热重载，无需重启")
        else:
            print(f"⚠️  端口 {BACKEND_PORT} 已被占用 (PID: {pid})")
            print("💡 可能是其他程序占用，请检查或运行 python main.py --clean")
        sys.exit(1)

    dev = "--prod" not in sys.argv
    try:
        p = start_backend(dev_mode=dev, interactive=True)
        if p:
            print("按 Ctrl+C 停止后端服务...")
            p.wait()
    except KeyboardInterrupt:
        print("\n正在停止后端...")
    except Exception as e:
        print(f"\n[错误] {e}")
        sys.exit(1)
