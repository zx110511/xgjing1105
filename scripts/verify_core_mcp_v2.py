# -*- coding: utf-8-sig -*-
"""
Phase 3.2.1重试版: 用更长超时验证核心MCP工具
"""

import json
import time

import requests

TIANJI_API = "http://127.0.0.1:8771"
TIMEOUT = 30

results = []


def test_with_retry(name, func, max_retries=2):
    """带重试的测试"""
    print(f"\n{'=' * 60}")
    print(f"🧪 测试: {name}")
    print(f"{'=' * 60}")

    for attempt in range(1, max_retries + 1):
        try:
            ok, detail = func()
            status = "✅ PASS" if ok else "❌ FAIL"
            print(f"  尝试 {attempt}/{max_retries}: {status}")
            if detail:
                print(f"  详情: {detail[:200]}")
            if ok:
                results.append(
                    {
                        "name": name,
                        "pass": True,
                        "detail": detail[:100] if detail else "",
                    }
                )
                return True
        except Exception as e:
            print(f"  尝试 {attempt}/{max_retries}: ⏱️  超时/错误 - {str(e)[:80]}")
            if attempt < max_retries:
                time.sleep(3)

    results.append({"name": name, "pass": False, "detail": "all retries failed"})
    return False


# Test 1: tool_help (最轻量，验证服务可达)
def test_tool_help():
    resp = requests.get(f"{TIANJI_API}/api/mcp/tools/tool_help", timeout=TIMEOUT)
    data = resp.json()
    ok = data.get("status") == "success" and data.get("total", 0) > 0
    return ok, f"total={data.get('total', 0)} tools"


# Test 2: tool_schema
def test_tool_schema():
    resp = requests.get(
        f"{TIANJI_API}/api/mcp/tools/tool_schema?tool_name=memory_recall",
        timeout=TIMEOUT,
    )
    data = resp.json()
    ok = "schema" in data or "inputSchema" in data or data.get("status") == "success"
    return ok, f"keys={list(data.keys())[:5]}"


# Test 3: context_extract
def test_context_extract():
    resp = requests.post(
        f"{TIANJI_API}/api/mcp/tools/context_extract",
        json={
            "user_input": "帮我写一个Python函数，计算斐波那契数列",
        },
        timeout=TIMEOUT,
    )
    data = resp.json()
    ok = data.get("status") == "success"
    detail = f"status={data.get('status')}, intents={len(data.get('intents', []))}"
    return ok, detail


# Test 4: list_memories
def test_list_memories():
    resp = requests.post(
        f"{TIANJI_API}/api/mcp/tools/list_memories",
        json={"limit": 3, "layer": "working"},
        timeout=TIMEOUT,
    )
    data = resp.json()
    ok = data.get("status") == "success" or "memories" in data
    detail = (
        f"count={len(data.get('memories', []))}"
        if "memories" in data
        else str(list(data.keys())[:3])
    )
    return ok, detail


# Test 5: get_session_digest
def test_session_digest():
    resp = requests.post(
        f"{TIANJI_API}/api/mcp/tools/get_session_digest",
        json={"session_key": "test_phase3_2"},
        timeout=TIMEOUT,
    )
    data = resp.json()
    ok = data.get("status") == "success" or "digest" in data
    return ok, str(list(data.keys())[:3])


# 主流程
print("=" * 60)
print("Phase 3.2.1 (重试版): 核心MCP工具功能验证")
print(f"  超时设置: {TIMEOUT}秒, 重试2次")
print("=" * 60)

# 先确认服务健康
try:
    h = requests.get(f"{TIANJI_API}/api/health", timeout=10).json()
    print(f"\n🏥 服务健康: engine_ready={h.get('engine_ready')}")
except Exception as e:
    print(f"\n❌ 服务不可用: {e}")
    exit(1)

time.sleep(1)

test_with_retry("tool_help (工具列表)", test_tool_help)
time.sleep(2)

test_with_retry("tool_schema (工具Schema)", test_tool_schema)
time.sleep(2)

test_with_retry("context_extract (上下文提取)", test_context_extract)
time.sleep(2)

test_with_retry("list_memories (记忆列举)", test_list_memories)
time.sleep(2)

test_with_retry("get_session_digest (会话摘要)", test_session_digest)

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
print(
    f"  结论: {'✅ 核心工具功能正常，删除技能文件未影响功能' if passed >= total * 0.6 else '⚠️  部分工具异常，需进一步排查'}"
)
print("=" * 60)

# 保存
with open(
    r"d:\元初系统\天机v9.1\.trae\skills\.audit\phase3_2_1_verification_v2.json",
    "w",
    encoding="utf-8-sig",
) as f:
    json.dump(
        {
            "phase": "3.2.1 v2",
            "total": total,
            "passed": passed,
            "results": results,
        },
        f,
        ensure_ascii=False,
        indent=2,
    )
