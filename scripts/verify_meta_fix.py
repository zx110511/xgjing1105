"""验证meta层修复 - 写入测试并验证layer不被降级"""

import io
import json
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 写入一条meta层测试记录
content = (
    "[META-LAYER-FIX-VERIFY] 验证meta层不被降级到episodic。此记录应保持layer=meta。"
)
data = json.dumps(
    {
        "content": content,
        "layer": "meta",
        "tags": ["meta-fix-verify", "system-decision", "test"],
        "priority": "critical",
        "use_llm": False,
    },
    ensure_ascii=False,
).encode("utf-8")

req = urllib.request.Request(
    "http://127.0.0.1:8771/api/memory/",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)

print("=" * 60)
print("1. 写入meta层测试记录")
print("=" * 60)
t0 = time.time()
r = urllib.request.urlopen(req, timeout=30)
elapsed = time.time() - t0
response = json.loads(r.read().decode("utf-8"))
print(f"  耗时: {elapsed:.2f}s")
print(f"  返回layer: {response.get('layer')}")
print(f"  返回id: {response.get('id')}")
test_id = response.get("id")
print("  期望layer: meta")
print(f"  修复生效: {response.get('layer') == 'meta'}")

print()
print("=" * 60)
print("2. 通过ID查询验证")
print("=" * 60)
if test_id:
    req2 = urllib.request.Request(f"http://127.0.0.1:8771/api/memory/{test_id}")
    r2 = urllib.request.urlopen(req2, timeout=10)
    data2 = json.loads(r2.read().decode("utf-8"))
    print(f"  ID: {data2.get('id')}")
    print(f"  Layer: {data2.get('layer')}")
    print(f"  Priority: {data2.get('priority')}")
    print(f"  修复验证: {'PASS' if data2.get('layer') == 'meta' else 'FAIL'}")

print()
print("=" * 60)
print("3. 重新补录L5 Meta策略记录（之前被错误降级到episodic）")
print("=" * 60)
# 删除之前被错误降级的记录
if test_id:
    try:
        req_del = urllib.request.Request(
            f"http://127.0.0.1:8771/api/memory/{test_id}", method="DELETE"
        )
        urllib.request.urlopen(req_del, timeout=10)
        print(f"  测试记录已删除: {test_id}")
    except:
        pass

# 重新写入L5 Meta策略记录
content_meta = """[跨会话审计补录 L5 Meta-系统级策略沉淀-RETRY] 2026-06-25至2026-07-04共10天28+会话系统级策略沉淀。
六大主线: (1)启动稳定性 (2)智能体调度科学化 (3)MCP技能规范化 (4)记忆系统健康 (5)工业化小说生产 (6)规则强制执行。
累计测试100+项100%通过率, 平均评分9.95+分。"""
data_meta = json.dumps(
    {
        "content": content_meta,
        "layer": "meta",
        "tags": [
            "system-decision",
            "cross-session-audit",
            "meta-layer-fix",
            "P0_critical",
        ],
        "priority": "critical",
        "use_llm": False,
    },
    ensure_ascii=False,
).encode("utf-8")

req_meta = urllib.request.Request(
    "http://127.0.0.1:8771/api/memory/",
    data=data_meta,
    headers={"Content-Type": "application/json"},
    method="POST",
)
t0 = time.time()
r_meta = urllib.request.urlopen(req_meta, timeout=30)
elapsed = time.time() - t0
response_meta = json.loads(r_meta.read().decode("utf-8"))
print(f"  耗时: {elapsed:.2f}s")
print(f"  返回layer: {response_meta.get('layer')}")
print(f"  返回id: {response_meta.get('id')}")
print(f"  修复生效: {response_meta.get('layer') == 'meta'}")

print()
print("=" * 60)
print("4. memory_recall搜索验证")
print("=" * 60)
# 搜索meta层记录
import urllib.parse

query = "meta-layer-fix"
encoded_q = urllib.parse.quote(query)
req_search = urllib.request.Request(
    f"http://127.0.0.1:8771/api/platform/recall?query={encoded_q}&limit=3"
)
r_search = urllib.request.urlopen(req_search, timeout=15)
search_results = json.loads(r_search.read().decode("utf-8"))
print(f"  搜索'{query}' -> {len(search_results)}条")
for item in search_results[:3]:
    print(f"    - {item.get('id')} (layer={item.get('layer')})")

print()
print("修复验证完成")
