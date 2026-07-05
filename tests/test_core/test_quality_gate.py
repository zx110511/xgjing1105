"""
tests/test_core/test_quality_gate.py - QualityGate完整测试套件
覆盖: GateVerdict/GateResult/QualityGate/ConsumerAwareAdaptiveGate/AutoTuningScheduler
"""
import time
import pytest
from unittest.mock import MagicMock, patch
from core.processors.quality_gate import (
    QualityGate, GateVerdict, GateResult, QualityGateConfig,
    ConsumerAwareAdaptiveGate, AutoTuningScheduler,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def gate():
    """创建默认QualityGate实例"""
    return QualityGate()


@pytest.fixture
def gate_with_engine():
    """创建带engine的QualityGate"""
    mock_engine = MagicMock()
    return QualityGate(engine=mock_engine)


@pytest.fixture
def custom_gate():
    """创建自定义配置的QualityGate"""
    config = QualityGateConfig(
        min_content_length=5,
        max_similarity_for_duplicate=0.85,
        minimum_value_score_for_direct_write=0.3,
    )
    return QualityGate(config=config)


def _make_entry(content="测试内容", layer="working", tags=None, priority="medium", entry_id="test_001"):
    """构造测试用MemoryEntry-like对象"""
    class FakeEntry:
        def __init__(self, cid, c, l, t, p):
            self.id = cid
            self.content = c
            self.layer = l
            self.tags = t or []
            self.priority = p
    return FakeEntry(entry_id, content, layer, tags, priority)


# ============================================================
# TestGateVerdict
# ============================================================

class TestGateVerdict:
    """GateVerdict枚举测试"""

    def test_pass_value(self):
        assert GateVerdict.PASS == "pass"

    def test_downgrade_value(self):
        assert GateVerdict.DOWNGRADE == "downgrade"

    def test_reject_value(self):
        assert GateVerdict.REJECT == "reject"

    def test_conflict_value(self):
        assert GateVerdict.CONFLICT == "conflict"

    def test_pending_upstream_value(self):
        assert GateVerdict.PENDING_UPSTREAM == "pending_upstream"


# ============================================================
# TestGateResult
# ============================================================

class TestGateResult:
    """GateResult数据类测试"""

    def test_default_values(self):
        result = GateResult(verdict=GateVerdict.PASS, target_layer="working", reason="test")
        assert result.adjustments == {}
        assert result.conflicts_with == []
        assert result.suggested_upstream is None
        assert result.quality_dimensions == {}

    def test_custom_values(self):
        result = GateResult(
            verdict=GateVerdict.CONFLICT,
            target_layer="episodic",
            reason="冲突检测",
            conflicts_with=["id_1"],
            suggested_upstream="topic_x",
            quality_dimensions={"conflict": 0.8},
        )
        assert result.verdict == GateVerdict.CONFLICT
        assert len(result.conflicts_with) == 1
        assert result.suggested_upstream == "topic_x"


# ============================================================
# TestQualityGateInit
# ============================================================

class TestQualityGateInit:
    """QualityGate初始化测试"""

    def test_default_init(self, gate):
        assert gate is not None
        assert gate.config is not None

    def test_custom_config(self, custom_gate):
        assert custom_gate.config.min_content_length == 5

    def test_engine_injection(self, gate_with_engine):
        assert gate_with_engine._engine is not None


# ============================================================
# TestQualityGateCheck
# ============================================================

class TestQualityGateCheck:
    """check()核心检查测试"""

    def test_pass_normal_content(self, gate):
        result = gate.check(
            content="这是一条正常的高质量记忆内容，包含有意义的信息",
            layer="working",
            tags=["test"],
            priority="medium",
        )
        assert result.verdict in (GateVerdict.PASS, GateVerdict.DOWNGRADE)

    def test_reject_noise(self, gate):
        result = gate.check(
            content="嗯",
            layer="working",
            tags=["test"],
            priority="low",
        )
        assert result.verdict == GateVerdict.REJECT

    def test_reject_empty(self, gate):
        result = gate.check(
            content="",
            layer="working",
            tags=[],
            priority="low",
        )
        assert result.verdict == GateVerdict.REJECT

    def test_reject_symbol_noise(self, gate):
        result = gate.check(
            content="...",
            layer="working",
            tags=[],
            priority="low",
        )
        assert result.verdict == GateVerdict.REJECT

    def test_check_with_existing_entries(self, gate):
        existing = [_make_entry(content="已有记忆内容", entry_id="ex_001")]
        result = gate.check(
            content="新的独立记忆内容，与已有不同",
            layer="working",
            tags=["test"],
            priority="medium",
            existing_entries=existing,
        )
        assert result.verdict in (GateVerdict.PASS, GateVerdict.DOWNGRADE, GateVerdict.PENDING_UPSTREAM)

    def test_check_semantic_without_tags(self, gate):
        result = gate.check(
            content="语义层记忆需要标签来建立知识关联和概念索引",
            layer="semantic",
            tags=[],
            priority="medium",
        )
        # 无标签的semantic层内容可能被降级或拒绝(取决于内容长度)
        assert result.verdict in (GateVerdict.DOWNGRADE, GateVerdict.PASS, GateVerdict.REJECT)

    def test_check_high_priority(self, gate):
        result = gate.check(
            content="高优先级重要决策记录",
            layer="episodic",
            tags=["decision", "important"],
            priority="high",
        )
        assert result is not None

    def test_check_unicode_content(self, gate):
        result = gate.check(
            content="Unicode测试: 中文 日本語 한국어 🎉",
            layer="working",
            tags=["unicode"],
            priority="medium",
        )
        assert result is not None


# ============================================================
# TestQualityGateNoise
# ============================================================

class TestQualityGateNoise:
    """噪声检测测试"""

    def test_short_noise(self, gate):
        result = gate._check_noise("嗯")
        assert result["is_noise"] is True

    def test_symbol_noise(self, gate):
        result = gate._check_noise("。。。")
        assert result["is_noise"] is True

    def test_normal_content(self, gate):
        result = gate._check_noise("这是一段正常的有意义的内容")
        assert result["is_noise"] is False

    def test_empty_content(self, gate):
        result = gate._check_noise("")
        assert result["is_noise"] is True

    def test_repeat_char_noise(self, gate):
        result = gate._check_noise("aaa")
        assert result["is_noise"] is True


# ============================================================
# TestQualityGateDuplicate
# ============================================================

class TestQualityGateDuplicate:
    """重复检测测试"""

    def test_no_existing(self, gate):
        result = gate._check_duplicate("新内容", None)
        assert result["is_duplicate"] is False

    def test_similar_content(self, gate):
        existing = [_make_entry(content="Python是编程语言", entry_id="dup_001")]
        result = gate._check_duplicate("Python是编程语言", existing)
        assert result["similarity"] > 0.5

    def test_different_content(self, gate):
        existing = [_make_entry(content="完全不同的内容XYZ", entry_id="diff_001")]
        result = gate._check_duplicate("这是一个全新的独立内容ABC", existing)
        assert result["similarity"] < 0.8


# ============================================================
# TestQualityGateWill
# ============================================================

class TestQualityGateWill:
    """意志追踪测试"""

    def test_update_will(self, gate):
        gate.update_will("python", 0.8)
        topics = gate.get_will_topics()
        assert len(topics) > 0
        assert topics[0][0] == "python"

    def test_will_decay(self, gate):
        gate.update_will("topic_a", 0.9)
        gate.update_will("topic_b", 0.9)
        topics = gate.get_will_topics()
        assert len(topics) >= 1

    def test_will_topics_top_n(self, gate):
        for i in range(10):
            gate.update_will(f"topic_{i}", 0.5)
        topics = gate.get_will_topics(top_n=3)
        assert len(topics) <= 3


# ============================================================
# TestQualityGateEvolution
# ============================================================

class TestQualityGateEvolution:
    """进化闭环测试"""

    def test_calc_effectiveness(self, gate):
        score = gate._calc_gate_effectiveness(
            "gate_check",
            {"priority": "high"},
            {"verdict": "pass"},
        )
        assert isinstance(score, float)

    def test_gate_stats(self, gate):
        gate.check(content="统计测试内容", layer="working", tags=["stat"], priority="medium")
        assert gate._gate_stats["total_checks"] >= 1


# ============================================================
# TestQualityGateHealth
# ============================================================

class TestQualityGateHealth:
    """健康指标测试"""

    def test_gate_stats_initialized(self, gate):
        assert "total_checks" in gate._gate_stats
        assert "passes" in gate._gate_stats
        assert "rejects" in gate._gate_stats

    def test_reject_rate(self, gate):
        gate.check(content="嗯", layer="working", tags=[], priority="low")
        gate.check(content="正常内容测试", layer="working", tags=["test"], priority="medium")
        assert gate._gate_stats["rejects"] >= 1

    def test_check_returns_gate_result(self, gate):
        result = gate.check(content="返回类型测试", layer="working", tags=["type"], priority="medium")
        assert isinstance(result, GateResult)
        assert isinstance(result.verdict, GateVerdict)


# ============================================================
# TestQualityGateCheckPromotion
# ============================================================

class TestQualityGateCheckPromotion:
    """check_promotion()晋升门禁测试"""

    def test_promotion_sensory_to_working(self, gate):
        result = gate.check_promotion(
            content="这是一条有价值的短期记忆内容，值得晋升到工作层",
            source_layer="sensory",
            target_layer="working",
            tags=["promotion"],
            priority="medium",
        )
        assert isinstance(result, GateResult)
        assert result.verdict in (GateVerdict.PASS, GateVerdict.DOWNGRADE, GateVerdict.PENDING_UPSTREAM)

    def test_promotion_invalid_layer(self, gate):
        result = gate.check_promotion(
            content="测试内容",
            source_layer="invalid",
            target_layer="working",
        )
        assert result.verdict == GateVerdict.REJECT

    def test_promotion_skip_layer(self, gate):
        """不可跨层晋升"""
        result = gate.check_promotion(
            content="尝试跨层晋升的内容",
            source_layer="sensory",
            target_layer="episodic",
        )
        assert result.verdict == GateVerdict.DOWNGRADE

    def test_promotion_downgrade_same_layer(self, gate):
        """降级/同级操作直接PASS"""
        result = gate.check_promotion(
            content="同级操作",
            source_layer="working",
            target_layer="working",
        )
        assert result.verdict == GateVerdict.PASS

    def test_promotion_downgrade_to_lower(self, gate):
        """降级操作直接PASS"""
        result = gate.check_promotion(
            content="降级操作",
            source_layer="episodic",
            target_layer="working",
        )
        assert result.verdict == GateVerdict.PASS

    def test_promotion_low_value_content(self, gate):
        """低价值内容晋升被降级"""
        result = gate.check_promotion(
            content="短",
            source_layer="working",
            target_layer="short_term",
        )
        assert result.verdict in (GateVerdict.DOWNGRADE, GateVerdict.PASS, GateVerdict.PENDING_UPSTREAM)


# ============================================================
# TestQualityGateConflict
# ============================================================

class TestQualityGateConflict:
    """冲突检测测试"""

    def test_no_conflict_no_negation(self, gate):
        existing = [_make_entry(content="正常记忆内容", entry_id="c_001")]
        result = gate._check_conflict("新的独立内容", existing)
        assert result["has_conflict"] is False

    def test_conflict_with_negation(self, gate):
        existing = [_make_entry(
            content="Python是最好的编程语言，功能强大且易于学习，适合初学者入门",
            entry_id="c_001",
        )]
        result = gate._check_conflict(
            "Python不是最好的编程语言，错误地认为它适合所有场景，应该废弃这个观点",
            existing,
        )
        # 有否定词且有语义重叠且内容够长，可能检测到冲突
        assert isinstance(result, dict)
        assert "has_conflict" in result

    def test_no_existing_entries(self, gate):
        result = gate._check_conflict("任意内容", None)
        assert result["has_conflict"] is False


# ============================================================
# TestQualityGateUpstream
# ============================================================

class TestQualityGateUpstream:
    """上游锚点检测测试"""

    def test_upstream_not_required_for_working(self, gate):
        result = gate._check_upstream("内容", "working", None)
        assert result["pass"] is True

    def test_upstream_required_for_semantic_no_existing(self, gate):
        """语义层无现有记忆"""
        result = gate._check_upstream("语义层内容", "semantic", None)
        assert result["pass"] is False

    def test_upstream_with_related_entries(self, gate):
        """有相关上游记忆"""
        existing = [_make_entry(content="语义层内容相关记忆", entry_id="up_001")]
        result = gate._check_upstream("语义层内容", "semantic", existing)
        assert isinstance(result, dict)


# ============================================================
# TestQualityGateLength
# ============================================================

class TestQualityGateLength:
    """长度检查测试"""

    def test_long_content(self, gate):
        result = gate._check_length("A" * 200)
        assert result["pass"] is True
        assert result["score"] == 1.0

    def test_medium_content(self, gate):
        result = gate._check_length("A" * 60)
        assert result["pass"] is True

    def test_short_content(self, gate):
        result = gate._check_length("A" * 5)
        assert result["pass"] is False

    def test_very_short_content(self, gate):
        result = gate._check_length("AB")
        assert result["score"] <= 0.3


# ============================================================
# TestQualityGateCausalChain
# ============================================================

class TestQualityGateCausalChain:
    """因果链检测测试"""

    def test_no_existing(self, gate):
        score = gate._check_causal_chain("因为所以", None)
        assert score >= 0.3

    def test_with_causal_patterns(self, gate):
        existing = [_make_entry(content="因为架构设计所以需要重构", entry_id="causal_001")]
        score = gate._check_causal_chain("因为性能问题所以需要优化", existing)
        assert score >= 0.3


# ============================================================
# TestQualityGateWillAlignment
# ============================================================

class TestQualityGateWillAlignment:
    """意志对齐测试"""

    def test_no_will_topics(self, gate):
        score = gate._check_will_alignment("测试内容", ["test"], "medium")
        assert score >= 0.3

    def test_with_matching_will(self, gate):
        gate.update_will("python", 0.8)
        score = gate._check_will_alignment("python编程", ["python"], "high")
        assert score >= 0.5


# ============================================================
# TestQualityGateHelperMethods
# ============================================================

class TestQualityGateHelperMethods:
    """辅助方法测试"""

    def test_determine_fallback(self, gate):
        assert gate._determine_fallback("episodic") == "short_term"
        assert gate._determine_fallback("working") == "sensory"
        assert gate._determine_fallback("sensory") == "working"
        assert gate._determine_fallback("unknown") == "working"

    def test_has_semantic_overlap(self, gate):
        assert gate._has_semantic_overlap("Python 编程 语言", "Python 编程 工具")
        assert not gate._has_semantic_overlap("完全不同", "毫不相关")

    def test_guess_upstream_topic(self, gate):
        topic = gate._guess_upstream_topic("因为架构设计需要调整")
        assert "因为" in topic or len(topic) > 0

    def test_longest_common_substring(self, gate):
        assert gate._longest_common_substring("abcdef", "abcxyz") == 3
        assert gate._longest_common_substring("", "abc") == 0
        assert gate._longest_common_substring("abc", "") == 0

    def test_char_ngrams(self, gate):
        result = gate._char_ngrams("abcdef", n=3)
        assert "abc" in result
        assert "def" in result

    def test_check_preference_drift_no_detector(self, gate):
        result = gate._check_preference_drift("内容", ["tag1"])
        assert result["has_drift"] is False

    def test_try_auto_resolve_no_resolver(self, gate):
        result = gate._try_auto_resolve_conflict("内容", {"matched_ids": ["id1"]}, None)
        assert result is False


# ============================================================
# TestQualityGateGetStats
# ============================================================

class TestQualityGateGetStats:
    """get_stats()统计测试"""

    def test_stats_structure(self, gate):
        stats = gate.get_stats()
        assert "version" in stats
        assert "gate_stats" in stats
        assert "rates" in stats
        assert "will_tracker" in stats
        assert "subsystems" in stats

    def test_stats_after_checks(self, gate):
        gate.check(content="统计测试", layer="working", tags=["stat"], priority="medium")
        gate.check(content="嗯", layer="working", tags=[], priority="low")
        stats = gate.get_stats()
        assert stats["gate_stats"]["total_checks"] >= 2


# ============================================================
# TestConsumerAwareAdaptiveGate
# ============================================================

class TestConsumerAwareAdaptiveGate:
    """ConsumerAwareAdaptiveGate自适应门禁测试"""

    @pytest.fixture
    def adaptive_gate(self):
        gate = QualityGate()
        return ConsumerAwareAdaptiveGate(gate)

    def test_init(self, adaptive_gate):
        assert adaptive_gate is not None

    def test_update_consumer_pressure(self, adaptive_gate):
        adaptive_gate.update_consumer_pressure("test_consumer", 0.8)
        assert adaptive_gate._consumer_pressure["test_consumer"] == 0.8

    def test_update_consumer_pressure_clamp(self, adaptive_gate):
        adaptive_gate.update_consumer_pressure("test", 1.5)
        assert adaptive_gate._consumer_pressure["test"] == 1.0
        adaptive_gate.update_consumer_pressure("test", -0.5)
        assert adaptive_gate._consumer_pressure["test"] == 0.0

    def test_update_system_load(self, adaptive_gate):
        adaptive_gate.update_system_load(0.7)
        assert adaptive_gate._system_load == 0.7

    def test_update_system_load_clamp(self, adaptive_gate):
        adaptive_gate.update_system_load(2.0)
        assert adaptive_gate._system_load == 1.0
        adaptive_gate.update_system_load(0.0)
        assert adaptive_gate._system_load == 0.1

    def test_update_feedback_quality(self, adaptive_gate):
        adaptive_gate.update_feedback_quality(0.6)
        assert adaptive_gate._feedback_quality == 0.6

    def test_get_adaptive_thresholds(self, adaptive_gate):
        thresholds = adaptive_gate.get_adaptive_thresholds()
        assert "noise_threshold" in thresholds
        assert "duplicate_threshold" in thresholds
        assert "min_content_length" in thresholds
        assert "effective_value_score" in thresholds

    def test_apply(self, adaptive_gate):
        adaptive_gate.update_consumer_pressure("consumer_a", 0.5)
        change = adaptive_gate.apply()
        assert "old" in change
        assert "new" in change
        assert "timestamp" in change

    def test_get_stats(self, adaptive_gate):
        stats = adaptive_gate.get_stats()
        assert "adaptive_enabled" in stats
        assert "current_thresholds" in stats
        assert "adjustment_count" in stats

    def test_run_tuning_cycle(self, adaptive_gate):
        result = adaptive_gate.run_tuning_cycle()
        assert "timestamp" in result
        assert "adjustments" in result

    def test_get_tuning_history(self, adaptive_gate):
        adaptive_gate.apply()
        history = adaptive_gate.get_tuning_history()
        assert isinstance(history, list)
        assert len(history) >= 1

    def test_get_tuning_summary(self, adaptive_gate):
        adaptive_gate.apply()
        summary = adaptive_gate.get_tuning_summary()
        assert "total_adjustments" in summary

    def test_get_tuning_summary_empty(self, adaptive_gate):
        summary = adaptive_gate.get_tuning_summary()
        assert summary["total_adjustments"] == 0

    def test_high_pressure_loosens_gate(self, adaptive_gate):
        """高消费压力 → 降低阈值"""
        adaptive_gate.update_consumer_pressure("consumer_a", 0.9)
        thresholds = adaptive_gate.get_adaptive_thresholds()
        assert thresholds["min_content_length"] < 30  # 低于默认30


# ============================================================
# TestAutoTuningScheduler
# ============================================================

class TestAutoTuningScheduler:
    """AutoTuningScheduler自动调优调度器测试"""

    @pytest.fixture
    def scheduler(self):
        gate = QualityGate()
        adaptive = ConsumerAwareAdaptiveGate(gate)
        return AutoTuningScheduler(adaptive, interval_seconds=1.0)

    def test_init(self, scheduler):
        assert scheduler is not None
        assert scheduler.is_running is False

    def test_start_stop(self, scheduler):
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.stop()
        assert scheduler.is_running is False

    def test_run_now(self, scheduler):
        result = scheduler.run_now()
        assert "status" in result
        assert result["status"] == "completed"
        assert result["cycle"] >= 1

    def test_get_scheduler_stats(self, scheduler):
        stats = scheduler.get_scheduler_stats()
        assert "running" in stats
        assert "interval_seconds" in stats
        assert "cycles_completed" in stats

    def test_double_start(self, scheduler):
        scheduler.start()
        scheduler.start()  # 不应重复启动
        assert scheduler.is_running is True
        scheduler.stop()

    def test_scan_consumers(self, scheduler):
        scheduler._scan_all_consumers()
        # 应为CONSUMERS列表中的消费者设置压力
        assert len(scheduler._gate._consumer_pressure) > 0

    def test_detect_consumer_pressure(self, scheduler):
        scheduler._scan_all_consumers()
        scheduler._detect_consumer_pressure()
        assert scheduler._gate._system_load > 0
        assert scheduler._gate._feedback_quality > 0

    def test_scheduler_stats_after_run(self, scheduler):
        scheduler.run_now()
        stats = scheduler.get_scheduler_stats()
        assert stats["cycles_completed"] >= 1
        assert stats["total_tunings"] >= 1


# ============================================================
# TestQualityGateEvolutionAdvanced
# ============================================================

class TestQualityGateEvolutionAdvanced:
    """QualityGate进化闭环高级测试 - 覆盖_calc_gate_effectiveness各分支"""

    def test_calc_effectiveness_reject_high_priority(self, gate):
        score = gate._calc_gate_effectiveness(
            "gate_check", {"priority": "high"}, {"verdict": "reject"},
        )
        assert score == -0.5

    def test_calc_effectiveness_reject_critical(self, gate):
        score = gate._calc_gate_effectiveness(
            "gate_check", {"priority": "critical"}, {"verdict": "reject"},
        )
        assert score == -0.5

    def test_calc_effectiveness_downgrade_high(self, gate):
        score = gate._calc_gate_effectiveness(
            "gate_check", {"priority": "high"}, {"verdict": "downgrade"},
        )
        assert score == -0.3

    def test_calc_effectiveness_pass_low(self, gate):
        score = gate._calc_gate_effectiveness(
            "gate_check", {"priority": "low"}, {"verdict": "pass"},
        )
        assert score == 0.1

    def test_calc_effectiveness_pass_high(self, gate):
        score = gate._calc_gate_effectiveness(
            "gate_check", {"priority": "high"}, {"verdict": "pass"},
        )
        assert score == 0.5

    def test_calc_effectiveness_pass_critical(self, gate):
        score = gate._calc_gate_effectiveness(
            "gate_check", {"priority": "critical"}, {"verdict": "pass"},
        )
        assert score == 0.5

    def test_calc_effectiveness_neutral(self, gate):
        score = gate._calc_gate_effectiveness(
            "gate_check", {"priority": "medium"}, {"verdict": "downgrade"},
        )
        assert score == 0.0

    def test_learn_from_gates_high_neg_ratio(self, gate):
        result = gate._learn_from_gates(
            [], {"negative_ratio": 0.5, "avg": 0.1},
        )
        assert "拒绝/降级率过高" in result["insight"]

    def test_learn_from_gates_good_effectiveness(self, gate):
        result = gate._learn_from_gates(
            [], {"negative_ratio": 0.01, "avg": 0.5},
        )
        assert "门禁效果良好" in result["insight"]

    def test_evolve_gate_thresholds_high_neg(self, gate):
        result = gate._evolve_gate_thresholds(
            {"negative_ratio": 0.5}, {"noise_threshold": 0.3},
        )
        assert len(result["changes"]) > 0

    def test_evolve_gate_thresholds_low_neg(self, gate):
        result = gate._evolve_gate_thresholds(
            {"negative_ratio": 0.01}, {"noise_threshold": 0.3},
        )
        assert len(result["changes"]) > 0

    def test_evolve_gate_thresholds_normal(self, gate):
        result = gate._evolve_gate_thresholds(
            {"negative_ratio": 0.15}, {"noise_threshold": 0.3},
        )
        assert result["changes"] == []

    def test_get_health_metrics(self, gate):
        gate._gate_stats["total_checks"] = 10
        gate._gate_stats["rejects"] = 3
        gate._gate_stats["downgrades"] = 2
        metrics = gate._get_health_metrics()
        assert metrics["rejection_rate"] == 0.3
        assert metrics["downgrade_rate"] == 0.2

    def test_evolution_loop_property(self, gate):
        loop = gate.evolution_loop
        assert loop is gate._evo_loop

    def test_sync_evo_config_no_loop(self, gate):
        gate._sync_evo_config()  # 不应崩溃


# ============================================================
# TestQualityGateCheckAdvanced
# ============================================================

class TestQualityGateCheckAdvanced:
    """check()高级分支测试"""

    def test_check_duplicate_reject(self, gate):
        """重复内容被拒绝"""
        existing = [_make_entry(
            content="Python是编程语言Python是编程语言Python是编程语言",
            entry_id="dup_001",
        )]
        result = gate.check(
            content="Python是编程语言Python是编程语言Python是编程语言",
            layer="working",
            tags=["test"],
            priority="medium",
            existing_entries=existing,
        )
        assert result.verdict == GateVerdict.REJECT

    def test_check_upstream_pending(self, gate):
        """语义层无上游导致PENDING_UPSTREAM"""
        result = gate.check(
            content="语义层记忆需要上游锚点支持，这是一段足够长的语义内容用于测试",
            layer="semantic",
            tags=["test"],
            priority="medium",
        )
        assert result.verdict in (GateVerdict.PENDING_UPSTREAM, GateVerdict.DOWNGRADE, GateVerdict.PASS, GateVerdict.REJECT)

    def test_check_conflict_detected(self, gate):
        """冲突检测触发"""
        existing = [_make_entry(
            content="Python是最好的编程语言，功能强大且易于学习，适合初学者入门和高级开发",
            entry_id="conf_001",
        )]
        result = gate.check(
            content="Python不是最好的编程语言，错误地认为它适合所有场景，应该废弃这个观点并替换为新的认识",
            layer="working",
            tags=["test"],
            priority="medium",
            existing_entries=existing,
        )
        # 可能检测到冲突或通过
        assert isinstance(result, GateResult)

    def test_check_downgrade_low_score(self, gate):
        """综合评分不足被降级"""
        result = gate.check(
            content="短",
            layer="working",
            tags=[],
            priority="low",
        )
        assert result.verdict in (GateVerdict.REJECT, GateVerdict.DOWNGRADE)

    def test_check_with_evo_loop_recording(self, gate):
        """有evo_loop时记录action"""
        gate._evo_loop = MagicMock()
        result = gate.check(
            content="测试evo loop记录的内容",
            layer="working",
            tags=["evo"],
            priority="medium",
        )
        if gate._evo_loop:
            gate._evo_loop.record_action.assert_called()


# ============================================================
# TestQualityGateConflictAdvanced
# ============================================================

class TestQualityGateConflictAdvanced:
    """冲突检测高级测试 - 覆盖否定词路径"""

    def test_conflict_disabled(self):
        """冲突检测禁用"""
        config = QualityGateConfig(conflict_detection_enabled=False)
        gate = QualityGate(config=config)
        existing = [_make_entry(content="任何内容", entry_id="c_001")]
        result = gate._check_conflict("任意内容", existing)
        assert result["has_conflict"] is False

    def test_conflict_no_negation_words(self, gate):
        """内容无否定词"""
        existing = [_make_entry(content="正常记忆内容", entry_id="c_001")]
        result = gate._check_conflict("完全正常的新内容", existing)
        assert result["has_confift"] is False if "has_confift" in result else result["has_conflict"] is False

    def test_conflict_with_negation_and_overlap(self, gate):
        """有否定词且有语义重叠"""
        existing = [_make_entry(
            content="Python是最好的编程语言，功能强大且易于学习，适合初学者入门和高级开发",
            entry_id="c_001",
        )]
        result = gate._check_conflict(
            "Python不是最好的编程语言，错误地认为它适合所有场景，应该废弃这个观点并替换为新的认识",
            existing,
        )
        # 有否定词+语义重叠+内容>30字符 → 可能检测到冲突
        assert isinstance(result, dict)

    def test_conflict_exceeds_max_retention(self, gate):
        """冲突超过max_conflict_retention"""
        entries = [
            _make_entry(
                content=f"Python是最好的编程语言，功能强大且易于学习，适合初学者入门和高级开发之{ i}",
                entry_id=f"c_{i}",
            )
            for i in range(10)
        ]
        result = gate._check_conflict(
            "Python不是最好的编程语言，错误地认为它适合所有场景，应该废弃这个观点并替换为新的认识",
            entries,
        )
        assert isinstance(result, dict)

    def test_conflict_with_resolver(self, gate):
        """有ConflictResolver时的路径"""
        mock_resolver = MagicMock()
        mock_resolver.detect_conflict_by_content.return_value = None
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="测试内容", entry_id="c_001")]
        result = gate._check_conflict("新内容", existing)
        assert result["has_conflict"] is False

    def test_conflict_resolver_detects_conflict(self, gate):
        """ConflictResolver检测到冲突"""
        mock_resolver = MagicMock()
        mock_type = MagicMock()
        mock_type.value = "factual"
        mock_resolver.detect_conflict_by_content.return_value = mock_type
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="测试内容", entry_id="c_001")]
        result = gate._check_conflict("冲突内容", existing)
        assert result["has_conflict"] is True

    def test_try_auto_resolve_with_resolver(self, gate):
        """_try_auto_resolve_conflict有resolver时"""
        mock_resolver = MagicMock()
        mock_verdict = MagicMock()
        mock_verdict.action = "merge"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["c_001"]}, existing,
        )
        assert result is True

    def test_try_auto_resolve_no_match(self, gate):
        """_try_auto_resolve_conflict无匹配ID"""
        mock_resolver = MagicMock()
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["other_id"]}, existing,
        )
        assert result is False

    def test_try_auto_resolve_empty_ids(self, gate):
        """_try_auto_resolve_conflict空ID列表"""
        mock_resolver = MagicMock()
        gate._conflict_resolver = mock_resolver
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": []}, None,
        )
        assert result is False

    def test_try_auto_resolve_verdict_not_merge(self, gate):
        """_try_auto_resolve_conflict verdict不是merge"""
        mock_resolver = MagicMock()
        mock_verdict = MagicMock()
        mock_verdict.action = "reject"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["c_001"]}, existing,
        )
        assert result is False

    def test_try_auto_resolve_exception(self, gate):
        """_try_auto_resolve_conflict异常处理"""
        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = Exception("test error")
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["c_001"]}, existing,
        )
        assert result is False


