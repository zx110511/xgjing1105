# -*- coding: utf-8-sig -*-
"""测试启动器启动（前台运行，观察详细输出）"""

import os
import sys

sys.path.insert(0, r"d:\元初系统\天机v9.1")

os.environ["EMBEDDING_ENGINE"] = "tfidf"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["PYTHONUTF8"] = "1"
os.environ["TIANJI_V91_PROTOCOL_MODE"] = "true"
os.environ["TIANJI_V91_EVENT_WIRING"] = "true"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["AI_MEMORY_ROOT"] = r"d:\元初系统\天机v9.1"
os.environ["AI_MEMORY_PORT"] = "8771"
os.environ["PYTHONPATH"] = r"d:\元初系统\天机v9.1"

from launcher.tianji_v91_launcher import TianjiLauncher

launcher = TianjiLauncher(port=8771)

print("正在启动...")
success = launcher.start(daemon=False, quick_start=True)
print(f"启动结果: {success}")

if success:
    import time

    print("\n服务运行中，按 Ctrl+C 停止...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
        launcher.stop()
        print("已停止")
