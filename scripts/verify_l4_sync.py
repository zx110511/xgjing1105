# -*- coding: utf-8-sig -*-
"""验证L4知识写入结果"""

import requests

TIANJI_API = "http://127.0.0.1:8771"

print("=" * 60)
print("Phase 3.1 验证: L4 Semantic知识写入")
print("=" * 60)

# 测试1: search_memories
print("\n[1/3] search_memories '领域技能库'...")
try:
    r = requests.post(
        f"{TIANJI_API}/api/mcp/tools/search_memories",
        json={"query": "领域技能库", "limit": 6},
        timeout=10,
    )
    data = r.json()
    results = data.get("results", [])
    print(f"  状态: {data.get('status')}")
    print(f"  结果数: {len(results)}")
    for i, x in enumerate(results[:4]):
        preview = x.get("content", "")[:60].replace("\n", " ")
        layer = x.get("layer", "?")
        print(f"  [{i + 1}] [{layer}] {preview}...")
except Exception as e:
    print(f"  失败: {e}")

# 测试2: memory_recall 语义检索
print("\n[2/3] memory_recall '激进精简 技能归位'...")
try:
    r = requests.post(
        f"{TIANJI_API}/api/mcp/tools/memory_recall",
        json={"query": "激进精简 技能归位", "layers": ["semantic"], "limit": 5},
        timeout=10,
    )
    data = r.json()
    results = data.get("results", [])
    print(f"  状态: {data.get('status')}")
    print(f"  结果数: {len(results)}")
    for i, x in enumerate(results[:3]):
        preview = x.get("content", "")[:60].replace("\n", " ")
        score = x.get("relevance_score", 0)
        print(f"  [{i + 1}] [{score:.2f}] {preview}...")
except Exception as e:
    print(f"  失败: {e}")

# 测试3: memory_stats
print("\n[3/3] memory_stats 统计...")
try:
    r = requests.get(f"{TIANJI_API}/api/mcp/tools/get_stats", timeout=10)
    data = r.json()
    print(f"  总记忆数: {data.get('total_entries', '?')}")
    layers = data.get("layers", {})
    for layer_name, layer_info in layers.items():
        if isinstance(layer_info, dict):
            print(f"  {layer_name}: {layer_info.get('count', '?')} 条")
except Exception as e:
    print(f"  失败: {e}")

print("\n" + "=" * 60)
print("Phase 3.1 验证完成")
print("=" * 60)