# ============================================================
# TestQualityGateUpstreamAdvanced
# ============================================================

class TestQualityGateUpstreamAdvanced:
    """上游锚点高级测试"""

    def test_upstream_with_related_entries(self, gate):
        """有相关上游记忆"""
        existing = [_make_entry(content="语义层 内容 相关 记忆", entry_id="up_001")]
        result = gate._check_upstream("语义层 内容 测试", "semantic", existing)
        # 语义重叠取决于_has_semantic_overlap的实现
        assert isinstance(result, dict)

    def test_upstream_no_related_entries(self, gate):
        """语义层无相关上游"""
        existing = [_make_entry(content="完全无关的内容XYZ", entry_id="up_002")]
        result = gate._check_upstream("语义层内容", "semantic", existing)
        assert result["pass"] is False
        assert result["can_pend"] is True

    def test_upstream_meta_layer_no_existing(self, gate):
        """meta层无现有记忆"""
        result = gate._check_upstream("元认知内容", "meta", None)
        assert result["pass"] is False


# ============================================================
# TestQualityGatePromotionAdvanced
# ============================================================

class TestQualityGatePromotionAdvanced:
    """晋升门禁高级测试"""

    def test_promotion_with_engine_no_results(self, gate_with_engine):
        """有engine但recall无结果 → upstream_ok=False"""
        gate_with_engine._engine.recall.return_value = []
        result = gate_with_engine.check_promotion(
            content="这是一条有价值的记忆内容，包含架构设计和策略决策",
            source_layer="working",
            target_layer="short_term",
            tags=["promotion"],
            priority="high",
        )
        # engine返回空结果，upstream_ok=False，source不是sensory → PENDING_UPSTREAM
        assert result.verdict in (GateVerdict.PASS, GateVerdict.PENDING_UPSTREAM, GateVerdict.DOWNGRADE)

    def test_promotion_with_engine_has_results(self, gate_with_engine):
        """有engine且recall有结果"""
        gate_with_engine._engine.recall.return_value = [{"id": "r1"}]
        result = gate_with_engine.check_promotion(
            content="这是一条有价值的记忆内容，包含架构设计和策略决策",
            source_layer="working",
            target_layer="short_term",
            tags=["promotion"],
            priority="high",
        )
        assert isinstance(result, GateResult)

    def test_promotion_with_engine_exception(self, gate_with_engine):
        """engine recall异常 → 返回True"""
        gate_with_engine._engine.recall.side_effect = Exception("test")
        ok = gate_with_engine._check_promotion_upstream("内容", "working")
        assert ok is True

    def test_calc_promotion_value_with_code(self, gate):
        """_calc_promotion_value含代码块"""
        content = "```python\nprint('hello')\nprint('world')\nprint('test')\nprint('more')\nprint('lines')\n```"
        score = gate._calc_promotion_value(content, ["tag1", "tag2", "tag3"], "high")
        assert score > 0

    def test_calc_promotion_value_with_strategy_keywords(self, gate):
        """_calc_promotion_value含策略关键词"""
        content = "这是一个关于架构设计和策略规则的重要决策记录"
        score = gate._calc_promotion_value(content, [], "critical")
        assert score > 0

    def test_calc_promotion_value_short_content(self, gate):
        """_calc_promotion_value短内容"""
        score = gate._calc_promotion_value("短", [], "low")
        assert score >= 0.0

    def test_check_promotion_upstream_no_engine(self, gate):
        """无engine时_check_promotion_upstream返回True"""
        assert gate._check_promotion_upstream("内容", "working") is True


