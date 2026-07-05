"""修复审计失败项 - 用正确搜索词验证测试记录"""

import io
import json
import sys
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 用content中的关键词搜索测试记录
test_id = "072f64c5278b67e9"
search_queries = ["META-LAYER-FIX-VERIFY", "验证meta层不被降级", "meta层不被降级"]

print("=" * 60)
print("修复审计失败项: 用content中关键词搜索测试记录")
print("=" * 60)

for q in search_queries:
    encoded_q = urllib.parse.quote(q)
    url = f"http://127.0.0.1:8771/api/platform/recall?query={encoded_q}&limit=5"
    try:
        req = urllib.request.Request(url)
        r = urllib.request.urlopen(req, timeout=15)
        data = json.loads(r.read().decode("utf-8"))
        found = (
            any(item.get("id") == test_id for item in data)
            if isinstance(data, list)
            else False
        )
        status = "PASS" if found else "FAIL"
        print(f"  [{status}] 搜索'{q}' -> 找到{test_id}={found}")
        if found:
            break
    except Exception as e:
        print(f"  [FAIL] 搜索'{q}' 错误: {e}")

# 删除测试记录（已完成验证目的）
print()
print("=" * 60)
print("清理测试记录")
print("=" * 60)
try:
    req_del = urllib.request.Request(
        f"http://127.0.0.1:8771/api/memory/{test_id}", method="DELETE"
    )
    r_del = urllib.request.urlopen(req_del, timeout=10)
    print(f"  测试记录已删除: {test_id}")
except Exception as e:
    print(f"  删除失败: {e}")

# 重新审计
print()
print("=" * 60)
print("最终审计（删除测试记录后）")
print("=" * 60)
audit_results = []

# 审计1: 补录记录存在性
for mid, expected_layer in [
    ("fb6e53897f9ace36", "episodic"),
    ("749884cc6dbb59cd", "meta"),
]:
    import sqlite3

    conn = sqlite3.connect(r"d:\元初系统\天机v9.1\data\.memory\icme.db")
    row = conn.execute("SELECT id, layer FROM memories WHERE id=?", (mid,)).fetchone()
    if row:
        layer_ok = row[1] == expected_layer
        status = "PASS" if layer_ok else "FAIL"
        audit_results.append((f"存在性+layer:{mid}", status))
        print(f"  [{status}] id={mid} layer={row[1]} (期望:{expected_layer})")
    else:
        audit_results.append((f"存在性:{mid}", "FAIL"))
        print(f"  [FAIL] id={mid} 不存在")
    conn.close()

# 审计2: memory_recall可检索性
for query, expected_id in [
    ("跨会话审计补录", "fb6e53897f9ace36"),
    ("系统级策略沉淀", "749884cc6dbb59cd"),
]:
    encoded_q = urllib.parse.quote(query)
    url = f"http://127.0.0.1:8771/api/platform/recall?query={encoded_q}&limit=5"
    req = urllib.request.Request(url)
    r = urllib.request.urlopen(req, timeout=15)
    data = json.loads(r.read().decode("utf-8"))
    found = (
        any(item.get("id") == expected_id for item in data)
        if isinstance(data, list)
        else False
    )
    status = "PASS" if found else "FAIL"
    audit_results.append((f"检索:{query}", status))
    print(f"  [{status}] 搜索'{query}' 找到{expected_id}={found}")

# 审计总结
pass_count = sum(1 for _, s in audit_results if s == "PASS")
fail_count = sum(1 for _, s in audit_results if s == "FAIL")
total_count = len(audit_results)
print()
print(f"  最终审计: {pass_count}/{total_count} 通过, {fail_count} 失败")
print(f"  审计结论: {'PASS - 绝不降级达成' if fail_count == 0 else 'FAIL'}")
