"""
系统文件选择器

提供原生的文件/文件夹选择对话框
"""
from fastapi import APIRouter, HTTPException
import sys
import subprocess
import threading

router = APIRouter(prefix="/api/system", tags=["system"])

# 用于存储选择结果的全局变量
_selected_path = None
_selection_done = threading.Event()


def _open_folder_dialog_windows():
    """Windows 原生文件夹选择对话框"""
    global _selected_path
    try:
        # 使用 PowerShell 调用 Windows Forms 的 FolderBrowserDialog
        ps_script = """
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "选择模型文件夹"
$dialog.ShowNewFolderButton = $false
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
"""
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0 and result.stdout.strip():
            _selected_path = result.stdout.strip()
        else:
            _selected_path = None

    except Exception as e:
        print(f"打开文件夹选择器失败: {e}")
        _selected_path = None
    finally:
        _selection_done.set()


def _open_folder_dialog_linux():
    """Linux 原生文件夹选择对话框（使用 zenity）"""
    global _selected_path
    try:
        result = subprocess.run(
            ["zenity", "--file-selection", "--directory", "--title=选择模型文件夹"],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0 and result.stdout.strip():
            _selected_path = result.stdout.strip()
        else:
            _selected_path = None

    except FileNotFoundError:
        print("zenity 未安装，请安装: sudo apt-get install zenity")
        _selected_path = None
    except Exception as e:
        print(f"打开文件夹选择器失败: {e}")
        _selected_path = None
    finally:
        _selection_done.set()


def _open_folder_dialog_mac():
    """macOS 原生文件夹选择对话框（使用 osascript）"""
    global _selected_path
    try:
        result = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose folder with prompt "选择模型文件夹")'],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0 and result.stdout.strip():
            _selected_path = result.stdout.strip()
        else:
            _selected_path = None

    except Exception as e:
        print(f"打开文件夹选择器失败: {e}")
        _selected_path = None
    finally:
        _selection_done.set()


@router.post("/select-folder")
async def select_folder():
    """
    打开系统文件夹选择对话框

    Returns:
        {
            "path": "C:/Users/.../folder",
            "canceled": false
        }
    """
    global _selected_path, _selection_done

    try:
        _selected_path = None
        _selection_done.clear()

        # 根据操作系统选择对应的实现
        if sys.platform == "win32":
            thread = threading.Thread(target=_open_folder_dialog_windows)
        elif sys.platform == "darwin":
            thread = threading.Thread(target=_open_folder_dialog_mac)
        else:  # Linux
            thread = threading.Thread(target=_open_folder_dialog_linux)

        thread.start()
        thread.join(timeout=300)  # 最多等待5分钟

        if not _selection_done.is_set():
            raise HTTPException(status_code=408, detail="选择超时")

        return {
            "path": _selected_path or "",
            "canceled": _selected_path is None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开文件选择器失败: {str(e)}")