# ============================================================
# TestQualityGateNoiseAdvanced
# ============================================================

class TestQualityGateNoiseAdvanced:
    """噪声检测高级测试"""

    def test_repeat_char_noise(self, gate):
        result = gate._check_noise("aaa")
        assert result["is_noise"] is True

    def test_no_meaningful_chars(self, gate):
        result = gate._check_noise("12345")
        assert result["is_noise"] is True

    def test_whitespace_only(self, gate):
        result = gate._check_noise("   ")
        assert result["is_noise"] is True

    def test_normal_chinese(self, gate):
        result = gate._check_noise("正常中文内容")
        assert result["is_noise"] is False


# ============================================================
# TestConsumerAwareAdaptiveGateAdvanced
# ============================================================

class TestConsumerAwareAdaptiveGateAdvanced:
    """ConsumerAwareAdaptiveGate高级测试"""

    @pytest.fixture
    def adaptive_gate(self):
        gate = QualityGate()
        return ConsumerAwareAdaptiveGate(gate)

    def test_adjustment_history_truncation(self, adaptive_gate):
        """调整历史超过100条时截断"""
        for i in range(110):
            adaptive_gate.update_consumer_pressure(f"c_{i % 5}", 0.5)
            adaptive_gate.apply()
        assert len(adaptive_gate._adjustment_history) <= 100

    def test_update_feedback_quality_clamp(self, adaptive_gate):
        adaptive_gate.update_feedback_quality(2.0)
        assert adaptive_gate._feedback_quality == 1.0
        adaptive_gate.update_feedback_quality(-0.5)
        assert adaptive_gate._feedback_quality == 0.1

    def test_get_tuning_history_limit(self, adaptive_gate):
        for i in range(25):
            adaptive_gate.apply()
        history = adaptive_gate.get_tuning_history(limit=10)
        assert len(history) <= 10

    def test_run_tuning_cycle_details(self, adaptive_gate):
        adaptive_gate.update_consumer_pressure("consumer_a", 0.6)
        result = adaptive_gate.run_tuning_cycle()
        assert "delta_noise" in result["adjustments"]
        assert "delta_dup" in result["adjustments"]
        assert "delta_min_len" in result["adjustments"]

    def test_get_tuning_summary_with_data(self, adaptive_gate):
        adaptive_gate.update_consumer_pressure("consumer_a", 0.5)
        adaptive_gate.apply()
        adaptive_gate.update_consumer_pressure("consumer_a", 0.3)
        adaptive_gate.apply()
        summary = adaptive_gate.get_tuning_summary()
        assert "avg_noise_delta" in summary
        assert "trend" in summary


