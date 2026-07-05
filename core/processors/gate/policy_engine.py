# -*- coding: utf-8-sig -*-
"""天机v10.0.1 门禁策略引擎 PolicyEngine  [v10-ready]

实现 IGatePolicy 协议，承载:
    1. 三问推演 Q1/Q2 正向评分 (用户意志 / 知识因果链)
    2. 7 因子综合评分 (information_density / semantic_novelty /
       knowledge_chain_value / redundancy / conflict / staleness / noise)
    3. 阈值配置管理 (PASS / DOWNGRADE / REJECT 可配置)

从 core/quality_gate.py 提取的评分与阈值逻辑，独立为可配置策略引擎。

架构定位: core/gate/ 门禁策略子包 — 评分与阈值层
版本: 1.0.0
"""

from __future__ import annotations

from typing import Any

try:
    from ..config import DEFAULT_CONFIG, QualityGateConfig
    from ..shared.protocols import IGatePolicy
except ImportError:  # pragma: no cover - 兼容直接执行
    pass  # type: ignore

from .noise_filter import NoiseFilter, _resolve_config, has_semantic_overlap


class PolicyEngine:
    """门禁策略引擎 — IGatePolicy 实现 (7因子评分 + 阈值管理)  [v10-ready]

    本地实现: 进程内静态阈值 + 规则评分。
    远程实现: 灵境策略中心可动态下发阈值并集中演化(见 RemoteGateStrategy)。

    满足 ``isinstance(PolicyEngine(), IGatePolicy) == True``:
    实现 should_apply() 与 get_threshold()，并额外提供 evaluate() 综合评分。
    """

    #: 综合评分各因子权重 (与 v9.1 QualityGate 保持一致)
    _WEIGHTS = {
        "length": 0.12,
        "novelty": 0.18,
        "tags": 0.08,
        "upstream": 0.18,
        "will": 0.18,
        "causal": 0.12,
        "drift": 0.14,
    }

    _LAYER_ORDER = ["sensory", "working", "short_term", "episodic", "semantic", "meta"]

    def __init__(
        self,
        config: Any | None = None,
        thresholds: dict | None = None,
        noise_filter: NoiseFilter | None = None,
    ) -> None:
        """初始化策略引擎  [v10-ready]

        Args:
            config: QualityGateConfig 或含 quality_gate 属性的配置对象。
            thresholds: 可选阈值覆盖 (PASS/DOWNGRADE/REJECT 等)。
            noise_filter: 可选共享的 NoiseFilter (用于冗余因子计算)。
        """
        self.config = _resolve_config(config)
        self._noise = noise_filter or NoiseFilter(self.config)
        base = getattr(self.config, "minimum_value_score_for_direct_write", 0.3)
        self._thresholds: dict[str, float] = {
            "pass": float(base),
            "downgrade": float(base) * 0.5,
            "reject": 0.0,
            "min_content_length": float(getattr(self.config, "min_content_length", 10)),
            "max_similarity_for_duplicate": float(
                getattr(self.config, "max_similarity_for_duplicate", 0.85)
            ),
            "noise_threshold": float(getattr(self.config, "noise_threshold", 0.3)),
        }
        if thresholds:
            self._thresholds.update({k: float(v) for k, v in thresholds.items()})

    # ==================================================================
    # IGatePolicy 协议方法
    # ==================================================================
    def should_apply(self, metadata: dict[str, Any]) -> bool:
        """判定本策略是否适用于该上下文  [v10-ready]

        Args:
            metadata: 内容元数据。显式 skip_gate/bypass_gate 时跳过门禁。

        Returns:
            是否应用本门禁策略。
        """
        md = metadata or {}
        if md.get("skip_gate") or md.get("bypass_gate"):
            return False
        return True

    def get_threshold(self, key: str) -> float:
        """获取指定阈值  [v10-ready]

        Args:
            key: 阈值名称 (pass/downgrade/reject/min_content_length 等)。

        Returns:
            阈值数值；未知键回退到 config 属性，最终回退 0.0。
        """
        if key in self._thresholds:
            return float(self._thresholds[key])
        val = getattr(self.config, key, None)
        return float(val) if isinstance(val, (int, float)) else 0.0

    def set_threshold(self, key: str, value: float) -> None:
        """更新指定阈值 (供自适应/远程下发使用)  [v10-ready]"""
        self._thresholds[key] = float(value)

    def evaluate(self, content: str, metadata: dict | None = None) -> float:
        """返回综合质量评分 (7因子加权)  [v10-ready]

        Args:
            content: 待评估文本。
            metadata: 元数据 (layer/tags/priority/existing_entries/will_tracker)。

        Returns:
            综合评分 (0.0 ~ 1.0)。
        """
        dims = self.score_dimensions(content, metadata)
        return self.compute_overall(dims)

    # ==================================================================
    # 维度评分 (内部因子)
    # ==================================================================
    def score_dimensions(self, content: str, metadata: dict | None = None) -> dict:
        """计算各正向评分维度  [v10-ready]

        Args:
            content: 待评估文本。
            metadata: 元数据。

        Returns:
            维度评分字典 (length/duplicate/tags/upstream/will/causal/drift)。
        """
        md = metadata or {}
        layer = md.get("layer", "working")
        tags = md.get("tags", []) or []
        priority = md.get("priority", "medium")
        existing = md.get("existing_entries")
        will_tracker = md.get("will_tracker", {}) or {}

        dims: dict[str, float] = {}
        dims["length"] = self.check_length(content)["score"]
        dims["duplicate"] = self._noise.check_duplicate(content, existing)["similarity"]
        dims["tags"] = self.check_tags(tags, layer)["score"]
        dims["upstream"] = self.check_upstream(content, layer, existing)["score"]
        dims["will"] = self.check_will_alignment(content, tags, priority, will_tracker)
        dims["causal"] = self.check_causal_chain(content, existing)
        dims["drift"] = md.get("drift_score", 0.5)
        return dims

    def score_factors(self, content: str, metadata: dict | None = None) -> dict:
        """对外暴露的 7 因子语义评分视图  [v10-ready]

        将内部维度映射为任务约定的 7 因子命名。

        Returns:
            {information_density, semantic_novelty, knowledge_chain_value,
             redundancy, conflict, staleness, noise} 字典。
        """
        md = metadata or {}
        existing = md.get("existing_entries")
        dims = self.score_dimensions(content, metadata)
        noise = self._noise.check_noise(content)
        stale = self._noise.check_staleness(content, md)
        conflict = self._noise.check_conflict(
            content, existing, md.get("conflict_resolver")
        )
        return {
            "information_density": dims["length"],
            "semantic_novelty": round(1.0 - dims["duplicate"], 4),
            "knowledge_chain_value": round(
                (dims["upstream"] + dims["causal"]) / 2.0, 4
            ),
            "redundancy": dims["duplicate"],
            "conflict": 1.0 if conflict["has_conflict"] else 0.0,
            "staleness": round(1.0 - stale["score"], 4),
            "noise": round(1.0 - noise["score"], 4),
        }

    def compute_overall(self, dims: dict) -> float:
        """7因子加权综合评分  [v10-ready]

        Args:
            dims: 维度评分字典。

        Returns:
            综合评分 (0.0 ~ 1.0)。
        """
        w = self._WEIGHTS
        overall = (
            dims.get("length", 0.5) * w["length"]
            + (1.0 - dims.get("duplicate", 0.0)) * w["novelty"]
            + dims.get("tags", 0.5) * w["tags"]
            + dims.get("upstream", 0.5) * w["upstream"]
            + dims.get("will", 0.5) * w["will"]
            + dims.get("causal", 0.5) * w["causal"]
            + dims.get("drift", 0.5) * w["drift"]
        )
        return overall

    # ------------------------------------------------------------------
    # information_density — 长度/密度
    # ------------------------------------------------------------------
    def check_length(self, content: str) -> dict:
        """信息密度(长度)评分  [v10-ready]"""
        length = len(content)
        min_len = getattr(self.config, "min_content_length", 10)
        if length >= min_len * 3:
            return {"pass": True, "score": 1.0}
        elif length >= min_len * 2:
            return {"pass": True, "score": 0.8}
        elif length >= min_len:
            return {"pass": True, "score": 0.6}
        elif length >= min_len * 0.5:
            return {"pass": False, "score": 0.3}
        return {"pass": False, "score": 0.1}

    # ------------------------------------------------------------------
    # 标签门禁
    # ------------------------------------------------------------------
    def check_tags(self, tags: list[str], layer: str) -> dict:
        """标签完整度评分  [v10-ready]"""
        if layer not in getattr(self.config, "require_tags_for_layers", []):
            return {"pass": True, "score": 1.0}
        if tags and len(tags) > 0:
            return {"pass": True, "score": min(1.0, len(tags) / 3.0)}
        return {"pass": False, "score": 0.0, "suggested": ["auto-generated"]}

    # ------------------------------------------------------------------
    # knowledge_chain_value — 上游锚点
    # ------------------------------------------------------------------
    def check_upstream(
        self, content: str, layer: str, existing_entries: list | None
    ) -> dict:
        """上游知识锚点存在性评分  [v10-ready]

        [FIX-META-LAYER] meta是ICME顶层(L5)，不应要求上游锚点。
        系统级策略/元认知由系统管理员或天机总控显式写入，应尊重其意图。
        """
        if layer == "meta":
            return {"pass": True, "score": 1.0}
        if layer not in getattr(self.config, "require_upstream_for_layers", []):
            return {"pass": True, "score": 0.8}
        if not existing_entries:
            return {
                "pass": False,
                "score": 0.0,
                "can_pend": True,
                "reason": "语义层无现有记忆可关联,待上游补全",
                "fallback_layer": "episodic",
            }
        content_lower = content.lower()
        related = []
        for entry in existing_entries:
            existing_content = (
                entry.content if hasattr(entry, "content") else entry.get("content", "")
            )
            if has_semantic_overlap(content_lower, existing_content.lower()):
                entry_id = entry.id if hasattr(entry, "id") else entry.get("id", "")
                related.append(entry_id)
        if related:
            return {
                "pass": True,
                "score": min(1.0, len(related) / 3.0),
                "related_ids": related,
            }
        return {
            "pass": False,
            "score": 0.15,
            "can_pend": True,
            "reason": "未找到语义关联上游, 等待更多上下文",
            "suggested_upstream": self._noise.guess_upstream_topic(content),
            "fallback_layer": "episodic",
        }

    # ------------------------------------------------------------------
    # Q1 用户活动意志
    # ------------------------------------------------------------------
    def check_will_alignment(
        self,
        content: str,
        tags: list[str],
        priority: str,
        will_tracker: dict | None = None,
    ) -> float:
        """用户活动意志对齐评分  [v10-ready]"""
        will_tracker = will_tracker or {}
        score = 0.3
        content_lower = content.lower()
        for topic, intensity in will_tracker.items():
            if topic.lower() in content_lower:
                score = max(score, 0.5 + intensity * 0.5)
        for tag in tags:
            if tag in will_tracker:
                score = max(score, 0.5 + will_tracker[tag] * 0.5)
        priority_bonus = {"critical": 0.3, "high": 0.2, "medium": 0.1, "low": 0.0}
        score += priority_bonus.get(priority, 0.0)
        return min(1.0, score)

    # ------------------------------------------------------------------
    # Q2 知识因果链
    # ------------------------------------------------------------------
    def check_causal_chain(self, content: str, existing_entries: list | None) -> float:
        """知识因果链上下游评分  [v10-ready]"""
        if not existing_entries:
            return 0.3
        causal_patterns = [
            "因为",
            "所以",
            "因此",
            "由于",
            "导致",
            "引起",
            "基于",
            "根据",
            "参考",
            "继承",
            "依赖",
            "实现",
            "定义",
            "决定",
            "配置",
            "构建",
        ]
        upstream_score = 0.0
        downstream_score = 0.0
        for entry in existing_entries[:30]:
            existing_content = (
                entry.content if hasattr(entry, "content") else entry.get("content", "")
            )
            if any(p in content for p in causal_patterns) and any(
                p in existing_content for p in causal_patterns
            ):
                upstream_score += 0.1
        content_lower = content.lower()
        lower_contents = [
            e.content.lower() if hasattr(e, "content") else e.get("content", "").lower()
            for e in (existing_entries or [])[:30]
        ]
        for lc in lower_contents:
            if has_semantic_overlap(content_lower, lc) and len(content) > len(lc) * 0.5:
                downstream_score += 0.1
        chain_score = min(1.0, (upstream_score + downstream_score) / 2.0)
        return max(0.3, chain_score)

    # ------------------------------------------------------------------
    # 降级目标层
    # ------------------------------------------------------------------
    def determine_fallback(self, layer: str) -> str:
        """计算降级目标层 (下沉一级)  [v10-ready]"""
        if layer in self._LAYER_ORDER:
            idx = self._LAYER_ORDER.index(layer)
            if idx > 0:
                return self._LAYER_ORDER[idx - 1]
        return "working"
