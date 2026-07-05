
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 脚本式手动验证文件：pytest 收集时跳过，避免在 import 阶段执行完整 autopilot 周期
if __name__ != "__main__":
    import pytest
    pytest.skip("script-style manual verification; run directly with python", allow_module_level=True)

from daemon.tianji_daemon import TianjiAutopilot

print("=" * 60)
print("  天机 Autopilot v3.0 全面验证")
print("=" * 60)

# 初始化Autopilot
ap = TianjiAutopilot()
print(f"\n✅ 任务总数: {len(ap.TASK_CONFIGS)}")
print(f"  - 智能任务: {len(ap.TASK_CONFIGS_BASE)}")
print(f"  - 模块巡检: {len(ap._UNCOVERED_MODULES)}")
print(f"  - 守护任务: {len(ap._DAEMON_TASKS)}")

# 运行第一个周期
print("\n" + "=" * 60)
print("  运行第 1 个周期")
print("=" * 60)
for k in ap._last_run:
    ap._last_run[k] = 0.0
for k in ap._adaptive_intervals:
    ap._adaptive_intervals[k] = 1

results = ap.run_cycle()

# 统计结果
ok_count = sum(1 for v in results.values() if isinstance(v, dict) and 'error' not in str(v))
err_count = sum(1 for v in results.values() if isinstance(v, dict) and 'error' in str(v))

print(f"\n📊 执行统计:")
print(f"  - 已执行任务: {len(results)}")
print(f"  - 成功: {ok_count}")
print(f"  - 失败: {err_count}")

# 显示详细结果
print("\n📋 任务详情:")
for task_name, task_result in sorted(results.items()):
    status = "✅ OK" if isinstance(task_result, dict) and 'error' not in str(task_result) else "❌ ERR"
    detail = ""
    if isinstance(task_result, dict):
        if 'module' in task_result:
            detail = f"active={task_result.get('governance_active', '?')}, healthy={task_result.get('healthy', '?')}"
        elif 'daemon' in task_result:
            detail = f"healthy={task_result.get('healthy', '?')}"
        elif 'error' in task_result:
            detail = str(task_result['error'])[:80]
    print(f"  {status} {task_name}: {detail or task_result}")

# 显示最终状态
print("\n" + "=" * 60)
print("  最终状态")
print("=" * 60)
status = ap.get_status()
print(f"\n📈 统计信息:")
print(f"  总任务数: {status['total_tasks']}")
print(f"  智能任务: {status['intelligent_tasks']}")
print(f"  模块巡检: {status['module_patrol_tasks']}")
print(f"  守护任务: {status['daemon_tasks']}")
print(f"  模块初始化: {status['modules_initialized']}")

stats = status['stats']
print(f"\n📊 执行统计:")
for k, v in sorted(stats.items()):
    if v and v != 0 and v != [] and v != {}:
        print(f"  {k}: {v}")

print("\n" + "=" * 60)
print("  验证完成")
print("=" * 60)
