# -*- coding: utf-8-sig -*-
"""
天机v9.1 MCP全部技能测试脚本 - 托盘运行版
============================================
基于托盘运行的天机真实数据，逐个测试MCP工具。
每个工具之间有足够的间隔，避免压垮单worker uvicorn。
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
    time.sleep(1.5)  # 工具间间隔，避免压垮单worker
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
        detail = str(result)[:80]
    print(f"  {status} [{category}] {name}: {detail}")
    return ok, result


def main():
    print("=" * 72)
    print("  天机v9.1 MCP全部技能综合测试 (托盘运行版)")
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

    # Stage 2: MCP工具清单
    print("[Stage 2] 获取MCP工具清单...")
    ok, mcp_data = api_call("/api/mcp/tools", method="GET", timeout=15)
    api_tool_count = 0
    if ok and isinstance(mcp_data, dict):
        tools = mcp_data.get("tools", [])
        api_tool_count = len(tools)
        print(f"  ✅ 检测到 {api_tool_count} 个工具 (API声明)")
    else:
        print("  ⚠️  无法获取工具清单")
    print()

    # Stage 3: 逐个测试MCP工具
    print("[Stage 3] 逐个测试MCP工具...")
    print()

    test_tools = {
        # Memory类
        "memory_remember": (
            "POST",
            {
                "content": "MCP托盘测试记忆 - 这是一条测试记忆内容，用于验证remember功能。",
                "layer": "working",
                "tags": ["test", "mcp", "tray"],
                "priority": "low",
            },
            "memory",
        ),
        "memory_recall": (
            "POST",
            {
                "query": "天机系统",
                "limit": 5,
                "layers": ["working", "episodic", "semantic"],
            },
            "memory",
        ),
        "search_memories": ("POST", {"query": "天机", "limit": 3}, "memory"),
        "get_memory": ("POST", {"memory_id": "test-mem-001"}, "memory"),
        "list_memories": ("POST", {"layer": "working", "limit": 5}, "memory"),
        "memory_stats": ("GET", {}, "memory"),
        "memory_capacity": ("GET", {}, "memory"),
        "memory_consolidate": ("POST", {}, "memory"),
        # Session类
        "get_session_digest": ("POST", {"session_key": "test-session-001"}, "session"),
        "build_working_representation": (
            "POST",
            {"query": "测试构建工作表示", "context": "测试上下文内容"},
            "session",
        ),
        "run_reflective_cycle": ("POST", {"cycle_type": "quick"}, "session"),
        "explain_memory_lineage": ("POST", {"memory_id": "test-mem-001"}, "session"),
        # Search类
        "search_perspective_memories": (
            "POST",
            {"observer": "用户", "subject": "天机系统", "limit": 5},
            "search",
        ),
        # LLM工具类
        "tianji_classify": (
            "POST",
            {"content": "这是一个测试文本，用于分类验证功能是否正常工作。"},
            "llm",
        ),
        "tianji_auto_tag": (
            "POST",
            {"content": "记忆系统测试内容，包含智能体调度和知识图谱。"},
            "llm",
        ),
        "tianji_summarize": (
            "POST",
            {
                "content": "天机系统是一个分布式自进化记忆智能体系统。它支持六层记忆架构，包括Sensory、Working、Short-Term、Episodic、Semantic和Meta层。",
                "max_length": 50,
            },
            "llm",
        ),
        "tianji_extract_knowledge": (
            "POST",
            {"content": "Python是一种高级编程语言，由Guido van Rossum于1991年创建。"},
            "llm",
        ),
        "tianji_expand_query": ("POST", {"query": "创作"}, "llm"),
        "tianji_normalize": ("POST", {"content": "测试文本 规范化 处理"}, "llm"),
        "tianji_disambiguate": (
            "POST",
            {"content": "苹果", "context": "我喜欢吃苹果"},
            "llm",
        ),
        # Agent调度类
        "agent_dispatch": ("POST", {"task": "测试任务", "complexity": "low"}, "agent"),
        # 系统类
        "tianji_health": ("GET", {}, "system"),
    }

    results = []
    for name, (method, params, category) in test_tools.items():
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
        print(f"    {cat}: {stats['passed']}/{stats['total']} ({pct:.1f}%)")
    print()

    if failed > 0:
        print("  失败工具列表:")
        for name, ok, cat in results:
            if not ok:
                print(f"    ❌ [{cat}] {name}")
        print()

    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
