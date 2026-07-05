import requests
import json
import time

base = 'http://127.0.0.1:8771'

print("=" * 70)
print("天机v9.1 强化验证报告 — P1三项修复验证")
print("=" * 70)

print("\n[1] /api/operations/header — TVP/MCP/Memory操作痕迹头部")
try:
    r = requests.get(f'{base}/api/operations/header', timeout=5)
    d = r.json()
    print(f"  Status: {r.status_code}")
    print(f"  Header: {d.get('header', '(empty)')}")
    print(f"  Recent count: {d.get('recent_count', 0)}")
    print(f"  Categories: {d.get('categories', [])}")
except Exception as e:
    print(f"  Error: {e}")

print("\n[2] /api/operations/summary — 操作统计")
try:
    r = requests.get(f'{base}/api/operations/summary', timeout=5)
    d = r.json()
    print(f"  Total operations: {d.get('total_operations', 0)}")
    by_cat = d.get('by_category', {})
    for cat, info in by_cat.items():
        print(f"  {cat}: {info.get('count', 0)} ({info.get('label', cat)})")
except Exception as e:
    print(f"  Error: {e}")

print("\n[3] 46模块realtime数据覆盖率 — _UNSAFE黑名单验证")
try:
    r = requests.get(f'{base}/api/system/stats', timeout=10)
    d = r.json()
    mods = d.get('modules', {})
    total = len(mods)
    with_data = 0
    without_data = []
    for name, info in sorted(mods.items()):
        rt_keys = [k for k in info.keys() if k not in ('status', 'last_update')]
        has_real = any(k not in ('state',) for k in rt_keys)
        if has_real:
            with_data += 1
        else:
            without_data.append(name)
    print(f"  Total: {total}, With data: {with_data}, Without: {len(without_data)}")
    if without_data:
        print(f"  No-data modules: {without_data}")
    coverage_pct = with_data / total * 100 if total > 0 else 0
    print(f"  Coverage: {coverage_pct:.1f}%")
except Exception as e:
    print(f"  Error: {e}")

print("\n[4] DeepSeek LLM分类API — confidence字段验证")
try:
    r = requests.post(f'{base}/api/llm/classify', json={
        'content': '天机EvolutionBus修复完成，7个模块成功注册到进化信号总线，系统自进化闭环已建立'
    }, timeout=15)
    d = r.json()
    print(f"  Status: {r.status_code}")
    print(f"  Layer: {d.get('layer', 'N/A')}")
    print(f"  Confidence: {d.get('confidence', 'N/A')}")
    print(f"  Tags: {d.get('tags', [])}")
    print(f"  Priority: {d.get('priority', 'N/A')}")
    print(f"  Value score: {d.get('value_score', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")

print("\n[5] LLM状态检查")
try:
    r = requests.get(f'{base}/api/llm/status', timeout=5)
    d = r.json()
    print(f"  Configured: {d.get('configured', False)}")
    print(f"  Model: {d.get('model', 'N/A')}")
    print(f"  Bridge injected: {d.get('bridge_injected', False)}")
except Exception as e:
    print(f"  Error: {e}")

print("\n[6] 记忆CRUD + 操作日志联动验证")
try:
    r = requests.post(f'{base}/api/memory', json={
        'content': 'P1强化验证测试：TVP/MCP/Memory操作痕迹头部展示功能验证条目',
        'layer': 'working',
        'tags': ['p1_verify', 'ops_header', 'test'],
        'priority': 'medium'
    }, timeout=10)
    create_result = r.json()
    mem_id = create_result.get('id', 'unknown')
    print(f"  Create: id={mem_id}, status={r.status_code}")

    r = requests.get(f'{base}/api/operations/header', timeout=5)
    d = r.json()
    header = d.get('header', '')
    has_memory_op = 'Memory' in header or 'memory' in header.lower()
    print(f"  Ops header after create: {header[:100]}")
    print(f"  Memory op in header: {has_memory_op}")

    r = requests.delete(f'{base}/api/memory/{mem_id}', timeout=10)
    print(f"  Delete: status={r.status_code}")
except Exception as e:
    print(f"  Error: {e}")

print("\n[7] EvolutionBus注册详情")
try:
    r = requests.get(f'{base}/api/system/stats', timeout=10)
    d = r.json()
    evo = d.get('modules', {}).get('evolution_bus', {})
    print(f"  Status: {evo.get('status')}")
    reg = evo.get('registered_modules', [])
    print(f"  Registered modules ({len(reg)}): {reg}")
    print(f"  Signals routed: {evo.get('signals_routed', 0)}")
    print(f"  Cross-module triggers: {evo.get('cross_module_triggers', 0)}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 70)
print("验证完成")
print("=" * 70)
