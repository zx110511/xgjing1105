# -*- coding: utf-8-sig -*-
"""测试全部71个MCP工具（保守间隔3秒，避免压垮服务）"""

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
            body = resp.read().decode("utf-8")
            return True, json.loads(body)
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
            body = resp.read().decode("utf-8")
            return True, json.loads(body)
        return False, {"error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as e:
        return False, {"error": f"HTTP {e.code}"}
    except Exception as e:
        return False, {"error": str(e)}


# 已知的工具路径和方法映射（基于之前的测试经验）
TOOL_MAP = {
    # 记忆类
    "memory_remember": (
        "POST",
        "/tools/memory_remember",
        {
            "content": "测试记忆内容MCP全量测试验证",
            "layer": "episodic",
            "tags": ["test", "mcp"],
        },
    ),
    "memory_recall": ("POST", "/tools/memory_recall", {"query": "测试", "limit": 5}),
    "memory_stats": ("GET", "/tools/memory_stats", {}),
    "memory_capacity": ("GET", "/tools/memory_capacity", {}),
    "memory_consolidate": ("POST", "/tools/memory_consolidate", {}),
    "search_memories": (
        "POST",
        "/tools/search_memories",
        {"query": "测试", "limit": 5},
    ),
    "get_memory": ("GET", "/tools/get_memory", {"memory_id": "test"}),
    "list_memories": ("GET", "/tools/list_memories", {"layer": "episodic", "limit": 5}),
    "memory_forget": ("POST", "/tools/memory_forget", {"memory_id": "test"}),
    # 会话类
    "get_session_digest": (
        "POST",
        "/tools/get_session_digest",
        {"session_key": "test-session-001"},
    ),
    "build_working_representation": (
        "POST",
        "/tools/build_working_representation",
        {"session_key": "test-session-001"},
    ),
    # 天机工具类
    "tianji_health": ("GET", "/tools/tianji_health", {}),
    "tianji_help": ("GET", "/tools/tianji_help", {}),
    "tianji_classify": ("POST", "/tools/tianji_classify", {"content": "测试文本分类"}),
    "tianji_auto_tag": (
        "POST",
        "/tools/tianji_auto_tag",
        {"content": "测试自动标签功能"},
    ),
    "tianji_summarize": (
        "POST",
        "/tools/tianji_summarize",
        {"content": "测试摘要生成功能的长文本内容测试"},
    ),
    "tianji_extract_knowledge": (
        "POST",
        "/tools/tianji_extract_knowledge",
        {"content": "测试知识提取"},
    ),
    "tianji_expand_query": ("POST", "/tools/tianji_expand_query", {"query": "测试"}),
    "tianji_semantic_search": (
        "POST",
        "/tools/tianji_semantic_search",
        {"query": "测试", "limit": 5},
    ),
    "tianji_normalize": (
        "POST",
        "/tools/tianji_normalize",
        {"content": "测试 规范化 处理"},
    ),
    "tianji_disambiguate": (
        "POST",
        "/tools/tianji_disambiguate",
        {"content": "苹果", "context": "我喜欢吃苹果"},
    ),
    "tianji_intercept": ("POST", "/tools/tianji_intercept", {"content": "测试拦截"}),
    "tianji_export": ("POST", "/tools/tianji_export", {"layer": "episodic"}),
    "tianji_summarize_conversation": (
        "POST",
        "/tools/tianji_summarize_conversation",
        {"session_key": "test"},
    ),
    "tianji_tool_owner": (
        "GET",
        "/tools/tianji_tool_owner",
        {"tool_name": "memory_remember"},
    ),
    "tianji_amim_status": ("GET", "/tools/tianji_amim_status", {}),
    "tianji_operation_header": ("GET", "/tools/tianji_operation_header", {}),
    # 图与进化类
    "memory_build_graph": ("POST", "/tools/memory_build_graph", {}),
    "memory_query_graph": ("POST", "/tools/memory_query_graph", {"query": "测试"}),
    "memory_evolve_self": ("POST", "/tools/memory_evolve_self", {}),
    "memory_learn_skill": ("POST", "/tools/memory_learn_skill", {"skill_name": "test"}),
    "memory_capture_multimodal": (
        "POST",
        "/tools/memory_capture_multimodal",
        {"content": "测试"},
    ),
    "explain_memory_lineage": (
        "POST",
        "/tools/explain_memory_lineage",
        {"memory_id": "test"},
    ),
    # 智能体调度类
    "context_extract": (
        "POST",
        "/tools/context_extract",
        {"content": "测试上下文提取"},
    ),
    "agent_dispatch": ("POST", "/tools/agent_dispatch", {"task": "测试任务"}),
    "system_status": ("GET", "/tools/system_status", {}),
    "rule_evaluate": ("POST", "/tools/rule_evaluate", {"rule": "test"}),
    # 命令执行类
    "execute_command": ("POST", "/tools/execute_command", {"command": "echo hello"}),
    "check_command": ("GET", "/tools/check_command", {"command_id": "test"}),
    "stop_command": ("POST", "/tools/stop_command", {"command_id": "test"}),
    # 进程类
    "list_processes": ("GET", "/tools/list_processes", {}),
    "get_process_info": ("GET", "/tools/get_process_info", {"pid": 1}),
    "kill_process": ("POST", "/tools/kill_process", {"pid": 1}),
    # 脚本类
    "run_script": ("POST", "/tools/run_script", {"script": "test"}),
    "get_script_status": ("GET", "/tools/get_script_status", {"script_id": "test"}),
    "list_scripts": ("GET", "/tools/list_scripts", {}),
    # 运维类
    "deploy_service": ("POST", "/tools/deploy_service", {"service": "test"}),
    "check_deployment": ("GET", "/tools/check_deployment", {"service": "test"}),
    "rollback_deployment": ("POST", "/tools/rollback_deployment", {"service": "test"}),
    "get_resource_usage": ("GET", "/tools/get_resource_usage", {}),
    "scale_service": (
        "POST",
        "/tools/scale_service",
        {"service": "test", "replicas": 2},
    ),
    "list_services": ("GET", "/tools/list_services", {}),
    # 性能类
    "profile_function": ("POST", "/tools/profile_function", {"function": "test"}),
    "get_performance_metrics": ("GET", "/tools/get_performance_metrics", {}),
    "analyze_bottleneck": ("POST", "/tools/analyze_bottleneck", {}),
    "get_memory_profile": ("GET", "/tools/get_memory_profile", {}),
    "get_cpu_profile": ("GET", "/tools/get_cpu_profile", {}),
    "list_profiling_sessions": ("GET", "/tools/list_profiling_sessions", {}),
    # 安全类
    "scan_vulnerabilities": ("POST", "/tools/scan_vulnerabilities", {}),
    "check_compliance": ("POST", "/tools/check_compliance", {}),
    "get_security_report": ("GET", "/tools/get_security_report", {}),
    "scan_dependencies": ("POST", "/tools/scan_dependencies", {}),
    "check_permissions": ("POST", "/tools/check_permissions", {}),
    "list_security_policies": ("GET", "/tools/list_security_policies", {}),
    # 其他
    "store_memory": (
        "POST",
        "/tools/store_memory",
        {"content": "测试存储记忆", "layer": "episodic", "tags": ["test"]},
    ),
    "delete_memory": ("POST", "/tools/delete_memory", {"memory_id": "test"}),
    "search_perspective_memories": (
        "POST",
        "/tools/search_perspective_memories",
        {"observer": "测试者", "subject": "测试对象", "limit": 5},
    ),
    "tool_help": ("GET", "/tools/tool_help", {}),
    "tool_schema": ("GET", "/tools/tool_schema", {"tool_name": "memory_remember"}),
    # Trae相关
    "trae_stream_capture": ("POST", "/tools/trae_stream_capture", {"content": "test"}),
    "trae_stream_snapshot": ("GET", "/tools/trae_stream_snapshot", {}),
    "trae_monitoring_stats": ("GET", "/tools/trae_monitoring_stats", {}),
    # 反思循环
    "run_reflective_cycle": ("POST", "/tools/run_reflective_cycle", {}),
}

print("=" * 72)
print("MCP全部71个工具测试（基于托盘运行真实数据）")
print("=" * 72)

# 先获取工具列表
print("\n[1/3] 获取工具列表...")
ok, result = http_get(f"{BASE}/tools/tool_help", timeout=15)
if not ok:
    print(f"❌ 获取工具列表失败: {result}")
    exit(1)

tool_names = result.get("tools", [])
print(f"✅ 共 {len(tool_names)} 个工具")
time.sleep(2)

# 高风险工具跳过
risky = {
    "memory_forget",
    "delete_memory",
    "kill_process",
    "stop_command",
    "rollback_deployment",
    "memory_evolve_self",
    "deploy_service",
    "scale_service",
    "tianji_export",
}

print(f"\n[2/3] 逐个测试 {len(tool_names)} 个工具（间隔3秒）...")
print()

results = []
passed = 0
failed = 0
skipped = 0
not_found = 0

for i, name in enumerate(tool_names):
    if name in risky:
        print(f"  [{i + 1:3d}/71] ⏭️  {name} (跳过: 高风险)")
        skipped += 1
        results.append({"name": name, "status": "skipped", "reason": "高风险"})
        time.sleep(1)
        continue

    # 从TOOL_MAP获取配置
    if name in TOOL_MAP:
        method, path, params = TOOL_MAP[name]
    else:
        # 默认尝试POST
        method = "POST"
        path = f"/tools/{name}"
        params = {"content": f"测试{name}功能"}

    url = f"{BASE}{path}"

    # 执行请求
    if method == "GET":
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            url = f"{url}?{query}"
        ok, resp = http_get(url, timeout=15)
    else:
        ok, resp = http_post(url, params, timeout=15)

    if ok:
        passed += 1
        print(f"  [{i + 1:3d}/71] ✅ {name}")
        results.append({"name": name, "status": "passed", "method": method})
    else:
        err = resp.get("error", "unknown")
        if "404" in err:
            not_found += 1
            status = "not_implemented"
            mark = "❌"
        elif "405" in err:
            not_found += 1
            status = "wrong_method"
            mark = "❌"
        else:
            status = "error"
            mark = "⚠️"
        failed += 1
        print(f"  [{i + 1:3d}/71] {mark} {name} - {err}")
        results.append({"name": name, "status": status, "error": err, "method": method})

    time.sleep(3)  # 保守间隔

print()
print("=" * 72)
print(f"测试完成: ✅ {passed} 通过 | ❌ {failed} 失败 | ⏭️ {skipped} 跳过")
print(f"  其中未实现(404/405): {not_found} 个")
print(f"通过率(含未实现): {passed / (passed + failed) * 100:.1f}%")
print(f"通过率(已实现): {passed / max(1, passed + failed - not_found) * 100:.1f}%")
print("=" * 72)

# 列出失败的工具
if failed > 0:
    print("\n失败的工具:")
    for r in results:
        if r["status"] != "passed" and r["status"] != "skipped":
            print(f"  - {r['name']}: {r.get('error', r['status'])} [{r['method']}]")

# 保存结果
with open(
    r"d:\元初系统\天机v9.1\tests\mcp_71_tools_final_result.json", "w", encoding="utf-8"
) as f:
    json.dump(
        {
            "total": len(tool_names),
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

print("\n结果已保存到 tests/mcp_71_tools_final_result.json")