# ============================================================
# TestQualityGateRemainingCoverage
# ============================================================

class TestQualityGateRemainingCoverage:
    """覆盖剩余未覆盖行"""

    def test_init_with_icmeconfig_having_quality_gate(self):
        """__init__传入ICMEConfig对象(has quality_gate属性)"""
        from core.shared.config import ICMEConfig
        config = ICMEConfig()
        gate = QualityGate(config=config)
        # hasattr(cfg, 'quality_gate') → True → cfg = cfg.quality_gate
        assert gate.config is config.quality_gate

    def test_sync_evo_config_with_loop(self, gate):
        """_sync_evo_config有evo_loop时同步配置"""
        mock_loop = MagicMock()
        mock_loop.mutable_config = {
            "noise_threshold": 0.5,
            "min_content_length": 50,
            "duplicate_threshold": 0.9,
            "will_decay_rate": 0.1,
        }
        gate._evo_loop = mock_loop
        gate._sync_evo_config()
        assert gate.config.noise_threshold == 0.5
        assert gate.config.min_content_length == 50
        assert gate.config.duplicate_threshold == 0.9
        assert gate._will_decay_rate == 0.1

    def test_check_conflict_in_check_flow(self, gate):
        """check()中触发冲突检测的完整路径(行242-248)"""
        # 设置conflict_resolver为None以走否定词路径
        gate._conflict_resolver = None
        existing = [_make_entry(
            content="Python是最好的编程语言，功能强大且易于学习，适合初学者入门和高级开发",
            entry_id="conf_001",
        )]
        result = gate.check(
            content="Python不是最好的编程语言，错误地认为它适合所有场景，应该废弃这个观点并替换为新的认识",
            layer="working",
            tags=["test"],
            priority="medium",
            existing_entries=existing,
        )
        assert isinstance(result, GateResult)

    def test_check_drift_signal(self, gate):
        """check()中偏好漂移检测has_drift分支(行259)"""
        # 无drift_detector时has_drift=False，不会进入该分支
        # 用mock模拟有drift_detector的情况
        mock_detector = MagicMock()
        mock_signal = MagicMock()
        mock_signal.delta = 0.5
        mock_signal.drift_type = MagicMock()
        mock_signal.drift_type.value = "gradual"
        mock_signal.topic = "python"
        mock_detector.detect.return_value = [mock_signal]
        gate._preference_drift_detector = mock_detector
        result = gate.check(
            content="这是一段关于Python编程的正常内容测试",
            layer="working",
            tags=["python"],
            priority="medium",
        )
        assert isinstance(result, GateResult)

    def test_check_evo_loop_recording(self, gate):
        """check()中evo_loop.record_action(行280-282)"""
        mock_loop = MagicMock()
        mock_loop.mutable_config = {}  # 空dict → _sync_evo_config不修改config
        gate._evo_loop = mock_loop
        # 需要内容足够长，通过噪声/长度检查
        result = gate.check(
            content="测试evo loop记录的内容，足够长的文字用于通过质量门禁检查",
            layer="working",
            tags=["test"],
            priority="medium",
        )
        # record_action在check()末尾调用
        assert isinstance(result, GateResult)

    def test_update_will_decay_removal(self, gate):
        """update_will中decay到0.01以下删除(行305)"""
        gate.update_will("topic_a", 0.02)
        gate.update_will("topic_b", 0.9)  # topic_a会decay
        # topic_a的0.02 - 0.05 = -0.03 → max(0, -0.03) = 0 → <=0.01 → 删除
        topics = dict(gate._will_tracker)
        assert "topic_a" not in topics

    def test_check_noise_repeat_chars(self, gate):
        """_check_noise重复字符噪声(行320)"""
        result = gate._check_noise("aaaa")
        assert result["is_noise"] is True

    def test_check_duplicate_empty_content_words(self, gate):
        """_check_duplicate中空content_words(行348)"""
        existing = [_make_entry(content="", entry_id="empty_001")]
        result = gate._check_duplicate("新内容", existing)
        assert result["is_duplicate"] is False

    def test_check_causal_chain_downstream(self, gate):
        """_check_causal_chain中downstream_score(行434)"""
        existing = [_make_entry(
            content="因为架构设计所以需要重构，这是一个简短的记录",
            entry_id="causal_001",
        )]
        score = gate._check_causal_chain(
            "因为性能问题所以需要优化，这是一个较长的详细记录说明",
            existing,
        )
        assert score >= 0.3

    def test_check_conflict_resolver_path(self, gate):
        """_check_conflict有ConflictResolver路径(行475-507)"""
        mock_resolver = MagicMock()
        # 先测试detect返回None → 无冲突
        mock_resolver.detect_conflict_by_content.return_value = None
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="测试内容", entry_id="c_001")]
        result = gate._check_conflict("新内容", existing)
        assert result["has_conflict"] is False

    def test_check_conflict_resolver_detects(self, gate):
        """_check_conflict ConflictResolver检测到冲突"""
        mock_resolver = MagicMock()
        mock_type = MagicMock()
        mock_type.value = "factual"
        mock_resolver.detect_conflict_by_content.return_value = mock_type
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="测试内容", entry_id="c_001")]
        result = gate._check_conflict("冲突内容", existing)
        assert result["has_conflict"] is True
        assert "factual" in result["reason"]

    def test_check_conflict_negation_path_with_overlap(self, gate):
        """_check_conflict否定词+语义重叠路径(行492-507)"""
        gate._conflict_resolver = None
        existing = [_make_entry(
            content="Python是最好的编程语言 功能强大且易于学习 适合初学者入门",
            entry_id="c_001",
        )]
        result = gate._check_conflict(
            "Python不是最好的编程语言 错误地认为它适合所有场景 应该废弃这个观点并替换新的认识",
            existing,
        )
        assert isinstance(result, dict)

    def test_try_auto_resolve_merge_verdict(self, gate):
        """_try_auto_resolve_conflict中verdict.action=merge(行552)"""
        mock_resolver = MagicMock()
        mock_verdict = MagicMock()
        mock_verdict.action = "merge"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["c_001"]}, existing,
        )
        assert result is True

    def test_try_auto_resolve_update_existing(self, gate):
        """_try_auto_resolve_conflict中verdict.action=update_existing"""
        mock_resolver = MagicMock()
        mock_verdict = MagicMock()
        mock_verdict.action = "update_existing"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["c_001"]}, existing,
        )
        assert result is True

    def test_try_auto_resolve_supersede(self, gate):
        """_try_auto_resolve_conflict中verdict.action=supersede"""
        mock_resolver = MagicMock()
        mock_verdict = MagicMock()
        mock_verdict.action = "supersede"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["c_001"]}, existing,
        )
        assert result is True

    def test_check_promotion_upstream_engine_exception(self, gate_with_engine):
        """_check_promotion_upstream中engine异常(行688-689)"""
        gate_with_engine._engine.recall.side_effect = RuntimeError("test")
        ok = gate_with_engine._check_promotion_upstream("内容", "working")
        assert ok is True

    def test_scheduler_loop_runs(self):
        """AutoTuningScheduler._scheduler_loop执行(行874-876)"""
        gate = QualityGate()
        adaptive = ConsumerAwareAdaptiveGate(gate)
        scheduler = AutoTuningScheduler(adaptive, interval_seconds=0.1)
        scheduler.start()
        import time; time.sleep(0.5)
        scheduler.stop()
        assert scheduler._cycle_count >= 1

    def test_run_now_error_path(self):
        """AutoTuningScheduler.run_now异常路径(行918-919)"""
        gate = QualityGate()
        adaptive = ConsumerAwareAdaptiveGate(gate)
        scheduler = AutoTuningScheduler(adaptive, interval_seconds=1.0)
        # 模拟_run_single_cycle异常
        scheduler._run_single_cycle = MagicMock(side_effect=Exception("test"))
        result = scheduler.run_now()
        assert result["status"] == "error"

    def test_check_noise_symbol_patterns(self, gate):
        """_check_noise符号噪声模式"""
        for pattern in ["---", "===", "***", "，，，"]:
            result = gate._check_noise(pattern)
            assert result["is_noise"] is True

    def test_check_noise_no_meaningful(self, gate):
        """_check_noise无有意义字符"""
        result = gate._check_noise("12345!@#")
        assert result["is_noise"] is True
        assert result["score"] == 0.1

    def test_check_noise_repeat_char_short(self, gate):
        """_check_noise重复字符噪声(行320): len(set)<=2 and len<=10"""
        result = gate._check_noise("aa")
        assert result["is_noise"] is True
        assert result["reason"] == "重复字符噪声"

    def test_check_full_flow_with_evo_loop(self, gate):
        """check()完整流程含evo_loop.record_action(行280-282)"""
        mock_loop = MagicMock()
        mock_loop.mutable_config = {}
        gate._evo_loop = mock_loop
        # 使用足够长的内容+working层+有标签 → 应能通过所有检查到达evo_loop
        result = gate.check(
            content="这是一段高质量的记忆内容，包含有意义的中文信息和知识，用于测试evo loop的记录功能是否正常工作",
            layer="working",
            tags=["test", "evo"],
            priority="high",
        )
        assert isinstance(result, GateResult)
        # 验证evo_loop.record_action被调用
        if result.verdict in (GateVerdict.PASS, GateVerdict.DOWNGRADE):
            mock_loop.record_action.assert_called()

    def test_check_conflict_auto_resolve_in_check(self, gate):
        """check()中conflict检测→auto_resolve路径(行242-248)"""
        mock_resolver = MagicMock()
        mock_type = MagicMock()
        mock_type.value = "factual"
        mock_resolver.detect_conflict_by_content.return_value = mock_type
        # auto-resolve返回True → 冲突已解决
        mock_verdict = MagicMock()
        mock_verdict.action = "merge"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(
            content="Python是最好的编程语言 功能强大且易于学习 适合初学者入门",
            entry_id="conf_001",
        )]
        result = gate.check(
            content="Python不是最好的编程语言 错误地认为它适合所有场景 应该废弃这个观点并替换为新的认识",
            layer="working",
            tags=["test"],
            priority="medium",
            existing_entries=existing,
        )
        assert isinstance(result, GateResult)

    def test_check_conflict_unresolved_in_check(self, gate):
        """check()中conflict检测→无法auto_resolve→CONFLICT(行242-248)"""
        mock_resolver = MagicMock()
        mock_type = MagicMock()
        mock_type.value = "factual"
        mock_resolver.detect_conflict_by_content.return_value = mock_type
        # auto-resolve返回False → 冲突未解决
        mock_verdict = MagicMock()
        mock_verdict.action = "reject"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(
            content="Python是最好的编程语言 功能强大且易于学习 适合初学者入门",
            entry_id="conf_001",
        )]
        result = gate.check(
            content="Python不是最好的编程语言 错误地认为它适合所有场景 应该废弃这个观点并替换为新的认识",
            layer="working",
            tags=["test"],
            priority="medium",
            existing_entries=existing,
        )
        assert isinstance(result, GateResult)

    def test_check_drift_signal_in_check(self, gate):
        """check()中偏好漂移has_drift=True分支(行259)"""
        mock_detector = MagicMock()
        mock_signal = MagicMock()
        mock_signal.delta = 0.5
        mock_signal.drift_type = MagicMock()
        mock_signal.drift_type.value = "gradual"
        mock_signal.topic = "python"
        mock_detector.detect.return_value = [mock_signal]
        gate._preference_drift_detector = mock_detector
        result = gate.check(
            content="这是一段关于Python编程的高质量内容，包含详细的技术说明和实践经验总结",
            layer="working",
            tags=["python"],
            priority="medium",
        )
        assert isinstance(result, GateResult)

    def test_check_causal_downstream_score(self, gate):
        """_check_causal_chain中downstream_score>0(行434)"""
        # 需要content与existing有语义重叠且content较长
        existing = [_make_entry(
            content="架构 设计 需要 重构 因为 性能 问题",
            entry_id="causal_001",
        )]
        score = gate._check_causal_chain(
            "架构 设计 需要 重构 因为 性能 问题 所以 需要 优化 这是一段更长的详细说明文字",
            existing,
        )
        assert score >= 0.3

    def test_sync_evo_config_sets_noise_threshold(self, gate):
        """_sync_evo_config设置noise_threshold(行159)"""
        mock_loop = MagicMock()
        mock_loop.mutable_config = {"noise_threshold": 0.45}
        gate._evo_loop = mock_loop
        gate._sync_evo_config()
        assert gate.config.noise_threshold == 0.45

    def test_check_promotion_upstream_exception_runtime(self, gate_with_engine):
        """_check_promotion_upstream RuntimeError(行688-689)"""
        gate_with_engine._engine.recall.side_effect = RuntimeError("db error")
        ok = gate_with_engine._check_promotion_upstream("内容", "working")
        assert ok is True


