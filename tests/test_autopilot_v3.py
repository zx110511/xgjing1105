
# -*- coding: utf-8 -*-
"""
天机 Autopilot v3.0 快速验证脚本
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
TIANJI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TIANJI_ROOT))

# 脚本式手动验证文件：pytest 收集时跳过，避免在 import 阶段执行完整 autopilot 周期
if __name__ != "__main__":
    import pytest
    pytest.skip("script-style manual verification; run directly with python", allow_module_level=True)

print("=" * 60)
print("  天机 Autopilot v3.0 功能验证")
print("=" * 60)

try:
    from daemon.tianji_daemon import TianjiAutopilot
    print("\n[1] 导入 TianjiAutopilot: 成功")

    ap = TianjiAutopilot()
    print("[2] 初始化 TianjiAutopilot: 成功")

    total_tasks = len(ap.TASK_CONFIGS)
    intelli_tasks = len(ap.TASK_CONFIGS_BASE)
    module_tasks = len(ap._UNCOVERED_MODULES)
    daemon_tasks = len(ap._DAEMON_TASKS)

    print(f"\n[3] 任务配置检查:")
    print(f"    - 总任务数: {total_tasks}")
    print(f"    - 智能任务: {intelli_tasks}")
    print(f"    - 模块巡检: {module_tasks}")
    print(f"    - 守护任务: {daemon_tasks}")

    expected_total = intelli_tasks + module_tasks + daemon_tasks
    if total_tasks >= expected_total:
        print(f"    ✓ 任务配置完整")
    else:
        print(f"    ✗ 任务配置不完整")

    print(f"\n[4] 运行第1个周期...")
    for k in ap._last_run:
        ap._last_run[k] = 0.0
    for k in ap._adaptive_intervals:
        ap._adaptive_intervals[k] = 1

    results = ap.run_cycle()

    ok_count = sum(1 for v in results.values() if isinstance(v, dict) and "error" not in str(v))
    err_count = sum(1 for v in results.values() if isinstance(v, dict) and "error" in str(v))

    print(f"\n[5] 执行结果:")
    print(f"    - 执行任务: {len(results)}")
    print(f"    - 成功: {ok_count}")
    print(f"    - 失败: {err_count}")

    print(f"\n[6] 详细结果:")
    for task_name, result in sorted(results.items())[:20]:
        status = "✓" if isinstance(result, dict) and "error" not in str(result) else "✗"
        detail = ""
        if isinstance(result, dict):
            if "module" in result:
                detail = f"active={result.get('active', '?')}, healthy={result.get('healthy', '?')}"
            elif "daemon" in result:
                detail = f"healthy={result.get('healthy', '?')}"
            elif "error" in result:
                detail = str(result["error"])[:50]
        print(f"    {status} {task_name}: {detail or result}")

    if len(results) > 20:
        print(f"    ... 还有 {len(results) - 20} 个任务")

    print(f"\n[7] 统计信息:")
    stats = ap.get_stats()
    for key, value in sorted(stats.items()):
        if value and value != 0 and value != [] and value != {}:
            print(f"    - {key}: {value}")

    print(f"\n[8] 最终状态:")
    status = ap.get_status()
    print(f"    - 周期数: {status['cycle_count']}")
    print(f"    - 系统负载: {status['system_load']}")
    print(f"    - 模块初始化: {status['modules_initialized']}")
    print(f"    - 总任务数: {status['total_tasks']}")

    print("\n" + "=" * 60)
    if err_count == 0:
        print("  ✓ 验证完成: 全部功能正常")
    else:
        print(f"  ⚠ 验证完成: 有 {err_count} 个任务失败")
    print("=" * 60)

except Exception as e:
    print(f"\n✗ 验证失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
