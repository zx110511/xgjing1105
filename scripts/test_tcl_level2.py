"""TCL Level 2 全链路验证脚本"""
import json
import urllib.request
import urllib.parse

def api_post(path, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:8771{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode("utf-8"))

def api_get(path):
    req = urllib.request.Request(f"http://127.0.0.1:8771{path}")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode("utf-8"))

print("=== TCL Level 2 全链路验证 ===\n")

# 1. TCL归一化测试
print("1. TCL归一化测试")
tests = ["天机记忆引擎", "L3", "QualityGate", "六层记忆架构", "DeepSeek", "TVP"]
for t in tests:
    r = api_post("/api/active/tcl/normalize", {"text": t, "mode": "single"})
    ct = r.get("canonical_term", "")
    conf = r.get("confidence", 0)
    method = r.get("method", "")
    print(f"   {t} -> {ct} (conf={conf}, method={method})")

print()

# 2. TCL消歧测试
print("2. TCL消歧测试")
r = api_post("/api/active/tcl/disambiguate", {"term": "记忆", "context": "将这条记忆存储到L4知枢层"})
print(f"   记忆(上下文:存储到L4) -> {r.get('canonical_term', '')} (conf={r.get('confidence', 0)})")

r = api_post("/api/active/tcl/disambiguate", {"term": "记忆", "context": "记忆晋升机制需要优化"})
print(f"   记忆(上下文:晋升优化) -> {r.get('canonical_term', '')} (conf={r.get('confidence', 0)})")

print()

# 3. TCL+记忆写入 合体测试
print("3. TCL+记忆写入 合体测试")
r = api_post("/api/platform/remember", {
    "content": "天机记忆引擎的ICME六层记忆架构包含DeepSeek驾驶者",
    "layer": "working",
    "tags": ["TCL测试"],
})
mem_id = r.get("id", "N/A")
status = r.get("status", "N/A")
metadata = r.get("metadata", {})
tcl_ids = metadata.get("tcl_canonical_ids", [])
print(f"   写入结果: id={str(mem_id)[:16]}..., status={status}")
print(f"   TCL canonical_ids: {tcl_ids}")

print()

# 4. TCL+记忆检索 合体测试
print("4. TCL+记忆检索 合体测试")
r = api_get("/api/search/?q=" + urllib.parse.quote("六层记忆架构") + "&limit=3")
if isinstance(r, list):
    print(f"   检索到 {len(r)} 条记忆")
    for item in r[:2]:
        content = item.get("content", "")[:80]
        print(f"   - {content}...")
elif isinstance(r, dict):
    entries = r.get("entries", r.get("results", []))
    print(f"   检索到 {len(entries)} 条记忆")

print()

# 5. TCL统计
print("5. TCL术语表统计")
r = api_get("/api/active/tcl/stats")
stats = r.get("stats", {})
print(f"   总术语数: {stats.get('total_terms', 0)}")
print(f"   总别名数: {stats.get('total_aliases', 0)}")
print(f"   平均别名/术语: {stats.get('avg_aliases_per_term', 0)}")
print(f"   缓存条目数: {stats.get('cache_entries', 0)}")

print()

# 6. 内容归一化测试
print("6. 内容归一化测试(全文)")
r = api_post("/api/active/tcl/normalize", {
    "text": "天机的六层记忆架构和DeepSeek驾驶者通过TVP协议进行Agent调度",
    "mode": "content",
})
print(f"   归一化术语数: {r.get('normalized_count', 0)}")
print(f"   canonical_ids: {r.get('canonical_ids', [])}")

print("\n=== TCL Level 2 全链路验证完成 ===")
