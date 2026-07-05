r"""
P06-P09 扩展验证 — OTel Eval + 三循环解耦 + 知识分库 + 因果图持久化
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import threading
from pathlib import Path
from typing import Dict, Any

_CHECK_COUNT = 0
_PASS_COUNT = 0
_FAIL_COUNT = 0
_MODULE_CHECKS: Dict[str, int] = {}

def check(name, condition, msg=""):
    global _CHECK_COUNT, _PASS_COUNT, _FAIL_COUNT
    _CHECK_COUNT += 1
    module = name.split("_")[0] if "_" in name else name
    _MODULE_CHECKS[module] = _MODULE_CHECKS.get(module, 0) + 1
    if condition:
        _PASS_COUNT += 1
        print(f"  [OK] {name}")
    else:
        _FAIL_COUNT += 1
        print(f"  [FAIL] {name} — {msg}")
    return condition


def test_p06_otel_eval():
    print("\n" + "=" * 60)
    print("P06: OTel Eval多维度评分矩阵")
    print("=" * 60)

    from core.enforcement.enforcement_hook import (
        EvalDimension, EvalScoringMatrix, OTEL_EVAL_DIMENSIONS,
        EvalResult, OTelEvalEngine,
    )

    check("p06_eval_dimension_count", len(EvalDimension) == 6,
          f"expected 6, got {len(EvalDimension)}")
    check("p06_eval_dim_correctness", hasattr(EvalDimension, "CORRECTNESS"))
    check("p06_eval_dim_relevance", hasattr(EvalDimension, "RELEVANCE"))
    check("p06_eval_dim_harmfulness", hasattr(EvalDimension, "HARMFULNESS"))
    check("p06_eval_dim_groundedness", hasattr(EvalDimension, "GROUNDEDNESS"))
    check("p06_eval_dim_completeness", hasattr(EvalDimension, "COMPLETENESS"))
    check("p06_eval_dim_coherence", hasattr(EvalDimension, "COHERENCE"))

    check("p06_otel_dimensions_count", len(OTEL_EVAL_DIMENSIONS) == 6)
    total_weight = sum(m.weight for m in OTEL_EVAL_DIMENSIONS.values())
    check("p06_otel_weight_sum", abs(total_weight - 1.0) < 0.01,
          f"weight sum={total_weight:.4f}")

    engine = OTelEvalEngine()
    check("p06_engine_init", engine is not None)

    engine.score_dimension(EvalDimension.CORRECTNESS, 0.95, "test")
    engine.score_dimension(EvalDimension.RELEVANCE, 0.85, "test")
    engine.score_dimension(EvalDimension.HARMFULNESS, 0.95, "test")
    engine.score_dimension(EvalDimension.GROUNDEDNESS, 0.80, "test")
    engine.score_dimension(EvalDimension.COMPLETENESS, 0.75, "test")
    engine.score_dimension(EvalDimension.COHERENCE, 0.90, "test")

    result = engine.evaluate()
    check("p06_eval_result_class", isinstance(result, EvalResult))
    check("p06_eval_composite_score", result.composite_score >= 0.80,
          f"composite={result.composite_score:.4f}")
    check("p06_eval_verdict_pass", result.overall_verdict == "pass",
          f"verdict={result.overall_verdict}")
    check("p06_eval_pass_count_6", result.pass_count == 6,
          f"pass_count={result.pass_count}")
    check("p06_eval_fail_count_0", result.fail_count == 0)
    check("p06_eval_to_dict", "composite_score" in result.to_dict())
    check("p06_eval_dimensions_in_dict", "correctness" in result.to_dict()["dimensions"])

    hook_result = {"violations": [], "compliance_rate": 0.95, "risk_level": "low"}
    result2 = engine.auto_evaluate_from_hook(hook_result)
    check("p06_auto_eval_hook", result2.overall_verdict == "pass",
          f"verdict={result2.overall_verdict}")

    hook_bad = {"violations": ["bad1", "bad2"], "compliance_rate": 0.50, "risk_level": "high"}
    result3 = engine.auto_evaluate_from_hook(hook_bad)
    check("p06_auto_eval_hook_bad", result3.overall_verdict in ("warn", "fail"),
          f"verdict={result3.overall_verdict}")

    stats = engine.get_stats()
    check("p06_engine_stats_total", stats["total_evals"] == 3,
          f"total_evals={stats['total_evals']}")
    check("p06_engine_stats_has_pass_rate", "pass_rate" in stats)
    check("p06_engine_stats_dim_avgs", "correctness" in stats["dimension_averages"])


def test_p07_three_cycle_orchestrator():
    print("\n" + "=" * 60)
    print("P07: DeepSeek Driver三循环解耦")
    print("=" * 60)

    from core.shared.deepseek_driver import (
        ThreeCycleOrchestrator, DeepSeekDriver, EventType, TianjiEvent,
        EventBus,
    )

    event_bus = EventBus()
    driver = DeepSeekDriver(event_bus=event_bus)
    check("p07_driver_init", driver is not None)

    orch = ThreeCycleOrchestrator(driver, max_workers=2)
    check("p07_orchestrator_init", orch is not None)
    check("p07_orchestrator_not_running", not orch.get_stats()["running"])

    orch.start(loop_b_interval=9999.0, loop_c_interval=99999.0)
    check("p07_orchestrator_started", orch.get_stats()["running"])
    check("p07_orchestrator_events_0", orch.get_stats()["events_processed"] == 0,
          f"events={orch.get_stats()['events_processed']}")

    event = TianjiEvent(
        event_type=EventType.CONVERSATION_INPUT,
        source="test",
        payload={"content": "hello"},
    )
    orch._on_event(event)
    time.sleep(0.1)
    check("p07_orchestrator_event_processed", orch.get_stats()["events_processed"] >= 1,
          f"events={orch.get_stats()['events_processed']}")
    check("p07_orchestrator_cycle_a", orch.get_stats()["cycle_a_fast_reacts"] >= 1,
          f"cycle_a={orch.get_stats()['cycle_a_fast_reacts']}")

    driver._urgency_accumulator._urgency = 15.0
    orch._on_event(event)
    time.sleep(0.1)
    check("p07_orchestrator_cycle_b_urgent", orch.get_stats()["cycle_b_deep_thinks"] >= 1,
          f"cycle_b={orch.get_stats()['cycle_b_deep_thinks']}")

    driver._urgency_accumulator._urgency = 35.0
    orch._on_event(event)
    time.sleep(0.1)
    check("p07_orchestrator_cycle_c_urgent", orch.get_stats()["cycle_c_evolutions"] >= 1,
          f"cycle_c={orch.get_stats()['cycle_c_evolutions']}")

    orch.stop()
    check("p07_orchestrator_stopped", not orch.get_stats()["running"])

    stats = orch.get_stats()
    check("p07_orchestrator_stats_keys",
          all(k in stats for k in ["running", "cycle_a_fast_reacts",
                                    "cycle_b_deep_thinks", "cycle_c_evolutions"]))
    check("p07_orchestrator_stats_urgency", "urgency" in stats)


def test_p08_knowledge_classified_index():
    print("\n" + "=" * 60)
    print("P08: Learning Loop知识分库+Skill提炼")
    print("=" * 60)

    from core.processors.learning_loop import (
        KnowledgeCategory, CategorizedKnowledge,
        KnowledgeClassifiedIndex, SkillExtractor,
    )

    check("p08_category_count", len(KnowledgeCategory) == 8,
          f"expected 8, got {len(KnowledgeCategory)}")
    check("p08_category_pattern", hasattr(KnowledgeCategory, "PATTERN"))
    check("p08_category_solution", hasattr(KnowledgeCategory, "SOLUTION"))
    check("p08_category_decision", hasattr(KnowledgeCategory, "DECISION"))
    check("p08_category_error", hasattr(KnowledgeCategory, "ERROR_PATTERN"))
    check("p08_category_workflow", hasattr(KnowledgeCategory, "WORKFLOW"))
    check("p08_category_best_practice", hasattr(KnowledgeCategory, "BEST_PRACTICE"))
    check("p08_category_skill", hasattr(KnowledgeCategory, "SKILL"))
    check("p08_category_insight", hasattr(KnowledgeCategory, "INSIGHT"))

    index = KnowledgeClassifiedIndex()
    check("p08_index_init", index is not None)

    k1 = CategorizedKnowledge(
        category=KnowledgeCategory.PATTERN,
        title="测试模式",
        body="这是一个测试模式描述",
        source_session="test_session",
        source_agent="tester",
        confidence=0.85,
        tags=["test", "pattern"],
        keywords=["test", "pattern"],
    )
    ok = index.add(k1)
    check("p08_index_add_pattern", ok)

    k2 = CategorizedKnowledge(
        category=KnowledgeCategory.SOLUTION,
        title="性能优化方案",
        body="使用缓存提升性能",
        source_session="test_session",
        source_agent="tester",
        confidence=0.90,
        tags=["perf", "cache"],
        keywords=["cache", "performance"],
    )
    index.add(k2)

    stats = index.get_stats()
    check("p08_index_stats_total", stats["total"] == 2,
          f"total={stats['total']}")
    check("p08_index_stats_by_category", stats["by_category"]["pattern"] == 1)
    check("p08_index_stats_solution", stats["by_category"]["solution"] == 1)

    results = index.search("性能")
    check("p08_index_search_cn", len(results) > 0,
          f"results={len(results)}")

    results = index.search("pattern")
    check("p08_index_search_en", len(results) > 0,
          f"results={len(results)}")

    by_cat = index.get_by_category(KnowledgeCategory.PATTERN)
    check("p08_index_get_by_category", len(by_cat) == 1)

    extractor = SkillExtractor(index=index)
    check("p08_extractor_init", extractor is not None)

    extractor.observe_pattern("fix_type_error", True, ["bug", "python"])
    extractor.observe_pattern("fix_type_error", True, ["bug", "typescript"])
    extractor.observe_pattern("fix_type_error", True, ["bug", "go"])

    skill = extractor.extract_skill(
        "fix_type_error",
        "def fix_type_error(code): pass",
        "修复类型错误的标准流程",
        ["pyright", "mypy"],
    )
    check("p08_extract_skill", skill is not None,
          f"skill={skill}")
    if skill:
        check("p08_skill_confidence", skill["confidence"] > 0,
              f"confidence={skill['confidence']}")
        check("p08_skill_usage", skill["usage_count"] == 3)
        check("p08_skill_success_rate", skill["success_rate"] == 1.0)
        check("p08_skill_deps", len(skill["dependencies"]) == 2)

    skills = extractor.get_skills()
    check("p08_extractor_skills_len", len(skills) >= 1,
          f"skills={len(skills)}")

    candidates = extractor.get_candidates()
    check("p08_extractor_candidates", "total_candidates" in candidates)
    check("p08_extractor_extracted", candidates["extracted_skills"] == 1)


    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        idx_path = Path(tmp) / "knowledge_index.json"
        idx2 = KnowledgeClassifiedIndex(index_path=idx_path)
        idx2.add(k1)
        idx2._save()
        check("p08_index_save", idx_path.exists())

        idx3 = KnowledgeClassifiedIndex(index_path=idx_path)
        check("p08_index_load", idx3.get_stats()["total"] == 1)


def test_p09_causal_graph_store():
    print("\n" + "=" * 60)
    print("P09: Evolution Loop因果图持久化")
    print("=" * 60)

    from core.processors.evolution_loop import (
        CausalGraphStore, ModuleCausalPair, CausalPairRecorder,
    )

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = CausalGraphStore(store_dir=Path(tmp))
        check("p09_store_init", store is not None)
        check("p09_store_dir_exists", store._store_dir.exists())

        pair1 = ModuleCausalPair(
            module_name="enforcement_hook",
            action="inject_check",
            state_before={"risk": "low"},
            state_after={"risk": "medium"},
            effectiveness=0.85,
        )
        pid1 = store.append_pair(pair1)
        check("p09_store_append", len(pid1) == 12,
              f"pair_id={pid1}")

        pair2 = ModuleCausalPair(
            module_name="enforcement_hook",
            action="inject_check",
            state_before={"risk": "low"},
            state_after={"risk": "low"},
            effectiveness=-0.30,
        )
        store.append_pair(pair2)

        pair3 = ModuleCausalPair(
            module_name="quality_gate",
            action="threshold_adjust",
            state_before={"noise": 0.3},
            state_after={"noise": 0.1},
            effectiveness=0.70,
        )
        store.append_pair(pair3)

        all_pairs = store.load_all_pairs()
        check("p09_store_load_all", len(all_pairs) == 3,
              f"pairs={len(all_pairs)}")

        mod_pairs = store.load_by_module("enforcement_hook")
        check("p09_store_load_module", len(mod_pairs) == 2,
              f"pairs={len(mod_pairs)}")

        act_pairs = store.load_by_action("inject_check")
        check("p09_store_load_action", len(act_pairs) == 2,
              f"pairs={len(act_pairs)}")

        graph = store.build_causal_graph()
        check("p09_graph_build", graph is not None)
        check("p09_graph_has_nodes", len(graph["nodes"]) > 0,
              f"nodes={len(graph['nodes'])}")
        check("p09_graph_has_edges", len(graph["edges"]) > 0,
              f"edges={len(graph['edges'])}")
        check("p09_graph_total_pairs", graph["total_pairs"] == 3)
        check("p09_graph_built_at", graph["built_at"] > 0)

        summary = store.get_summary()
        check("p09_summary_total", summary["total"] == 3)
        check("p09_summary_avg", summary["avg_effectiveness"] > 0,
              f"avg={summary['avg_effectiveness']}")
        check("p09_summary_modules", "enforcement_hook" in summary["modules"])
        check("p09_summary_top_actions", len(summary["top_actions"]) > 0)

        chain = store.visualize_causal_chain("inject_check")
        check("p09_chain_length", chain["chain_length"] == 2)
        check("p09_chain_trend", chain["trend_direction"] in ("improving", "declining", "stable"),
              f"trend={chain['trend_direction']}")
        check("p09_chain_has_effectiveness", len(chain["effectiveness_trend"]) == 2,
              f"len={len(chain['effectiveness_trend'])}")
        check("p09_chain_state_changes", len(chain["state_changes"]) == 2)

        dot = store.export_dot()
        check("p09_dot_non_empty", len(dot) > 0 and "digraph" in dot)
        check("p09_dot_has_edge", "->" in dot)

        dot_path = Path(tmp) / "causal_graph.dot"
        dot2 = store.export_dot(output_path=dot_path)
        check("p09_dot_export_file", dot_path.exists())

        stats = store.get_stats()
        check("p09_store_stats", "pairs_file" in stats)
        check("p09_store_stats_graph", "graph_file" in stats)


def main():
    print("=" * 60)
    print("P06-P09 扩展集成验证")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    test_p06_otel_eval()
    test_p07_three_cycle_orchestrator()
    test_p08_knowledge_classified_index()
    test_p09_causal_graph_store()

    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    for mod, cnt in sorted(_MODULE_CHECKS.items()):
        print(f"  [{mod}]: {cnt} checks")
    print(f"\n模块通过: {len(_MODULE_CHECKS)}")
    print(f"总检查点: {_CHECK_COUNT}")
    print(f"通过: {_PASS_COUNT} | 失败: {_FAIL_COUNT}")
    print(f"总体状态: {'ALL PASSED' if _FAIL_COUNT == 0 else 'SOME FAILED'}")

    return _FAIL_COUNT == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
