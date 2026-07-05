# -*- coding: utf-8-sig -*-
"""天机v9.1 启动包装器 — 确保UTF-8编码在所有模块import之前生效"""
import sys
import os
import io

# ===== P0: 最早期UTF-8强制 (在任何import之前) =====
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    
    # 直接替换标准流
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, 
            encoding="utf-8", 
            errors="replace",
            line_buffering=True
        )
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True
        )
    if hasattr(sys.stdin, "buffer"):
        sys.stdin = io.TextIOWrapper(
            sys.stdin.buffer,
            encoding="utf-8",
            errors="replace"
        )

# ===== 然后才导入uvicorn =====
import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8771)
