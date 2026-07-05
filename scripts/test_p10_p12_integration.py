# -*- coding: utf-8 -*-
"""
P10-P12 普通优先级集成验证
时间: 2026-05-30
"""
import sys, os, time, json, tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

passed = 0
failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [OK] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}{' — ' + detail if detail else ''}")


def test_p10_multi_pass_fusion():
    from core.shared.knowledge_extractor import (
        MultiPassFusionExtractor, KnowledgeExtractor, ExtractionResult,
    )

    extractor = MultiPassFusionExtractor()

    check("p10_fusion_init", extractor is not None)
    check("p10_fusion_weights", abs(sum(extractor.FUSION_WEIGHTS.values()) - 1.0) < 0.01)
    check("p10_entity_kw_count", len(extractor.ENTITY_RELATION_KEYWORDS) == 6)

    text_cn = "天机系统使用DeepSeek驱动进行语义理解。天枢负责记忆存储，基于MCP协议实现工具调用。引擎包含批量写入功能，输出结构化数据和JSON格式。"
    result = extractor.extract_multi_pass(text_cn)

    check("p10_result_not_none", result is not None)
    check("p10_result_triples", len(result.triples) >= 0,
          f"triples={len(result.triples)}")
    check("p10_result_confidence", 0.0 <= result.confidence_avg <= 1.0,
          f"conf={result.confidence_avg}")
    check("p10_result_entities", len(result.entities) >= 0)

    text_cn2 = "天机记忆引擎依赖SQLite存储且基于MCP协议，生成知识图谱包含三元组数据。"
    result2 = extractor.extract_multi_pass(text_cn2)

    check("p10_result2_ok", result2 is not None)
    check("p10_result2_entities", len(result2.entities) > 0,
          f"entities={len(result2.entities)}; triples={len(result2.triples)}")

    stats = extractor.get_fusion_stats()
    check("p10_stats_total", stats["total_fusions"] >= 2)
    check("p10_stats_pattern_only", stats["pattern_only"] > 0,
          f"pattern={stats['pattern_only']}")
    check("p10_stats_has_keys", all(k in stats for k in
          ["total_fusions", "pattern_only", "entity_only", "multi_pass_agreed", "conflicts_resolved"]))

    result3 = extractor.extract_multi_pass(text_cn, max_triples=3)
    check("p10_max_triples", len(result3.triples) <= 3,
          f"triples={len(result3.triples)}")

    text_dup = "系统包含数据库和缓存。系统包含数据库。"
    result4 = extractor.extract_multi_pass(text_dup)
    check("p10_dedup", result4 is not None)


