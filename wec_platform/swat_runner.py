"""
swat_runner.py — SWAT 可执行文件调用（无 Qt 依赖）
====================================================

提供一个纯 subprocess 的 SWAT 运行函数，供 CLI 或脚本使用；
图形界面中的实时进度版本见 ui/state.py 的 SwatWorker（基于 QThread）。
"""
from __future__ import annotations

import os
import subprocess
from typing import Callable, Optional


def run_swat(exe_path: str, cwd: str,
             log_cb: Optional[Callable[[str], None]] = None) -> int:
    """在 cwd（通常是 TxtInOut）下运行 SWAT 可执行文件，返回退出码。

    log_cb 不为空时逐行回传 stdout。
    """
    if not exe_path or not os.path.isfile(exe_path):
        raise FileNotFoundError(f"未找到 SWAT 可执行文件: {exe_path}")
    if log_cb:
        log_cb(f"启动 SWAT: {exe_path}\n工作目录: {cwd}\n")

    proc = subprocess.Popen(
        [exe_path], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in proc.stdout:
        if log_cb:
            log_cb(line.rstrip())
    proc.wait()
    return proc.returncode
