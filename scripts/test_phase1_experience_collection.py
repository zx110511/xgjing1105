# -*- coding: utf-8-sig -*-
"""Phase 1 MVP 验证测试 - 经验采集系统

验证项:
  1. 数据模型正确性
  2. 存储层CRUD
  3. 采集器功能
  4. 全文搜索
  5. 统计信息
  6. 异步写入
  7. 敏感信息脱敏
"""

from __future__ import annotations

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.processors.experience_models import (
    OperationTrace,
    ExperienceEntry,
    CollectionStats,
    ExperienceDomain,
    PatternType,
    ExperienceGrade,
)
from core.processors.experience_store import ExperienceStore
from core.processors.experience_collector import ExperienceCollector


def test_models():
    """测试1: 数据模型正确性"""
    print("\n" + "="*60)
    print("🧪 测试1: 数据模型正确性")
    print("="*60)

    trace = OperationTrace(
        session_id="test-session-001",
        agent_id="test-agent",
        task_type="code_review",
        tool_name="memory_recall",
        tool_params={"query": "测试查询", "layer": "semantic"},
        result_summary="成功找到10条结果",
        success=True,
        duration_ms=150.5,
        context_tags=["memory", "test"],
    )

    assert trace.trace_id.startswith("trace_"), "trace_id格式错误"
    assert trace.success is True
    assert trace.tool_name == "memory_recall"
    assert len(trace.tool_params) == 2
    assert len(trace.context_tags) == 2

    d = trace.to_dict()
    assert isinstance(d, dict)
    assert d["trace_id"] == trace.trace_id

    trace2 = OperationTrace.from_dict(d)
    assert trace2.trace_id == trace.trace_id
    assert trace2.tool_name == trace.tool_name

    h1 = trace.content_hash()
    h2 = trace2.content_hash()
    assert h1 == h2, "内容哈希不一致"

    print("✅ 数据模型测试通过")
    return True