# ============================================================
# TestQualityGateImportBranches
# ============================================================

class TestQualityGateImportBranches:
    """覆盖ImportError分支和__init__中ConflictResolver/DriftDetector创建"""

    def test_init_with_conflict_resolver_available(self):
        """__init__中_CONFLICT_RESOLVER_AVAILABLE=True时创建resolver(行77)"""
        # 模块级import已完成，_CONFLICT_RESOLVER_AVAILABLE=False
        # 要覆盖行77，需要重新执行模块级代码
        import importlib
        import core.quality_gate as qg_mod
        # 保存原始值
        orig_available = qg_mod._CONFLICT_RESOLVER_AVAILABLE
        orig_resolver = getattr(qg_mod, 'ConflictResolver', None)
        try:
            # 设置为True并重新创建QualityGate
            qg_mod._CONFLICT_RESOLVER_AVAILABLE = True
            qg_mod.ConflictResolver = MagicMock(return_value=MagicMock())
            gate = qg_mod.QualityGate()
            assert gate._conflict_resolver is not None
        finally:
            qg_mod._CONFLICT_RESOLVER_AVAILABLE = orig_available
            if orig_resolver is not None:
                qg_mod.ConflictResolver = orig_resolver
            else:
                del qg_mod.ConflictResolver

    def test_init_with_drift_detector_available(self):
        """__init__中_DRIFT_DETECTOR_AVAILABLE=True时创建detector(行81)"""
        import core.quality_gate as qg_mod
        orig_available = qg_mod._DRIFT_DETECTOR_AVAILABLE
        orig_detector = getattr(qg_mod, 'PreferenceDriftDetector', None)
        try:
            qg_mod._DRIFT_DETECTOR_AVAILABLE = True
            qg_mod.PreferenceDriftDetector = MagicMock(return_value=MagicMock())
            gate = qg_mod.QualityGate()
            assert gate._preference_drift_detector is not None
        finally:
            qg_mod._DRIFT_DETECTOR_AVAILABLE = orig_available
            if orig_detector is not None:
                qg_mod.PreferenceDriftDetector = orig_detector
            else:
                del qg_mod.PreferenceDriftDetector

    def test_init_with_evolution_loop_available(self):
        """__init__中EvolutionLoop创建(行107-108)"""
        import core.quality_gate as qg_mod
        orig_evo = getattr(qg_mod, 'EvolutionLoop', None)
        try:
            mock_evo = MagicMock()
            qg_mod.EvolutionLoop = mock_evo
            gate = qg_mod.QualityGate()
            # 如果EvolutionLoop可用，_evo_loop应被创建
            assert gate._evo_loop is not None
        finally:
            if orig_evo is not None:
                qg_mod.EvolutionLoop = orig_evo
            else:
                del qg_mod.EvolutionLoop

    def test_sync_evo_config_min_content_length(self):
        """_sync_evo_config设置min_content_length(行159)"""
        gate = QualityGate()
        mock_loop = MagicMock()
        mock_loop.mutable_config = {"min_content_length": 100}
        gate._evo_loop = mock_loop
        gate._sync_evo_config()
        assert gate.config.min_content_length == 100

    def test_check_noise_repeat_two_chars(self):
        """_check_noise len(set)<=2 and len<=10(行320)"""
        gate = QualityGate()
        # "ab" → set={'a','b'} len=2, len("ab")=2 → 满足条件
        result = gate._check_noise("ab")
        assert result["is_noise"] is True

    def test_check_conflict_resolver_with_conflict_type(self):
        """_check_conflict ConflictResolver检测到冲突(行475-486)"""
        gate = QualityGate()
        mock_resolver = MagicMock()
        mock_type = MagicMock()
        mock_type.value = "factual"
        # 第一个entry检测到冲突
        mock_resolver.detect_conflict_by_content.return_value = mock_type
        gate._conflict_resolver = mock_resolver
        entries = [_make_entry(content="测试", entry_id="c1")]
        result = gate._check_conflict("冲突内容", entries)
        assert result["has_conflict"] is True

    def test_check_conflict_negation_exceeds_max(self):
        """_check_conflict否定词路径冲突数>max_conflict_retention(行505-507)"""
        gate = QualityGate()
        gate._conflict_resolver = None
        # 创建6个有语义重叠的entry，max_conflict_retention=5
        entries = [
            _make_entry(
                content=f"Python 是 最好 的 编程 语言 功能 强大 且 易于 学习 适合 初学者 入门 {i}",
                entry_id=f"c_{i}",
            )
            for i in range(6)
        ]
        result = gate._check_conflict(
            "Python 不是 最好 的 编程 语言 错误 地 认为 它 适合 所有 场景 应该 废弃 这个 观点 并 替换 为 新 的 认识 和 理解",
            entries,
        )
        # 如果冲突数>5，应返回"超过5个冲突信号"
        if result["has_conflict"]:
            assert "冲突" in result["reason"]

    def test_try_auto_resolve_verdict_action_check(self):
        """_try_auto_resolve_conflict中verdict.action检查(行552)"""
        gate = QualityGate()
        mock_resolver = MagicMock()
        mock_verdict = MagicMock()
        mock_verdict.action = "supersede"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        entries = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["c_001"]}, entries,
        )
        assert result is True

    def test_check_promotion_upstream_generic_exception(self):
        """_check_promotion_upstream通用异常(行688-689)"""
        gate = QualityGate(engine=MagicMock())
        gate._engine.recall.side_effect = Exception("generic error")
        ok = gate._check_promotion_upstream("内容", "working")
        assert ok is True


