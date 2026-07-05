import requests, json

r = requests.get('http://127.0.0.1:8771/api/system/stats', timeout=10)
d = r.json()
mods = d.get('modules', {})

targets = ['namespace_manager', 'llm_bridge', 'chinese_tokenizer',
           'quality_gate', 'event_bus', 'memory_api',
           'encoding_safe', 'realtime_monitor', 'tvp_orchestrator']

for name in targets:
    v = mods.get(name, {})
    keys = [k for k in v.keys() if k not in ('status', 'last_update')]
    has_data = len(keys) > 0
    tag = '[OK]' if has_data else '[NO]'
    print(f'{tag} {name:25s} keys={keys}')
    if not has_data:
        print(f'   full={json.dumps(v, ensure_ascii=False)}')
