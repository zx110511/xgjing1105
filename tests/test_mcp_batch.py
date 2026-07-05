# -*- coding: utf-8-sig -*-
"""分批测试MCP工具，每批10个，中间休息15秒"""

import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8771/api/mcp"


def http_get(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        if resp.status == 200:
            return True, json.loads(resp.read().decode("utf-8"))
        return False, {"error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as e:
        return False, {"error": f"HTTP {e.code}"}
    except Exception as e:
        return False, {"error": str(e)}


def http_post(url, body, timeout=10):
    try:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        if resp.status == 200:
            return True, json.loads(resp.read().decode("utf-8"))
        return False, {"error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as e:
        return False, {"error": f"HTTP {e.code}"}
    except Exception as e:
        return False, {"error": str(e)}


# 工具配置
TOOLS = [
    # 记忆核心 (8个)
    (
        "memory_remember",
        "POST",
        {
            "content": "MCP全量测试-记忆写入验证",
            "layer": "episodic",
            "tags": ["test", "mcp"],
        },
    ),
    ("memory_recall", "POST", {"query": "测试", "limit": 5}),
    ("memory_stats", "GET", {}),
    ("memory_capacity", "GET", {}),
    ("memory_consolidate", "POST", {}),
    ("search_memories", "POST", {"query": "测试", "limit": 5}),
    ("get_memory", "GET", {"memory_id": "test"}),
    ("list_memories", "GET", {"layer": "episodic", "limit": 5}),
    # 会话与表达 (4个)
    ("get_session_digest", "POST", {"session_key": "test-session-001"}),
    ("build_working_representation", "POST", {"session_key": "test-session-001"}),
    ("explain_memory_lineage", "POST", {"memory_id": "test"}),
    ("context_extract", "POST", {"content": "测试上下文提取功能"}),
    # 天机工具 (15个)
    ("tianji_health", "GET", {}),
    ("tianji_help", "GET", {}),
    ("tianji_classify", "POST", {"content": "测试文本分类功能"}),
    ("tianji_auto_tag", "POST", {"content": "测试自动标签功能"}),
    (
        "tianji_summarize",
        "POST",
        {"content": "测试摘要生成长文本内容用于验证MCP工具功能"},
    ),
    ("tianji_extract_knowledge", "POST", {"content": "测试知识提取功能"}),
    ("tianji_expand_query", "POST", {"query": "测试"}),
    ("tianji_semantic_search", "POST", {"query": "测试", "limit": 5}),
    ("tianji_normalize", "POST", {"content": "测试 规范化 处理"}),
    ("tianji_disambiguate", "POST", {"content": "苹果", "context": "我喜欢吃苹果"}),
    ("tianji_intercept", "POST", {"content": "测试拦截"}),
    ("tianji_summarize_conversation", "POST", {"session_key": "test"}),
    ("tianji_tool_owner", "GET", {"tool_name": "memory_remember"}),
    ("tianji_amim_status", "GET", {}),
    ("tianji_operation_header", "GET", {}),
    # 图与进化 (5个)
    ("memory_build_graph", "POST", {}),
    ("memory_query_graph", "POST", {"query": "测试"}),
    ("memory_learn_skill", "POST", {"skill_name": "test_skill"}),
    ("memory_capture_multimodal", "POST", {"content": "测试多模态捕获"}),
    ("run_reflective_cycle", "POST", {}),
    # 智能体与规则 (4个)
    ("agent_dispatch", "POST", {"task": "测试任务描述"}),
    ("system_status", "GET", {}),
    ("rule_evaluate", "POST", {"rule": "test_rule"}),
    ("tool_help", "GET", {}),
    # 命令执行 (3个)
    ("execute_command", "POST", {"command": "echo hello_world"}),
    ("list_processes", "GET", {}),
    ("get_process_info", "GET", {"pid": 1}),
    # 脚本 (2个)
    ("list_scripts", "GET", {}),
    ("run_script", "POST", {"script": "test_script"}),
    # 运维 (4个)
    ("get_resource_usage", "GET", {}),
    ("list_services", "GET", {}),
    ("check_deployment", "GET", {"service": "test"}),
    ("deploy_service", "POST", {"service": "test"}),
    # 性能 (4个)
    ("get_performance_metrics", "GET", {}),
    ("get_memory_profile", "GET", {}),
    ("get_cpu_profile", "GET", {}),
    ("list_profiling_sessions", "GET", {}),
    # 安全 (4个)
    ("get_security_report", "GET", {}),
    ("check_compliance", "POST", {}),
    ("scan_dependencies", "POST", {}),
    ("list_security_policies", "GET", {}),
    # Trae相关 (3个)
    ("trae_stream_capture", "POST", {"content": "test"}),
    ("trae_stream_snapshot", "GET", {}),
    ("trae_monitoring_stats", "GET", {}),
    # 其他 (3个)
    (
        "store_memory",
        "POST",
        {"content": "store_memory测试", "layer": "episodic", "tags": ["test"]},
    ),
    (
        "search_perspective_memories",
        "POST",
        {"observer": "测试者", "subject": "测试对象", "limit": 5},
    ),
    ("delete_memory", "POST", {"memory_id": "test"}),  # 高风险，但测试一下
]

print("=" * 72)
print(f"MCP工具分批测试 - 共{len(TOOLS)}个工具")
print("=" * 72)

risky = {
    "memory_forget",
    "kill_process",
    "stop_command",
    "rollback_deployment",
    "memory_evolve_self",
    "scale_service",
    "tianji_export",
}

BATCH_SIZE = 8
BATCH_REST = 15  # 每批休息15秒

results = []
passed = 0
failed = 0
skipped = 0
not_found = 0

for batch_start in range(0, len(TOOLS), BATCH_SIZE):
    batch = TOOLS[batch_start : batch_start + BATCH_SIZE]
    batch_num = batch_start // BATCH_SIZE + 1
    total_batches = (len(TOOLS) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n--- 第{batch_num}/{total_batches}批 ({len(batch)}个工具) ---")

    for name, method, params in batch:
        if name in risky:
            print(f"  ⏭️  {name} (跳过)")
            skipped += 1
            results.append({"name": name, "status": "skipped"})
            continue

        path = f"/tools/{name}"
        url = f"{BASE}{path}"

        if method == "GET":
            if params:
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                url = f"{url}?{query}"
            ok, resp = http_get(url, timeout=12)
        else:
            ok, resp = http_post(url, params, timeout=12)

        if ok:
            passed += 1
            print(f"  ✅ {name}")
            results.append({"name": name, "status": "passed", "method": method})
        else:
            err = resp.get("error", "unknown")
            if "404" in err or "405" in err:
                not_found += 1
                mark = "❌"
            else:
                mark = "⚠️"
            failed += 1
            print(f"  {mark} {name} - {err}")
            results.append(
                {"name": name, "status": "error", "error": err, "method": method}
            )

        time.sleep(3)

    # 不是最后一批就休息
    if batch_start + BATCH_SIZE < len(TOOLS):
        print(f"  休息{BATCH_REST}秒...")
        time.sleep(BATCH_REST)

print()
print("=" * 72)
print(f"测试完成: ✅ {passed} 通过 | ❌ {failed} 失败 | ⏭️ {skipped} 跳过")
print(f"  未实现(404/405): {not_found} 个")
total_tested = passed + failed
print(f"通过率: {passed / max(1, total_tested) * 100:.1f}%")
print("=" * 72)

# 保存结果
with open(
    r"d:\元初系统\天机v9.1\tests\mcp_batch_test_result.json", "w", encoding="utf-8"
) as f:
    json.dump(
        {
            "total": len(TOOLS),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "not_found": not_found,
            "results": results,
        },
        f,
        ensure_ascii=False,
        indent=2,
    )

print("\n结果已保存到 tests/mcp_batch_test_result.json")
