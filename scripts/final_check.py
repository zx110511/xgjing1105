import requests

r = requests.get('http://127.0.0.1:8771/api/system/stats', timeout=10)
d = r.json()
mods = d.get('modules', {})

print("=== rt_cache raw data for target modules ===")
for name in ['namespace_manager', 'llm_bridge', 'chinese_tokenizer']:
    v = mods.get(name, {})
    print(f"\n{name}:")
    print(f"  keys={list(v.keys())}")
    print(f"  state={v.get('state')}")

print("\n=== Summary ===")
all_mods = d.get('modules', {})
with_data = [n for n,v in all_mods.items() if any(k not in ('status','last_update','state') for k in v.keys())]
no_data = [n for n,v in all_mods.items() if not any(k not in ('status','last_update','state') for k in v.keys())]
print(f"With data ({len(with_data)}): {sorted(with_data)}")
print(f"No data ({len(no_data)}): {sorted(no_data)}")
print(f"Total: {len(all_mods)}, Cache size: {d.get('_rt_cache_size', '?')}")
