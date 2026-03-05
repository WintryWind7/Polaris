import sys
import subprocess
import time
import shutil
import re
import urllib.request
import json
from pathlib import Path

# 项目根目录 (相对于 utils 目录)
ROOT_DIR = Path(__file__).parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_DIR = ROOT_DIR / "backend"

# 默认端口配置
BACKEND_PORT = 6547
FRONTEND_PORT = 6546

def find_npm():
    """查找 npm 命令"""
    npm_cmd = shutil.which("npm")
    if npm_cmd:
        return npm_cmd

    if sys.platform == 'win32':
        possible_paths = [
            r"C:\Program Files\nodejs\npm.cmd",
            r"C:\Program Files (x86)\nodejs\npm.cmd",
            Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
        ]
        for path in possible_paths:
            if Path(path).exists():
                return str(path)
    return None

def check_port_occupied(port):
    """
    检查端口是否被占用。
    始终返回 (bool, Optional[int]) 二元组，不会返回 None。
    """
    try:
        if sys.platform == 'win32':
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                encoding='gbk',
                errors='ignore'
            )
            pattern = rf'[:\s]{port}\s+.*LISTENING\s+(\d+)'
            match = re.search(pattern, result.stdout)
            if match:
                return True, int(match.group(1))
        else:
            result = subprocess.run(
                ['lsof', '-i', f':{port}', '-t'],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                return True, int(result.stdout.strip().split()[0])
    except Exception:
        pass
    return False, None

def kill_process(pid, graceful=True):
    """
    停止指定进程（包括子进程树）

    Args:
        pid: 进程 ID
        graceful: 是否先尝试优雅关闭（发送 SIGTERM/CTRL_C）
    """
    try:
        if sys.platform == 'win32':
            if graceful:
                # Windows: 先尝试发送 Ctrl+C 信号
                try:
                    subprocess.run(
                        ['taskkill', '/PID', str(pid), '/T'],
                        capture_output=True,
                        timeout=2
                    )
                    # 等待进程退出
                    time.sleep(1)
                    # 检查是否还在运行
                    check = subprocess.run(
                        ['tasklist', '/FI', f'PID eq {pid}'],
                        capture_output=True,
                        text=True
                    )
                    if str(pid) not in check.stdout:
                        return True  # 优雅关闭成功
                except:
                    pass

            # 强制关闭
            result = subprocess.run(
                ['taskkill', '/PID', str(pid), '/T', '/F'],
                capture_output=True
            )
            return result.returncode == 0
        else:
            if graceful:
                # Unix: 先发送 SIGTERM
                try:
                    subprocess.run(['kill', '-TERM', str(pid)], timeout=1)
                    time.sleep(1)
                    # 检查是否还在运行
                    check = subprocess.run(['kill', '-0', str(pid)], capture_output=True)
                    if check.returncode != 0:
                        return True  # 优雅关闭成功
                except:
                    pass

            # 强制关闭
            result = subprocess.run(
                ['kill', '-9', str(pid)],
                capture_output=True
            )
            return result.returncode == 0
    except Exception:
        return False

def clean_port(port, name=""):
    """尝试强制清理单个端口上的进程"""
    is_occupied, pid = check_port_occupied(port)
    if is_occupied and pid:
        kill_process(pid)
        time.sleep(0.5)
    return True

def kill_service_on_port(port):
    """杀死占用指定端口的进程，用于退出时的物理级清理"""
    is_occupied, pid = check_port_occupied(port)
    if is_occupied and pid:
        kill_process(pid)

def check_backend_alive(port):
    """
    通过 API 检查后端是否存活、验证是 Polaris 后端并返回 PID、热重载和 dev 状态。
    返回 (is_alive: bool, pid: Optional[int], hot: bool, dev: bool)
    """
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get("status") == "healthy":
                    return (
                        True,
                        data.get("pid"),
                        data.get("reload", False),
                        data.get("dev", False)
                    )
    except Exception:
        pass
    return False, None, False, False

def check_frontend_alive(port):
    """
    通过 frontend_id.json 验证前端身份，确认是 Polaris 前端并返回 PID 和热重载状态。
    返回 (is_alive: bool, pid: Optional[int], hot: bool)
    """
    try:
        # 使用 frontend_id.json 避免与 /health 代理路径冲突
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/frontend_id.json", timeout=2) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get("app") == "polaris-frontend":
                    # 身份确认，再查实际 PID
                    _, pid = check_port_occupied(port)
                    return True, pid, data.get("hot", False)
    except Exception:
        pass
    return False, None, False

def setup_log_file(name):
    """创建并准备日志文件"""
    log_dir = ROOT_DIR / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name}.log"

    f = open(log_file, "a", encoding="utf-8")
    f.write(f"\n--- {name.upper()} START AT {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    f.flush()
    return f
