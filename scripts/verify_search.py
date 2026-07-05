import urllib.request, urllib.parse, json

BASE = 'http://127.0.0.1:8771'

def get(path):
    r = urllib.request.urlopen(BASE + path)
    return json.loads(r.read())

# 测试TCL增强检索
try:
    q = 'ICME六层记忆架构'
    url = f'/api/search/semantic?query={urllib.parse.quote(q)}&limit=5'
    d = get(url)
    print(f"[PASS] 语义搜索: {len(d)}条")
except Exception as e:
    print(f"[FAIL] 语义搜索: {e}")

try:
    q = '感枢层'
    url = f'/api/memory/query?query={urllib.parse.quote(q)}&limit=5'
    d = get(url)
    print(f"[PASS] 记忆查询: {len(d)}条结果")
    # 检查结果中是否包含metadata.tcl_canonical_ids
    for entry in d:
        tcl = entry.get('metadata', {}).get('tcl_canonical_ids')
        if tcl:
            print(f"  → 条目 {entry.get('id','')[:8]} 含 {len(tcl)} 个canonical_ids")
except Exception as e:
    print(f"[FAIL] 记忆查询: {e}")

try:
    q = 'ICME'
    url = f'/api/platform/recall?query={urllib.parse.quote(q)}&limit=3'
    d = get(url)
    print(f"[PASS] TCL召回: {len(d)}条")
except Exception as e:
    print(f"[FAIL] TCL召回: {e}")

try:
    d = get('/api/asset/stats')
    print(f"[PASS] 快照统计: total={d.get('total_snapshots')}, size={d.get('total_size_bytes')}B")
except Exception as e:
    print(f"[FAIL] 快照统计: {e}")

print("\n全链路验证完成!")
