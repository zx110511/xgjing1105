# -*- coding: utf-8-sig -*-
"""
天机v9.1 MCP全部技能测试脚本 v2
====================================
基于实际API路由定义测试全部MCP工具。

API路径基准: /api/mcp/tools/{tool_name}
命名规范: snake_case (下划线命名)
请求方法: POST为主，list类工具为GET
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TIANJI_API_URL = "http://127.0.0.1:8771"

# ======================================================================
# 实际MCP工具清单 (从API路由提取)
# ======================================================================

# 工具定义: {name: {"method": "POST"/"GET", "params": {...}, "category": "xxx"}}
MCP_TOOLS = {
    # ===== Memory类 (记忆引擎) =====
    "store_memory": {
        "method": "POST",
        "params": {
            "content": "MCP测试记忆 - store_memory",
            "layer": "working",
            "tags": ["test", "mcp"],
            "priority": "low",
        },
        "category": "memory",
    },
    "search_memories": {
        "method": "POST",
        "params": {"query": "天机", "limit": 3},
        "category": "memory",
    },
    "get_memory": {
        "method": "POST",
        "params": {"memory_id": "test-mem-001"},
        "category": "memory",
    },
    "list_memories": {
        "method": "POST",
        "params": {"layer": "working", "limit": 5},
        "category": "memory",
    },
    "delete_memory": {
        "method": "POST",
        "params": {"memory_id": "test-mem-001"},
        "category": "memory",
    },
    "list_namespaces": {"method": "GET", "params": {}, "category": "memory"},
    "get_stats": {"method": "GET", "params": {}, "category": "memory"},
    # ===== Session类 (会话管理) =====
    "get_session_digest": {
        "method": "POST",
        "params": {"session_key": "test-session-001"},
        "category": "session",
    },
    "run_reflective_cycle": {
        "method": "POST",
        "params": {"cycle_type": "quick"},
        "category": "session",
    },
    "explain_memory_lineage": {
        "method": "POST",
        "params": {"memory_id": "test-mem-001"},
        "category": "session",
    },
    "build_working_representation": {
        "method": "POST",
        "params": {"query": "测试构建工作表示", "context": "测试上下文"},
        "category": "session",
    },
    # ===== Search类 (搜索增强) =====
    "search_perspective_memories": {
        "method": "POST",
        "params": {"observer": "用户", "subject": "天机系统", "limit": 5},
        "category": "search",
    },
    # ===== LLM工具类 (AI能力) =====
    "classify": {
        "method": "POST",
        "params": {"content": "这是一个测试文本，用于分类验证功能是否正常工作。"},
        "category": "llm",
    },
    "auto_tag": {
        "method": "POST",
        "params": {"content": "记忆系统测试内容，包含智能体调度和知识图谱。"},
        "category": "llm",
    },
    "summarize": {
        "method": "POST",
        "params": {
            "content": "天机系统是一个分布式自进化记忆智能体系统。它支持六层记忆架构，包括Sensory、Working、Short-Term、Episodic、Semantic和Meta层。系统提供MCP接口，支持多Agent协作。",
            "max_length": 50,
        },
        "category": "llm",
    },
    "extract_knowledge": {
        "method": "POST",
        "params": {
            "content": "Python是一种高级编程语言，由Guido van Rossum于1991年创建。"
        },
        "category": "llm",
    },
    "expand_query": {"method": "POST", "params": {"query": "创作"}, "category": "llm"},
    "assess_value": {
        "method": "POST",
        "params": {"content": "这是一段测试内容，用于价值评估。"},
        "category": "llm",
    },
    "decide_storage": {
        "method": "POST",
        "params": {"content": "这是一段测试内容，用于存储决策。"},
        "category": "llm",
    },
    "normalize": {
        "method": "POST",
        "params": {"content": "测试文本 规范化 处理"},
        "category": "llm",
    },
    "disambiguate": {
        "method": "POST",
        "params": {"content": "苹果", "context": "我喜欢吃苹果"},
        "category": "llm",
    },
    # ===== System类 (系统工具) =====
    "initialize_nexus_system": {"method": "POST", "params": {}, "category": "system"},
    "tool_help": {"method": "GET", "params": {"tool": "all"}, "category": "system"},
    "tool_schema": {"method": "GET", "params": {"tool": "all"}, "category": "system"},
    # ===== Agent Framework类 (智能体框架) =====
    "context_extract": {
        "method": "POST",
        "params": {"user_input": "帮我写一个Python脚本，实现文件读取和写入功能"},
        "category": "agent",
    },
    "rule_evaluate": {
        "method": "POST",
        "params": {"rule_id": "quality", "context": {}},
        "category": "agent",
    },
    "agent_dispatch": {
        "method": "POST",
        "params": {"task_type": "代码审查", "priority": "medium"},
        "category": "agent",
    },
    "system_status": {"method": "GET", "params": {}, "category": "agent"},
    # ===== Command类 (命令执行器) =====
    "execute_command": {
        "method": "POST",
        "params": {"command": "echo test_mcp", "timeout": 10},
        "category": "command",
    },
    "check_command": {
        "method": "POST",
        "params": {"command_id": "test-cmd-001"},
        "category": "command",
    },
    "stop_command": {
        "method": "POST",
        "params": {"command_id": "test-cmd-001"},
        "category": "command",
    },
    "list_processes": {"method": "GET", "params": {}, "category": "command"},
    "get_process_info": {"method": "POST", "params": {"pid": 0}, "category": "command"},
    "kill_process": {"method": "POST", "params": {"pid": 0}, "category": "command"},
    "run_script": {
        "method": "POST",
        "params": {"script_path": "", "args": []},
        "category": "command",
    },
    "get_script_status": {
        "method": "POST",
        "params": {"script_id": "test-script-001"},
        "category": "command",
    },
    "list_scripts": {"method": "GET", "params": {}, "category": "command"},
    # ===== Security类 (安全扫描) =====
    "scan_vulnerabilities": {
        "method": "POST",
        "params": {"target_path": str(PROJECT_ROOT / "core"), "scan_type": "quick"},
        "category": "security",
    },
    "check_compliance": {
        "method": "POST",
        "params": {"standard": "owasp", "target_path": str(PROJECT_ROOT / "core")},
        "category": "security",
    },
    "get_security_report": {"method": "GET", "params": {}, "category": "security"},
    "scan_dependencies": {
        "method": "POST",
        "params": {"target_path": str(PROJECT_ROOT)},
        "category": "security",
    },
    "check_permissions": {
        "method": "POST",
        "params": {"target_path": str(PROJECT_ROOT)},
        "category": "security",
    },
    "list_security_policies": {"method": "GET", "params": {}, "category": "security"},
    # ===== Performance类 (性能剖析) =====
    "profile_function": {
        "method": "POST",
        "params": {
            "module_path": "core.shared.mcp_bridge",
            "function_name": "TianjiMCPBridge",
            "duration": 5,
        },
        "category": "performance",
    },
    "get_performance_metrics": {
        "method": "GET",
        "params": {},
        "category": "performance",
    },
    "analyze_bottleneck": {
        "method": "POST",
        "params": {"target": "all", "threshold": 0.8},
        "category": "performance",
    },
    "get_memory_profile": {"method": "GET", "params": {}, "category": "performance"},
    "get_cpu_profile": {"method": "GET", "params": {}, "category": "performance"},
    "list_profiling_sessions": {
        "method": "GET",
        "params": {},
        "category": "performance",
    },
    # ===== Ops类 (运维引擎) =====
    "deploy_service": {
        "method": "POST",
        "params": {"service_name": "test-service", "environment": "dev"},
        "category": "ops",
    },
    "check_deployment": {
        "method": "POST",
        "params": {"service_name": "test-service"},
        "category": "ops",
    },
    "rollback_deployment": {
        "method": "POST",
        "params": {"service_name": "test-service"},
        "category": "ops",
    },
    "get_resource_usage": {"method": "GET", "params": {}, "category": "ops"},
    "scale_service": {
        "method": "POST",
        "params": {"service_name": "test-service", "replicas": 2},
        "category": "ops",
    },
    "list_services": {"method": "GET", "params": {}, "category": "ops"},
}

# 按类别分组
CATEGORY_GROUPS = {
    "记忆引擎 (memory-engine)": [
        "store_memory",
        "search_memories",
        "get_memory",
        "list_memories",
        "delete_memory",
        "list_namespaces",
        "get_stats",
    ],
    "会话管理 (session)": [
        "get_session_digest",
        "run_reflective_cycle",
        "explain_memory_lineage",
        "build_working_representation",
        "search_perspective_memories",
    ],
    "LLM智能工具 (llm-tools)": [
        "classify",
        "auto_tag",
        "summarize",
        "extract_knowledge",
        "expand_query",
        "assess_value",
        "decide_storage",
        "normalize",
        "disambiguate",
    ],
    "系统工具 (system)": ["initialize_nexus_system", "tool_help", "tool_schema"],
    "Agent框架 (agent-framework)": [
        "context_extract",
        "rule_evaluate",
        "agent_dispatch",
        "system_status",
    ],
    "命令执行器 (command-executor)": [
        "execute_command",
        "check_command",
        "stop_command",
        "list_processes",
        "get_process_info",
        "kill_process",
        "run_script",
        "get_script_status",
        "list_scripts",
    ],
    "安全扫描 (security-scanner)": [
        "scan_vulnerabilities",
        "check_compliance",
        "get_security_report",
        "scan_dependencies",
        "check_permissions",
        "list_security_policies",
    ],
    "性能剖析 (performance-profiler)": [
        "profile_function",
        "get_performance_metrics",
        "analyze_bottleneck",
        "get_memory_profile",
        "get_cpu_profile",
        "list_profiling_sessions",
    ],
    "运维引擎 (ops-engine)": [
        "deploy_service",
        "check_deployment",
        "rollback_deployment",
        "get_resource_usage",
        "scale_service",
        "list_services",
    ],
}


def api_call(
    path: str, data: dict = None, method: str = "POST", timeout: int = 20
) -> tuple[bool, Any]:
    """调用天机API"""
    url = f"{TIANJI_API_URL}{path}"
    try:
        if method == "GET" and data:
            query_string = "&".join(f"{k}={v}" for k, v in data.items() if v)
            if query_string:
                url = f"{url}?{query_string}"
            req = urllib.request.Request(url, method="GET")
        elif method == "GET":
            req = urllib.request.Request(url, method="GET")
        else:
            body = json.dumps(data or {}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method=method,
            )

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


def test_tool(tool_name: str, tool_def: dict) -> dict[str, Any]:
    """测试单个MCP工具"""
    method = tool_def["method"]
    params = tool_def["params"]
    start_time = time.time()

    api_path = f"/api/mcp/tools/{tool_name}"

    try:
        ok, result = api_call(api_path, params, method=method, timeout=20)
        elapsed = time.time() - start_time

        status = "pass" if ok else "fail"
        error_msg = "" if ok else str(result)

        result_str = str(result) if ok else ""
        if len(result_str) > 150:
            result_str = result_str[:150] + "..."

        return {
            "tool": tool_name,
            "method": method,
            "category": tool_def["category"],
            "status": status,
            "elapsed_ms": round(elapsed * 1000, 2),
            "error": error_msg,
            "result_preview": result_str,
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "tool": tool_name,
            "method": method,
            "category": tool_def["category"],
            "status": "error",
            "elapsed_ms": round(elapsed * 1000, 2),
            "error": str(e),
            "result_preview": "",
        }


def run_all_tests() -> dict[str, Any]:
    """运行全部测试"""
    print()
    print("=" * 72)
    print("  天机v9.1 MCP全部技能综合测试 v2.0")
    print("=" * 72)
    print()

    # 1. 服务健康检查
    print("[Stage 1] 检查天机服务状态...")
    ok, health = api_call("/api/health", method="GET", timeout=5)
    if not ok:
        print(f"  ❌ 天机服务未运行: {health}")
        return {"error": "service_not_running"}
    print(
        f"  ✅ 服务运行中 (engine_ready={health.get('engine_ready')}, version={health.get('version')})"
    )
    print()

    # 2. 获取MCP工具清单
    print("[Stage 2] 获取MCP工具清单...")
    ok, mcp_root = api_call("/api/mcp/", method="GET", timeout=5)
    api_tool_count = 0
    if ok and isinstance(mcp_root, dict):
        categories = mcp_root.get("categories", [])
        for cat in categories:
            api_tool_count += len(cat.get("tools", []))
        print(
            f"  ✅ 检测到 {len(categories)} 个分类, 共 {api_tool_count} 个工具 (API声明)"
        )
    else:
        print("  ⚠️  无法获取工具清单")
    print(f"  📋 测试脚本定义: {len(MCP_TOOLS)} 个工具")
    print()

    # 3. 按类别测试
    all_results = []
    category_stats = {}
    stage_num = 3

    for cat_name, tool_list in CATEGORY_GROUPS.items():
        print(f"[Stage {stage_num}] 测试 {cat_name} ({len(tool_list)}个工具)...")
        print()

        cat_results = []
        passed = 0
        failed = 0
        errors = 0

        for tool_name in tool_list:
            if tool_name not in MCP_TOOLS:
                print(f"  ⚠️  未定义工具: {tool_name}, 跳过")
                continue

            tool_def = MCP_TOOLS[tool_name]
            result = test_tool(tool_name, tool_def)
            cat_results.append(result)
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
            method_pad = result["method"].ljust(4)
            elapsed = result["elapsed_ms"]

            print(
                f"  {status_icon} [{status_text}] [{method_pad}] {tool_name:<32} {elapsed:>8.1f}ms",
                end="",
            )
            if result["status"] != "pass":
                err_short = result["error"][:55].replace("\n", " ")
                print(f"  - {err_short}", end="")
            print()

            if result["status"] == "pass":
                passed += 1
            elif result["status"] == "fail":
                failed += 1
            else:
                errors += 1

        total = len(tool_list)
        pass_rate = (passed / total * 100) if total > 0 else 0
        category_stats[cat_name] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": round(pass_rate, 2),
        }

        print()
        print(f"  📊 {passed}/{total} 通过 ({pass_rate:.1f}%)")
        print()
        stage_num += 1

    # 4. 汇总报告
    total_tools = len(all_results)
    total_passed = sum(s["passed"] for s in category_stats.values())
    total_failed = sum(s["failed"] for s in category_stats.values())
    total_errors = sum(s["errors"] for s in category_stats.values())
    overall_rate = (total_passed / total_tools * 100) if total_tools > 0 else 0

    # 失败工具列表
    failed_tools = [r for r in all_results if r["status"] != "pass"]

    print(f"[Stage {stage_num}] 生成测试报告...")
    print()

    print("=" * 72)
    print("  📊 测试结果总览")
    print("=" * 72)
    print()
    print(f"  工具总数:     {total_tools}")
    print(f"  ✅ 通过:      {total_passed}")
    print(f"  ❌ 失败:      {total_failed}")
    print(f"  ⚠️  错误:      {total_errors}")
    print(f"  📈 通过率:    {overall_rate:.2f}%")
    print()

    print("  分类通过率:")
    print()
    for cat_name, stats in category_stats.items():
        bar_len = 30
        filled = int(stats["pass_rate"] / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(
            f"    {cat_name:<34} {bar} {stats['pass_rate']:>5.1f}%  ({stats['passed']}/{stats['total']})"
        )

    print()

    if failed_tools:
        print("  ❌ 失败工具明细:")
        print()
        for r in failed_tools:
            err_short = r["error"][:80].replace("\n", " ")
            print(f"    [{r['category']:<8}] {r['tool']:<28} - {err_short}")
        print()

    print("=" * 72)

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "service_health": health,
        "api_declared_tools": api_tool_count,
        "tested_tools": total_tools,
        "passed": total_passed,
        "failed": total_failed,
        "errors": total_errors,
        "overall_pass_rate": round(overall_rate, 2),
        "category_stats": category_stats,
        "failed_tools": failed_tools,
        "all_results": all_results,
    }

    report_path = PROJECT_ROOT / "tests" / "mcp_test_report_v2.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  📄 详细报告已保存: {report_path}")
    print()

    return report


if __name__ == "__main__":
    report = run_all_tests()
    if "error" in report:
        sys.exit(1)
    sys.exit(0 if report["overall_pass_rate"] >= 50 else 1)