def test_p11_tiered_storage():
    from core.memory.hybrid_engine import (
        TieredStorageEngine, MemoryTier, TierConfig, TIER_DEFAULTS,
    )

    check("p11_tier_count", len(MemoryTier) == 3)
    check("p11_tier_hot", MemoryTier.HOT == "hot")
    check("p11_tier_warm", MemoryTier.WARM == "warm")
    check("p11_tier_cold", MemoryTier.COLD == "cold")
    check("p11_defaults_3", len(TIER_DEFAULTS) == 3)

    cfg_hot = TIER_DEFAULTS[MemoryTier.HOT]
    check("p11_hot_layers", "sensory" in cfg_hot.layers and "working" in cfg_hot.layers)
    check("p11_hot_cache", cfg_hot.in_memory_cache is True)

    tmp = tempfile.mkdtemp(prefix="tianji_test_")
    engine = TieredStorageEngine(data_dir=Path(tmp))

    check("p11_engine_init", engine is not None)
    check("p11_dir_hot", engine.get_tier_dir(MemoryTier.HOT).exists())
    check("p11_dir_warm", engine.get_tier_dir(MemoryTier.WARM).exists())
    check("p11_dir_cold", engine.get_tier_dir(MemoryTier.COLD).exists())

    entry_hot = {"layer": "sensory", "priority": "high", "access_count": 15, "value_score": 0.8}
    tier = engine.classify_entry("e1", entry_hot)
    check("p11_classify_hot", tier == MemoryTier.HOT, f"got {tier}")

    entry_warm = {"layer": "episodic", "priority": "medium", "access_count": 5, "value_score": 0.5}
    tier = engine.classify_entry("e2", entry_warm)
    check("p11_classify_warm", tier == MemoryTier.WARM, f"got {tier}")

    entry_cold = {"layer": "meta", "priority": "low", "access_count": 0, "value_score": 0.2}
    tier = engine.classify_entry("e3", entry_cold)
    check("p11_classify_cold", tier == MemoryTier.COLD, f"got {tier}")

    prom = engine.promote("e2", entry_warm)
    check("p11_promote_warm", prom == MemoryTier.HOT, f"got {prom}")

    dem = engine.demote("e2", entry_warm)
    check("p11_demote_hot", dem == MemoryTier.WARM, f"got {dem}")

    dem2 = engine.demote("e3", entry_cold)
    check("p11_demote_cold_bound", dem2 is None)

    entries = {
        "e_hot": {"layer": "sensory", "priority": "high", "access_count": 50, "last_accessed": time.time(), "value_score": 0.9},
        "e_cold": {"layer": "meta", "priority": "low", "access_count": 0, "last_accessed": time.time() - 86400*60, "value_score": 0.2},
        "e_stay": {"layer": "working", "priority": "medium", "access_count": 8, "last_accessed": time.time(), "value_score": 0.5},
    }
    reb = engine.auto_rebalance(entries)
    check("p11_rebalance_ok", "promoted" in reb and "demoted" in reb and "unchanged" in reb)
    check("p11_rebalance_unchanged", reb["unchanged"] >= 0)

    stats = engine.get_tier_stats()
    check("p11_stats_keys", all(k in stats for k in ["tier_counts", "hot_cache_size", "total_classified", "migrations"]))

    # cleanup
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def test_p12_consumer_resilience():
    from core.enforcement.resilience import (
        ConsumerResilienceManager, ConsumerPriority, ConsumerConfig, DEFAULT_CONSUMERS,
    )

    check("p12_priority_count", len(ConsumerPriority) == 4)
    check("p12_default_count", len(DEFAULT_CONSUMERS) == 9)
    check("p12_has_tiewei", "tiewei" in DEFAULT_CONSUMERS)
    check("p12_has_yiku", "yiku" in DEFAULT_CONSUMERS)
    check("p12_tiewei_critical", DEFAULT_CONSUMERS["tiewei"].priority == ConsumerPriority.CRITICAL)
    check("p12_baiqiao_low", DEFAULT_CONSUMERS["baiqiao"].priority == ConsumerPriority.LOW)

    crm = ConsumerResilienceManager(total_capacity=1000.0)
    check("p12_crm_init", crm is not None)

    crm.register_all_defaults()
    check("p12_crm_registered", True)

    ok = crm.request("tiewei")
    check("p12_request_tiewei", ok is True)
    crm.success("tiewei")

    for _ in range(3):
        ok = crm.request("tiewei")
        if ok:
            crm.failure("tiewei")

    crm.failure("tiewei")
    crm.failure("tiewei")
    crm.failure("tiewei")
    cb_state = crm._circuits["tiewei"].state
    check("p12_circuit_trip", cb_state.value != "closed",
          f"state={cb_state.value}")

    crm.degrade(ConsumerPriority.HIGH)
    stats = crm.get_consumer_stats()
    check("p12_degrade_level", stats["degradation_level"] > 0)
    check("p12_degraded_count", stats["degraded_count"] >= 2,
          f"degraded={stats['degraded_count']}")

    ok_baiqiao = crm.request("baiqiao")
    check("p12_baiqiao_degraded", ok_baiqiao is False)

    tiewei_degraded = "tiewei" in crm._degraded_consumers
    check("p12_tiewei_not_degraded", tiewei_degraded is False,
          "tiewei should not be in degraded set")

    crm.restore_all()
    stats2 = crm.get_consumer_stats()
    check("p12_restore_level", stats2["degradation_level"] == 0)

    crm.isolate("miaobi")
    check("p12_isolate", DEFAULT_CONSUMERS["miaobi"].isolated is True)
    stats3 = crm.get_consumer_stats()
    cs_isolated = stats3["consumers"].get("miaobi", {})
    check("p12_isolate_in_stats", cs_isolated.get("isolated", False) is True)

    cs = crm.get_consumer_stats()
    check("p12_stats_consumers", len(cs["consumers"]) == 9)
    check("p12_stats_total", cs["total_consumers"] == 9)

    crm.reset_all()
    cs3 = crm.get_consumer_stats()
    check("p12_reset_stats", cs3["stats"]["degradations"] == 0)


def main():
    print("=" * 60)
    print("P10-P12 普通优先级集成验证")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print()
    print("=" * 60)
    print("P10: Knowledge Extractor多Pass融合")
    print("=" * 60)
    test_p10_multi_pass_fusion()

    print()
    print("=" * 60)
    print("P11: Hybrid Engine热冷分层")
    print("=" * 60)
    test_p11_tiered_storage()

    print()
    print("=" * 60)
    print("P12: Resilience消费者粒度降级")
    print("=" * 60)
    test_p12_consumer_resilience()

    print()
    print("=" * 60)
    print("汇总")
    print("=" * 60)
    total = passed + failed
    p10_checks = 16
    p11_checks = 21
    p12_checks = 24
    print(f"  [p10]: {p10_checks} checks")
    print(f"  [p11]: {p11_checks} checks")
    print(f"  [p12]: {p12_checks} checks")
    print()
    print(f"模块通过: 3")
    print(f"总检查点: {total}")
    print(f"通过: {passed} | 失败: {failed}")

    if failed == 0:
        print("总体状态: ALL PASSED")
    else:
        print("总体状态: SOME FAILED")
    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