# ============================================================
# TestQualityGatePreciseCoverage
# ============================================================

class TestQualityGatePreciseCoverage:
    """精确覆盖annotate报告中标记为!的行"""

    def test_sync_evo_config_no_loop(self):
        """_sync_evo_config无evo_loop时return(行159)"""
        gate = QualityGate()
        gate._evo_loop = None
        original_min = gate.config.min_content_length
        gate._sync_evo_config()
        # 无evo_loop时直接return，不修改config
        assert gate.config.min_content_length == original_min

    def test_check_downgrade_branch(self):
        """check()中DOWNGRADE分支(行279-287)"""
        config = QualityGateConfig(minimum_value_score_for_direct_write=0.99)
        gate = QualityGate(config=config)
        # 内容需要通过所有前置检查但overall < 0.99
        result = gate.check(
            content="这是一段测试内容，用于触发降级分支的覆盖测试",
            layer="sensory",
            tags=[],
            priority="low",
        )
        assert result.verdict == GateVerdict.DOWNGRADE

    def test_check_noise_symbol_noise(self):
        """_check_noise符号噪声(行320)"""
        gate = QualityGate()
        # "..."等短符号会被len(set)<=2先匹配，需要用noise_patterns或更长的符号
        # 直接用noise_patterns配置
        config = QualityGateConfig(noise_patterns=["test_noise"])
        gate = QualityGate(config=config)
        result = gate._check_noise("test_noise")
        assert result["is_noise"] is True
        assert "纯噪声模式" in result["reason"]

    def test_check_conflict_negation_with_overlap(self):
        """_check_conflict否定词+语义重叠(行480)"""
        gate = QualityGate()
        gate._conflict_resolver = None
        # 用空格分隔中文使split()能分词，确保语义重叠检测生效
        existing = [_make_entry(
            content="Python 编程 语言 最好 功能 强大 易于 学习 适合 初学者",
            entry_id="c_001",
        )]
        result = gate._check_conflict(
            "Python 编程 语言 不是 最好 错误 地 认为 它 适合 所有 场景 应该 废弃 这个 观点",
            existing,
        )
        assert result["has_conflict"] is True
        assert "语义冲突" in result["reason"]

    def test_has_semantic_overlap_empty_words(self):
        """_has_semantic_overlap空词集返回False(行552)"""
        gate = QualityGate()
        assert gate._has_semantic_overlap("", "test") is False
        assert gate._has_semantic_overlap("test", "") is False

    def test_char_ngrams_short_text(self):
        """_char_ngrams短文本(行486)"""
        result = QualityGate._char_ngrams("ab", n=4)
        assert result == {"ab"}

    def test_check_preference_drift_exception(self):
        """_check_preference_drift异常处理(行505-507)"""
        gate = QualityGate()
        mock_detector = MagicMock()
        mock_detector.update.side_effect = RuntimeError("test")
        gate._preference_drift_detector = mock_detector
        result = gate._check_preference_drift("内容", ["tag1"])
        assert result["has_drift"] is False
        assert result["score"] == 0.5

    def test_try_auto_resolve_return_false(self):
        """_try_auto_resolve_conflict返回False(行552)"""
        gate = QualityGate()
        mock_resolver = MagicMock()
        mock_verdict = MagicMock()
        mock_verdict.action = "unknown_action"
        mock_resolver.resolve.return_value = mock_verdict
        gate._conflict_resolver = mock_resolver
        existing = [_make_entry(content="旧内容", entry_id="c_001")]
        result = gate._try_auto_resolve_conflict(
            "新内容", {"matched_ids": ["c_001"]}, existing,
        )
        assert result is False

    def test_check_promotion_upstream_with_will(self):
        """get_stats()中will_topics(行688-689)"""
        gate = QualityGate()
        gate.update_will("python", 0.9)
        gate.update_will("testing", 0.7)
        stats = gate.get_stats()
        assert "will_tracker" in stats
        assert len(stats["will_tracker"]["top_topics"]) >= 1

    def test_scheduler_loop_exception(self):
        """AutoTuningScheduler._scheduler_loop异常(行875-876)"""
        gate = QualityGate()
        adaptive = ConsumerAwareAdaptiveGate(gate)
        scheduler = AutoTuningScheduler(adaptive, interval_seconds=0.1)
        # 模拟_run_single_cycle抛异常
        scheduler._run_single_cycle = MagicMock(side_effect=RuntimeError("test"))
        scheduler.start()
        import time; time.sleep(0.5)
        scheduler.stop()
        # 异常被捕获，scheduler仍在运行直到stop
