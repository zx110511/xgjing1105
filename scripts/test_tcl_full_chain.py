"""TCL Level 2 合体运行全链路验证 - 通过REST API"""
import urllib.request, json, time

BASE = "http://127.0.0.1:8771"

def api_post(path, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}", data=body,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read().decode("utf-8"))

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read().decode("utf-8"))

print("=" * 60)
print("TCL Level 2 合体运行全链路验证")
print("=" * 60)

# 1. TCL归一化API测试
print("\n1. TCL归一化API测试")
tests = [
    ("天机记忆引擎", "ICME六层记忆架构"),
    ("L3", "忆枢层"),
    ("QualityGate", "QualityGate门禁"),
    ("六层记忆架构", "ICME六层记忆架构"),
    ("DeepSeek", "DeepSeek驾驶者"),
    ("TVP", "TVP透明调度协议"),
]
pass_count = 0
for input_term, expected_term in tests:
    r = api_post("/api/active/tcl/normalize", {"text": input_term, "mode": "single"})
    ct = r.get("canonical_term", "")
    conf = r.get("confidence", 0)
    method = r.get("method", "")
    ok = ct == expected_term
    if ok:
        pass_count += 1
    print(f"   {'PASS' if ok else 'FAIL'}: {input_term} -> {ct} (expected={expected_term}, conf={conf}, method={method})")
print(f"   归一化通过率: {pass_count}/{len(tests)}")

# 2. TCL消歧测试
print("\n2. TCL消歧测试")
r = api_post("/api/active/tcl/disambiguate", {"term": "记忆", "context": "将这条记忆存储到L4知枢层"})
ct = r.get("canonical_term", "")
conf = r.get("confidence", 0)
print(f"   记忆(上下文:存储到L4) -> {ct} (conf={conf})")

# 3. TCL+记忆写入 合体测试
print("\n3. TCL+记忆写入 合体测试")
r = api_post("/api/platform/remember", {
    "content": "天机记忆引擎的ICME六层记忆架构包含DeepSeek驾驶者，通过TVP透明调度协议实现Agent协作",
    "layer": "working",
    "tags": ["TCL合体验证"],
})
entry_id = r.get("id", "NONE")
print(f"   写入结果: id={entry_id}")

# 检查metadata中的tcl_canonical_ids
metadata = r.get("metadata", {})
tcl_ids = metadata.get("tcl_canonical_ids", "MISSING")
if tcl_ids != "MISSING":
    print(f"   PASS: tcl_canonical_ids = {tcl_ids}")
else:
    # 尝试从recall获取
    print(f"   metadata中未直接返回tcl_canonical_ids, 尝试recall验证...")

# 4. TCL+记忆检索 合体测试
print("\n4. TCL+记忆检索 合体测试")
# 用不同表述检索同一概念
recall_tests = [
    ("天机记忆引擎", "用别名'天机记忆引擎'检索"),
    ("六层记忆架构", "用别名'六层记忆架构'检索"),
]
for query, desc in recall_tests:
    import urllib.parse
    encoded_q = urllib.parse.quote(query)
    try:
        results = api_get(f"/api/platform/recall?query={encoded_q}&limit=5")
        print(f"   {desc}: 找到{len(results)}条结果")
        for item in results[:2]:
            content_preview = item.get("content", "")[:60]
            item_tcl = item.get("metadata", {}).get("tcl_canonical_ids", "N/A")
            print(f"     - {content_preview}... [tcl_ids={item_tcl}]")
    except Exception as e:
        print(f"   {desc}: 失败 - {e}")

# 5. TCL统计
print("\n5. TCL统计")
r = api_get("/api/active/tcl/stats")
stats = r.get("stats", {})
print(f"   术语总数: {stats.get('total_terms', 0)}")
print(f"   别名总数: {stats.get('total_aliases', 0)}")
print(f"   平均别名数: {stats.get('avg_aliases_per_term', 0)}")
print(f"   缓存条目: {stats.get('cache_entries', 0)}")

# 6. TCL添加术语测试
print("\n6. TCL添加术语测试")
r = api_post("/api/active/tcl/add-term", {
    "canonical_term": "TCL统一规范语言",
    "aliases": ["TCL", "规范语言", "Canonical Language", "统一术语"],
    "definition": "天机术语归一化架构，解决同义不同名导致的存储冗余和检索遗漏",
    "domain": "tianji_core",
})
print(f"   添加结果: {r}")

# 验证新术语可归一化
r2 = api_post("/api/active/tcl/normalize", {"text": "TCL", "mode": "single"})
print(f"   TCL归一化: {r2.get('canonical_term', '')} (conf={r2.get('confidence', 0)})")

print("\n" + "=" * 60)
print("TCL Level 2 合体运行验证完成!")
print("=" * 60)
