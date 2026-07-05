
# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

TIANJI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TIANJI_ROOT))

# 脚本式手动验证文件：pytest 收集时跳过，避免在 import 阶段执行完整 autopilot 周期
if __name__ != "__main__":
    import pytest
    pytest.skip("script-style manual verification; run directly with python", allow_module_level=True)

print("=" * 60)
print("  Tianji Autopilot v3.0 Verification")
print("=" * 60)

try:
    from daemon.tianji_daemon import TianjiAutopilot
    print("\n[1] Import TianjiAutopilot: OK")

    ap = TianjiAutopilot()
    print("[2] Initialize TianjiAutopilot: OK")

    total = len(ap.TASK_CONFIGS)
    intelli = len(ap.TASK_CONFIGS_BASE)
    module = len(ap._UNCOVERED_MODULES)
    daemon = len(ap._DAEMON_TASKS)

    print(f"\n[3] Task Configuration:")
    print(f"    - Total: {total}")
    print(f"    - Intelligent: {intelli}")
    print(f"    - Module Patrol: {module}")
    print(f"    - Daemon Tasks: {daemon}")

    expected = intelli + module + daemon
    if total >= expected:
        print(f"    OK: Task config complete")
    else:
        print(f"    WARNING: Task config incomplete")

    print(f"\n[4] Running first cycle...")
    for k in ap._last_run:
        ap._last_run[k] = 0.0
    for k in ap._adaptive_intervals:
        ap._adaptive_intervals[k] = 1

    results = ap.run_cycle()

    ok_count = sum(1 for v in results.values() if isinstance(v, dict) and "error" not in str(v))
    err_count = sum(1 for v in results.values() if isinstance(v, dict) and "error" in str(v))

    print(f"\n[5] Execution Results:")
    print(f"    - Tasks Run: {len(results)}")
    print(f"    - Success: {ok_count}")
    print(f"    - Failed: {err_count}")

    print(f"\n[6] Detailed Results (first 20):")
    i = 0
    for task_name, result in sorted(results.items()):
        if i >= 20:
            break
        status = "OK" if isinstance(result, dict) and "error" not in str(result) else "ERR"
        detail = ""
        if isinstance(result, dict):
            if "module" in result:
                detail = f"active={result.get('active', '?')}, healthy={result.get('healthy', '?')}"
            elif "daemon" in result:
                detail = f"healthy={result.get('healthy', '?')}"
            elif "error" in result:
                detail = str(result["error"])[:50]
        print(f"    [{status}] {task_name}: {detail or result}")
        i += 1

    if len(results) > 20:
        print(f"    ... {len(results) - 20} more tasks")

    print(f"\n[7] Statistics:")
    stats = ap.get_stats()
    for key, value in sorted(stats.items()):
        if value and value != 0 and value != [] and value != {}:
            print(f"    - {key}: {value}")

    print(f"\n[8] Final Status:")
    status = ap.get_status()
    print(f"    - Cycles: {status['cycle_count']}")
    print(f"    - Load: {status['system_load']}")
    print(f"    - Modules Initialized: {status['modules_initialized']}")
    print(f"    - Total Tasks: {status['total_tasks']}")

    print("\n" + "=" * 60)
    if err_count == 0:
        print("  VERIFICATION SUCCESS: All features working")
    else:
        print(f"  VERIFICATION COMPLETE: {err_count} tasks failed")
    print("=" * 60)

except Exception as e:
    print(f"\nVERIFICATION FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
