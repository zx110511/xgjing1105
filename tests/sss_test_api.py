import sys
import json
import urllib.request
import urllib.error
import urllib.parse
import time

BASE = "http://127.0.0.1:8771"
TIMEOUT = 30

def api(method, path, data=None):
    try:
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(
            f"{BASE}{path}",
            data=body,
            headers={"Content-Type": "application/json"} if body else {},
            method=method,
        )
        r = urllib.request.urlopen(req, timeout=TIMEOUT)
        return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"raw": str(e)}
        return e.code, err_body
    except Exception as e:
        return 0, {"error": str(e)}

results = []

def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append(f"{status} {name} {detail}")
    if not condition:
        print(f"  FAIL: {name} — {detail}")

print("=" * 60)
print("  天机 SSS级 API测试 v4")
print("=" * 60)

code, data = api("GET", "/")
test("T1 根路径", code == 200, f"code={code}")
test("T1 服务名", data.get("service") == "天机v9.1 元初系统", f"service={data.get('service')}")
test("T1 版本", data.get("version") is not None, f"version={data.get('version')}")

code, data = api("GET", "/api/health")
test("T2 健康检查", code == 200, f"code={code}")
test("T2 状态", data.get("status") == "healthy", f"status={data.get('status')}")
test("T2 引擎就绪", data.get("engine_ready") is True, f"engine_ready={data.get('engine_ready')}")

code, data = api("GET", "/api/stats")
test("T3 统计", code == 200, f"code={code}")
test("T3 条目数", data.get("total_entries", 0) >= 0, f"total={data.get('total_entries')}")

code, data = api("POST", "/api/memory/", {
    "content": "SSS级测试记忆条目-这是一条用于验证天机记忆系统完整性的测试数据，包含足够的字符长度以满足质量门禁要求",
    "layer": "working",
    "tags": ["test", "sss"],
    "priority": "high",
})
test("T4 写入记忆", code in (200, 201), f"code={code}")
entry_id = ""
if code in (200, 201):
    entry_id = data.get("id", "")
    test("T4 返回ID", bool(entry_id), f"id={entry_id}")

    code2, data2 = api("GET", f"/api/memory/{entry_id}")
    test("T5 读取记忆", code2 == 200, f"code={code2}")
    test("T5 内容存在", data2.get("content") is not None, f"content_len={len(data2.get('content',''))}")

    code3, _ = api("POST", "/api/memory/consolidate", {
        "entry_id": entry_id,
        "from_layer": "working",
        "to_layer": "short_term",
    })
    test("T6 整合", code3 == 200, f"code={code3}")
else:
    test("T4 返回ID", False, "写入失败无法继续")
    test("T5 读取记忆", False, "跳过")
    test("T6 整合", False, "跳过")

code, data = api("POST", "/api/search/", {
    "query": "测试",
    "limit": 5,
})
test("T7 搜索", code == 200, f"code={code}")

q_enc = urllib.parse.quote("测试")
code, data = api("GET", f"/api/search/quick?q={q_enc}")
test("T8 快速搜索", code == 200, f"code={code}")

code, data = api("GET", "/api/memory/layers/info")
test("T9 层信息", code == 200, f"code={code}")

code, data = api("GET", "/api/platform/health")
test("T10 平台健康", code == 200, f"code={code}")

code, data = api("GET", "/api/mcp/tools/tool_schema")
test("T11 MCP工具Schema", code == 200, f"code={code}")

code, data = api("GET", "/api/llm/status")
test("T12 LLM状态", code == 200, f"code={code}")

code, data = api("GET", "/api/active/platforms")
test("T13 主动记忆平台", code == 200, f"code={code}")

code, data = api("GET", "/api/orchestrator/status")
test("T14 Agent调度状态", code == 200, f"code={code}")

code, data = api("GET", "/api/memory/stats")
test("T15 记忆统计", code == 200, f"code={code}")

code, data = api("GET", "/api/search/index/status")
test("T16 搜索索引状态", code == 200, f"code={code}")

code, data = api("GET", "/api/summary/recent")
test("T17 近期摘要", code == 200, f"code={code}")

code, data = api("GET", "/api/mcp/tools/get_stats")
test("T18 MCP统计", code == 200, f"code={code}")

code, data = api("GET", "/api/orchestrator/agents")
test("T19 Agent列表", code == 200, f"code={code}")

if entry_id:
    code, data = api("DELETE", f"/api/memory/{entry_id}")
    test("T20 删除记忆", code == 200, f"code={code}")

code, data = api("GET", "/api/memory/")
test("T21 列表记忆", code == 200, f"code={code}")

code, data = api("GET", "/api/orchestrator/pipelines")
test("T22 流水线列表", code == 200, f"code={code}")

code, data = api("POST", "/api/mcp/tools/store_memory", {
    "content": "MCP工具存储测试-验证天机MCP接口的完整性和可靠性",
    "layer": "working",
    "tags": ["mcp", "test"],
})
test("T23 MCP存储", code == 200, f"code={code}")

code, data = api("POST", "/api/mcp/tools/search_memories", {
    "query": "MCP测试",
    "limit": 3,
})
test("T24 MCP搜索", code == 200, f"code={code}")

code, data = api("POST", "/api/orchestrator/pipeline/create", {
    "pipeline_type": "development",
    "task_goal": "SSS测试流水线",
})
test("T25 创建流水线", code == 200, f"code={code}")

code, data = api("GET", "/api/search/semantic?q=test")
test("T26 语义搜索", code in (200, 503), f"code={code}")

code, data = api("GET", "/api/platform/stats")
test("T27 平台统计", code == 200, f"code={code}")

code, data = api("GET", "/api/mcp/tools/list_namespaces")
test("T28 MCP命名空间", code == 200, f"code={code}")

print()
for r in results:
    print(r)

pass_count = sum(1 for r in results if r.startswith("PASS"))
fail_count = sum(1 for r in results if r.startswith("FAIL"))
print(f"\n{'='*60}")
print(f"  结果: {pass_count} PASS / {fail_count} FAIL / {len(results)} TOTAL")
if fail_count == 0:
    print("  状态: SSS级测试全部通过!")
else:
    print("  状态: 存在失败项，需要修复")
print(f"{'='*60}")
