# -*- coding: utf-8-sig -*-
"""天机v9.1 全局UTF-8编码修复 — Python进程最早加载

Python启动时自动import此文件 (优先级高于所有用户代码),
确保stdout/stderr在第一条print之前就是UTF-8。

放置位置: 项目根目录 (sys.path[0])
激活方式: python -S sitecustomize.py 或自动检测
"""
import sys
import io

if sys.platform == "win32":
    # 强制标准流为UTF-8
    _orig_stdout = sys.stdout
    _orig_stderr = sys.stderr
    _orig_stdin = sys.stdin

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stdin, "reconfigure"):
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # 低版本兼容: 替换底层流
    if sys.version_info < (3, 7):
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )

    # 确保默认编码也是UTF-8
    if hasattr(sys, "setdefaultencoding"):
        try:
            sys.setdefaultencoding("utf-8")
        except Exception:
            pass
