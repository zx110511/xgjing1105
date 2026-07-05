# -*- coding: utf-8-sig -*-
"""质量门禁 — 核心门禁

从 quality_gate.py 拆分 (SSS-PhaseB)
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from ..shared.config import DEFAULT_CONFIG, QualityGateConfig
from .gate import (
    PLUGIN_INFO,
    LocalGateStrategy,
    NoiseFilter,
    PolicyEngine,
    RemoteGateStrategy,
)
from .gate.noise_filter import (
    char_ngrams,
    has_semantic_overlap,
    longest_common_substring,
)
from ..shared.protocols import (
    GateResult as ProtocolGateResult,
)
# SSS-PhaseE: 补充GateResult/GateVerdict导入 (拆分时遗漏)
from .quality_gate_models import GateResult, GateVerdict
from ..shared.protocols import (
    GateVerdict as ProtocolGateVerdict,
)
from ..shared.protocols import (
    IGatePolicy,
    IGateStrategy,
)
try:
    from .processors.conflict_resolver import (
        ConflictResolver,
        ResolutionVerdict,
    )
    from .processors.preference_drift_detector import PreferenceDriftDetector
    _CONFLICT_RESOLVER_AVAILABLE = True  # SSS-PhaseE: 导入成功标志
    _DRIFT_DETECTOR_AVAILABLE = True
except ImportError:
    ConflictResolver = None
    ResolutionVerdict = None
    PreferenceDriftDetector = None
    _CONFLICT_RESOLVER_AVAILABLE = False  # SSS-PhaseE: 补充缺失标志
    _DRIFT_DETECTOR_AVAILABLE = False
try:
    from .evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


from typing import Dict

class QualityGate:
    """高质量记忆写入门禁 (兼容层, 委托 LocalGateStrategy 插件)  [v10-ready]

    本地实现: 内部委托 core.gate 插件 (NoiseFilter/PolicyEngine/
    LocalGateStrategy) 完成三问推演；对外保持 v9.1 富 GateResult 接口。
    远程实现: v10.0 分布式可切换 core.gate.RemoteGateStrategy。
    """

    def __init__(self, config: Optional[QualityGateConfig] = None, engine=None):
        """初始化门禁兼容层并装配门禁插件  [v10-ready]"""
        cfg = config or DEFAULT_CONFIG.quality_gate
        if hasattr(cfg, "quality_gate"):
            cfg = cfg.quality_gate
        self.config = cfg
        self._engine = engine
        self._will_tracker: Dict[str, float] = defaultdict(float)
        self._will_decay_rate = 0.05

        # 装配门禁插件 (核心逻辑承载)
        self._noise_filter = NoiseFilter(self.config)
        self._policy_engine = PolicyEngine(self.config, noise_filter=self._noise_filter)

        self._conflict_resolver = None
        if _CONFLICT_RESOLVER_AVAILABLE:
            self._conflict_resolver = ConflictResolver()

        self._preference_drift_detector = None
        if _DRIFT_DETECTOR_AVAILABLE:
            self._preference_drift_detector = PreferenceDriftDetector()

        # v10-ready 本地门禁策略 (基于 protocols 契约)
        self._strategy = LocalGateStrategy(
            config=self.config,
            noise_filter=self._noise_filter,
            policy_engine=self._policy_engine,
            conflict_resolver=self._conflict_resolver,
        )

        self._gate_stats = {
            "total_checks": 0,
            "passes": 0,
            "downgrades": 0,
            "rejects": 0,
            "conflicts": 0,
        }

        self._evo_loop = None
        try:
            from .evolution_loop import EvolutionLoop

            self._evo_loop = EvolutionLoop(
                module_name="quality_gate",
                effectiveness_fn=self._calc_gate_effectiveness,
                learn_fn=self._learn_from_gates,
                evolve_fn=self._evolve_gate_thresholds,
                mutable_config={
                    "noise_threshold": self.config.noise_threshold
                    if hasattr(self.config, "noise_threshold")
                    else 0.3,
                    "min_content_length": self.config.min_content_length
                    if hasattr(self.config, "min_content_length")
                    else 20,
                    "duplicate_threshold": self.config.duplicate_threshold
                    if hasattr(self.config, "duplicate_threshold")
                    else 0.85,
                    "will_decay_rate": self._will_decay_rate,
                },
                health_metrics_fn=self._get_health_metrics,
            )
        except ImportError:
            pass

    # ==================================================================
    # v10-ready 策略访问器
    # ==================================================================
    @property
    def strategy(self) -> LocalGateStrategy:
        """获取内部委托的本地门禁策略实例  [v10-ready]"""
        return self._strategy

    def strategy_check(
        self, content: str, metadata: Optional[dict] = None
    ) -> ProtocolGateResult:
        """以 v10 协议形态执行门禁判定 (返回 protocols.GateResult)  [v10-ready]"""
        return self._strategy.check(content, metadata or {})

    # ==================================================================
    # 进化闭环回调
    # ==================================================================
    def _calc_gate_effectiveness(
        self, action: str, state_before: Dict, state_after: Dict
    ) -> float:
        """计算门禁动作有效性 (供进化闭环)  [v10-ready]"""
        verdict = state_after.get("verdict", "")
        priority = state_before.get("priority", "medium")
        if verdict == "reject" and priority in ("high", "critical"):
            return -0.5
        if verdict == "downgrade" and priority in ("high", "critical"):
            return -0.3
        if verdict == "pass" and priority == "low":
            return 0.1
        if verdict == "pass" and priority in ("high", "critical"):
            return 0.5
        return 0.0

    def _learn_from_gates(self, causal_pairs, effectiveness_summary) -> Dict:
        """从门禁因果对中学习洞察  [v10-ready]"""
        neg_ratio = effectiveness_summary.get("negative_ratio", 0.0)
        avg_eff = effectiveness_summary.get("avg", 0.0)
        insight = ""
        if neg_ratio > 0.3:
            insight = f"拒绝/降级率过高({neg_ratio:.0%})，阈值可能过严"
        elif avg_eff > 0.3:
            insight = f"门禁效果良好(平均效果{avg_eff:.2f})"
        return {
            "insight": insight,
            "negative_ratio": neg_ratio,
            "avg_effectiveness": avg_eff,
        }

    def _evolve_gate_thresholds(self, learn_result, mutable_config) -> Dict:
        """根据学习结果演化门禁阈值  [v10-ready]"""
        changes = []
        neg_ratio = learn_result.get("negative_ratio", 0.0)
        if neg_ratio > 0.3:
            old_noise = mutable_config.get("noise_threshold", 0.3)
            new_noise = min(old_noise * 1.1, 0.6)
            changes.append(
                {
                    "rule": "noise_threshold",
                    "old_value": old_noise,
                    "new_value": new_noise,
                }
            )
        elif neg_ratio < 0.05:
            old_noise = mutable_config.get("noise_threshold", 0.3)
            new_noise = max(old_noise * 0.95, 0.1)
            changes.append(
                {
                    "rule": "noise_threshold",
                    "old_value": old_noise,
                    "new_value": new_noise,
                }
            )
        return {"changes": changes}

    def _get_health_metrics(self) -> Dict[str, float]:
        """门禁健康指标 (拒绝率/降级率)  [v10-ready]"""
        total = max(self._gate_stats["total_checks"], 1)
        return {
            "rejection_rate": self._gate_stats["rejects"] / total,
            "downgrade_rate": self._gate_stats["downgrades"] / total,
        }

    @property
    def evolution_loop(self):
        """进化闭环实例访问器  [v10-ready]"""
        return self._evo_loop

    def _sync_evo_config(self):
        """同步进化闭环可变配置回门禁  [v10-ready]"""
        if not self._evo_loop:
            return
        mc = self._evo_loop.mutable_config
        if "noise_threshold" in mc:
            self.config.noise_threshold = mc["noise_threshold"]
        if "min_content_length" in mc:
            self.config.min_content_length = mc["min_content_length"]
        if "duplicate_threshold" in mc:
            self.config.duplicate_threshold = mc["duplicate_threshold"]
        if "will_decay_rate" in mc:
            self._will_decay_rate = mc["will_decay_rate"]

    # ==================================================================
    # 核心判定 (v9.1 富结果接口, 委托插件检测)
    # ==================================================================
    def check(
        self,
        content: str,
        layer: str,
        tags: List[str],
        priority: str,
        existing_entries: Optional[List] = None,
    ) -> "GateResult":
        """门禁判定 — 返回 v9.1 富 GateResult  [v10-ready]

        内部各检测步骤委托 NoiseFilter / PolicyEngine 插件完成，
        编排与状态 (will_tracker/stats/evo_loop) 由本兼容层维护。
        """
        self._sync_evo_config()
        self._gate_stats["total_checks"] += 1
        dims = {}

        noise_check = self._check_noise(content)
        if noise_check["is_noise"]:
            self._gate_stats["rejects"] += 1
            result = GateResult(
                verdict=GateVerdict.REJECT,
                target_layer="",
                reason=f"噪声内容被拒绝: {noise_check['reason']}",
                quality_dimensions={"noise": 0.0},
            )

        dims["noise"] = noise_check["score"]

        length_check = self._check_length(content)
        if not length_check["pass"]:
            return GateResult(
                verdict=GateVerdict.DOWNGRADE
                if length_check["score"] > 0.3
                else GateVerdict.REJECT,
                target_layer=self.config.auto_downgrade_noisy_to,
                reason=f"内容过短 ({len(content)}字符), 最低要求{self.config.min_content_length}",
                quality_dimensions={"length": length_check["score"]},
            )

        dims["length"] = length_check["score"]

        dup_check = self._check_duplicate(content, existing_entries)
        if dup_check["is_duplicate"]:
            return GateResult(
                verdict=GateVerdict.REJECT,
                target_layer="",
                reason=f"与已有记忆高度重复 (相似度{dup_check['similarity']:.2f})",
                conflicts_with=dup_check.get("matched_ids", []),
                quality_dimensions={"duplicate": dup_check["similarity"]},
            )
        dims["duplicate"] = dup_check["similarity"]

        tag_check = self._check_tags(tags, layer)
        if not tag_check["pass"]:
            return GateResult(
                verdict=GateVerdict.DOWNGRADE,
                target_layer=self.config.auto_downgrade_noisy_to,
                reason=f"层级 {layer} 要求标签，当前标签: {tags}",
                adjustments={"suggested_tags": tag_check.get("suggested", [])},
                quality_dimensions={"tags": 0.0},
            )
        dims["tags"] = tag_check["score"]

        upstream_check = self._check_upstream(content, layer, existing_entries)
        if not upstream_check["pass"]:
            return GateResult(
                verdict=GateVerdict.PENDING_UPSTREAM
                if upstream_check["can_pend"]
                else GateVerdict.DOWNGRADE,
                target_layer=upstream_check.get("fallback_layer", "working"),
                reason=f"缺少上游知识锚点: {upstream_check['reason']}",
                suggested_upstream=upstream_check.get("suggested_upstream"),
                quality_dimensions={"upstream": upstream_check["score"]},
            )
        dims["upstream"] = upstream_check["score"]

        will_score = self._check_will_alignment(content, tags, priority)
        dims["will"] = will_score

        causal_score = self._check_causal_chain(content, existing_entries)
        dims["causal"] = causal_score

        conflict_check = self._check_conflict(content, existing_entries)
        if conflict_check["has_conflict"]:
            resolved = self._try_auto_resolve_conflict(
                content, conflict_check, existing_entries
            )
            if resolved:
                dims["conflict_resolved"] = 1.0
            else:
                return GateResult(
                    verdict=GateVerdict.CONFLICT,
                    target_layer=layer,
                    reason=f"检测到潜在知识冲突: {conflict_check['reason']}",
                    conflicts_with=conflict_check.get("matched_ids", []),
                    quality_dimensions=dims,
                )

        drift_check = self._check_preference_drift(content, tags)
        dims["drift"] = drift_check["score"]
        if drift_check["has_drift"]:
            dims["drift_signal"] = drift_check["drift_type"]

        overall = self._policy_engine.compute_overall(dims)

        if overall >= self.config.minimum_value_score_for_direct_write:
            self._gate_stats["passes"] += 1
            result = GateResult(
                verdict=GateVerdict.PASS,
                target_layer=layer,
                reason=f"高质量记忆, 综合评分{overall:.2f}",
                quality_dimensions=dims,
            )
        else:
            self._gate_stats["downgrades"] += 1
            fallback = self._determine_fallback(layer)
            result = GateResult(
                verdict=GateVerdict.DOWNGRADE,
                target_layer=fallback,
                reason=f"综合质量不足({overall:.2f}<{self.config.minimum_value_score_for_direct_write}), 降级至{fallback}",
                quality_dimensions=dims,
            )

        if self._evo_loop:
            self._evo_loop.record_action(
                action="gate_check",
                state_before={"priority": priority, "layer": layer},
                state_after={"verdict": result.verdict.value},
            )

        return result

    def update_will(self, topic: str, intensity: float):
        """更新用户活动意志强度并衰减其他主题  [v10-ready]"""
        current = self._will_tracker.get(topic, 0.0)
        self._will_tracker[topic] = max(0.0, min(1.0, current + intensity))
        for t in list(self._will_tracker.keys()):
            if t != topic:
                self._will_tracker[t] = max(
                    0.0, self._will_tracker[t] - self._will_decay_rate
                )
                if self._will_tracker[t] <= 0.01:
                    del self._will_tracker[t]

    def get_will_topics(self, top_n: int = 5) -> List[Tuple[str, float]]:
        """获取意志强度 TopN 主题  [v10-ready]"""
        return sorted(self._will_tracker.items(), key=lambda x: x[1], reverse=True)[
            :top_n
        ]

    # ==================================================================
    # 检测方法 — 全部委托至 core.gate 插件  [v10-ready]
    # ==================================================================
    def _check_noise(self, content: str) -> dict:
        """噪声检测 (委托 NoiseFilter)  [v10-ready]"""
        return self._noise_filter.check_noise(content)

    def _check_length(self, content: str) -> dict:
        """长度/密度检测 (委托 PolicyEngine)  [v10-ready]"""
        return self._policy_engine.check_length(content)

    def _check_duplicate(self, content: str, existing_entries: Optional[List]) -> dict:
        """冗余检测 (委托 NoiseFilter)  [v10-ready]"""
        return self._noise_filter.check_duplicate(content, existing_entries)

    def _check_tags(self, tags: List[str], layer: str) -> dict:
        """标签检测 (委托 PolicyEngine)  [v10-ready]"""
        return self._policy_engine.check_tags(tags, layer)

    def _check_upstream(
        self, content: str, layer: str, existing_entries: Optional[List]
    ) -> dict:
        """上游锚点检测 (委托 PolicyEngine)  [v10-ready]"""
        return self._policy_engine.check_upstream(content, layer, existing_entries)

    def _check_will_alignment(
        self, content: str, tags: List[str], priority: str
    ) -> float:
        """用户意志对齐评分 (委托 PolicyEngine)  [v10-ready]"""
        return self._policy_engine.check_will_alignment(
            content, tags, priority, self._will_tracker
        )

    def _check_causal_chain(
        self, content: str, existing_entries: Optional[List]
    ) -> float:
        """知识因果链评分 (委托 PolicyEngine)  [v10-ready]"""
        return self._policy_engine.check_causal_chain(content, existing_entries)

    def _check_conflict(self, content: str, existing_entries: Optional[List]) -> dict:
        """矛盾检测 (委托 NoiseFilter)  [v10-ready]"""
        return self._noise_filter.check_conflict(
            content, existing_entries, self._conflict_resolver
        )

    @staticmethod
    def _char_ngrams(text: str, n: int = 4) -> set:
        """字符 n-gram (委托 NoiseFilter)  [v10-ready]"""
        return char_ngrams(text, n)

    def _check_preference_drift(self, content: str, tags: List[str]) -> dict:
        """偏好漂移检测 (保留本地, 依赖 drift detector)  [v10-ready]"""
        if not self._preference_drift_detector:
            return {"has_drift": False, "score": 0.5, "drift_type": "none"}
        try:
            for tag in tags:
                self._preference_drift_detector.update(tag, 1.0)
            signals = self._preference_drift_detector.detect()
            if signals:
                strongest = max(signals, key=lambda s: abs(s.delta))
                return {
                    "has_drift": True,
                    "score": min(1.0, abs(strongest.delta) * 2),
                    "drift_type": strongest.drift_type.value,
                    "topic": strongest.topic,
                    "delta": strongest.delta,
                }
        except Exception:
            pass
        return {"has_drift": False, "score": 0.5, "drift_type": "none"}

    def _try_auto_resolve_conflict(
        self, content: str, conflict_check: dict, existing_entries: Optional[List]
    ) -> bool:
        """尝试自动消解冲突 (依赖 conflict resolver)  [v10-ready]"""
        if not self._conflict_resolver:
            return False
        try:
            conflict_ids = conflict_check.get("matched_ids", [])
            if not conflict_ids or not existing_entries:
                return False
            for entry in existing_entries[:20]:
                entry_id = entry.id if hasattr(entry, "id") else entry.get("id", "")
                if entry_id in conflict_ids:
                    existing_content = (
                        entry.content
                        if hasattr(entry, "content")
                        else entry.get("content", "")
                    )
                    verdict = self._conflict_resolver.resolve(
                        new_content=content,
                        existing_content=existing_content,
                    )
                    if (
                        verdict
                        and hasattr(verdict, "action")
                        and verdict.action in ("merge", "update_existing", "supersede")
                    ):
                        return True
            return False
        except Exception:
            return False

    def _determine_fallback(self, layer: str) -> str:
        """降级目标层 (委托 PolicyEngine)  [v10-ready]"""
        return self._policy_engine.determine_fallback(layer)

    def _has_semantic_overlap(self, text1: str, text2: str) -> bool:
        """语义重叠判定 (委托 gate 工具函数)  [v10-ready]"""
        return has_semantic_overlap(text1, text2)

    def _guess_upstream_topic(self, content: str) -> str:
        """猜测上游主题 (委托 NoiseFilter)  [v10-ready]"""
        return self._noise_filter.guess_upstream_topic(content)

    @staticmethod
    def _longest_common_substring(s1: str, s2: str) -> int:
        """最长公共子串 (委托 gate 工具函数)  [v10-ready]"""
        return longest_common_substring(s1, s2)

    # ==================================================================
    # 层级晋升门禁
    # ==================================================================
    def check_promotion(
        self,
        content: str,
        source_layer: str,
        target_layer: str,
        tags: List[str] = None,
        priority: str = "medium",
        override_threshold: float | None = None,
    ) -> "GateResult":
        """层级转换门禁 — 晋升价值/上游/跨层校验  [v10-ready]

        override_threshold: 外部传入的动态阈值，覆盖默认硬编码阈值。
        当容量压力大时，consolidate_batch可传入较低阈值以降低门禁标准。
        """
        self._gate_stats["total_checks"] += 1
        layer_order = [
            "sensory",
            "working",
            "short_term",
            "episodic",
            "semantic",
            "meta",
        ]
        promotion_thresholds = {
            ("sensory", "working"): 0.3,
            ("working", "short_term"): 0.4,
            ("short_term", "episodic"): 0.5,
            ("episodic", "semantic"): 0.6,
            ("semantic", "meta"): 0.7,
        }

        if source_layer not in layer_order or target_layer not in layer_order:
            return GateResult(
                verdict=GateVerdict.REJECT,
                target_layer=source_layer,
                reason=f"无效层级: {source_layer}→{target_layer}",
                quality_dimensions={"promotion": 0.0},
            )

        src_idx = layer_order.index(source_layer)
        tgt_idx = layer_order.index(target_layer)

        if tgt_idx <= src_idx:
            return GateResult(
                verdict=GateVerdict.PASS,
                target_layer=target_layer,
                reason="降级/同级操作，无需晋升门禁",
                quality_dimensions={"promotion": 1.0},
            )

        if tgt_idx > src_idx + 1:
            return GateResult(
                verdict=GateVerdict.DOWNGRADE,
                target_layer=layer_order[src_idx + 1],
                reason=f"不可跨层晋升({source_layer}→{target_layer})，先晋升至{layer_order[src_idx + 1]}",
                quality_dimensions={"promotion": 0.2},
            )

        # 动态阈值: override_threshold优先，否则使用默认硬编码阈值
        threshold = override_threshold if override_threshold is not None else promotion_thresholds.get((source_layer, target_layer), 0.5)

        value_score = self._calc_promotion_value(content, tags or [], priority)

        upstream_ok = self._check_promotion_upstream(content, target_layer)

        if value_score < threshold:
            self._gate_stats["downgrades"] += 1
            return GateResult(
                verdict=GateVerdict.DOWNGRADE,
                target_layer=source_layer,
                reason=f"晋升价值不足({value_score:.2f}<{threshold:.2f})，留在{source_layer}",
                quality_dimensions={"promotion": value_score, "threshold": threshold},
            )

        if not upstream_ok and source_layer != "sensory":
            return GateResult(
                verdict=GateVerdict.PENDING_UPSTREAM,
                target_layer=source_layer,
                reason=f"目标层{target_layer}缺少上游锚点，暂缓晋升",
                suggested_upstream=target_layer,
                quality_dimensions={"promotion": value_score, "upstream": 0.0},
            )

        self._gate_stats["passes"] += 1
        return GateResult(
            verdict=GateVerdict.PASS,
            target_layer=target_layer,
            reason=f"晋升通过: {source_layer}→{target_layer} (价值{value_score:.2f}≥阈值{threshold:.2f})",
            quality_dimensions={
                "promotion": value_score,
                "threshold": threshold,
                "upstream": 1.0,
            },
        )

    def _calc_promotion_value(
        self, content: str, tags: List[str], priority: str
    ) -> float:
        """计算晋升价值分  [v10-ready]"""
        length_score = min(len(content) / 500.0, 1.0) * 0.2
        structure_score = 0.0
        if "```" in content:
            structure_score += 0.15
        if any(
            kw in content.lower() for kw in ["架构", "设计", "策略", "规则", "决策"]
        ):
            structure_score += 0.2
        if "\n" in content and len(content.split("\n")) > 5:
            structure_score += 0.1
        tag_score = min(len(tags) / 5.0, 1.0) * 0.15
        priority_score = {"critical": 0.3, "high": 0.2, "medium": 0.1, "low": 0.0}.get(
            priority, 0.0
        )
        return min(length_score + structure_score + tag_score + priority_score, 1.0)

    def _check_promotion_upstream(self, content: str, target_layer: str) -> bool:
        """晋升上游锚点存在性校验 (依赖 engine.recall)  [v10-ready]"""
        if self._engine is None:
            return True
        try:
            results = self._engine.recall(
                query=content[:100], limit=3, min_score=0.0, layers=[target_layer]
            )
            return len(results) > 0
        except Exception:
            return True

    def get_stats(self) -> Dict[str, Any]:
        """门禁运行统计快照  [v10-ready]"""
        total = max(self._gate_stats.get("total_checks", 0), 1)
        will_topics = []
        if hasattr(self, "_will_tracker") and self._will_tracker:
            sorted_will = sorted(
                self._will_tracker.items(), key=lambda x: x[1], reverse=True
            )
            will_topics = [(k, round(v, 3)) for k, v in sorted_will[:5]]
        return {
            "version": "5.1",
            "gate_stats": dict(self._gate_stats),
            "rates": {
                "pass_rate": round(self._gate_stats.get("passes", 0) / total, 4),
                "rejection_rate": round(self._gate_stats.get("rejects", 0) / total, 4),
                "downgrade_rate": round(
                    self._gate_stats.get("downgrades", 0) / total, 4
                ),
            },
            "config_snapshot": {
                "noise_threshold": getattr(
                    getattr(self, "config", None), "noise_threshold", 0.3
                ),
                "min_content_length": getattr(
                    getattr(self, "config", None), "min_content_length", 20
                ),
                "duplicate_threshold": getattr(
                    getattr(self, "config", None), "duplicate_threshold", 0.85
                ),
            },
            "will_tracker": {
                "active_topics": len(self._will_tracker)
                if hasattr(self, "_will_tracker")
                else 0,
                "top_topics": will_topics,
            },
            "subsystems": {
                "conflict_resolver_available": getattr(self, "_conflict_resolver", None)
                is not None,
                "drift_detector_available": getattr(
                    self, "_preference_drift_detector", None
                )
                is not None,
                "evo_loop_active": getattr(self, "_evo_loop", None) is not None,
                "strategy_plugin": type(getattr(self, "_strategy", None)).__name__,
            },
        }




__all__ = ["QualityGate"]
