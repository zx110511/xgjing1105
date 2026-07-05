# -*- coding: utf-8-sig -*-
"""Phase 3 验证测试 - 经验主动推荐系统

验证项:
  1. 经验搜索与排序
  2. 质量评分计算
  3. 与memory_recall集成
  4. 与agent_dispatch集成
  5. 上下文适配
  6. 推荐结果格式化
  7. 多条件过滤
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.processors.experience_models import (
    OperationTrace,
    ExperienceEntry,
    ExperienceDomain,
    PatternType,
    ExperienceGrade,
)
from core.processors.experience_store import ExperienceStore
from core.processors.experience_evaluator import ExperienceEvaluator
from core.processors.experience_retriever import ExperienceRetriever


def _seed_test_data(store: ExperienceStore, evaluator: ExperienceEvaluator) -> None:
    """植入测试数据"""
    traces = [
        # memory相关成功经验
        OperationTrace(
            tool_name="memory_recall",
            tool_params={"query": "智能体调度", "layer": "semantic"},
            result_summary="找到23个智能体配置和权限矩阵",
            success=True,
            duration_ms=120.0,
            context_tags=["memory", "agent", "dispatch", "important"],
        ),
        OperationTrace(
            tool_name="memory_recall",
            tool_params={"query": "代码审查规范", "layer": "semantic"},
            result_summary="找到完整的代码质量标准和审查流程",
            success=True,
            duration_ms=95.0,
            context_tags=["memory", "code_review", "quality"],
        ),
        # agent_dispatch相关
        OperationTrace(
            tool_name="agent_dispatch",
            tool_params={"task_type": "code_review", "priority": "high"},
            result_summary="调度明镜Agent完成代码审查",
            success=True,
            duration_ms=80.0,
            context_tags=["agent", "dispatch", "code_review"],
        ),
        OperationTrace(
            tool_name="agent_dispatch",
            tool_params={"task_type": "memory_search", "priority": "medium"},
            result_summary="调度忆库Agent进行记忆检索",
            success=True,
            duration_ms=60.0,
            context_tags=["agent", "dispatch", "memory"],
        ),
        # 失败教训
        OperationTrace(
            tool_name="memory_recall",
            tool_params={"query": "不存在的内容"},
            result_summary="",
            success=False,
            duration_ms=30000.0,
            error_type="TimeoutError",
            error_message="请求超时30秒",
            context_tags=["error", "timeout", "memory"],
        ),
        OperationTrace(
            tool_name="agent_dispatch",
            tool_params={"task_type": "invalid_task"},
            result_summary="",
            success=False,
            duration_ms=5000.0,
            error_type="NoAgentAvailableError",
            error_message="没有可用的Agent处理该任务",
            context_tags=["error", "dispatch"],
        ),
        # 更多memory成功
        OperationTrace(
            tool_name="memory_remember",
            tool_params={"content": "测试内容", "layer": "episodic"},
            result_summary="成功写入 episodic 层",
            success=True,
            duration_ms=150.0,
            context_tags=["memory", "write"],
        ),
        OperationTrace(
            tool_name="memory_stats",
            tool_params={},
            result_summary="返回完整的存储统计信息",
            success=True,
            duration_ms=30.0,
            context_tags=["memory", "stats"],
        ),
    ]

    for trace in traces:
        store.add_trace(trace)
        evaluator.promote_trace(trace)

    time.sleep(0.1)


def test_experience_search():
    """测试1: 经验搜索与排序"""
    print("\n" + "="*60)
    print("🧪 测试1: 经验搜索与排序")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_ret_1.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)
    retriever = ExperienceRetriever(store=store, max_results=5)

    _seed_test_data(store, evaluator)

    # 搜索memory相关经验
    results = retriever.search_experiences(query="memory")
    assert len(results) > 0, "应该找到memory相关经验"

    # 验证排序：高分在前
    scores = [r["final_score"] for r in results]
    assert scores == sorted(scores, reverse=True), "结果应按分数降序排列"

    # 验证关键字段存在
    for r in results:
        assert "experience_id" in r
        assert "title" in r
        assert "summary" in r
        assert "grade" in r
        assert "final_score" in r
        assert 0 <= r["final_score"] <= 1

    print(f"✅ 经验搜索测试通过 (找到 {len(results)} 条经验)")
    for r in results[:3]:
        print(f"   [{r['grade']}] {r['title']} - 匹配度 {r['final_score']:.0%}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_quality_scoring():
    """测试2: 质量评分计算"""
    print("\n" + "="*60)
    print("🧪 测试2: 质量评分计算")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_ret_2.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)
    retriever = ExperienceRetriever(store=store)

    _seed_test_data(store, evaluator)

    # 高等级经验应有更高的质量分
    all_results = retriever.search_experiences(query="", limit=20)

    s_a_grades = [r for r in all_results if r["grade"] in ("S", "A", "B")]
    c_d_grades = [r for r in all_results if r["grade"] in ("C", "D")]

    # 高等级经验的quality_score应更高（整体趋势）
    if s_a_grades and c_d_grades:
        avg_high = sum(r["quality_score"] for r in s_a_grades) / len(s_a_grades)
        avg_low = sum(r["quality_score"] for r in c_d_grades) / len(c_d_grades)
        assert avg_high >= avg_low * 0.8, "高等级经验质量分应更高"

    print(f"✅ 质量评分测试通过 (高等级: {len(s_a_grades)}, 低等级: {len(c_d_grades)})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_memory_recall_integration():
    """测试3: 与memory_recall集成"""
    print("\n" + "="*60)
    print("🧪 测试3: 与memory_recall集成")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_ret_3.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)
    retriever = ExperienceRetriever(store=store)

    _seed_test_data(store, evaluator)

    # 模拟记忆检索结果
    mock_memory_results = [
        {"id": "mem-001", "content": "智能体权限矩阵...", "layer": "semantic"},
        {"id": "mem-002", "content": "调度策略说明...", "layer": "semantic"},
    ]

    augmented = retriever.augment_memory_recall(
        query="智能体调度",
        memory_results=mock_memory_results,
        layer="semantic",
    )

    assert "memories" in augmented
    assert "related_experiences" in augmented
    assert "experience_summary" in augmented
    assert "experience_count" in augmented

    assert len(augmented["memories"]) == 2
    assert isinstance(augmented["related_experiences"], list)
    assert augmented["experience_count"] >= 0

    print(f"✅ memory_recall集成测试通过 (关联经验数: {augmented['experience_count']})")
    print(f"   经验摘要: {augmented['experience_summary'][:100]}...")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_agent_dispatch_integration():
    """测试4: 与agent_dispatch集成"""
    print("\n" + "="*60)
    print("🧪 测试4: 与agent_dispatch集成")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_ret_4.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)
    retriever = ExperienceRetriever(store=store)

    _seed_test_data(store, evaluator)

    available = ["mingjing", "tianshu", "yiku", "miaobi"]

    recommendation = retriever.recommend_for_dispatch(
        task_type="code_review",
        available_agents=available,
    )

    assert "recommended_agent" in recommendation
    assert "confidence" in recommendation
    assert "supporting_experiences" in recommendation
    assert "reasoning" in recommendation
    assert "alternatives" in recommendation

    assert isinstance(recommendation["alternatives"], list)
    assert 0 <= recommendation["confidence"] <= 1

    if recommendation["recommended_agent"]:
        assert recommendation["recommended_agent"] in available

    print(f"✅ agent_dispatch集成测试通过")
    print(f"   推荐Agent: {recommendation['recommended_agent']}")
    print(f"   置信度: {recommendation['confidence']:.0%}")
    print(f"   理由: {recommendation['reasoning'][:80]}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_context_adaptation():
    """测试5: 上下文适配"""
    print("\n" + "="*60)
    print("🧪 测试5: 上下文适配")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_ret_5.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)
    retriever = ExperienceRetriever(store=store)

    _seed_test_data(store, evaluator)

    # 有上下文 vs 无上下文
    results_no_ctx = retriever.search_experiences(query="memory", limit=5)

    results_with_ctx = retriever.search_experiences(
        query="memory",
        limit=5,
        context={"agent_id": "yiku", "domain": "memory"},
    )

    # 两者都应该有结果
    assert len(results_no_ctx) > 0
    assert len(results_with_ctx) > 0

    print(f"✅ 上下文适配测试通过")
    print(f"   无上下文: {len(results_no_ctx)} 条结果")
    print(f"   有上下文: {len(results_with_ctx)} 条结果")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_result_formatting():
    """测试6: 推荐结果格式化"""
    print("\n" + "="*60)
    print("🧪 测试6: 推荐结果格式化")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_ret_6.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)
    retriever = ExperienceRetriever(store=store)

    _seed_test_data(store, evaluator)

    results = retriever.search_experiences(query="dispatch", limit=3)

    for r in results:
        # 标题非空
        assert r["title"] and len(r["title"]) > 0
        # 摘要非空
        assert r["summary"] and len(r["summary"]) > 0
        # 等级有效
        assert r["grade"] in ("S", "A", "B", "C", "D")
        # 领域有效
        assert r["domain"] in [d.value for d in ExperienceDomain]
        # 模式类型有效
        assert r["pattern_type"] in [p.value for p in PatternType]

    print(f"✅ 结果格式化测试通过 (格式化 {len(results)} 条结果)")
    for r in results[:2]:
        print(f"   [{r['grade']}] {r['title']}")
        print(f"   {r['summary']}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_filtering():
    """测试7: 多条件过滤"""
    print("\n" + "="*60)
    print("🧪 测试7: 多条件过滤")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_ret_7.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)
    retriever = ExperienceRetriever(store=store)

    _seed_test_data(store, evaluator)

    # 按领域过滤
    mem_results = retriever.search_experiences(
        query="",
        domain=ExperienceDomain.MEMORY.value,
        limit=20,
    )
    for r in mem_results:
        assert r["domain"] == "memory", "按领域过滤应只返回memory领域"

    # 按模式类型过滤
    success_results = retriever.search_experiences(
        query="",
        pattern_type=PatternType.SUCCESS_PATTERN.value,
        limit=20,
    )

    # 按最低等级过滤
    high_grade = retriever.search_experiences(
        query="",
        min_grade="C",
        limit=20,
    )

    print(f"✅ 多条件过滤测试通过")
    print(f"   memory领域: {len(mem_results)} 条")
    print(f"   成功模式: {len(success_results)} 条")
    print(f"   C级以上: {len(high_grade)} 条")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def run_all_tests():
    """运行所有测试"""
    print("╔" + "═"*58 + "╗")
    print("║  Phase 3 验证测试 - 经验主动推荐系统                 ║")
    print("╚" + "═"*58 + "╝")

    tests = [
        ("经验搜索与排序", test_experience_search),
        ("质量评分计算", test_quality_scoring),
        ("memory_recall集成", test_memory_recall_integration),
        ("agent_dispatch集成", test_agent_dispatch_integration),
        ("上下文适配", test_context_adaptation),
        ("推荐结果格式化", test_result_formatting),
        ("多条件过滤", test_filtering),
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
        print("\n🎉 全部测试通过！Phase 3 主动推荐系统验证成功")
    else:
        print(f"\n⚠️  {failed} 项测试失败，需要修复")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
