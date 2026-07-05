import requests
import json

base = 'http://127.0.0.1:8771'

print("=" * 70)
print("SSS级天机v9.1 46模块绝对真实审计报告")
print("=" * 70)

print("\n[1] 健康检查")
try:
    r = requests.get(f'{base}/api/health', timeout=5)
    h = r.json()
    print(f"  状态: {h.get('status')}")
    print(f"  版本: {h.get('version')}")
    print(f"  引擎就绪: {h.get('engine_ready')}")
    print(f"  嵌入就绪: {h.get('embedding_ready')}")
    layers = h.get('layers', {})
    for name, info in layers.items():
        print(f"  层 {name}: {info.get('entry_count', 0)} 条")
except Exception as e:
    print(f"  错误: {e}")

print("\n[2] 记忆统计")
try:
    r = requests.get(f'{base}/api/memory/stats', timeout=5)
    s = r.json()
    print(f"  总条目: {s.get('total_entries', 0)}")
    print(f"  总访问: {s.get('total_accesses', 0)}")
    print(f"  运行时间: {s.get('uptime_seconds', 0):.0f}s")
    print(f"  存储后端: {s.get('storage_backend', 'unknown')}")
    print(f"  DB大小: {s.get('db_size_mb', 0):.2f}MB")
except Exception as e:
    print(f"  错误: {e}")

print("\n[3] 容器模块状态")
try:
    r = requests.get(f'{base}/api/system/stats', timeout=10)
    d = r.json()
    mods = d.get('modules', {})
    coverage = d.get('coverage', {})
    print(f"  总模块: {coverage.get('total', 0)}")
    print(f"  在线: {coverage.get('online', 0)}")
    print(f"  有统计: {coverage.get('with_stats', 0)}")

    daemon_with_data = []
    daemon_no_data = []
    core_with_data = []
    core_no_data = []

    for name, info in sorted(mods.items()):
        rt_keys = [k for k in info.keys() if k not in ('status', 'last_update')]
        has_real_data = any(k not in ('state',) for k in rt_keys)
        if name in ('skill_pipeline', 'agent_scheduler',
                     'tvp_bridge', 'evolution_loop', 'auto_capture', 'backup_manager',
                     'daemon_watchdog', 'daemon_autobackup', 'daemon_autorepair',
                     'daemon_integrity', 'agent_build', 'agent_test', 'agent_recovery',
                     'agent_pipeline_logger', 'agent_orchestrator', 'agent_runtime_recovery'):
            if has_real_data:
                daemon_with_data.append(name)
            else:
                daemon_no_data.append(name)
        else:
            if has_real_data:
                core_with_data.append(name)
            else:
                core_no_data.append(name)

    print(f"\n  Daemon模块有数据({len(daemon_with_data)}): {daemon_with_data}")
    print(f"  Daemon模块无数据({len(daemon_no_data)}): {daemon_no_data}")
    print(f"  核心模块有数据({len(core_with_data)}): {core_with_data}")
    print(f"  核心模块无数据({len(core_no_data)}): {core_no_data}")
except Exception as e:
    print(f"  错误: {e}")

print("\n[4] EvolutionBus验证")
try:
    r = requests.get(f'{base}/api/system/stats', timeout=10)
    d = r.json()
    evo_bus = d.get('modules', {}).get('evolution_bus', {})
    print(f"  状态: {evo_bus.get('status')}")
    print(f"  数据: {json.dumps(evo_bus, indent=2, ensure_ascii=False)}")
except Exception as e:
    print(f"  错误: {e}")

print("\n[5] 记忆CRUD闭环验证")
try:
    r = requests.post(f'{base}/api/memory', json={
        'content': 'SSS审计测试记忆条目 - EvolutionBus修复验证',
        'layer': 'working',
        'tags': ['sss_audit', 'evolution_bus_fix', 'test'],
        'priority': 'medium'
    }, timeout=10)
    create_result = r.json()
    mem_id = create_result.get('id', 'unknown')
    print(f"  Create: id={mem_id}, status={r.status_code}")

    r = requests.get(f'{base}/api/memory/search?query=EvolutionBus修复验证&limit=5', timeout=10)
    search_result = r.json()
    found = len(search_result) if isinstance(search_result, list) else search_result.get('total', 0)
    print(f"  Search: 找到{found}条相关记忆")

    r = requests.delete(f'{base}/api/memory/{mem_id}', timeout=10)
    print(f"  Delete: status={r.status_code}")
except Exception as e:
    print(f"  错误: {e}")

print("\n[6] MCP工具验证")
try:
    r = requests.get(f'{base}/api/mcp/health', timeout=5)
    print(f"  MCP健康: status={r.status_code}")
except Exception as e:
    print(f"  MCP健康检查: {e}")

print("\n[7] DeepSeek LLM验证")
try:
    r = requests.post(f'{base}/api/llm/classify', json={
        'content': 'EvolutionBus修复验证 - 这条记忆应该存储在哪一层？'
    }, timeout=15)
    result = r.json()
    print(f"  分类结果: layer={result.get('recommended_layer')}, confidence={result.get('confidence')}")
except Exception as e:
    print(f"  LLM分类: {e}")

print("\n" + "=" * 70)
print("审计完成")
print("=" * 70)
