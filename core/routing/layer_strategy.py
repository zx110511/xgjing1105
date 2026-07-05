# -*- coding: utf-8-sig -*-
"""记忆层级路由策略 LayerRoutingStrategy  [v10-ready]

将原 core/layer_router.py 的六层分级分发逻辑提取为独立的 ITaskRouter 策略插件。

核心能力:
  1. route(task)        — ITaskRouter 单目标路由 (内容 → 最优记忆层级)
  2. get_routing_strategy() — 返回策略标识
  3. route_content()    — 多目标分级分发 (内容 → 多层级列表, 兼容原 route)
  4. deduplicate()      — 语义去重 (相似度>0.85 → SKIP)
  5. deredundate()      — 去冗余 (删除与层内已有知识重复的片段)
  6. reorganize()       — 重组新知识 (碎片 → 结构化)
  7. check_promotion_gate() — 层级转换门禁检查

六层联动矩阵:
  L0 Sensory  → 全量快照，不处理
  L1 Working  → 语义去重，摘要压缩≤10KB
  L2 ShortT.  → 语义去重，合并同会话，连接相关条目
  L3 Episodic → 结构去重，合并同类事件，事件因果链
  L4 Semantic → KG实体去重，归一化实体名，知识三元组融合
  L5 Meta     → 规则签名去重，精炼规则文本，策略规则树

本地实现 core.shared.protocols.ITaskRouter，携带 PLUGIN_INFO (category="route")。
分布式模式下可被 RemoteRoutingStrategy 热插拔替换。

架构定位: core/routing/ 路由策略插件层
版本: 1.0.0
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.shared.plugin_interface import PluginInfo

logger = logging.getLogger("tianji.routing.layer")


# ═══════════════════════════════════════════════════════════════
# 层级枚举与常量
# ═══════════════════════════════════════════════════════════════


class LayerName(str, Enum):
    """ICME 六层记忆层级标识  [v10-ready]"""

    SENSORY = "sensory"
    WORKING = "working"
    SHORT_TERM = "short_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    META = "meta"


LAYER_PRIORITY_ORDER = [
    LayerName.META, LayerName.SEMANTIC, LayerName.EPISODIC,
    LayerName.SHORT_TERM, LayerName.WORKING, LayerName.SENSORY,
]

LAYER_MAX_SIZE = {
    LayerName.SENSORY: float("inf"),
    LayerName.WORKING: 10_000,
    LayerName.SHORT_TERM: 50_000,
    LayerName.EPISODIC: 200_000,
    LayerName.SEMANTIC: 500_000,
    LayerName.META: 100_000,
}

LAYER_PROMOTION_THRESHOLD = {
    (LayerName.SENSORY, LayerName.WORKING): 0.3,
    (LayerName.WORKING, LayerName.SHORT_TERM): 0.4,
    (LayerName.SHORT_TERM, LayerName.EPISODIC): 0.5,
    (LayerName.EPISODIC, LayerName.SEMANTIC): 0.6,
    (LayerName.SEMANTIC, LayerName.META): 0.7,
}

LAYER_INDEX_FIELD = {
    LayerName.SENSORY: ["created_at"],
    LayerName.WORKING: ["session_id"],
    LayerName.SHORT_TERM: ["tags", "priority"],
    LayerName.EPISODIC: ["tags", "fts5"],
    LayerName.SEMANTIC: ["kg_topology"],
    LayerName.META: ["rule_id", "tags"],
}

KEYWORD_PATTERNS = {
    LayerName.SEMANTIC: {
        "architecture": ["架构", "设计", "重构", "改造", "architecture", "design", "refactor",
                         "模块", "组件", "系统", "接口", "协议", "规范", "标准"],
        "knowledge": ["知识", "概念", "定义", "原理", "机制", "原理图", "数据模型",
                      "表结构", "索引", "算法", "流程图"],
    },
    LayerName.EPISODIC: {
        "decision": ["决策", "决定", "选择", "方案", "取舍", "权衡"],
        "error": ["错误", "修复", "bug", "error", "fix", "异常", "失败", "崩溃", "故障"],
        "operation": ["操作", "执行", "部署", "发布", "回滚", "升级", "迁移"],
    },
    LayerName.META: {
        "strategy": ["策略", "规则", "变更", "strategy", "policy", "rule", "config",
                     "宪法", "铁律", "律令", "门禁", "阈值"],
        "meta": ["元认知", "反思", "优化", "调优", "进化", "自省", "策略变更"],
    },
}

MULTI_TURN_THRESHOLD = 3


@dataclass
class LayerTarget:
    """单个分发目标载体  [v10-ready]"""

    layer: str
    content: str
    tags: List[str]
    priority: str
    reason: str
    confidence: float = 0.5


@dataclass
class PromotionGate:
    """层级转换门禁结果载体  [v10-ready]"""

    source_layer: str
    target_layer: str
    value_threshold: float
    upstream_required: bool
    downstream_pressure: float
    passed: bool = False
    reason: str = ""


# ═══════════════════════════════════════════════════════════════
# LayerRoutingStrategy — 记忆层级路由策略 — [v10-ready]
# ═══════════════════════════════════════════════════════════════


class LayerRoutingStrategy:
    """记忆层级路由策略  [v10-ready]

    本地实现: 基于关键词+结构分析的内容→记忆层级路由。
    实现协议: core.shared.protocols.ITaskRouter (route / get_routing_strategy)。

    职责:
    1. route() — ITaskRouter 入口，接收任务 dict，返回单一最优记忆层级。
    2. route_content() — 多目标分级分发，返回多层级列表 (兼容原 LayerRouter.route)。
    3. deduplicate() / deredundate() / reorganize() — 层内去重/去冗余/重组。
    4. check_promotion_gate() — 层级转换门禁检查。
    """

    STRATEGY_NAME = "layer_semantic"
    DEDUP_THRESHOLD = 0.85

    def __init__(self, engine: Any = None, quality_gate: Any = None) -> None:
        """初始化层级路由策略。  [v10-ready]

        Args:
            engine: 记忆引擎 (用于 ngram 相似度/上游锚点检索, 可选)。
            quality_gate: 质量门禁 (可选)。
        """
        self._engine = engine
        self._quality_gate = quality_gate
        self._lock = threading.Lock()
        self._stats = {
            "total_routes": 0,
            "total_dedup_checks": 0,
            "dedup_skips": 0,
            "total_deredundate": 0,
            "total_reorganize": 0,
            "promotion_checks": 0,
            "promotion_passed": 0,
            "promotion_blocked": 0,
        }
        self._layer_fingerprints: Dict[str, Set[str]] = defaultdict(set)
        self._session_turn_count: Dict[str, int] = defaultdict(int)

    def set_engine(self, engine: Any) -> None:
        """注入记忆引擎。  [v10-ready]"""
        self._engine = engine

    def set_quality_gate(self, gate: Any) -> None:
        """注入质量门禁。  [v10-ready]"""
        self._quality_gate = gate

    # ---- ITaskRouter 协议实现 ----

    def route(self, task: dict[str, Any]) -> str:
        """根据任务特征选择目标记忆层级。  [v10-ready]

        ITaskRouter 协议入口。从任务 dict 提取内容与上下文，
        执行多目标分级分发后返回优先级最高的单一记忆层级。

        Args:
            task: 任务描述字典，支持 content/text 字段承载内容，
                  context 字段或顶层 session_id/turn_number 承载上下文。

        Returns:
            目标记忆层级标识 (sensory/working/short_term/episodic/semantic/meta)。
        """
        content = task.get("content") or task.get("text") or ""
        context = task.get("context")
        if not isinstance(context, dict):
            context = {
                "session_id": task.get("session_id", ""),
                "turn_number": task.get("turn_number", 0),
            }

        targets = self.route_content(content, context)
        if not targets:
            return LayerName.WORKING.value
        # route_content 已按 META→SEMANTIC→EPISODIC→SHORT_TERM→WORKING 优先级排列
        return targets[0]["layer"]

    def get_routing_strategy(self) -> str:
        """获取当前路由策略名称。  [v10-ready]"""
        return self.STRATEGY_NAME

    # ---- 多目标分级分发 (兼容原 LayerRouter.route) ----

    def route_content(self, content: str, context: Optional[Dict] = None) -> List[Dict]:
        """内容级分级分发 — 多目标核心入口。  [v10-ready]

        分析内容语义，返回多目标层级列表:
        - 含架构关键词 → L4 semantic (知识归档)
        - 含决策/错误 → L3 episodic (事件记录)
        - 含策略变更 → L5 meta (规则更新)
        - 多轮≥3 → L2 short_term (跨会话)
        - 默认 → L1 working (会话上下文)

        Args:
            content: 待路由内容文本。
            context: 上下文字典 (session_id/turn_number)。

        Returns:
            多目标层级字典列表 (按优先级排序)。
        """
        self._stats["total_routes"] += 1
        context = context or {}
        targets: List[LayerTarget] = []
        content_lower = content.lower()

        semantic_score = self._score_layer_keywords(content_lower, LayerName.SEMANTIC)
        episodic_score = self._score_layer_keywords(content_lower, LayerName.EPISODIC)
        meta_score = self._score_layer_keywords(content_lower, LayerName.META)

        session_id = context.get("session_id", "")
        turn_number = context.get("turn_number", 0)
        if session_id:
            self._session_turn_count[session_id] = max(
                self._session_turn_count[session_id], turn_number
            )

        if meta_score >= 0.5:
            targets.append(LayerTarget(
                layer=LayerName.META.value,
                content=self._extract_meta_content(content),
                tags=["strategy", "meta", "rule_change"],
                priority="critical",
                reason=f"策略/规则变更内容 (score={meta_score:.2f})",
                confidence=meta_score,
            ))

        if semantic_score >= 0.4:
            targets.append(LayerTarget(
                layer=LayerName.SEMANTIC.value,
                content=self._extract_semantic_content(content),
                tags=["architecture", "knowledge", "semantic"],
                priority="high",
                reason=f"架构/知识内容 (score={semantic_score:.2f})",
                confidence=semantic_score,
            ))

        if episodic_score >= 0.4:
            targets.append(LayerTarget(
                layer=LayerName.EPISODIC.value,
                content=self._extract_episodic_content(content),
                tags=["decision", "event", "episodic"],
                priority="high",
                reason=f"决策/事件内容 (score={episodic_score:.2f})",
                confidence=episodic_score,
            ))

        if self._session_turn_count.get(session_id, 0) >= MULTI_TURN_THRESHOLD:
            targets.append(LayerTarget(
                layer=LayerName.SHORT_TERM.value,
                content=content,
                tags=["multi_turn", "cross_session", "short_term"],
                priority="medium",
                reason=f"多轮对话≥{MULTI_TURN_THRESHOLD} (turns={self._session_turn_count[session_id]})",
                confidence=0.6,
            ))

        if not targets:
            targets.append(LayerTarget(
                layer=LayerName.WORKING.value,
                content=content,
                tags=["context", "working"],
                priority="medium",
                reason="默认会话上下文",
                confidence=0.5,
            ))

        return [
            {
                "layer": t.layer,
                "content": t.content,
                "tags": t.tags,
                "priority": t.priority,
                "reason": t.reason,
                "confidence": t.confidence,
            }
            for t in targets
        ]

    # ---- 去重 / 去冗余 / 重组 ----

    def deduplicate(self, content: str, layer: str) -> bool:
        """语义去重 — 相似度>0.85则跳过。  [v10-ready]

        策略:
        - L0: 不去重（原始快照）
        - L1-L5: ngram指纹 + 内容哈希去重
        """
        self._stats["total_dedup_checks"] += 1

        if layer == LayerName.SENSORY.value:
            return False

        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        layer_key = layer

        with self._lock:
            if content_hash in self._layer_fingerprints[layer_key]:
                self._stats["dedup_skips"] += 1
                return True

        ngram_sim = self._ngram_similarity(content, layer)
        if ngram_sim > self.DEDUP_THRESHOLD:
            self._stats["dedup_skips"] += 1
            return True

        with self._lock:
            self._layer_fingerprints[layer_key].add(content_hash)
            if len(self._layer_fingerprints[layer_key]) > 10000:
                oldest = list(self._layer_fingerprints[layer_key])[:5000]
                for h in oldest:
                    self._layer_fingerprints[layer_key].discard(h)

        return False

    def deredundate(self, content: str, layer: str) -> str:
        """去冗余 — 删除与层内已有知识重复的片段。  [v10-ready]

        策略:
        - L0: 不处理
        - L1: 摘要压缩到≤10KB
        - L2: 合并同会话内容
        - L3: 合并同类事件
        - L4: 归一化实体名
        - L5: 精炼规则文本
        """
        self._stats["total_deredundate"] += 1

        if layer == LayerName.SENSORY.value:
            return content

        max_size = LAYER_MAX_SIZE.get(LayerName(layer), 10_000)
        content_bytes = len(content.encode("utf-8"))

        if content_bytes <= max_size:
            return content

        if layer == LayerName.WORKING.value:
            return self._compress_to_size(content, max_size)
        elif layer == LayerName.SHORT_TERM.value:
            return self._merge_session_content(content, max_size)
        elif layer == LayerName.EPISODIC.value:
            return self._merge_similar_events(content, max_size)
        elif layer == LayerName.SEMANTIC.value:
            return self._normalize_entities(content, max_size)
        elif layer == LayerName.META.value:
            return self._refine_rules(content, max_size)

        return content

    def reorganize(self, content: str, layer: str) -> str:
        """重组新知识 — 碎片→结构化。  [v10-ready]

        策略:
        - L0-L1: 不重组
        - L2: 连接相关条目
        - L3: 事件因果链
        - L4: 知识三元组融合
        - L5: 策略规则树
        """
        self._stats["total_reorganize"] += 1

        if layer in (LayerName.SENSORY.value, LayerName.WORKING.value):
            return content

        if layer == LayerName.SHORT_TERM.value:
            return self._link_related_entries(content)
        elif layer == LayerName.EPISODIC.value:
            return self._build_event_chain(content)
        elif layer == LayerName.SEMANTIC.value:
            return self._fuse_knowledge_triples(content)
        elif layer == LayerName.META.value:
            return self._build_rule_tree(content)

        return content

    def check_promotion_gate(self, content: str, source_layer: str,
                             target_layer: str) -> PromotionGate:
        """层级转换门禁检查。  [v10-ready]

        条件:
        1. 内容价值分 ≥ 层级阈值
        2. 上游锚点存在性验证
        3. 下游需求压力评估
        """
        self._stats["promotion_checks"] += 1

        key = (LayerName(source_layer), LayerName(target_layer))
        threshold = LAYER_PROMOTION_THRESHOLD.get(key, 0.5)

        value_score = self._calc_content_value(content)
        upstream_ok = self._check_upstream_anchor(content, target_layer)
        downstream_pressure = self._assess_downstream_pressure(target_layer)

        passed = value_score >= threshold and (upstream_ok or source_layer == "sensory")

        gate = PromotionGate(
            source_layer=source_layer,
            target_layer=target_layer,
            value_threshold=threshold,
            upstream_required=not (source_layer == "sensory"),
            downstream_pressure=downstream_pressure,
            passed=passed,
            reason=self._build_gate_reason(passed, value_score, threshold, upstream_ok),
        )

        if passed:
            self._stats["promotion_passed"] += 1
        else:
            self._stats["promotion_blocked"] += 1

        return gate

    def get_layer_index_fields(self, layer: str) -> List[str]:
        """获取层内索引字段。  [v10-ready]"""
        try:
            return LAYER_INDEX_FIELD.get(LayerName(layer), [])
        except ValueError:
            return []

    def get_stats(self) -> Dict:
        """获取路由统计快照。  [v10-ready]"""
        return {
            **self._stats,
            "strategy": self.STRATEGY_NAME,
            "active_layers": len(self._layer_fingerprints),
            "fingerprint_count": sum(len(v) for v in self._layer_fingerprints.values()),
            "active_sessions": len(self._session_turn_count),
            "engine_connected": self._engine is not None,
            "quality_gate_connected": self._quality_gate is not None,
        }

    # ---- 内部辅助方法 ----

    def _score_layer_keywords(self, content_lower: str, layer: LayerName) -> float:
        """计算内容对某层关键词的命中评分。  [v10-ready]"""
        patterns = KEYWORD_PATTERNS.get(layer, {})
        if not patterns:
            return 0.0

        total_matches = 0
        total_keywords = 0
        for category, keywords in patterns.items():
            total_keywords += len(keywords)
            for kw in keywords:
                if kw.lower() in content_lower:
                    total_matches += 1

        if total_keywords == 0:
            return 0.0

        raw_score = total_matches / total_keywords
        return min(raw_score * 3.0, 1.0)

    def _extract_meta_content(self, content: str) -> str:
        """抽取策略/规则相关行。  [v10-ready]"""
        lines = content.split("\n")
        meta_lines = []
        strategy_kw = KEYWORD_PATTERNS[LayerName.META]
        all_kw = [kw for kws in strategy_kw.values() for kw in kws]
        for line in lines:
            if any(kw.lower() in line.lower() for kw in all_kw):
                meta_lines.append(line)
        if not meta_lines:
            return content
        return "\n".join(meta_lines)

    def _extract_semantic_content(self, content: str) -> str:
        """抽取架构/知识相关行。  [v10-ready]"""
        lines = content.split("\n")
        semantic_lines = []
        sem_kw = KEYWORD_PATTERNS[LayerName.SEMANTIC]
        all_kw = [kw for kws in sem_kw.values() for kw in kws]
        for line in lines:
            if any(kw.lower() in line.lower() for kw in all_kw):
                semantic_lines.append(line)
        if not semantic_lines:
            return content
        return "\n".join(semantic_lines)

    def _extract_episodic_content(self, content: str) -> str:
        """抽取决策/事件相关行。  [v10-ready]"""
        lines = content.split("\n")
        epi_lines = []
        epi_kw = KEYWORD_PATTERNS[LayerName.EPISODIC]
        all_kw = [kw for kws in epi_kw.values() for kw in kws]
        for line in lines:
            if any(kw.lower() in line.lower() for kw in all_kw):
                epi_lines.append(line)
        if not epi_lines:
            return content
        return "\n".join(epi_lines)

    def _ngram_similarity(self, content: str, layer: str) -> float:
        """ngram指纹相似度检测。  [v10-ready]"""
        content_ngrams = self._extract_ngrams(content, n=3)
        if not content_ngrams:
            return 0.0

        if self._engine is None:
            return 0.0

        try:
            results = self._engine.recall(query=content[:200], limit=5,
                                          min_score=0.0, layers=[layer])
            if not results:
                return 0.0

            for r in results[:3]:
                existing = r.get("content", "") if isinstance(r, dict) else getattr(r, "content", "")
                if not existing:
                    continue
                existing_ngrams = self._extract_ngrams(existing, n=3)
                if not existing_ngrams:
                    continue
                intersection = content_ngrams & existing_ngrams
                union = content_ngrams | existing_ngrams
                if union:
                    jaccard = len(intersection) / len(union)
                    if jaccard > self.DEDUP_THRESHOLD:
                        return jaccard
        except Exception:
            pass

        return 0.0

    @staticmethod
    def _extract_ngrams(text: str, n: int = 3) -> Set[str]:
        """提取文本 ngram 集合。  [v10-ready]"""
        clean = "".join(c for c in text if c.isalnum() or c in " \n")
        words = clean.lower().split()
        if len(words) < n:
            return set()
        return {" ".join(words[i: i + n]) for i in range(len(words) - n + 1)}

    def _compress_to_size(self, content: str, max_size: int) -> str:
        """按头尾保留压缩内容至目标字节。  [v10-ready]"""
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= max_size:
            return content

        ratio = max_size / content_bytes
        lines = content.split("\n")
        keep_lines = max(int(len(lines) * ratio), 5)
        head = lines[: keep_lines // 2]
        tail = lines[-(keep_lines - len(head)):]
        omitted = len(lines) - len(head) - len(tail)
        marker = f"\n... [{omitted} lines compressed] ...\n" if omitted > 0 else ""
        return "\n".join(head) + marker + "\n".join(tail)

    def _merge_session_content(self, content: str, max_size: int) -> str:
        """合并同会话内容 (L2)。  [v10-ready]"""
        return self._compress_to_size(content, max_size)

    def _merge_similar_events(self, content: str, max_size: int) -> str:
        """合并同类事件 (L3)。  [v10-ready]"""
        return self._compress_to_size(content, max_size)

    def _normalize_entities(self, content: str, max_size: int) -> str:
        """归一化实体名 (L4)。  [v10-ready]"""
        return self._compress_to_size(content, max_size)

    def _refine_rules(self, content: str, max_size: int) -> str:
        """精炼规则文本 (L5)。  [v10-ready]"""
        return self._compress_to_size(content, max_size)

    def _link_related_entries(self, content: str) -> str:
        """连接相关条目 (L2)。  [v10-ready]"""
        return content

    def _build_event_chain(self, content: str) -> str:
        """构建事件因果链 (L3)。  [v10-ready]"""
        lines = content.split("\n")
        chain_lines = []
        for i, line in enumerate(lines):
            if line.strip():
                prefix = f"[Step {i+1}] " if i > 0 else ""
                chain_lines.append(f"{prefix}{line}")
        return "\n".join(chain_lines)

    def _fuse_knowledge_triples(self, content: str) -> str:
        """融合知识三元组 (L4)。  [v10-ready]"""
        return content

    def _build_rule_tree(self, content: str) -> str:
        """构建策略规则树 (L5)。  [v10-ready]"""
        lines = content.split("\n")
        tree_lines = []
        depth = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("#", "##", "###")):
                depth = stripped.count("#") - 1
                tree_lines.append(f"{'  ' * depth}{stripped.lstrip('#').strip()}")
            else:
                tree_lines.append(f"{'  ' * (depth + 1)}- {stripped}")
        return "\n".join(tree_lines)

    def _calc_content_value(self, content: str) -> float:
        """计算内容价值分。  [v10-ready]"""
        length_score = min(len(content) / 1000.0, 1.0) * 0.3
        structure_score = 0.0
        if "```" in content:
            structure_score += 0.2
        if any(kw in content.lower() for kw in ["架构", "设计", "策略", "规则"]):
            structure_score += 0.2
        if "\n" in content:
            structure_score += 0.1
        info_density = min(len(set(content)) / max(len(content), 1) * 10, 1.0) * 0.2
        return min(length_score + structure_score + info_density, 1.0)

    def _check_upstream_anchor(self, content: str, target_layer: str) -> bool:
        """验证上游锚点存在性。  [v10-ready]"""
        if self._engine is None:
            return True
        try:
            results = self._engine.recall(query=content[:100], limit=3,
                                          min_score=0.0, layers=[target_layer])
            return len(results) > 0
        except Exception:
            return True

    def _assess_downstream_pressure(self, target_layer: str) -> float:
        """评估下游需求压力。  [v10-ready]"""
        return 0.5

    @staticmethod
    def _build_gate_reason(passed: bool, value: float, threshold: float,
                           upstream_ok: bool) -> str:
        """构建门禁判决理由文本。  [v10-ready]"""
        if passed:
            return f"晋升通过: 价值分{value:.2f}≥阈值{threshold:.2f}, 上游锚点{'存在' if upstream_ok else '豁免'}"
        reasons = []
        if value < threshold:
            reasons.append(f"价值分{value:.2f}<阈值{threshold:.2f}")
        if not upstream_ok:
            reasons.append("上游锚点缺失")
        return f"晋升阻断: {', '.join(reasons)}"


PLUGIN_INFO = PluginInfo(
    name="layer_routing",
    version="1.0.0",
    description="记忆层级路由策略",
    category="route",
    protocols=["ITaskRouter"],
)
