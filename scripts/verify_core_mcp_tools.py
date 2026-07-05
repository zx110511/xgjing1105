# -*- coding: utf-8-sig -*-
"""
Phase 3.2.1: 验证4个核心MCP工具功能正常
测试工具: memory_remember, memory_recall, context_extract, agent_dispatch
验证: 删除技能文件后，工具功能不退化
"""

import json
import time

import requests

TIANJI_API = "http://127.0.0.1:8771"

results = []


def test_tool(name, description, func):
    """测试单个工具"""
    print(f"\n{'=' * 60}")
    print(f"🧪 测试: {name}")
    print(f"   {description}")
    print(f"{'=' * 60}")
    try:
        ok, detail = func()
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"\n   结果: {status}")
        if detail:
            print(f"   详情: {detail[:200]}")
        results.append(
            {"name": name, "pass": ok, "detail": detail[:100] if detail else ""}
        )
        return ok
    except Exception as e:
        print(f"\n   结果: ❌ ERROR - {e}")
        results.append({"name": name, "pass": False, "detail": str(e)[:100]})
        return False


# Test 1: memory_remember
def test_memory_remember():
    test_content = "Phase3.2验证测试 - memory_remember功能验证 - 2026-07-03"
    resp = requests.post(
        f"{TIANJI_API}/api/mcp/tools/store_memory",
        json={
            "content": test_content,
            "layer": "working",
            "tags": ["test", "phase3.2", "validation"],
            "priority": "low",
        },
        timeout=10,
    )
    data = resp.json()
    ok = data.get("status") == "success"
    return ok, f"entry_id={data.get('entry_id', 'N/A')}"


# Test 2: memory_recall
def test_memory_recall():
    resp = requests.post(
        f"{TIANJI_API}/api/mcp/tools/memory_recall",
        json={
            "query": "测试 验证",
            "layers": ["working"],
            "limit": 3,
        },
        timeout=10,
    )
    data = resp.json()
    ok = data.get("status") == "success" and len(data.get("results", [])) > 0
    detail = f"found {len(data.get('results', []))} results"
    return ok, detail


# Test 3: context_extract
def test_context_extract():
    resp = requests.post(
        f"{TIANJI_API}/api/mcp/tools/context_extract",
        json={
            "user_input": "请帮我写一个Python脚本，实现记忆的增删改查功能，还要支持语义搜索，用SQLite数据库",
            "context": "用户是Python开发者，正在开发记忆系统",
        },
        timeout=10,
    )
    data = resp.json()
    ok = data.get("status") == "success"
    detail = f"intents={len(data.get('intents', []))}, entities={len(data.get('entities', []))}"
    return ok, detail


# Test 4: agent_dispatch
def test_agent_dispatch():
    resp = requests.post(
        f"{TIANJI_API}/api/mcp/tools/agent_dispatch",
        json={
            "task_type": "创作一篇科幻小说的第一章",
            "task_data": {"genre": "sci-fi", "length": "5000字"},
            "priority": "medium",
        },
        timeout=10,
    )
    data = resp.json()
    ok = data.get("status") == "success"
    detail = f"recommended={data.get('recommended_agent', 'N/A')}, confidence={data.get('confidence', 'N/A')}"
    return ok, detail


# 主流程
print("=" * 60)
print("Phase 3.2.1: 核心MCP工具功能验证")
print("  目标: 验证删除技能文件后，工具功能不退化")
print("  工具: memory_remember, memory_recall, context_extract, agent_dispatch")
print("=" * 60)

# 先确认服务健康
try:
    h = requests.get(f"{TIANJI_API}/api/health", timeout=5).json()
    print(f"\n🏥 服务健康: engine_ready={h.get('engine_ready')}")
except Exception as e:
    print(f"\n❌ 服务不可用: {e}")
    exit(1)

time.sleep(0.5)

# 逐个测试
test_tool("memory_remember (记忆写入)", "验证写入功能正常", test_memory_remember)
time.sleep(1)

test_tool("memory_recall (记忆检索)", "验证检索功能正常", test_memory_recall)
time.sleep(1)

test_tool("context_extract (上下文提取)", "验证意图解析功能正常", test_context_extract)
time.sleep(1)

test_tool("agent_dispatch (Agent调度)", "验证智能调度功能正常", test_agent_dispatch)

# 汇总
print("\n" + "=" * 60)
print("📊 测试汇总")
print("=" * 60)

passed = sum(1 for r in results if r["pass"])
total = len(results)

for r in results:
    status = "✅" if r["pass"] else "❌"
    print(f"  {status} {r['name']}")

print(f"\n  通过率: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"  状态: {'✅ 全部通过' if passed == total else '⚠️  有失败'}")
print("=" * 60)

# 保存结果
with open(
    r"d:\元初系统\天机v9.1\.trae\skills\.audit\phase3_2_1_verification.json",
    "w",
    encoding="utf-8-sig",
) as f:
    json.dump(
        {
            "phase": "3.2.1",
            "description": "核心MCP工具功能验证",
            "timestamp": "2026-07-03",
            "total": total,
            "passed": passed,
            "results": results,
        },
        f,
        ensure_ascii=False,
        indent=2,
    )
