"""
Polaris 启动脚本

- 开发模式：python main.py --dev
- 生产模式：python main.py
- 清理端口：python main.py --clean

Ref: /docs/spec/main.md
"""
import os
import sys
import time
import signal
from pathlib import Path

# 修复 Windows 终端输出 Emoji 的编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.backend_launcher import start_backend
from utils.frontend_launcher import start_frontend
from utils.launcher_utils import (
    BACKEND_PORT, FRONTEND_PORT,
    LAST_BACKEND_PORT, LAST_FRONTEND_PORT,
    check_backend_alive, check_frontend_alive,
    check_port_occupied, kill_process,
    check_restart_signal
)


class PolarisLauncher:
    """Polaris 启动器：启动服务并等待退出信号"""

    def __init__(self, dev_mode: bool):
        self.dev_mode = dev_mode
        self.backend_pid = None
        self.frontend_pid = None
        self.should_exit = False

    def start_dev_mode(self):
        """开发模式：启动前后端开发服务器"""
        print("\n✨ Polaris Launcher [Development Mode]")
        print("-" * 50)

        # 启动前清理旧阵地
        self._kill_services()

        print("[Backend ]  ○ 启动中...", end="", flush=True)
        p_backend = start_backend(dev_mode=True, interactive=False, quiet=True)
        if not p_backend:
            print("\r[Backend ]  ✗ 启动失败，请检查 data/logs/backend_server.log")
            sys.exit(1)

        print("\r[Backend ]  ○ 已启动，等待就绪...")

        print("[Frontend]  ○ 启动中...", end="", flush=True)
        p_frontend = start_frontend(dev_mode=True, interactive=False, quiet=True)
        if not p_frontend:
            print("\r[Frontend]  ✗ 启动失败，请检查 data/logs/frontend_dev.log")
            sys.exit(1)

        print("\r[Frontend]  ○ 已启动，等待就绪...")

        # --- 核心逻辑：启动后立即落账 ---
        # 只要进程拉起来了，就承认这是“最后一次启动成功的端口”
        self._update_last_ports()

        # 等待后端就绪
        for _ in range(10):
            time.sleep(1)
            alive, pid, hot, dev = check_backend_alive(BACKEND_PORT)
            if alive:
                hot_tag = " (热重载)" if hot else ""
                print(f"[Backend ]  ✓ 已就绪    http://127.0.0.1:{BACKEND_PORT}{hot_tag}  PID:{pid}")
                self.backend_pid = pid
                break
        else:
            print("[Backend ]  ✗ 就绪检查超时")

        # 等待前端就绪
        for _ in range(15):
            time.sleep(1)
            alive, pid, hot = check_frontend_alive(FRONTEND_PORT)
            if alive:
                hot_tag = " (热重载)" if hot else ""
                print(f"[Frontend]  ✓ 已就绪    http://127.0.0.1:{FRONTEND_PORT}{hot_tag}  PID:{pid}")
                self.frontend_pid = pid
                break
        else:
            print("[Frontend]  ✗ 就绪检查超时")

        print("-" * 50)
        print("✅ 所有服务已就绪，按 Ctrl+C 关闭所有服务")

    def start_prod_mode(self):
        """生产模式：构建前端并启动后端（后端托管静态文件）"""
        if sys.platform == 'win32':
            os.system('chcp 65001 > nul')

        try:
            print("\n✨ Polaris Launcher [Production Mode]")
        except UnicodeEncodeError:
            print("\n[*] Polaris Launcher [Production Mode]")
        print("-" * 50)

        self._kill_services()

        # 构建前端
        print("[Frontend]  ○ 构建中...", end="", flush=True)
        start_frontend(dev_mode=False, interactive=False, quiet=True)
        print("\r[Frontend]  ✓ 构建完成")

        # 启动后端
        print("[Backend ]  ○ 启动中...", end="", flush=True)
        p = start_backend(dev_mode=False, interactive=False, quiet=True)
        if not p:
            print("\r[Backend ]  ✗ 启动失败，请检查 data/logs/backend_server.log")
            sys.exit(1)

        # --- 核心逻辑：启动后立即落账 ---
        self._update_last_ports()

        # 等待后端就绪
        for _ in range(10):
            time.sleep(1)
            alive, pid, hot, dev = check_backend_alive(BACKEND_PORT)
            if alive:
                print(f"\r[Backend ]  ✓ 已启动    http://127.0.0.1:{BACKEND_PORT}  PID:{pid}")
                print(f"[Frontend]  ✓ 已托管    http://127.0.0.1:{BACKEND_PORT}/app")
                self.backend_pid = pid
                break
        else:
            print("\r[Backend ]  ✗ 启动超时")
            sys.exit(1)

        print("-" * 50)
        print("✅ 所有服务已就绪，按 Ctrl+C 关闭所有服务")

    def _update_last_ports(self):
        """启动后记录端口信息，代替锁文件"""
        try:
            from backend.config.manager import ConfigManager
            ConfigManager().update({
                "server": {
                    "last_port": BACKEND_PORT,
                    "last_frontend_port": FRONTEND_PORT if self.dev_mode else None
                }
            })
        except Exception:
            pass

    def shutdown(self, *_):
        """处理 Ctrl+C：清理所有 Polaris 服务"""
        if self.should_exit:
            return
        self.should_exit = True

        try:
            print("\n\n🛑 正在关闭 Polaris...")
        except UnicodeEncodeError:
            print("\n\n[Stop] 正在关闭 Polaris...")

        self._kill_services()
        self._reset_terminal()

        print("✅ 所有服务已清理完毕")
        sys.exit(0)

    def _kill_services(self):
        """清理所有相关的服务进程（当前和历史端口）"""
        b_ports = {BACKEND_PORT, LAST_BACKEND_PORT} - {None}
        f_ports = {FRONTEND_PORT, LAST_FRONTEND_PORT} - {None}

        for port in b_ports:
            is_occupied, pid = check_port_occupied(port)
            if is_occupied and pid:
                b_healthy, _, _, _ = check_backend_alive(port)
                if b_healthy:
                    kill_process(pid)

        if self.dev_mode:
            for port in f_ports:
                is_occupied, pid = check_port_occupied(port)
                if is_occupied and pid:
                    f_healthy, _, _ = check_frontend_alive(port)
                    if f_healthy:
                        kill_process(pid)

    def _reset_terminal(self):
        """重置终端状态，防止被子进程污染"""
        import subprocess
        if sys.platform == 'win32':
            try:
                subprocess.run(['powershell', '-Command', '[Console]::ResetColor()'],
                             capture_output=True, timeout=1)
            except:
                pass
        else:
            try:
                subprocess.run(['stty', 'sane'], timeout=1)
            except:
                pass

        try:
            sys.stdout.write('\033[0m')
            sys.stdout.write('\033[?25h')
            sys.stdout.flush()
        except:
            pass

    def run(self):
        """主入口：启动服务并等待退出信号"""
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        if self.dev_mode:
            self.start_dev_mode()
        else:
            self.start_prod_mode()

        try:
            while not self.should_exit:
                time.sleep(1)
                if check_restart_signal():
                    print("\n\n🔄 检测到重启信号，正在重启服务...")
                    self._kill_services()
                    os.execv(sys.executable, [sys.executable] + sys.argv)
        except KeyboardInterrupt:
            self.shutdown()


