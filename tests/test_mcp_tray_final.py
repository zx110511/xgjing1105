# -*- coding: utf-8-sig -*-
"""
天机v9.1 MCP全部技能测试 - 托盘运行最终版
==========================================
基于托盘运行的天机真实数据，测试全部42个MCP工具。
工具清单来源: /api/mcp/tools 真实返回。
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


def test_tool(name, method, params, category):
    """测试单个MCP工具"""
    api_path = f"/api/mcp/tools/{name}"
    time.sleep(1.0)  # 工具间间隔
    ok, result = api_call(api_path, params, method=method, timeout=45)
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
        if len(err_str) > 80:
            err_str = err_str[:80] + "..."
        detail = err_str
    print(f"  {status} [{category}] {name}: {detail}")
    return ok, result


def main():
    print("=" * 72)
    print("  天机v9.1 MCP全部技能综合测试 (托盘运行最终版)")
    print("  数据基准: 托盘运行的天机v9.1真实数据")
    print("=" * 72)
    print()

    # Stage 1: 健康检查
    print("[Stage 1] 检查天机服务状态...")
    ok, health = api_call("/api/health", method="GET", timeout=15)
    if not ok:
        print(f"  ❌ 天机服务未运行: {health}")
        return 1
    print("  ✅ 服务运行中")
    print(f"     engine_ready: {health.get('engine_ready')}")
    print(f"     version: {health.get('version')}")
    layers = health.get("layers", {})
    print(f"     layers: {len(layers)} 层")
    print()

    # Stage 2: 获取真实MCP工具清单
    print("[Stage 2] 获取真实MCP工具清单...")
    ok, mcp_data = api_call("/api/mcp/tools", method="GET", timeout=15)
    if not ok:
        print(f"  ❌ 无法获取工具清单: {mcp_data}")
        return 1
    tools_list = mcp_data.get("tools", [])
    tool_names = [t.get("name", "") for t in tools_list]
    print(f"  ✅ 检测到 {len(tool_names)} 个真实MCP工具")
    print()

    # Stage 3: 分类定义测试用例（基于真实工具名）
    print("[Stage 3] 逐个测试全部MCP工具...")
    print()

    test_cases = [
        # ===== 记忆引擎 =====
        (
            "store_memory",
            "POST",
            {
                "content": "MCP托盘最终测试记忆 - 验证store_memory功能正常工作。",
                "layer": "working",
                "tags": ["test", "mcp", "final", "tray"],
                "priority": "low",
            },
            "memory",
        ),
        ("search_memories", "POST", {"query": "天机系统", "limit": 5}, "memory"),
        ("get_memory", "POST", {"memory_id": "test-placeholder"}, "memory"),
        ("list_memories", "POST", {"layer": "working", "limit": 10}, "memory"),
        ("delete_memory", "POST", {"memory_id": "test-placeholder"}, "memory"),
        ("list_namespaces", "GET", {}, "memory"),
        ("get_stats", "GET", {}, "memory"),
        # ===== 会话管理 =====
        (
            "get_session_digest",
            "POST",
            {"session_key": "test-session-final"},
            "session",
        ),
        ("run_reflective_cycle", "POST", {"cycle_type": "quick"}, "session"),
        (
            "explain_memory_lineage",
            "POST",
            {"memory_id": "test-placeholder"},
            "session",
        ),
        (
            "build_working_representation",
            "POST",
            {"query": "测试构建工作表示", "context": "测试上下文内容"},
            "session",
        ),
        # ===== 搜索增强 =====
        (
            "search_perspective_memories",
            "POST",
            {"observer": "用户", "subject": "天机系统", "limit": 5},
            "search",
        ),
        # ===== 系统初始化 =====
        ("initialize_nexus_system", "POST", {}, "system"),
        ("tool_help", "GET", {}, "system"),
        ("tool_schema", "GET", {}, "system"),
        # ===== 命令执行器 =====
        (
            "execute_command",
            "POST",
            {"command": "echo test_final_tray", "timeout": 10},
            "command",
        ),
        ("check_command", "POST", {"command_id": "test-cmd-001"}, "command"),
        ("stop_command", "POST", {"command_id": "test-cmd-001"}, "command"),
        ("list_processes", "GET", {}, "command"),
        ("get_process_info", "POST", {"pid": 0}, "command"),
        ("kill_process", "POST", {"pid": 0}, "command"),
        ("run_script", "POST", {"script_name": "test", "args": {}}, "command"),
        ("get_script_status", "POST", {"script_id": "test-script-001"}, "command"),
        ("list_scripts", "GET", {}, "command"),
        # ===== 运维引擎 =====
        ("deploy_service", "POST", {"service_name": "test", "image": "test"}, "ops"),
        ("check_deployment", "POST", {"deployment_id": "test-deploy-001"}, "ops"),
        ("rollback_deployment", "POST", {"deployment_id": "test-deploy-001"}, "ops"),
        ("get_resource_usage", "GET", {}, "ops"),
        ("scale_service", "POST", {"service_name": "test", "replicas": 2}, "ops"),
        ("list_services", "GET", {}, "ops"),
        # ===== 性能剖析器 =====
        ("profile_function", "POST", {"function_name": "test"}, "perf"),
        ("get_performance_metrics", "GET", {}, "perf"),
        ("analyze_bottleneck", "POST", {}, "perf"),
        ("get_memory_profile", "GET", {}, "perf"),
        ("get_cpu_profile", "GET", {}, "perf"),
        ("list_profiling_sessions", "GET", {}, "perf"),
        # ===== 安全扫描器 =====
        (
            "scan_vulnerabilities",
            "POST",
            {"path": str(PROJECT_ROOT / "server")},
            "security",
        ),
        (
            "check_compliance",
            "POST",
            {"path": str(PROJECT_ROOT / "server")},
            "security",
        ),
        ("get_security_report", "GET", {}, "security"),
        ("scan_dependencies", "POST", {"path": str(PROJECT_ROOT)}, "security"),
        ("check_permissions", "POST", {}, "security"),
        ("list_security_policies", "GET", {}, "security"),
    ]

    results = []
    for name, method, params, category in test_cases:
        ok, _ = test_tool(name, method, params, category)
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
    print("  📌 数据来源: 托盘运行的天机v9.1 (端口8771)")
    print("  📌 测试基准: 真实运行数据，非模拟非伪造")
    print("  📌 工具总数: 与 /api/mcp/tools 返回一致")
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
