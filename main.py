"""
Polaris 启动脚本

- 开发模式：python main.py --dev
- 生产模式：python main.py
- 清理端口：python main.py --clean

Ref: /docs/spec/main.md
"""
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
    check_backend_alive, check_frontend_alive,
    check_port_occupied, kill_process
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

        # 检查后端状态
        b_alive, b_pid, b_hot, b_dev = check_backend_alive(BACKEND_PORT)
        if b_alive:
            hot_tag = " (热重载)" if b_hot else ""
            print(f"[Backend ]  ● 已在运行  http://127.0.0.1:{BACKEND_PORT}{hot_tag}  PID:{b_pid}")
            print("💡 后端支持热重载，无需重启")
            self.backend_pid = b_pid
        else:
            print("[Backend ]  ○ 启动中...", end="", flush=True)
            p = start_backend(dev_mode=True, interactive=False, quiet=True)
            if not p:
                print("\r[Backend ]  ✗ 启动失败，请检查 data/logs/backend_server.log")
                sys.exit(1)

            # 等待后端就绪
            for _ in range(10):
                time.sleep(1)
                alive, pid, hot, dev = check_backend_alive(BACKEND_PORT)
                if alive:
                    hot_tag = " (热重载)" if hot else ""
                    print(f"\r[Backend ]  ✓ 已启动    http://127.0.0.1:{BACKEND_PORT}{hot_tag}  PID:{pid}")
                    self.backend_pid = pid
                    break
            else:
                print("\r[Backend ]  ✗ 启动超时")
                sys.exit(1)

        # 检查前端状态
        f_alive, f_pid, f_hot = check_frontend_alive(FRONTEND_PORT)
        if f_alive:
            hot_tag = " (热重载)" if f_hot else ""
            print(f"[Frontend]  ● 已在运行  http://127.0.0.1:{FRONTEND_PORT}{hot_tag}  PID:{f_pid}")
            print("💡 前端支持热重载，无需重启")
            self.frontend_pid = f_pid
        else:
            print("[Frontend]  ○ 启动中...", end="", flush=True)
            p = start_frontend(dev_mode=True, interactive=False, quiet=True)
            if not p:
                print("\r[Frontend]  ✗ 启动失败，请检查 data/logs/frontend_dev.log")
                sys.exit(1)

            # 等待前端就绪
            for _ in range(15):
                time.sleep(1)
                alive, pid, hot = check_frontend_alive(FRONTEND_PORT)
                if alive:
                    hot_tag = " (热重载)" if hot else ""
                    print(f"\r[Frontend]  ✓ 已启动    http://127.0.0.1:{FRONTEND_PORT}{hot_tag}  PID:{pid}")
                    self.frontend_pid = pid
                    break
            else:
                print("\r[Frontend]  ✗ 启动超时")
                sys.exit(1)

        print("-" * 50)
        print("✅ 所有服务已就绪，按 Ctrl+C 关闭所有服务")

    def start_prod_mode(self):
        """生产模式：构建前端并启动后端（后端托管静态文件）"""
        # Set console encoding to utf-8 if on windows to avoid encoding errors with emojis
        if sys.platform == 'win32':
            os.system('chcp 65001 > nul')

        try:
            print("\n✨ Polaris Launcher [Production Mode]")
        except UnicodeEncodeError:
            print("\n[*] Polaris Launcher [Production Mode]")
        print("-" * 50)

        # 检查后端状态
        b_alive, b_pid, b_hot, b_dev = check_backend_alive(BACKEND_PORT)
        if b_alive:
            print(f"[Backend ]  ● 已在运行  http://127.0.0.1:{BACKEND_PORT}  PID:{b_pid}")
            print(f"[Frontend]  ● 已托管    http://127.0.0.1:{BACKEND_PORT}/app")
            print("💡 后端支持热重载，无需重启")
            self.backend_pid = b_pid
            print("-" * 50)
            print("✅ 所有服务已就绪，按 Ctrl+C 关闭所有服务")
            return

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

    def shutdown(self, *_):
        """处理 Ctrl+C：清理所有 Polaris 服务"""
        if self.should_exit:
            return
        self.should_exit = True

        try:
            print("\n\n🛑 正在关闭 Polaris...")
        except UnicodeEncodeError:
            print("\n\n[Stop] 正在关闭 Polaris...")

        # 清理后端
        is_occupied, pid = check_port_occupied(BACKEND_PORT)
        if is_occupied and pid:
            # 验证是否是 Polaris 后端
            b_alive, b_pid, _, _ = check_backend_alive(BACKEND_PORT)
            if b_alive:
                print(f"[Backend ]  正在关闭 (PID: {pid})...")
                kill_process(pid)
            else:
                print(f"[Backend ]  端口 {BACKEND_PORT} 被占用，但不是 Polaris 服务，跳过")

        # 清理前端（仅开发模式）
        if self.dev_mode:
            is_occupied, pid = check_port_occupied(FRONTEND_PORT)
            if is_occupied and pid:
                # 验证是否是 Polaris 前端
                f_alive, f_pid, _ = check_frontend_alive(FRONTEND_PORT)
                if f_alive:
                    print(f"[Frontend]  正在关闭 (PID: {pid})...")
                    kill_process(pid)
                else:
                    print(f"[Frontend]  端口 {FRONTEND_PORT} 被占用，但不是 Polaris 服务，跳过")

        # 重置终端状态（防止终端污染）
        self._reset_terminal()

        print("✅ 所有服务已清理完毕")
        sys.exit(0)

    def _reset_terminal(self):
        """重置终端状态，防止被子进程污染"""
        import os
        import subprocess

        if sys.platform == 'win32':
            # Windows: 重置控制台模式
            try:
                # 使用 PowerShell 重置控制台
                subprocess.run(['powershell', '-Command', '[Console]::ResetColor()'],
                             capture_output=True, timeout=1)
            except:
                pass
        else:
            # Unix/Linux/Mac: 使用 stty 和 reset
            try:
                # 恢复终端设置
                subprocess.run(['stty', 'sane'], timeout=1)
                # 或者使用 reset 命令（更彻底但可能清屏）
                # subprocess.run(['reset'], timeout=1)
            except:
                pass

        # 通用方法：重置 ANSI 转义序列
        try:
            # 重置颜色和样式
            sys.stdout.write('\033[0m')
            # 显示光标
            sys.stdout.write('\033[?25h')
            # 刷新输出
            sys.stdout.flush()
        except:
            pass

    def run(self):
        """主入口：启动服务并等待退出信号"""
        # 注册退出信号
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        # 启动服务
        if self.dev_mode:
            self.start_dev_mode()
        else:
            self.start_prod_mode()

        # 主线程等待退出信号
        try:
            while not self.should_exit:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()


