import sys
import subprocess
import time
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.launcher_utils import (
    FRONTEND_DIR, FRONTEND_PORT, find_npm, 
    setup_log_file, clean_port
)

def start_frontend(dev_mode=True, interactive=True, quiet=False):
    """启动前端服务"""
    npm_cmd = find_npm()
    if not npm_cmd:
        print("[错误] 找不到 npm 命令，请先安装 Node.js")
        if interactive:
            sys.exit(1)
        return None

    # 检查 node_modules
    if not (FRONTEND_DIR / "node_modules").exists():
        if not quiet:
            print("[前端] 首次运行，正在安装依赖...")
        subprocess.run([npm_cmd, "install"], cwd=FRONTEND_DIR, check=True)

    if dev_mode:
        if interactive:
            clean_port(FRONTEND_PORT, "前端开发")

        if not quiet:
            print(f"🚀 正在启动前端开发服务器 (端口: {FRONTEND_PORT})...")
        log_f = setup_log_file("frontend_dev")

        # 创建启动参数，隔离子进程
        popen_kwargs = {
            'cwd': FRONTEND_DIR,
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
            [npm_cmd, "run", "dev"],
            **popen_kwargs
        )

        time.sleep(2)
        if process.poll() is not None:
            print("[错误] 前端启动失败，请检查 data/logs/frontend_dev.log")
            if interactive:
                sys.exit(1)
            return None

        if not quiet:
            print(f"✓ 前端开发服务器已启动: http://127.0.0.1:{FRONTEND_PORT}")
        return process
    else:
        # 生产模式构建
        if not quiet:
            print("[前端] 正在构建生产版本...")
        result = subprocess.run(
            [npm_cmd, "run", "build"],
            cwd=FRONTEND_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode != 0:
            print("[错误] 前端构建失败:")
            print(result.stderr)
            if interactive:
                sys.exit(1)
            return None
        if not quiet:
            print("[前端] 构建完成")
        return True

if __name__ == "__main__":
    from utils.launcher_utils import check_frontend_alive, check_port_occupied

    # 检查端口是否已被占用
    is_occupied, pid = check_port_occupied(FRONTEND_PORT)
    if is_occupied:
        # 尝试通过 API 确认是否是 Polaris 前端
        f_alive, f_pid, f_hot = check_frontend_alive(FRONTEND_PORT)
        if f_alive:
            hot_tag = " (热重载)" if f_hot else ""
            print(f"⚠️  前端已在运行{hot_tag}")
            print(f"    http://127.0.0.1:{FRONTEND_PORT}")
            print(f"    PID: {f_pid}")
            print("💡 前端支持热重载，无需重启")
        else:
            print(f"⚠️  端口 {FRONTEND_PORT} 已被占用 (PID: {pid})")
            print("💡 可能是其他程序占用，请检查或运行 python main.py --clean")
        sys.exit(1)

    dev = "--prod" not in sys.argv
    try:
        p = start_frontend(dev_mode=dev, interactive=True)
        if p and p is not True:
            print("按 Ctrl+C 停止前端开发服务器...")
            p.wait()
    except KeyboardInterrupt:
        print("\n正在停止前端...")
    except Exception as e:
        print(f"\n[错误] {e}")
        sys.exit(1)
