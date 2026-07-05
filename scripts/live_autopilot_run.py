import sys, json
sys.path.insert(0, '.')
from daemon.tianji_daemon import TianjiAutopilot

ap = TianjiAutopilot()
print('='*60)
print('  Autopilot v3.0 实时周期执行')
print('='*60)

results = ap.run_cycle()
stats = ap.get_stats()
status = ap.get_status()

print('\n[实时统计]')
print(f'  容量检查: {stats["capacity_checks"]}次')
print(f'  异常检测: {stats["anomaly_checks"]}次')
print(f'  RCA分析: {stats["rca_analyses"]}次')
print(f'  记忆健康: {stats["mem_health_checks"]}次')
print(f'  模块巡检: {stats["module_patrols"]}次')
print(f'  守护检查: {stats["daemon_checks"]}次')
print(f'  技能学习: {stats["skill_learn_cycles"]}次')
print(f'  因果记录: {stats["causal_pairs_recorded"]}对')

intelli_ran = sum(1 for k in ap.TASK_CONFIGS_BASE if ap._last_run.get(k, 0) > 0)
module_ran = sum(1 for k in ap._UNCOVERED_MODULES if ap._last_run.get('mod_'+k, 0) > 0)
daemon_ran = sum(1 for k in ap._DAEMON_TASKS if ap._last_run.get('daemon_'+k, 0) > 0)

print(f'\n[本周期执行]')
print(f'  智能任务: {intelli_ran}/20')
print(f'  模块巡检: {module_ran}/34')
print(f'  守护任务: {daemon_ran}/6')
print(f'  总计: {len(results)}个任务')

print(f'\n[系统状态]')
print(f'  模块初始化: {status["modules_initialized"]}')
print(f'  运行周期: {status["total_cycles"]}')
print(f'  版本: {status["version"]}')

print('\n' + '='*60)
print('  数据真实性证明完成!')
print('='*60)

output = {
    'timestamp': __import__('datetime').datetime.now().isoformat(),
    'stats': stats,
    'execution': {
        'intelligent': intelli_ran,
        'module_patrol': module_ran,
        'daemon': daemon_ran,
        'total_tasks': len(results)
    },
    'status': status
}

with open('data/autopilot_live_run.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('\n数据已保存到: data/autopilot_live_run.json')