def clean():
    """清理所有 Polaris 服务（验证后再 kill）"""
    try:
        print("🛑 正在清理 Polaris 所有服务...")
    except UnicodeEncodeError:
        print("[Stop] 正在清理 Polaris 所有服务...")

    # 清理后端
    is_occupied, pid = check_port_occupied(BACKEND_PORT)
    if is_occupied and pid:
        b_alive, b_pid, _, _ = check_backend_alive(BACKEND_PORT)
        if b_alive:
            print(f"[Backend ]  正在关闭 (PID: {pid})...")
            kill_process(pid)
        else:
            print(f"[Backend ]  端口 {BACKEND_PORT} 被占用，但不是 Polaris 服务，跳过")
    else:
        print(f"[Backend ]  端口 {BACKEND_PORT} 未被占用")

    # 清理前端
    is_occupied, pid = check_port_occupied(FRONTEND_PORT)
    if is_occupied and pid:
        f_alive, f_pid, _ = check_frontend_alive(FRONTEND_PORT)
        if f_alive:
            print(f"[Frontend]  正在关闭 (PID: {pid})...")
            kill_process(pid)
        else:
            print(f"[Frontend]  端口 {FRONTEND_PORT} 被占用，但不是 Polaris 服务，跳过")
    else:
        print(f"[Frontend]  端口 {FRONTEND_PORT} 未被占用")

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
