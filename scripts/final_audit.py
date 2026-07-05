"""最严审计验证 - 绝不降级"""
import sys
import io
import urllib.request
import urllib.parse
import json
import sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db = r'd:\元初系统\天机v9.1\data\.memory\icme.db'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

audit_results = []

print("=" * 70)
print("最严审计验证 - 绝不降级")
print("=" * 70)

# 审计1: 补录记录存在性
print("\n[审计1] 补录记录存在性")
for mid, expected_layer in [
    ('fb6e53897f9ace36', 'episodic'),
    ('749884cc6dbb59cd', 'meta'),
    ('072f64c5278b67e9', 'meta'),
]:
    row = conn.execute("SELECT id, layer, content FROM memories WHERE id=?", (mid,)).fetchone()
    if row:
        layer_ok = row['layer'] == expected_layer
        status = 'PASS' if layer_ok else 'FAIL'
        audit_results.append((f'存在性+layer:{mid}', status))
        print(f"  [{status}] id={mid} layer={row['layer']} (期望:{expected_layer})")
    else:
        audit_results.append((f'存在性:{mid}', 'FAIL'))
        print(f"  [FAIL] id={mid} 不存在")

# 审计2: FTS5索引同步
print("\n[审计2] FTS5索引同步")
for mid in ['fb6e53897f9ace36', '749884cc6dbb59cd', '072f64c5278b67e9']:
    row = conn.execute("SELECT rowid FROM memories WHERE id=?", (mid,)).fetchone()
    if row:
        fts_row = conn.execute("SELECT rowid FROM memories_fts WHERE rowid=?", (row[0],)).fetchone()
        status = 'PASS' if fts_row else 'FAIL'
        audit_results.append((f'FTS5索引:{mid}', status))
        print(f"  [{status}] id={mid} rowid={row[0]} FTS5存在={fts_row is not None}")

# 审计3: memory_recall可检索性
print("\n[审计3] memory_recall可检索性")
test_searches = [
    ('跨会话审计补录', 'fb6e53897f9ace36'),
    ('系统级策略沉淀', '749884cc6dbb59cd'),
    ('meta-layer-fix', '072f64c5278b67e9'),
]
for query, expected_id in test_searches:
    encoded_q = urllib.parse.quote(query)
    url = f'http://127.0.0.1:8771/api/platform/recall?query={encoded_q}&limit=5'
    try:
        req = urllib.request.Request(url)
        r = urllib.request.urlopen(req, timeout=15)
        data = json.loads(r.read().decode('utf-8'))
        found = any(item.get('id') == expected_id for item in data) if isinstance(data, list) else False
        status = 'PASS' if found else 'FAIL'
        audit_results.append((f'检索:{query}', status))
        print(f"  [{status}] 搜索'{query}' 期望id={expected_id} 找到={found}")
    except Exception as e:
        audit_results.append((f'检索:{query}', 'FAIL'))
        print(f"  [FAIL] 搜索'{query}' 错误: {e}")

# 审计4: MCP memory_recall可用性
print("\n[审计4] MCP memory_recall端点可用性")
try:
    encoded_q = urllib.parse.quote('跨会话审计补录')
    url = f'http://127.0.0.1:8771/api/platform/recall?query={encoded_q}&limit=3'
    req = urllib.request.Request(url)
    t0 = __import__('time').time()
    r = urllib.request.urlopen(req, timeout=15)
    elapsed = __import__('time').time() - t0
    data = json.loads(r.read().decode('utf-8'))
    count = len(data) if isinstance(data, list) else 0
    status = 'PASS' if count > 0 and elapsed < 5 else 'FAIL'
    audit_results.append(('MCP端点可用性', status))
    print(f"  [{status}] 耗时={elapsed:.2f}s 命中={count}条")
except Exception as e:
    audit_results.append(('MCP端点可用性', 'FAIL'))
    print(f"  [FAIL] 错误: {e}")

# 审计5: 按layer统计
print("\n[审计5] layer分布统计")
rows = conn.execute(
    "SELECT layer, COUNT(*) as cnt FROM memories GROUP BY layer ORDER BY cnt DESC"
).fetchall()
total = sum(r['cnt'] for r in rows)
print(f"  总记录数: {total}")
for r in rows:
    print(f"  {r['layer']}: {r['cnt']} ({100*r['cnt']/total:.1f}%)")

# 审计6: quality_gate代码修复
print("\n[审计6] quality_gate代码修复验证")
import os
fix_file = r'd:\元初系统\天机v9.1\core\processors\gate\policy_engine.py'
with open(fix_file, 'r', encoding='utf-8') as f:
    content = f.read()
has_fix = 'if layer == "meta":' in content and 'FIX-META-LAYER' in content
status = 'PASS' if has_fix else 'FAIL'
audit_results.append(('quality_gate代码修复', status))
print(f"  [{status}] policy_engine.py包含meta层跳过修复: {has_fix}")
print(f"  注意: 代码修复需重启服务生效，已用SQL直接修复数据")

# 审计总结
print("\n" + "=" * 70)
print("审计总结")
print("=" * 70)
pass_count = sum(1 for _, s in audit_results if s == 'PASS')
fail_count = sum(1 for _, s in audit_results if s == 'FAIL')
total_count = len(audit_results)
print(f"  通过: {pass_count}/{total_count}")
print(f"  失败: {fail_count}/{total_count}")
print(f"  通过率: {100*pass_count/total_count:.1f}%")
print(f"  审计结论: {'PASS - 绝不降级达成' if fail_count == 0 else 'FAIL - 需要修复'}")

if fail_count > 0:
    print("\n  失败项:")
    for name, status in audit_results:
        if status == 'FAIL':
            print(f"    - {name}")

conn.close()
print("\n最严审计完成")
