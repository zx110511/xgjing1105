# -*- coding: utf-8-sig -*-
r"""
LLM桥接层 (兼容层) — DeepSeek ←→ ICME Engine v2.0  [v10-ready]
================================================================
本文件自 P2-6 起瘦身为**兼容层 (thin wrapper)**。

核心 LLM 策略逻辑已迁出至 core/llm/ 子包：
  - DeepSeekLLMStrategy      (core/llm/deepseek_strategy.py)
  - ClassificationEngine     (core/llm/classification.py)
  - KnowledgeExtractionEngine(core/llm/knowledge_extraction.py)
  - RemoteLLMStrategy        (core/llm/remote_stub.py, v10 预留)

本层职责 (保持 v9.1 现有调用方零改动):
  - 保留 `from core.shared.llm_bridge import LLMBridge` 导入路径
  - LLMBridge 类内部委托至 DeepSeekLLMStrategy 完成全部 LLM 原语调用
  - 保留 enrich_remember / enrich_recall 富化编排 + EvolutionLoop 闭环

灵境道谱溯源: D9-4【桥接通道煞】· 道九·通道体 · 四地煞之桥之术

设计原则 (继承自原 LLMBridge):
  - 同步封装 (engine 是同步的)
  - 降级友好 (DeepSeek 不可用时静默回退)
  - 零阻塞感知 (超时保护)
  - 线程安全 (threading.RLock)
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from core.llm.deepseek_strategy import DeepSeekLLMStrategy

try:
    from ..processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


class LLMBridge:
    """LLM 桥接器 (兼容层)。  [v10-ready]

    内部委托至 DeepSeekLLMStrategy，对外保持与 v9.1 完全一致的公开 API。
    """

    def __init__(
        self,
        config: Optional[Any] = None,
        recorder: Optional[Any] = None,
        learning_engine: Optional[Any] = None,
    ):
        """初始化 LLM 桥接器。

        Args:
            config: 可选 DeepSeekConfig；为 None 时由策略从环境加载。
            recorder: 可选行为记录器。
            learning_engine: 可选学习引擎。
        """
        self._lock = threading.RLock()
        self._recorder = recorder
        self._learning_engine = learning_engine

        # 委托核心 — DeepSeek LLM 策略
        self._strategy = DeepSeekLLMStrategy(
            config=config,
            recorder=recorder,
            learning_engine=learning_engine,
        )

        # 桥接层富化编排统计 (LLM 原语统计由 strategy 维护)
        self._stats = {
            "enrich_remember_ops": 0,
            "enrich_recall_ops": 0,
            "start_time": time.time(),
        }
        self._errors = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="llm_bridge",
                    effectiveness_fn=self._calc_bridge_effectiveness,
                    learn_fn=self._learn_from_bridge,
                    evolve_fn=self._evolve_bridge_config,
                    mutable_config={
                        "fallback_threshold": 0.3,
                        "enrich_timeout_ms": 5000,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(
                    f"LLMBridge EvolutionLoop init failed: {e}"
                )

    @property
    def is_ready(self) -> bool:
        """DeepSeek 是否就绪可用。  [v10-ready]"""
        return self._strategy.is_ready

    # ------------------------------------------------------------------
    # LLM 原语 — 委托至 DeepSeekLLMStrategy
    # ------------------------------------------------------------------

    def classify_content(
        self, content: str, context: Optional[Dict] = None
    ) -> Optional[Any]:
        """判定记忆层级 — 返回 ClassificationResult。  [v10-ready]"""
        return self._strategy.classify_content(content, context)

    def auto_tag(self, content: str) -> List[str]:
        """自动生成标签。  [v10-ready]"""
        return self._strategy.auto_tag(content)

    def assess_value(self, content: str) -> float:
        """评估记忆价值 0.0-1.0。  [v10-ready]"""
        return self._strategy.assess_value(content)

    def decide_storage(
        self, content: str, context: Optional[Dict] = None
    ) -> Optional[Any]:
        """综合存储策略决策 — 返回 StorageDecision。  [v10-ready]"""
        return self._strategy.decide_storage(content, context)

    def extract_knowledge(self, content: str) -> List[Dict]:
        """提取知识三元组。  [v10-ready]"""
        return self._strategy.extract_knowledge(content)

    def summarize(self, content: str, max_length: int = 200) -> str:
        """生成摘要。  [v10-ready]"""
        return self._strategy.summarize(content, max_length)

    def expand_query(self, query: str) -> List[str]:
        """查询扩展。  [v10-ready]"""
        return self._strategy.expand_query(query)

    # ------------------------------------------------------------------
    # 富化编排 (桥接层职责)
    # ------------------------------------------------------------------

    def enrich_remember(
        self,
        content: str,
        layer: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: Optional[str] = None,
    ) -> Dict[str, Any]:
        """记忆写入富化 — 自动分类/打标/评估/知识提取。  [v10-ready]

        Args:
            content: 记忆内容文本。
            layer: 调用方已指定层级 (优先保留)。
            tags: 调用方已指定标签 (优先保留)。
            priority: 调用方已指定优先级 (优先保留)。

        Returns:
            富化结果字典；DeepSeek 不可用时返回原样默认值。
        """
        with self._lock:
            self._stats["enrich_remember_ops"] += 1
        enrichment = {
            "layer": layer,
            "tags": tags or [],
            "priority": priority or "medium",
            "value_score": 0.5,
            "summary": "",
            "knowledge_triples": [],
            "llm_enriched": False,
        }

        if not self.is_ready:
            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="enrich_remember",
                        state_before={"ready": False},
                        state_after={"ready": False, "llm_enriched": False},
                    )
                except Exception:
                    pass
            return enrichment

        decision = self.decide_storage(content)

        if decision is None:
            return enrichment

        enrichment["llm_enriched"] = True

        if not layer:
            enrichment["layer"] = decision.layer
        if not tags:
            enrichment["tags"] = decision.tags
        if not priority:
            enrichment["priority"] = decision.priority
        enrichment["value_score"] = decision.value_score

        # 摘要: content>100字符时触发 (中文字符密度高, 100字符≈300字节已有足够信息量)
        if len(content) > 100:
            # decide_storage内部已调用summarize，直接复用结果，避免重复API调用
            enrichment["summary"] = decision.summary or ""

        if decision.value_score >= 0.5:
            enrichment["knowledge_triples"] = self.extract_knowledge(content)

        # 自动打标补充: 当decide_storage未返回足够标签时, 调用auto_tag增强
        if len(enrichment.get("tags", [])) < 3:
            try:
                extra_tags = self.auto_tag(content)
                existing = set(enrichment.get("tags", []))
                for t in extra_tags:
                    if t not in existing and len(enrichment["tags"]) < 6:
                        enrichment["tags"].append(t)
                        existing.add(t)
            except Exception:
                pass

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="enrich_remember",
                    state_before={"ready": True, "llm_enriched": False},
                    state_after={
                        "ready": True,
                        "llm_enriched": True,
                        "layer": enrichment["layer"],
                        "value_score": enrichment["value_score"],
                        "triples_count": len(enrichment["knowledge_triples"]),
                    },
                )
            except Exception:
                pass

        return enrichment

    def enrich_recall(self, query: str, entries: List, limit: int = 20) -> List:
        """检索结果富化 — 查询扩展 + 重排序。  [v10-ready]

        Args:
            query: 原始查询文本。
            entries: 召回的候选条目列表。
            limit: 返回条目上限。

        Returns:
            富化重排后的条目列表；DeepSeek 不可用时按原序截断。
        """
        with self._lock:
            self._stats["enrich_recall_ops"] += 1
        if not self.is_ready or not entries:
            return entries[:limit]

        expansions = self.expand_query(query)

        scored = []
        for entry in entries[: min(50, len(entries))]:
            content = (
                entry.content if hasattr(entry, "content") else entry.get("content", "")
            )
            base_score = (
                entry.value_score()
                if hasattr(entry, "value_score")
                else entry.get("value_score", 0.5)
            )
            for exp in expansions:
                if exp.lower() in content.lower():
                    base_score *= 1.3
                    break
            scored.append((base_score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        result = [e for _, e in scored[:limit]]

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="enrich_recall",
                    state_before={"query": query, "entries_in": len(entries)},
                    state_after={
                        "query": query,
                        "entries_out": len(result),
                        "expansions": len(expansions),
                    },
                )
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # 健康/统计/演化
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """获取桥接器健康状态。  [v10-ready]"""
        strategy_stats = self._strategy.get_stats()
        with self._lock:
            return {
                "status": "ready" if self.is_ready else "not_ready",
                "version": "2.0",
                "is_ready": self.is_ready,
                "total_calls": strategy_stats.get("total_calls", 0),
                "successful_calls": strategy_stats.get("successful_calls", 0),
                "failed_calls": strategy_stats.get("failed_calls", 0),
                "fallback_calls": strategy_stats.get("fallback_calls", 0),
                "errors": self._errors,
                "evo_loop_active": self._evo_loop is not None,
                "recorder_attached": self._recorder is not None,
                "enrich_remember_ops": self._stats["enrich_remember_ops"],
                "enrich_recall_ops": self._stats["enrich_recall_ops"],
            }

    def get_stats(self) -> Dict[str, Any]:
        """获取桥接器统计。  [v10-ready]"""
        strategy_stats = self._strategy.get_stats()
        with self._lock:
            return {
                "version": "2.0",
                "status": "ready" if self.is_ready else "not_ready",
                "is_ready": self.is_ready,
                **self._stats,
                "errors": self._errors,
                "evo_loop_active": self._evo_loop is not None,
                "recorder_attached": self._recorder is not None,
                "strategy": strategy_stats,
                "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
            }

    def tick(self):
        """推进演化闭环一拍。  [v10-ready]"""
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_bridge_effectiveness(
        self, action: str, state_before: Dict[str, Any], state_after: Dict[str, Any]
    ) -> float:
        if action == "enrich_remember":
            if state_after.get("llm_enriched", False):
                score = state_after.get("value_score", 0.5)
                triples = state_after.get("triples_count", 0)
                return min(0.8, score * 0.4 + triples * 0.1)
            return 0.1
        elif action == "enrich_recall":
            expansions = state_after.get("expansions", 0)
            entries_out = state_after.get("entries_out", 0)
            return min(0.6, 0.2 + expansions * 0.1 + entries_out * 0.02)
        return 0.0

    def _learn_from_bridge(
        self, causal_pairs: List[Any], effectiveness_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        strategy_stats = self._strategy.get_stats()
        total_calls = max(strategy_stats.get("total_calls", 0), 1)
        with self._lock:
            return {
                "patterns_found": len(causal_pairs),
                "avg_effectiveness": effectiveness_summary.get(
                    "avg_effectiveness", 0.0
                ),
                "success_rate": strategy_stats.get("successful_calls", 0) / total_calls,
                "total_enriched": (
                    self._stats["enrich_remember_ops"]
                    + self._stats["enrich_recall_ops"]
                ),
            }

    def _evolve_bridge_config(
        self, learn_result: Dict[str, Any], mutable_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        changes = {}
        success_rate = learn_result.get("success_rate", 1.0)
        if success_rate < 0.5:
            changes["enrich_timeout_ms"] = min(
                10000, mutable_config.get("enrich_timeout_ms", 5000) + 1000
            )
        if success_rate > 0.9 and mutable_config.get("enrich_timeout_ms", 5000) > 2000:
            changes["enrich_timeout_ms"] = max(
                2000, mutable_config.get("enrich_timeout_ms", 5000) - 500
            )
        return {"rules_modified": changes, "skills_created": []}