def clean():
    """清理所有可能的 Polaris 服务路径"""
    try:
        print("🛑 正在清理 Polaris 所有服务...")
    except UnicodeEncodeError:
        print("[Stop] 正在清理 Polaris 所有服务...")

    from utils.launcher_utils import _load_ports
    _, _, last_b, last_f = _load_ports()
    
    b_ports = {BACKEND_PORT, last_b} - {None}
    f_ports = {FRONTEND_PORT, last_f} - {None}

    for port in b_ports:
        is_occupied, pid = check_port_occupied(port)
        if is_occupied and pid:
            b_alive, _, _, _ = check_backend_alive(port)
            if b_alive:
                print(f"[Backend ]  正在关闭进程 (PID: {pid}, Port: {port})...")
                kill_process(pid)
    
    for port in f_ports:
        is_occupied, pid = check_port_occupied(port)
        if is_occupied and pid:
            f_alive, _, _ = check_frontend_alive(port)
            if f_alive:
                print(f"[Frontend]  正在关闭进程 (PID: {pid}, Port: {port})...")
                kill_process(pid)

    print("✅ 所有服务已清理完毕")


def main():
    if "--clean" in sys.argv:
        clean()
        return

    dev_mode = "--dev" in sys.argv or "-dev" in sys.argv
    launcher = PolarisLauncher(dev_mode=dev_mode)
    launcher.run()


if __name__ == "__main__":
    main()
