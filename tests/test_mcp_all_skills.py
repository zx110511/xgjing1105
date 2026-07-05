# -*- coding: utf-8-sig -*-
"""
天机v9.1 MCP全部技能测试脚本
====================================
测试6个MCP Server的全部工具，生成测试报告。

MCP Server清单:
  1. memory-engine-global   (39个工具)  - 记忆引擎
  2. agent-framework-global  (5个工具)  - Agent调度框架
  3. command-executor        (9个工具)  - 命令执行器
  4. security-scanner        (6个工具)  - 安全扫描
  5. performance-profiler    (6个工具)  - 性能剖析
  6. ops-engine              (6个工具)  - 运维引擎

总计: 71个工具
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# 确保项目根目录在sys.path中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TIANJI_API_URL = "http://127.0.0.1:8771"

# ======================================================================
# 工具列表定义
# ======================================================================

MEMORY_TOOLS = [
    "memory_remember",
    "memory_recall",
    "memory_forget",
    "memory_stats",
    "memory_capacity",
    "memory_consolidate",
    "search_memories",
    "tianji_semantic_search",
    "tianji_expand_query",
    "tianji_classify",
    "tianji_auto_tag",
    "tianji_summarize",
    "tianji_extract_knowledge",
    "memory_build_graph",
    "memory_query_graph",
    "build_working_representation",
    "tianji_intercept",
    "context_extract",
    "tianji_normalize",
    "tianji_disambiguate",
    "tianji_health",
    "tianji_help",
    "system_status",
    "tianji_tool_owner",
    "rule_evaluate",
    "get_session_digest",
    "tianji_summarize_conversation",
    "explain_memory_lineage",
    "tianji_export",
    "list_memories",
    "get_memory",
    "agent_dispatch",
    "memory_learn_skill",
    "memory_capture_multimodal",
    "run_reflective_cycle",
    "memory_update",
    "search_quick",
    "memory_insert",
    "memory_replace",
    "memory_rethink",
    "memory_share",
    "memory_recall_shared",
    "memory_list_shared",
]

AGENT_FRAMEWORK_TOOLS = [
    "context_extract",
    "agent_dispatch",
    "system_status",
    "rule_evaluate",
    "pipeline_create",
]

COMMAND_TOOLS = [
    "execute_command",
    "check_command",
    "stop_command",
    "list_processes",
    "get_process_info",
    "kill_process",
    "run_script",
    "get_script_status",
    "list_scripts",
]

SECURITY_TOOLS = [
    "scan_vulnerabilities",
    "check_compliance",
    "get_security_report",
    "scan_dependencies",
    "check_permissions",
    "list_security_policies",
]

PERFORMANCE_TOOLS = [
    "profile_function",
    "get_performance_metrics",
    "analyze_bottleneck",
    "get_memory_profile",
    "get_cpu_profile",
    "list_profiling_sessions",
]

OPS_TOOLS = [
    "deploy_service",
    "check_deployment",
    "rollback_deployment",
    "get_resource_usage",
    "scale_service",
    "list_services",
]

ALL_SERVERS = {
    "memory-engine-global": MEMORY_TOOLS,
    "agent-framework-global": AGENT_FRAMEWORK_TOOLS,
    "command-executor": COMMAND_TOOLS,
    "security-scanner": SECURITY_TOOLS,
    "performance-profiler": PERFORMANCE_TOOLS,
    "ops-engine": OPS_TOOLS,
}

# ======================================================================
# 测试参数配置
# ======================================================================

TEST_PARAMS = {
    # memory-engine-global
    "memory_remember": {
        "content": "MCP测试记忆条目 - 测试用",
        "layer": "working",
        "tags": ["test", "mcp"],
        "priority": "low",
    },
    "memory_recall": {"query": "天机", "limit": 3},
    "memory_forget": {"entry_id": "test-001"},
    "memory_stats": {},
    "memory_capacity": {},
    "memory_consolidate": {},
    "search_memories": {"query": "测试", "limit": 3},
    "tianji_semantic_search": {"query": "记忆系统", "limit": 3},
    "tianji_expand_query": {"query": "创作"},
    "tianji_classify": {"text": "这是一个测试文本，用于分类验证。"},
    "tianji_auto_tag": {"content": "记忆系统测试内容，包含智能体调度"},
    "tianji_summarize": {
        "content": "天机系统是一个分布式自进化记忆智能体系统。它支持六层记忆架构，包括Sensory、Working、Short-Term、Episodic、Semantic和Meta层。系统提供MCP接口，支持多Agent协作。",
        "max_length": 50,
    },
    "tianji_extract_knowledge": {
        "content": "Python是一种高级编程语言，由Guido van Rossum于1991年创建。",
        "knowledge_type": "entities",
    },
    "memory_build_graph": {"max_nodes": 10},
    "memory_query_graph": {"query": "Agent", "depth": 2},
    "build_working_representation": {
        "session_id": "test-session-001",
        "context": "测试上下文",
    },
    "tianji_intercept": {"user_input": "测试拦截", "context": {}},
    "context_extract": {"user_input": "帮我写一个Python脚本，实现文件读取功能"},
    "tianji_normalize": {"text": "测试文本 规范化处理"},
    "tianji_disambiguate": {"word": "苹果", "context": "我喜欢吃苹果"},
    "tianji_health": {},
    "tianji_help": {},
    "system_status": {},
    "tianji_tool_owner": {"tool_name": "memory_remember"},
    "rule_evaluate": {"rule_id": "test", "context": {}},
    "get_session_digest": {"session_id": "test-session"},
    "tianji_summarize_conversation": {
        "messages": [{"role": "user", "content": "你好"}]
    },
    "explain_memory_lineage": {"memory_id": "test-mem-001"},
    "tianji_export": {"format": "json", "limit": 5},
    "list_memories": {"layer": "working", "limit": 5},
    "get_memory": {"entry_id": "test-mem-001"},
    "agent_dispatch": {"task_type": "代码审查", "task_data": {}, "priority": "medium"},
    "memory_learn_skill": {"skill_name": "test-skill", "skill_description": "测试技能"},
    "memory_capture_multimodal": {
        "content_type": "text",
        "content": "多模态测试内容",
        "tags": ["test"],
    },
    "run_reflective_cycle": {"cycle_type": "quick", "context": {}},
    "memory_update": {"entry_id": "test-001", "updates": {"content": "更新后的内容"}},
    "search_quick": {"query": "测试", "limit": 5},
    "memory_insert": {"content": "插入测试", "layer": "working"},
    "memory_replace": {"entry_id": "test-001", "content": "替换内容"},
    "memory_rethink": {"entry_id": "test-001", "reflection": "反思内容"},
    "memory_share": {"entry_id": "test-001", "shared_with": ["agent1"]},
    "memory_recall_shared": {"query": "测试"},
    "memory_list_shared": {},
    # agent-framework-global
    "context_extract": {"user_input": "帮我分析这段代码的问题"},
    "agent_dispatch": {"task_type": "代码优化", "priority": "medium"},
    "system_status": {},
    "rule_evaluate": {"rule_id": "quality", "context": {}},
    "pipeline_create": {
        "pipeline_type": "development",
        "stages": ["analyze", "execute"],
    },
    # command-executor
    "execute_command": {"command": "echo test", "timeout": 10},
    "check_command": {"command_id": "test-cmd-001"},
    "stop_command": {"command_id": "test-cmd-001"},
    "list_processes": {"filter": "python"},
    "get_process_info": {"pid": 0},
    "kill_process": {"pid": 0},
    "run_script": {"script_path": "", "args": []},
    "get_script_status": {"script_id": "test-script-001"},
    "list_scripts": {},
    # security-scanner
    "scan_vulnerabilities": {
        "target_path": str(PROJECT_ROOT / "core"),
        "scan_type": "quick",
        "severity": "medium",
    },
    "check_compliance": {
        "standard": "owasp",
        "target_path": str(PROJECT_ROOT / "core"),
    },
    "get_security_report": {"report_type": "summary", "format": "json"},
    "scan_dependencies": {"target_path": str(PROJECT_ROOT), "include_dev": True},
    "check_permissions": {"target_path": str(PROJECT_ROOT), "check_type": "all"},
    "list_security_policies": {"policy_type": "all"},
    # performance-profiler
    "profile_function": {
        "module_path": "core.shared.mcp_bridge",
        "function_name": "TianjiMCPBridge",
        "duration": 5,
    },
    "get_performance_metrics": {"metric_type": "all", "time_range": "1h"},
    "analyze_bottleneck": {"target": "all", "threshold": 0.8},
    "get_memory_profile": {"top_n": 10},
    "get_cpu_profile": {"top_n": 10},
    "list_profiling_sessions": {},
    # ops-engine
    "deploy_service": {
        "service_name": "test-service",
        "environment": "dev",
        "config": {},
    },
    "check_deployment": {"service_name": "test-service"},
    "rollback_deployment": {"service_name": "test-service"},
    "get_resource_usage": {},
    "scale_service": {"service_name": "test-service", "replicas": 2},
    "list_services": {},
}

# ======================================================================
# 测试辅助函数
# ======================================================================


def api_call(
    path: str, data: dict = None, method: str = "POST", timeout: int = 15
) -> tuple[bool, Any]:
    """调用天机API"""
    url = f"{TIANJI_API_URL}{path}"
    try:
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method=method,
            )
        else:
            req = urllib.request.Request(url, method=method)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8-sig", errors="replace"))
            return True, result
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8-sig", errors="replace")
            return False, f"HTTP {e.code}: {body[:200]}"
        except Exception:
            return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def test_tool_via_api(server_name: str, tool_name: str) -> dict[str, Any]:
    """通过API测试单个工具"""
    params = TEST_PARAMS.get(tool_name, {})
    start_time = time.time()

    # 优先使用 /api/mcp/tools/{tool_name} 接口
    api_path = f"/api/mcp/tools/{tool_name}"

    try:
        ok, result = api_call(api_path, params, method="POST", timeout=20)
        elapsed = time.time() - start_time

        status = "pass" if ok else "fail"
        error_msg = "" if ok else str(result)

        return {
            "server": server_name,
            "tool": tool_name,
            "status": status,
            "elapsed_ms": round(elapsed * 1000, 2),
            "error": error_msg,
            "result_preview": str(result)[:200] if ok else "",
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "server": server_name,
            "tool": tool_name,
            "status": "error",
            "elapsed_ms": round(elapsed * 1000, 2),
            "error": str(e),
            "result_preview": "",
        }


# ======================================================================
# 主测试流程
# ======================================================================


def run_all_tests() -> dict[str, Any]:
    """运行全部测试"""
    print("=" * 70)
    print("  天机v9.1 MCP全部技能测试")
    print("=" * 70)
    print()

    # 1. 服务健康检查
    print("[1/6] 检查天机服务状态...")
    ok, health = api_call("/api/health", method="GET", timeout=5)
    if not ok:
        print(f"  ❌ 天机服务未运行: {health}")
        return {"error": "service_not_running"}
    print(
        f"  ✅ 服务运行中 (engine_ready={health.get('engine_ready')}, version={health.get('version')})"
    )
    print()

    # 2. 获取MCP工具清单
    print("[2/6] 获取MCP工具清单...")
    ok, mcp_tools = api_call("/api/mcp/tools", method="GET", timeout=5)
    if ok and isinstance(mcp_tools, list):
        print(f"  ✅ 检测到 {len(mcp_tools)} 个MCP工具")
    else:
        print("  ⚠️  无法获取工具清单，使用预定义列表")
        mcp_tools = []
    print()

    # 3. 逐个Server测试
    all_results = []
    server_stats = {}

    for server_idx, (server_name, tool_list) in enumerate(ALL_SERVERS.items(), 3):
        print(f"[{server_idx}/8] 测试 {server_name} ({len(tool_list)}个工具)...")
        print()

        server_results = []
        passed = 0
        failed = 0
        skipped = 0

        for tool_name in tool_list:
            result = test_tool_via_api(server_name, tool_name)
            server_results.append(result)
            all_results.append(result)

            status_icon = (
                "✅"
                if result["status"] == "pass"
                else "❌"
                if result["status"] == "fail"
                else "⚠️"
            )
            status_text = (
                "PASS"
                if result["status"] == "pass"
                else "FAIL"
                if result["status"] == "fail"
                else "ERR"
            )
            elapsed = result["elapsed_ms"]

            print(
                f"  {status_icon} [{status_text}] {tool_name:<35} {elapsed:>8.1f}ms",
                end="",
            )
            if result["status"] != "pass":
                print(f"  - {result['error'][:60]}", end="")
            print()

            if result["status"] == "pass":
                passed += 1
            elif result["status"] == "fail":
                failed += 1
            else:
                skipped += 1

        total = len(tool_list)
        pass_rate = (passed / total * 100) if total > 0 else 0
        server_stats[server_name] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": round(pass_rate, 2),
        }

        print()
        print(f"  统计: {passed}/{total} 通过 ({pass_rate:.1f}%)")
        print()

    # 4. 生成汇总报告
    print("[8/8] 生成测试报告...")
    print()

    total_tools = sum(s["total"] for s in server_stats.values())
    total_passed = sum(s["passed"] for s in server_stats.values())
    total_failed = sum(s["failed"] for s in server_stats.values())
    overall_rate = (total_passed / total_tools * 100) if total_tools > 0 else 0

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "service_health": health,
        "total_tools": total_tools,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "overall_pass_rate": round(overall_rate, 2),
        "server_stats": server_stats,
        "results": all_results,
    }

    # 打印汇总
    print("=" * 70)
    print("  测试结果汇总")
    print("=" * 70)
    print()
    print(f"  总工具数: {total_tools}")
    print(f"  通过: {total_passed}")
    print(f"  失败: {total_failed}")
    print(f"  通过率: {overall_rate:.2f}%")
    print()

    for server_name, stats in server_stats.items():
        bar_len = 30
        filled = int(stats["pass_rate"] / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(
            f"  {server_name:<28} {bar} {stats['pass_rate']:>5.1f}%  ({stats['passed']}/{stats['total']})"
        )

    print()
    print("=" * 70)

    # 保存报告
    report_path = PROJECT_ROOT / "tests" / "mcp_test_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  详细报告已保存: {report_path}")
    print()

    return report


# ======================================================================
# 主入口
# ======================================================================

if __name__ == "__main__":
    report = run_all_tests()
    if "error" in report:
        sys.exit(1)
    sys.exit(0 if report["overall_pass_rate"] >= 50 else 1)
