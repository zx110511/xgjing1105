# -*- coding: utf-8-sig -*-
"""Phase 4 验证测试 - 经验自进化闭环系统

验证项:
  1. 经验自动升级（基于复用次数和成功率）
  2. 经验自动降级（长期未使用或成功率下降）
  3. 经验自动淘汰（过期/质量过低）
  4. 反馈循环（使用结果回写）
  5. 重复经验合并
  6. 生命周期分布统计
  7. 全链路闭环（采集→评估→推荐→使用→反馈→进化）
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
from core.processors.experience_evolution import (
    ExperienceEvolutionEngine,
    EvolutionResult,
)


_exp_id_counter = 0

def _create_test_experience(
    store: ExperienceStore,
    tool: str,
    grade: str = "C",
    reuse_count: int = 0,
    success_rate: float = 0.7,
    quality_score: float = 0.7,
    domain: str = "memory",
    pattern: str = "success_pattern",
    age_days: float = 0,
    last_used_days: float = 0,
    confidence: float = 0.6,
) -> ExperienceEntry:
    """创建测试用经验条目"""
    global _exp_id_counter
    _exp_id_counter += 1
    now = time.time()
    exp = ExperienceEntry(
        experience_id=f"exp_{tool}_{_exp_id_counter:04d}",
        domain=ExperienceDomain(domain),
        pattern_type=PatternType(pattern),
        grade=ExperienceGrade(grade),
        trigger_context={
            "tool": tool,
            "task_type": f"{tool}_task",
            "agent": "test_agent",
        },
        solution={
            "tool_chain": [tool],
            "parameters": {"param1": "value1"},
            "steps": ["step1", "step2"],
        },
        outcome={
            "quality_score": quality_score,
            "duration_ms": 100.0,
            "success": True,
            "sample_count": 1,
        },
        metadata={
            "reuse_count": reuse_count,
            "success_rate": success_rate,
            "success_count": int(success_rate * max(reuse_count, 1)),
            "total_uses": max(reuse_count, 1),
            "confidence": confidence,
            "tags": [tool, "test"],
            "last_used_at": now - last_used_days * 86400,
        },
        source_trace_ids=[f"trace_{tool}_001"],
        created_at=now - age_days * 86400,
        updated_at=now - age_days * 86400,
    )
    store.add_experience(exp)
    return exp


def test_auto_upgrade():
    """测试1: 经验自动升级"""
    print("\n" + "="*60)
    print("🧪 测试1: 经验自动升级")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_evo_1.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    engine = ExperienceEvolutionEngine(
        store=store,
        upgrade_reuse_threshold=5,
        upgrade_success_rate=0.8,
        downgrade_unused_days=30,
    )

    exp = _create_test_experience(
        store,
        tool="memory_recall",
        grade="C",
        reuse_count=8,
        success_rate=0.92,
        quality_score=0.85,
    )
    assert exp.grade.value == "C", "初始等级应为C"

    result = engine.run_evolution_cycle()

    updated = store.get_experience(exp.experience_id)
    assert updated is not None
    assert updated.grade.value == "B", f"应升级到B级，实际为{updated.grade.value}"
    assert len(result.upgraded) >= 1, "应有升级的经验"

    print(f"✅ 经验自动升级测试通过 (C → {updated.grade.value})")
    print(f"   升级数量: {len(result.upgraded)}")
    print(f"   总检查数: {result.total_checked}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_auto_downgrade():
    """测试2: 经验自动降级"""
    print("\n" + "="*60)
    print("🧪 测试2: 经验自动降级")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_evo_2.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    engine = ExperienceEvolutionEngine(
        store=store,
        downgrade_unused_days=30,
        downgrade_success_rate=0.4,
    )

    exp = _create_test_experience(
        store,
        tool="old_tool",
        grade="B",
        reuse_count=2,
        success_rate=0.5,
        quality_score=0.5,
        last_used_days=45,
    )
    assert exp.grade.value == "B", "初始等级应为B"

    result = engine.run_evolution_cycle()

    updated = store.get_experience(exp.experience_id)
    assert updated is not None
    assert updated.grade.value == "C", f"应降级到C级，实际为{updated.grade.value}"
    assert len(result.downgraded) >= 1, "应有降级的经验"

    print(f"✅ 经验自动降级测试通过 (B → {updated.grade.value})")
    print(f"   降级数量: {len(result.downgraded)}")
    print(f"   未使用天数: 45天")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_auto_archive():
    """测试3: 经验自动淘汰归档"""
    print("\n" + "="*60)
    print("🧪 测试3: 经验自动淘汰归档")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_evo_3.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    engine = ExperienceEvolutionEngine(
        store=store,
        archive_max_age_days=180,
        archive_min_grade="D",
    )

    exp = _create_test_experience(
        store,
        tool="ancient_tool",
        grade="D",
        reuse_count=1,
        success_rate=0.3,
        quality_score=0.1,
        confidence=0.1,
        age_days=200,
        last_used_days=190,
    )

    result = engine.run_evolution_cycle()

    updated = store.get_experience(exp.experience_id)
    assert updated is not None
    assert updated.metadata.get("archived", False), "应标记为已归档"
    assert len(result.archived) >= 1, "应有归档的经验"

    print(f"✅ 经验自动淘汰测试通过")
    print(f"   归档数量: {len(result.archived)}")
    print(f"   归档原因: {updated.metadata.get('archive_reason')}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_feedback_loop():
    """测试4: 反馈循环 - 使用结果回写"""
    print("\n" + "="*60)
    print("🧪 测试4: 反馈循环 - 使用结果回写")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_evo_4.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    engine = ExperienceEvolutionEngine(store=store)

    exp = _create_test_experience(
        store,
        tool="feedback_test",
        grade="C",
        reuse_count=3,
        success_rate=0.75,
        confidence=0.6,
    )
    original_reuse = exp.metadata.get("reuse_count", 0)
    original_conf = exp.metadata.get("confidence", 0.5)

    ok = engine.record_usage_feedback(
        experience_id=exp.experience_id,
        success=True,
        duration_ms=95.0,
        feedback_note="使用成功，效果良好",
    )
    assert ok, "反馈记录应成功"

    updated = store.get_experience(exp.experience_id)
    assert updated is not None
    assert updated.metadata.get("reuse_count", 0) == original_reuse + 1, "复用次数应+1"
    assert updated.metadata.get("confidence", 0) > original_conf, "成功反馈应提升置信度"
    assert updated.metadata.get("success_rate", 0) > 0, "成功率应更新"

    print(f"✅ 反馈循环测试通过")
    print(f"   复用次数: {original_reuse} → {updated.metadata.get('reuse_count')}")
    print(f"   置信度: {original_conf:.2f} → {updated.metadata.get('confidence', 0):.2f}")
    print(f"   成功率: {exp.metadata.get('success_rate'):.0%} → {updated.metadata.get('success_rate', 0):.0%}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_duplicate_merge():
    """测试5: 重复经验合并"""
    print("\n" + "="*60)
    print("🧪 测试5: 重复经验合并")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_evo_5.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    engine = ExperienceEvolutionEngine(store=store)

    exp1 = _create_test_experience(
        store,
        tool="merge_tool",
        grade="B",
        reuse_count=5,
        success_rate=0.85,
        quality_score=0.8,
    )
    exp2 = _create_test_experience(
        store,
        tool="merge_tool",
        grade="C",
        reuse_count=3,
        success_rate=0.7,
        quality_score=0.6,
    )

    all_before = store.list_experiences(limit=100)
    count_before = len([e for e in all_before if not e.metadata.get("archived", False)])

    result = engine.run_evolution_cycle()

    all_after = store.list_experiences(limit=100)
    active_after = [e for e in all_after if not e.metadata.get("archived", False)]
    archived_after = [e for e in all_after if e.metadata.get("archived", False)]

    assert len(result.merged) >= 1, "应有合并的经验"
    assert len(archived_after) >= 1, "应有被归档的重复经验"

    print(f"✅ 重复经验合并测试通过")
    print(f"   合并前活跃经验数: {count_before}")
    print(f"   合并后活跃经验数: {len(active_after)}")
    print(f"   合并归档数: {len(result.merged)}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_lifecycle_distribution():
    """测试6: 生命周期分布统计"""
    print("\n" + "="*60)
    print("🧪 测试6: 生命周期分布统计")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_evo_6.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    engine = ExperienceEvolutionEngine(store=store)

    grades = ["S", "A", "B", "C", "D"]
    for i, g in enumerate(grades):
        _create_test_experience(
            store,
            tool=f"dist_tool_{g}",
            grade=g,
            reuse_count=i,
            success_rate=0.5 + i * 0.1,
        )

    dist = engine.get_lifecycle_distribution()

    for g in grades:
        assert g in dist, f"分布中应包含{g}级"
        assert dist[g] >= 1, f"{g}级至少应有1条经验"

    assert "archived" in dist

    stats = engine.get_stats()
    assert "evolution_version" in stats
    assert "engine_stats" in stats
    assert "config" in stats

    print(f"✅ 生命周期分布统计测试通过")
    print(f"   分布: S={dist['S']} A={dist['A']} B={dist['B']} C={dist['C']} D={dist['D']}")
    print(f"   归档: {dist['archived']}")
    print(f"   引擎版本: {stats['evolution_version']}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def test_full_closure():
    """测试7: 全链路闭环（采集→评估→推荐→使用→反馈→进化）"""
    print("\n" + "="*60)
    print("🧪 测试7: 全链路闭环验证")
    print("="*60)

    test_db = Path(__file__).parent.parent / "data" / ".memory" / "test_evo_7.db"
    if test_db.exists():
        test_db.unlink()

    store = ExperienceStore(db_path=test_db)
    evaluator = ExperienceEvaluator(store=store)
    retriever = ExperienceRetriever(store=store, max_results=5)
    engine = ExperienceEvolutionEngine(
        store=store,
        upgrade_reuse_threshold=3,
        upgrade_success_rate=0.7,
    )

    # Step 1: 采集 - 生成多条操作轨迹
    print("   Step 1: 采集操作轨迹...")
    for i in range(10):
        trace = OperationTrace(
            tool_name="memory_recall",
            tool_params={"query": f"test_query_{i}", "layer": "semantic"},
            result_summary=f"找到 {i*5} 条相关记忆",
            success=i < 9,
            duration_ms=80.0 + i * 5,
            context_tags=["memory", "test", "recall"],
        )
        store.add_trace(trace)
        evaluator.promote_trace(trace)

    traces_count = store.count_traces()
    exps_count = store.count_experiences()
    print(f"   轨迹数: {traces_count}, 经验数: {exps_count}")

    # Step 2: 检索 - 使用推荐系统
    print("   Step 2: 经验检索推荐...")
    results = retriever.search_experiences(query="memory_recall")
    assert len(results) > 0, "应能检索到经验"
    print(f"   检索到 {len(results)} 条经验")

    # Step 3: 使用反馈 - 模拟多次成功使用
    print("   Step 3: 使用反馈回写...")
    top_exp_id = results[0]["experience_id"]
    for i in range(6):
        engine.record_usage_feedback(
            experience_id=top_exp_id,
            success=True,
            duration_ms=70.0 + i,
            feedback_note=f"第{i+1}次使用成功",
        )

    updated_exp = store.get_experience(top_exp_id)
    assert updated_exp is not None
    print(f"   复用次数: {updated_exp.metadata.get('reuse_count', 0)}")
    print(f"   成功率: {updated_exp.metadata.get('success_rate', 0):.0%}")

    # Step 4: 进化 - 运行进化循环
    print("   Step 4: 执行进化循环...")
    result = engine.run_evolution_cycle()
    print(f"   {result.summary()}")

    final_exp = store.get_experience(top_exp_id)
    assert final_exp is not None

    dist = engine.get_lifecycle_distribution()
    print(f"   最终等级分布: S={dist['S']} A={dist['A']} B={dist['B']} C={dist['C']} D={dist['D']}")

    stats = engine.get_stats()
    assert stats["engine_stats"]["evolution_cycles"] >= 1

    print(f"✅ 全链路闭环测试通过")
    print(f"   初始等级: C → 最终等级: {final_exp.grade.value}")
    print(f"   进化循环数: {stats['engine_stats']['evolution_cycles']}")
    print(f"   总升级数: {stats['engine_stats']['total_upgraded']}")

    store.close()
    if test_db.exists():
        test_db.unlink()
    return True


def run_all_tests():
    """运行所有测试"""
    print("╔" + "═"*58 + "╗")
    print("║  Phase 4 验证测试 - 经验自进化闭环系统              ║")
    print("╚" + "═"*58 + "╝")

    tests = [
        ("经验自动升级", test_auto_upgrade),
        ("经验自动降级", test_auto_downgrade),
        ("经验自动淘汰", test_auto_archive),
        ("反馈循环", test_feedback_loop),
        ("重复经验合并", test_duplicate_merge),
        ("生命周期分布", test_lifecycle_distribution),
        ("全链路闭环", test_full_closure),
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
        print("\n🎉 全部测试通过！Phase 4 自进化闭环系统验证成功")
    else:
        print(f"\n⚠️  {failed} 项测试失败，需要修复")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
