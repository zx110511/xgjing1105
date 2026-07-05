# -*- coding: utf-8-sig -*-
"""Phase 2 验证测试 - 经验自动评估系统

验证项:
  1. 五维评分正确性
  2. 模式分类准确性
  3. 经验等级计算
  4. 轨迹升级为经验
  5. 经验去重与合并
  6. 批量评估
  7. 失败教训识别
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.processors.experience_models import (
    OperationTrace,
    ExperienceEntry,
    PatternType,
    ExperienceGrade,
)
from core.processors.experience_store import ExperienceStore
from core.processors.experience_evaluator import ExperienceEvaluator


def test_dimension_scoring():
    """测试1: 五维评分正确性"""
    print("\n" + "="*60)
    print("🧪 测试1: 五维评分正确性")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_eval_1.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)

    # 成功的快速调用
    trace1 = OperationTrace(
        tool_name="memory_recall",
        tool_params={"query": "test", "limit": 10},
        result_summary="成功找到10条相关记忆，包含完整的上下文信息",
        success=True,
        duration_ms=80.0,
        context_tags=["memory", "search", "important"],
    )

    eval1 = evaluator.evaluate_trace(trace1)

    assert 0 <= eval1["overall_score"] <= 1, "综合评分应在0-1之间"
    assert eval1["pattern_type"] in [PatternType.SUCCESS_PATTERN, PatternType.BEST_PRACTICE]
    assert eval1["grade"] in [ExperienceGrade.C, ExperienceGrade.D]

    dims = eval1["dimensions"]
    assert "completeness" in dims
    assert "efficiency" in dims
    assert "innovation" in dims
    assert "reusability" in dims
    assert "stability" in dims

    assert 0 <= dims["completeness"] <= 1
    assert 0 <= dims["efficiency"] <= 1
    assert dims["efficiency"] > 0.5, "快速调用效率分应较高"

    print(f"✅ 五维评分测试通过 (总分: {eval1['overall_score']:.3f})")
    print(f"   各维度: 完成度={dims['completeness']:.2f}, 效率={dims['efficiency']:.2f}, "
          f"创新={dims['innovation']:.2f}, 复用={dims['reusability']:.2f}, "
          f"稳定={dims['stability']:.2f}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_failure_evaluation():
    """测试2: 失败教训识别"""
    print("\n" + "="*60)
    print("🧪 测试2: 失败教训识别")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_eval_2.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)

    # 失败的调用
    trace_fail = OperationTrace(
        tool_name="memory_recall",
        tool_params={"query": "test"},
        result_summary="",
        success=False,
        duration_ms=30000.0,
        error_type="TimeoutError",
        error_message="请求超时，服务响应时间超过30秒",
        context_tags=["error", "timeout"],
    )

    eval_fail = evaluator.evaluate_trace(trace_fail)

    assert eval_fail["pattern_type"] == PatternType.FAILURE_LESSON, \
        f"失败应识别为失败教训，实际为{eval_fail['pattern_type']}"

    assert eval_fail["should_promote"] is True, "失败教训也应该被沉淀"

    assert eval_fail["dimensions"]["completeness"] == 0.0, "失败的完成度应为0"

    print(f"✅ 失败教训识别测试通过 (类型: {eval_fail['pattern_type'].value})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_promote_trace():
    """测试3: 轨迹升级为经验"""
    print("\n" + "="*60)
    print("🧪 测试3: 轨迹升级为经验")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_eval_3.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)

    trace = OperationTrace(
        tool_name="agent_dispatch",
        tool_params={"task_type": "code_review", "priority": "high"},
        result_summary="成功调度到明镜Agent进行代码审查",
        success=True,
        duration_ms=120.0,
        agent_id="tianshu",
        context_tags=["agent", "dispatch", "code_review"],
    )
    store.add_trace(trace)

    eid = evaluator.promote_trace(trace)
    assert eid is not None, "应该成功升级为经验"

    exp = store.get_experience(eid)
    assert exp is not None, "经验应该存在"
    assert len(exp.source_trace_ids) == 1
    assert trace.trace_id in exp.source_trace_ids

    assert exp.outcome.get("quality_score", 0) > 0
    assert exp.metadata.get("confidence", 0) > 0

    exp_count = store.count_experiences()
    assert exp_count >= 1

    print(f"✅ 轨迹升级测试通过 (经验ID: {eid})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_experience_merge():
    """测试4: 经验去重与合并"""
    print("\n" + "="*60)
    print("🧪 测试4: 经验去重与合并")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_eval_4.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)

    # 第一条轨迹
    trace1 = OperationTrace(
        tool_name="memory_recall",
        tool_params={"query": "测试查询", "layer": "semantic"},
        result_summary="找到5条结果",
        success=True,
        duration_ms=100.0,
        context_tags=["memory"],
    )
    store.add_trace(trace1)
    eid1 = evaluator.promote_trace(trace1)
    assert eid1 is not None

    # 第二条相似轨迹（相同工具+相似参数）
    trace2 = OperationTrace(
        tool_name="memory_recall",
        tool_params={"query": "另一个查询", "layer": "semantic"},
        result_summary="找到8条结果",
        success=True,
        duration_ms=120.0,
        context_tags=["memory"],
    )
    store.add_trace(trace2)
    eid2 = evaluator.promote_trace(trace2)

    # 应该合并到同一个经验
    assert eid2 == eid1, f"相似轨迹应该合并，期望{eid1}，实际{eid2}"

    exp = store.get_experience(eid1)
    assert exp is not None
    assert len(exp.source_trace_ids) == 2, f"应该有2条源轨迹，实际{len(exp.source_trace_ids)}"
    assert exp.metadata.get("reuse_count", 0) >= 1

    print(f"✅ 经验合并测试通过 (经验ID: {eid1}, 轨迹数: {len(exp.source_trace_ids)})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_grade_calculation():
    """测试5: 经验等级计算"""
    print("\n" + "="*60)
    print("🧪 测试5: 经验等级计算")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_eval_5.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)

    # 单条高质量轨迹 -> C级
    trace = OperationTrace(
        tool_name="memory_recall",
        tool_params={"query": "test", "limit": 20},
        result_summary="成功找到20条高质量结果，完全匹配需求",
        success=True,
        duration_ms=90.0,
        context_tags=["memory", "important", "high_quality"],
    )
    store.add_trace(trace)
    eid = evaluator.promote_trace(trace)
    assert eid is not None

    exp = store.get_experience(eid)
    assert exp is not None
    # 单条轨迹应该是C或D级
    assert exp.grade in [ExperienceGrade.C, ExperienceGrade.D], \
        f"单条轨迹等级应为C/D，实际为{exp.grade}"

    print(f"✅ 经验等级测试通过 (等级: {exp.grade.value})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_batch_evaluation():
    """测试6: 批量评估"""
    print("\n" + "="*60)
    print("🧪 测试6: 批量评估")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_eval_6.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)

    # 生成10条轨迹（5成功，5失败）
    for i in range(10):
        success = i % 2 == 0
        trace = OperationTrace(
            tool_name=f"tool_{i % 3}",
            tool_params={"param": f"value_{i}"},
            result_summary=f"结果_{i}" if success else "",
            success=success,
            duration_ms=100.0 + i * 10,
            error_type="TestError" if not success else "",
            error_message=f"测试错误{i}" if not success else "",
            context_tags=[f"tag_{i}"],
        )
        store.add_trace(trace)

    assert store.count_traces() == 10

    result = evaluator.evaluate_pending(limit=10)

    assert result["total"] == 10
    assert result["promoted"] > 0, "至少应该有一些被提升"
    assert result["errors"] == 0

    exp_count = store.count_experiences()
    assert exp_count > 0, "应该生成经验条目"

    print(f"✅ 批量评估测试通过 (提升: {result['promoted']}, 跳过: {result['skipped']})")
    print(f"   最终经验数: {exp_count}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_best_practice_detection():
    """测试7: 最佳实践识别"""
    print("\n" + "="*60)
    print("🧪 测试7: 最佳实践识别")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_eval_7.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)

    # 高质量的成功调用
    trace = OperationTrace(
        tool_name="memory_recall",
        tool_params={
            "query": "智能体调度系统设计",
            "layer": "semantic",
            "limit": 20,
            "threshold": 0.7,
        },
        result_summary="成功检索到23条相关记忆，包括架构设计、权限矩阵、协作模式等完整知识体系，匹配度高，覆盖全面",
        success=True,
        duration_ms=95.0,
        agent_id="tianshu",
        context_tags=["memory", "search", "agent_dispatch", "architecture", "important"],
    )
    store.add_trace(trace)

    evaluation = evaluator.evaluate_trace(trace)

    assert evaluation["overall_score"] >= 0.6, f"高质量调用评分应较高，实际{evaluation['overall_score']}"
    assert evaluation["pattern_type"] in [PatternType.BEST_PRACTICE, PatternType.SUCCESS_PATTERN]
    assert evaluation["should_promote"] is True

    print(f"✅ 最佳实践识别测试通过 (评分: {evaluation['overall_score']:.3f}, 模式: {evaluation['pattern_type'].value})")
    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def run_all_tests():
    """运行所有测试"""
    print("╔" + "═"*58 + "╗")
    print("║  Phase 2 验证测试 - 经验自动评估系统                   ║")
    print("╚" + "═"*58 + "╝")

    tests = [
        ("五维评分正确性", test_dimension_scoring),
        ("失败教训识别", test_failure_evaluation),
        ("轨迹升级为经验", test_promote_trace),
        ("经验去重与合并", test_experience_merge),
        ("经验等级计算", test_grade_calculation),
        ("批量评估", test_batch_evaluation),
        ("最佳实践识别", test_best_practice_detection),
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
        print("\n🎉 全部测试通过！Phase 2 自动评估系统验证成功")
    else:
        print(f"\n⚠️  {failed} 项测试失败，需要修复")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