def test_store_crud():
    """测试2: 存储层CRUD"""
    print("\n" + "="*60)
    print("🧪 测试2: 存储层CRUD")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_experience.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)

    trace1 = OperationTrace(
        session_id="sess-001",
        agent_id="agent-a",
        tool_name="memory_recall",
        tool_params={"query": "test", "limit": 10},
        result_summary="OK",
        success=True,
        duration_ms=100.0,
        context_tags=["test"],
    )
    tid1 = store.add_trace(trace1)

    trace2 = OperationTrace(
        session_id="sess-001",
        agent_id="agent-b",
        tool_name="agent_dispatch",
        tool_params={"task_type": "review"},
        result_summary="dispatched",
        success=True,
        duration_ms=50.0,
        context_tags=["dispatch"],
    )
    tid2 = store.add_trace(trace2)

    trace3 = OperationTrace(
        session_id="sess-002",
        agent_id="agent-a",
        tool_name="memory_recall",
        tool_params={"query": "fail_test"},
        result_summary="",
        success=False,
        duration_ms=200.0,
        error_type="TimeoutError",
        error_message="Request timed out after 30s",
        context_tags=["error", "test"],
    )
    tid3 = store.add_trace(trace3)

    assert store.count_traces() == 3, f"期望3条轨迹，实际{store.count_traces()}"

    got = store.get_trace(tid1)
    assert got is not None
    assert got.trace_id == tid1
    assert got.tool_name == "memory_recall"

    by_tool = store.list_traces(tool_name="memory_recall")
    assert len(by_tool) == 2, f"期望2条memory_recall轨迹，实际{len(by_tool)}"

    by_agent = store.list_traces(agent_id="agent-a")
    assert len(by_agent) == 2

    success_traces = store.list_traces(success=True)
    assert len(success_traces) == 2

    fail_traces = store.list_traces(success=False)
    assert len(fail_traces) == 1

    print("✅ 存储层CRUD测试通过")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_experience_entry():
    """测试3: 经验条目"""
    print("\n" + "="*60)
    print("🧪 测试3: 经验条目")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_experience2.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)

    trace = OperationTrace(
        session_id="sess-exp",
        agent_id="tianshu",
        tool_name="memory_recall",
        tool_params={"query": "智能体调度", "layer": "semantic"},
        result_summary="找到23个智能体配置",
        success=True,
        duration_ms=180.0,
        context_tags=["memory", "agent"],
    )
    store.add_trace(trace)

    exp = ExperienceEntry.from_trace(trace)
    assert exp.domain == ExperienceDomain.MEMORY
    assert exp.pattern_type == PatternType.SUCCESS_PATTERN
    assert exp.grade == ExperienceGrade.D
    assert len(exp.source_trace_ids) == 1

    eid = store.add_experience(exp)
    assert store.count_experiences() == 1

    got_exp = store.get_experience(eid)
    assert got_exp is not None
    assert got_exp.experience_id == eid

    exp_list = store.list_experiences(domain="memory")
    assert len(exp_list) == 1

    print("✅ 经验条目测试通过")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_fulltext_search():
    """测试4: 全文搜索"""
    print("\n" + "="*60)
    print("🧪 测试4: 全文搜索")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_experience3.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)

    traces = [
        OperationTrace(
            tool_name="memory_recall",
            result_summary="成功检索到记忆系统相关内容",
            success=True,
            context_tags=["memory"],
        ),
        OperationTrace(
            tool_name="agent_dispatch",
            result_summary="智能体调度完成，分配给天枢处理",
            success=True,
            context_tags=["agent"],
        ),
        OperationTrace(
            tool_name="scan_vulnerabilities",
            result_summary="安全扫描发现3个高危漏洞",
            success=True,
            error_message="",
            context_tags=["security"],
        ),
    ]
    for t in traces:
        store.add_trace(t)

    time.sleep(0.1)

    results = store.search_traces("记忆")
    assert len(results) >= 1, f"搜索'记忆'应至少返回1条，实际{len(results)}"

    results2 = store.search_traces("智能体")
    assert len(results2) >= 1, f"搜索'智能体'应至少返回1条，实际{len(results2)}"

    results3 = store.search_traces("漏洞")
    assert len(results3) >= 1, f"搜索'漏洞'应至少返回1条，实际{len(results3)}"

    print(f"✅ 全文搜索测试通过 (记忆:{len(results)} 智能体:{len(results2)} 漏洞:{len(results3)})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_collector():
    """测试5: 采集器功能"""
    print("\n" + "="*60)
    print("🧪 测试5: 采集器功能")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_experience4.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    collector = ExperienceCollector(store=store, async_enabled=False)

    assert collector.enabled is True

    tid1 = collector.collect_trace(
        tool_name="memory_recall",
        tool_params={"query": "测试", "layer": "semantic"},
        result_summary="成功",
        success=True,
        duration_ms=120.0,
        agent_id="tianshu",
        session_id="test-collector",
        context_tags=["test", "memory"],
    )
    assert tid1 != ""

    tid2 = collector.collect_mcp_call(
        tool_name="agent_dispatch",
        params={"task_type": "code_review", "priority": "high"},
        result={"status": "success", "agent": "mingjing"},
        success=True,
        duration_ms=80.0,
        agent_id="tianshu",
        session_id="test-collector",
    )
    assert tid2 != ""

    tid3 = collector.collect_mcp_call(
        tool_name="some_tool",
        params={"password": "secret123", "api_key": "sk-xxx", "normal_param": "value"},
        result="error",
        success=False,
        duration_ms=50.0,
        error=ValueError("test error"),
    )
    assert tid3 != ""

    time.sleep(0.1)

    stats = collector.get_stats()
    assert stats["session_stats"]["collected"] == 3
    assert stats["session_stats"]["success"] == 2
    assert stats["session_stats"]["failure"] == 1

    recent = collector.get_recent_traces(limit=10)
    assert len(recent) == 3

    fail_trace = store.get_trace(tid3)
    assert fail_trace is not None
    assert fail_trace.success is False
    assert fail_trace.error_type == "ValueError"

    assert "***REDACTED***" in str(fail_trace.tool_params.get("password", "")), \
        "敏感参数未脱敏"
    assert "***REDACTED***" in str(fail_trace.tool_params.get("api_key", "")), \
        "API Key未脱敏"

    print("✅ 采集器功能测试通过")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_stats():
    """测试6: 统计信息"""
    print("\n" + "="*60)
    print("🧪 测试6: 统计信息")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_experience5.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)

    for i in range(10):
        success = i % 2 == 0
        trace = OperationTrace(
            tool_name="memory_recall" if i < 5 else "agent_dispatch",
            agent_id="test-agent",
            success=success,
            duration_ms=100.0 + i,
            context_tags=[f"tag_{i}"],
        )
        store.add_trace(trace)

    stats = store.get_stats()

    assert stats.total_traces == 10
    assert stats.success_count == 5
    assert stats.failure_count == 5
    assert "memory" in stats.by_domain
    assert "memory_recall" in stats.by_tool
    assert "test-agent" in stats.by_agent
    assert stats.avg_duration_ms > 0

    print(f"✅ 统计信息测试通过 (总轨迹:{stats.total_traces} 成功:{stats.success_count} 失败:{stats.failure_count})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_async_collector():
    """测试7: 异步写入"""
    print("\n" + "="*60)
    print("🧪 测试7: 异步写入")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_experience6.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    collector = ExperienceCollector(store=store, async_enabled=True, flush_interval=0.2)

    for i in range(5):
        collector.collect_trace(
            tool_name=f"test_tool_{i}",
            success=True,
            duration_ms=50.0,
        )

    time.sleep(1.0)

    flushed = collector.flush()
    time.sleep(0.1)

    count = store.count_traces()
    assert count == 5, f"异步写入后应有5条轨迹，实际{count}"

    print(f"✅ 异步写入测试通过 (最终轨迹数:{count})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def run_all_tests():
    """运行所有测试"""
    print("╔" + "═"*58 + "╗")
    print("║  Phase 1 MVP 验证测试 - 经验采集系统                   ║")
    print("╚" + "═"*58 + "╝")

    tests = [
        ("数据模型正确性", test_models),
        ("存储层CRUD", test_store_crud),
        ("经验条目", test_experience_entry),
        ("全文搜索", test_fulltext_search),
        ("采集器功能", test_collector),
        ("统计信息", test_stats),
        ("异步写入", test_async_collector),
    ]

    results = []
    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            ok = test_func()
            if ok:
                passed += 1
                results.append((name, "✅ PASS"))
            else:
                failed += 1
                results.append((name, "❌ FAIL"))
        except Exception as e:
            failed += 1
            results.append((name, f"❌ ERROR: {e}"))
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    for name, status in results:
        print(f"   {status:20s} - {name}")

    print(f"\n总计: {len(tests)} 项测试")
    print(f"通过: {passed} 项")
    print(f"失败: {failed} 项")
    print(f"通过率: {passed/len(tests)*100:.1f}%")

    if failed == 0:
        print("\n🎉 全部测试通过！Phase 1 MVP 验证成功")
    else:
        print(f"\n⚠️  {failed} 项测试失败，需要修复")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
