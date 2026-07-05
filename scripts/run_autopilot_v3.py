import sys, time, json
sys.path.insert(0, '.')

from daemon.tianji_daemon import TianjiAutopilot

ap = TianjiAutopilot()
print(f'Total tasks: {len(ap.TASK_CONFIGS)}')
print(f'  Intelligent: {len(ap.TASK_CONFIGS_BASE)}')
print(f'  Module patrol: {len(ap._UNCOVERED_MODULES)}')
print(f'  Daemon: {len(ap._DAEMON_TASKS)}')
print()

for cycle in range(1, 3):
    print(f'===== AUTOPILOT v3.0 CYCLE {cycle} =====')
    for k in ap._last_run:
        ap._last_run[k] = 0.0
    for k in ap._adaptive_intervals:
        ap._adaptive_intervals[k] = 1

    results = ap.run_cycle()
    ok_count = sum(1 for v in results.values() if isinstance(v, dict) and 'error' not in str(v))
    err_count = sum(1 for v in results.values() if isinstance(v, dict) and 'error' in str(v))
    print(f'  Tasks run: {len(results)}, OK: {ok_count}, ERR: {err_count}')

    for task_name, task_result in sorted(results.items()):
        status = 'OK' if isinstance(task_result, dict) and 'error' not in str(task_result) else 'ERR'
        detail = ''
        if isinstance(task_result, dict):
            if 'module' in task_result:
                detail = f"active={task_result.get('governance_active', '?')}"
            elif 'daemon' in task_result:
                detail = f"healthy={task_result.get('healthy', '?')}"
            elif 'error' in task_result:
                detail = str(task_result['error'])[:60]
        print(f'  [{status}] {task_name}: {detail or task_result}')
    time.sleep(0.3)

print()
print('=' * 60)
print('  AUTOPILOT v3.0 FINAL STATUS')
print('=' * 60)
status = ap.get_status()
print(f'  total_tasks: {status["total_tasks"]}')
print(f'  intelligent_tasks: {status["intelligent_tasks"]}')
print(f'  module_patrol_tasks: {status["module_patrol_tasks"]}')
print(f'  daemon_tasks: {status["daemon_tasks"]}')
print(f'  modules_initialized: {status["modules_initialized"]}')

stats = status['stats']
for k, v in sorted(stats.items()):
    if v and v != 0 and v != [] and v != {}:
        print(f'  {k}: {v}')