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
    check_backend_alive, check_frontend_alive,
    check_port_occupied, kill_process,
    write_lock, read_lock, clear_lock, is_process_running,
    write_restart_signal, check_restart_signal
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

        # 写入锁文件，记录当前运行状态（供 --clean 和下次启动读取）
        # 写入失败不影响服务运行，仅丢失封像能力
        try:
            write_lock(
                backend_pid=self.backend_pid,
                backend_port=BACKEND_PORT,
                frontend_pid=self.frontend_pid,
                frontend_port=FRONTEND_PORT,
            )
        except Exception as e:
            print(f"[Warn] 锁文件写入失败（不影响服务）: {e}")

    def start_prod_mode(self):
        """生产模式：构建前端并启动后端（后端托管静态文件）"""
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
            write_lock(backend_pid=self.backend_pid, backend_port=BACKEND_PORT)
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
        write_lock(backend_pid=self.backend_pid, backend_port=BACKEND_PORT)

    def shutdown(self, *_):
        """处理 Ctrl+C：清理所有 Polaris 服务"""
        if self.should_exit:
            return
        self.should_exit = True

        try:
            print("\n\n🛑 正在关闭 Polaris...")
        except UnicodeEncodeError:
            print("\n\n[Stop] 正在关闭 Polaris...")

        # 清理后端 —— 先用记录的 PID kill，再扫端口清理残留 worker
        if self.backend_pid:
            print(f"[Backend ]  正在关闭 (PID: {self.backend_pid})...")
            kill_process(self.backend_pid)
        # 等待进程退出，再扫端口清理残留（uvicorn reload 模式在 Windows 上
        # 会用 multiprocessing.spawn 创建独立 worker，kill 父进程后 worker 可能残留）
        time.sleep(1.5)
        is_occupied, pid = check_port_occupied(BACKEND_PORT)
        if is_occupied and pid and pid != self.backend_pid:
            kill_process(pid)

        # 清理前端（仅开发模式）—— 同样先用 PID，再扫端口
        if self.dev_mode:
            if self.frontend_pid:
                print(f"[Frontend]  正在关闭 (PID: {self.frontend_pid})...")
                kill_process(self.frontend_pid)
            time.sleep(1)
            is_occupied, pid = check_port_occupied(FRONTEND_PORT)
            if is_occupied and pid and pid != self.frontend_pid:
                kill_process(pid)

        # 删除锁文件
        clear_lock()

        # 重置终端状态（防止终端污染）
        self._reset_terminal()

        print("✅ 所有服务已清理完毕")
        sys.exit(0)

    def _reset_terminal(self):
        """重置终端状态，防止被子进程污染"""
        import os
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

    def _kill_services(self):
        """停止当前运行的后端和前端子进程（用于重启前清场）"""
        if self.backend_pid:
            kill_process(self.backend_pid)
        time.sleep(1.5)
        is_occupied, pid = check_port_occupied(BACKEND_PORT)
        if is_occupied and pid and pid != self.backend_pid:
            kill_process(pid)

        if self.dev_mode and self.frontend_pid:
            kill_process(self.frontend_pid)
            time.sleep(1)
            is_occupied, pid = check_port_occupied(FRONTEND_PORT)
            if is_occupied and pid and pid != self.frontend_pid:
                kill_process(pid)

        clear_lock()

    def run(self):
        """主入口：启动服务并等待退出信号或重启信号"""
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        if self.dev_mode:
            self.start_dev_mode()
        else:
            self.start_prod_mode()

        try:
            while not self.should_exit:
                time.sleep(1)
                # 检测重启信号文件（由 /api/restart 写入）
                if check_restart_signal():
                    print("\n\n🔄 检测到重启信号，正在重启服务...")
                    self._kill_services()
                    # 用 os.execv 替换自身进程 —— 自动重读 config.json 获取新端口
                    os.execv(sys.executable, [sys.executable] + sys.argv)
        except KeyboardInterrupt:
            self.shutdown()


def clean():
    """清理所有 Polaris 服务——优先读锁文件精准 kill，安全兜底扫端口"""
    try:
        print("🛑 正在清理 Polaris 所有服务...")
    except UnicodeEncodeError:
        print("[Stop] 正在清理 Polaris 所有服务...")

    lock = read_lock()
    b_pid   = lock.get("backend_pid")
    b_port  = lock.get("backend_port", BACKEND_PORT)
    f_pid   = lock.get("frontend_pid")
    f_port  = lock.get("frontend_port", FRONTEND_PORT)

    # ── 清理后端 ──
    if b_pid and is_process_running(b_pid):
        print(f"[Backend ]  正在关闭 (PID: {b_pid}, 来自锁文件)...")
        kill_process(b_pid)
        time.sleep(1.5)

    # 扫端口兜底（清理 uvicorn worker 残留）
    is_occupied, pid = check_port_occupied(b_port)
    if is_occupied and pid and pid != b_pid:
        # 锁文件 PID 仍在运行时：这是 uvicorn worker 残留，直接杀
        # 锁文件 PID 已死时：必须健康检查确认是 Polaris 才 kill，防止误杀无关进程
        if b_pid and is_process_running(b_pid):
            print(f"[Backend ]  清理残留 worker (PID: {pid})...")
            kill_process(pid)
        else:
            b_alive, _, _, _ = check_backend_alive(b_port)
            if b_alive:
                print(f"[Backend ]  清理 Polaris 进程 (PID: {pid})...")
                kill_process(pid)
            else:
                print(f"[Backend ]  端口 {b_port} 被占用，但不是 Polaris 服务，跳过")
    elif not b_pid:
        # 锁文件不存在时，回退到健康检查
        is_occupied, pid = check_port_occupied(b_port)
        if is_occupied and pid:
            b_alive, _, _, _ = check_backend_alive(b_port)
            if b_alive:
                print(f"[Backend ]  正在关闭 (PID: {pid})...")
                kill_process(pid)
            else:
                print(f"[Backend ]  端口 {b_port} 被占用，但不是 Polaris 服务，跳过")
        else:
            print(f"[Backend ]  端口 {b_port} 未被占用")

    # ── 清理前端 ──
    if f_pid and is_process_running(f_pid):
        print(f"[Frontend]  正在关闭 (PID: {f_pid}, 来自锁文件)...")
        kill_process(f_pid)
        time.sleep(1)

    is_occupied, pid = check_port_occupied(f_port)
    if is_occupied and pid and pid != f_pid:
        if f_pid and is_process_running(f_pid):
            print(f"[Frontend]  清理残留进程 (PID: {pid})...")
            kill_process(pid)
        else:
            f_alive, _, _ = check_frontend_alive(f_port)
            if f_alive:
                print(f"[Frontend]  清理 Polaris 进程 (PID: {pid})...")
                kill_process(pid)
            else:
                print(f"[Frontend]  端口 {f_port} 被占用，但不是 Polaris 服务，跳过")
    elif not f_pid:
        is_occupied, pid = check_port_occupied(f_port)
        if is_occupied and pid:
            f_alive, _, _ = check_frontend_alive(f_port)
            if f_alive:
                print(f"[Frontend]  正在关闭 (PID: {pid})...")
                kill_process(pid)
            else:
                print(f"[Frontend]  端口 {f_port} 被占用，但不是 Polaris 服务，跳过")
        else:
            print(f"[Frontend]  端口 {f_port} 未被占用")

    # 删除锁文件
    clear_lock()
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
