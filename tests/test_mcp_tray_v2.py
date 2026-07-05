# -*- coding: utf-8-sig -*-
"""
天机v9.1 MCP全部技能测试脚本 - 托盘运行版 v2
==============================================
基于托盘运行的天机真实数据。
测试全部MCP工具 + LLM工具 + 系统工具。
每个工具之间有足够间隔，避免压垮单worker uvicorn。
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TIANJI_API_URL = "http://127.0.0.1:8771"


def api_call(path, data=None, method="POST", timeout=30):
    """API调用封装"""
    url = f"{TIANJI_API_URL}{path}"
    try:
        if method == "GET":
            req = urllib.request.Request(url, method="GET")
        else:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                method=method,
                headers={"Content-Type": "application/json"},
            )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return False, f"HTTP {e.code}: {e.read().decode('utf-8')[:200]}"
        except:
            return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def test_tool(name, method, api_path, params, category):
    """测试单个工具"""
    time.sleep(1.0)  # 工具间间隔
    ok, result = api_call(api_path, params, method=method, timeout=30)
    status = "✅" if ok else "❌"
    detail = ""
    if ok:
        if isinstance(result, dict):
            keys = list(result.keys())[:5]
            detail = f"keys={keys}"
        elif isinstance(result, list):
            detail = f"list(len={len(result)})"
        else:
            detail = f"type={type(result).__name__}"
    else:
        err_str = str(result)
        if len(err_str) > 100:
            err_str = err_str[:100] + "..."
        detail = err_str
    print(f"  {status} [{category}] {name}: {detail}")
    return ok, result


def main():
    print("=" * 72)
    print("  天机v9.1 MCP全部技能综合测试 (托盘运行版 v2)")
    print("=" * 72)
    print()

    # Stage 1: 健康检查
    print("[Stage 1] 检查天机服务状态...")
    ok, health = api_call("/api/health", method="GET", timeout=15)
    if not ok:
        print(f"  ❌ 天机服务未运行: {health}")
        return 1
    print(
        f"  ✅ 服务运行中 (engine_ready={health.get('engine_ready')}, version={health.get('version')})"
    )
    print()

    # Stage 2: 获取MCP工具清单
    print("[Stage 2] 获取MCP工具清单...")
    ok, mcp_data = api_call("/api/mcp/tools", method="GET", timeout=15)
    api_tool_count = 0
    if ok and isinstance(mcp_data, dict):
        tools = mcp_data.get("tools", [])
        api_tool_count = len(tools)
        print(f"  ✅ 检测到 {api_tool_count} 个MCP工具 (API声明)")
    else:
        print("  ⚠️  无法获取MCP工具清单")
    print()

    # Stage 3: 逐个测试所有工具
    print("[Stage 3] 逐个测试全部工具...")
    print()

    test_tools = [
        # ===== Memory类 (MCP工具 - /api/mcp/tools/) =====
        (
            "store_memory",
            "POST",
            "/api/mcp/tools/store_memory",
            {
                "content": "MCP托盘测试记忆 - store_memory测试内容，用于验证记忆写入功能。",
                "layer": "working",
                "tags": ["test", "mcp", "tray"],
                "priority": "low",
            },
            "memory",
        ),
        (
            "search_memories",
            "POST",
            "/api/mcp/tools/search_memories",
            {"query": "天机", "limit": 3},
            "memory",
        ),
        (
            "list_memories",
            "POST",
            "/api/mcp/tools/list_memories",
            {"layer": "working", "limit": 5},
            "memory",
        ),
        ("get_stats", "GET", "/api/mcp/tools/get_stats", {}, "memory"),
        ("list_namespaces", "GET", "/api/mcp/tools/list_namespaces", {}, "memory"),
        ("memory_consolidate", "POST", "/api/mcp/tools/consolidate", {}, "memory"),
        # ===== Session类 (MCP工具) =====
        (
            "get_session_digest",
            "POST",
            "/api/mcp/tools/get_session_digest",
            {"session_key": "test-session-001"},
            "session",
        ),
        (
            "build_working_representation",
            "POST",
            "/api/mcp/tools/build_working_representation",
            {"query": "测试构建工作表示", "context": "测试上下文内容"},
            "session",
        ),
        (
            "run_reflective_cycle",
            "POST",
            "/api/mcp/tools/run_reflective_cycle",
            {"cycle_type": "quick"},
            "session",
        ),
        (
            "explain_memory_lineage",
            "POST",
            "/api/mcp/tools/explain_memory_lineage",
            {"memory_id": "test-mem-001"},
            "session",
        ),
        # ===== Search类 (MCP工具) =====
        (
            "search_perspective_memories",
            "POST",
            "/api/mcp/tools/search_perspective_memories",
            {"observer": "用户", "subject": "天机系统", "limit": 5},
            "search",
        ),
        # ===== LLM类 (API路径: /api/llm/) =====
        (
            "classify",
            "POST",
            "/api/llm/classify",
            {"content": "这是一个测试文本，用于分类验证功能是否正常工作。"},
            "llm",
        ),
        (
            "auto_tag",
            "POST",
            "/api/llm/auto_tag",
            {"content": "记忆系统测试内容，包含智能体调度和知识图谱。"},
            "llm",
        ),
        (
            "summarize",
            "POST",
            "/api/llm/summarize",
            {
                "content": "天机系统是一个分布式自进化记忆智能体系统。它支持六层记忆架构，包括Sensory、Working、Short-Term、Episodic、Semantic和Meta层。",
                "max_length": 50,
            },
            "llm",
        ),
        (
            "extract_knowledge",
            "POST",
            "/api/llm/extract_knowledge",
            {"content": "Python是一种高级编程语言，由Guido van Rossum于1991年创建。"},
            "llm",
        ),
        ("expand_query", "POST", "/api/llm/expand_query", {"query": "创作"}, "llm"),
        (
            "analyze_value",
            "POST",
            "/api/llm/analyze_value",
            {"content": "这是一段测试内容，用于价值评估。"},
            "llm",
        ),
        (
            "decide_storage",
            "POST",
            "/api/llm/decide_storage",
            {"content": "这是一段测试内容，用于存储决策。"},
            "llm",
        ),
        ("llm_status", "GET", "/api/llm/status", {}, "llm"),
        # ===== Agent调度类 =====
        (
            "agent_dispatch",
            "POST",
            "/api/orchestrator/dispatch",
            {"task": "测试任务描述", "complexity": "low"},
            "agent",
        ),
        # ===== 命令执行类 (MCP工具) =====
        (
            "execute_command",
            "POST",
            "/api/mcp/tools/execute_command",
            {"command": "echo hello_tianji_test", "timeout": 10},
            "command",
        ),
        ("list_processes", "GET", "/api/mcp/tools/list_processes", {}, "command"),
        # ===== 安全类 (MCP工具) =====
        (
            "scan_vulnerabilities",
            "POST",
            "/api/mcp/tools/scan_vulnerabilities",
            {"path": str(PROJECT_ROOT / "server")},
            "security",
        ),
        (
            "check_compliance",
            "POST",
            "/api/mcp/tools/check_compliance",
            {"path": str(PROJECT_ROOT / "server")},
            "security",
        ),
        (
            "list_security_policies",
            "GET",
            "/api/mcp/tools/list_security_policies",
            {},
            "security",
        ),
        # ===== 运维类 (MCP工具) =====
        ("list_services", "GET", "/api/mcp/tools/list_services", {}, "ops"),
        # ===== 性能剖析类 (MCP工具) =====
        (
            "list_profiling_sessions",
            "GET",
            "/api/mcp/tools/list_profiling_sessions",
            {},
            "perf",
        ),
        # ===== 系统状态类 =====
        ("system_stats", "GET", "/api/status/system/stats", {}, "system"),
        # ===== 编排器类 =====
        ("orchestrator_agents", "GET", "/api/orchestrator/agents", {}, "orchestrator"),
    ]

    results = []
    for name, method, path, params, category in test_tools:
        ok, _ = test_tool(name, method, path, params, category)
        results.append((name, ok, category))

    print()
    print("=" * 72)
    print("  测试结果汇总")
    print("=" * 72)

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed

    # 按分类统计
    cat_stats = {}
    for name, ok, cat in results:
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "passed": 0}
        cat_stats[cat]["total"] += 1
        if ok:
            cat_stats[cat]["passed"] += 1

    print(f"  总计: {total} 个工具")
    print(f"  通过: {passed} 个 ✅")
    print(f"  失败: {failed} 个 ❌")
    print(f"  通过率: {passed / total * 100:.2f}%")
    print()

    print("  分类统计:")
    for cat, stats in sorted(cat_stats.items()):
        pct = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        mark = "✅" if pct >= 80 else "⚠️" if pct >= 50 else "❌"
        print(f"    {mark} {cat}: {stats['passed']}/{stats['total']} ({pct:.1f}%)")
    print()

    if failed > 0:
        print("  失败工具列表:")
        for name, ok, cat in results:
            if not ok:
                print(f"    ❌ [{cat}] {name}")
        print()

    print("=" * 72)
    print()
    print("  数据来源: 托盘运行的天机v9.1 (端口8771)")
    print("  测试基准: 真实运行数据，非模拟")
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
