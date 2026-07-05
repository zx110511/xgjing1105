"""测试 /api/platform/recall 端点"""

import io
import json
import sys
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

print("=" * 60)
print("测试 /api/platform/recall 端点")
print("=" * 60)

test_queries = [
    "跨会话审计补录",
    "系统级策略沉淀",
    "10day-backfill",
    "fb6e53897f9ace36",
]

for q in test_queries:
    encoded_q = urllib.parse.quote(q)
    url = f"http://127.0.0.1:8771/api/platform/recall?query={encoded_q}&limit=5"
    try:
        req = urllib.request.Request(url)
        r = urllib.request.urlopen(req, timeout=15)
        data = json.loads(r.read().decode("utf-8"))
        count = len(data) if isinstance(data, list) else 0
        print(f"  Q='{q}' -> {count}条")
        if count > 0:
            for item in data[:3]:
                mid = item.get("id", "?")
                layer = item.get("layer", "?")
                content_preview = (item.get("content") or "")[:50]
                print(f"    - {mid} (layer={layer}): {content_preview}")
    except Exception as e:
        print(f"  Q='{q}' -> 错误: {e}")
    print()

print("=" * 60)
print("测试 /api/mcp/tools/search_memories 端点")
print("=" * 60)
for q in test_queries[:2]:
    url = "http://127.0.0.1:8771/api/mcp/tools/search_memories"
    data_body = json.dumps({"query": q, "limit": 5, "threshold": 0.0}).encode("utf-8")
    try:
        req = urllib.request.Request(
            url,
            data=data_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        r = urllib.request.urlopen(req, timeout=15)
        data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, dict):
            results = data.get("results", [])
            count = len(results)
        else:
            count = len(data) if isinstance(data, list) else 0
            results = data if isinstance(data, list) else []
        print(f"  Q='{q}' -> {count}条")
        for item in results[:3]:
            mid = item.get("id", "?")
            layer = item.get("layer", "?")
            print(f"    - {mid} (layer={layer})")
    except Exception as e:
        print(f"  Q='{q}' -> 错误: {e}")
    print()
