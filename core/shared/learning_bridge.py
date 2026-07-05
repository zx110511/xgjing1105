r"""
天机闭环学习桥接 (Tianji Learning Bridge) v1.0
================================================
连接 ICME Engine 与 Learning Loop 的信号桥梁。

当 engine.remember() 或 engine.consolidate() 完成时，
本模块自动提取经验知识并沉淀到 L4 Semantic 层。

设计哲学:
  不引入新的复杂依赖，而是作为 engine 的轻量级插件，
  在关键节点注入学习信号。

灵境道谱溯源: D3-2【经验煞】· 道三·进化体道 · 四地煞之化之术
  - 经验自动提炼+技能发现+知识分库存储
"""

import time
import json
import logging
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class KnowledgeCategory(str, Enum):
    SUCCESS_PATTERN = "success_pattern"
    FAILURE_PATTERN = "failure_pattern"
    OPTIMIZATION_HINT = "optimization_hint"
    ARCHITECTURE_INSIGHT = "architecture_insight"
    USER_PREFERENCE = "user_preference"
    TOOL_USAGE_PATTERN = "tool_usage_pattern"
    ERROR_RECOVERY = "error_recovery"
    DOMAIN_KNOWLEDGE = "domain_knowledge"


@dataclass
class LearningSignal:
    signal_type: str
    source_layer: str
    content_summary: str
    category: KnowledgeCategory
    confidence: float
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ClosedLoopLearningBridge:
    """
    轻量级闭环学习桥接器。

    职责:
    1. 监听 engine 的 remember/consolidate 事件
    2. 提取结构化学习信号
    3. 将高价值信号写入 L4 Semantic 层
    4. 维护 8 类知识分库索引
    """

    KNOWLEDGE_CATEGORIES = [c.value for c in KnowledgeCategory]

    def __init__(self, engine=None):
        self._engine = engine
        self._signal_buffer: List[LearningSignal] = []
        self._buffer_max = 100
        self._stats = {
            "signals_received": 0,
            "signals_extracted": 0,
            "knowledge_stored": 0,
            "skills_discovered": 0,
            "category_distribution": {c: 0 for c in self.KNOWLEDGE_CATEGORIES},
        }
        self._last_batch_store_time = 0.0
        self._batch_interval_seconds = 300

    def on_remember(self, result: dict, content: str, layer: str):
        """remember() 完成后的回调 — 提取学习信号"""
        self._stats["signals_received"] += 1

        status = result.get("status", "")
        actual_layer = result.get("actual_layer", layer)

        if status == "rejected":
            signal = self._extract_failure_signal(content, actual_layer)
        elif status == "stored" and result.get("llm_enriched"):
            signal = self._extract_success_signal(content, actual_layer, result)
        elif "conflict" in str(status):
            signal = self._extract_conflict_signal(content, actual_layer, result)
        else:
            signal = None

        if signal:
            self._signal_buffer.append(signal)
            self._stats["signals_extracted"] += 1
            self._check_batch_store()

    def on_consolidation(self, event: dict):
        """consolidation() 完成后的回调 — 提取固化经验"""
        event_type = event.get("event", "")
        promoted = event.get("promoted_count", 0)

        if event_type == "consolidation_executed" and promoted > 0:
            signal = LearningSignal(
                signal_type="consolidation_success",
                source_layer=event.get("from_layer", ""),
                content_summary=f"Layer {event.get('from_layer')}→{event.get('to_layer')}: {promoted} entries promoted",
                category=KnowledgeCategory.ARCHITECTURE_INSIGHT,
                confidence=min(0.9, 0.5 + promoted * 0.05),
                metadata=event,
            )
            self._signal_buffer.append(signal)
            self._stats["signals_extracted"] += 1

    def _extract_failure_signal(self, content: str, layer: str) -> Optional[LearningSignal]:
        category = KnowledgeCategory.FAILURE_PATTERN
        if "安全" in content or "security" in content.lower():
            category = KnowledgeCategory.SECURITY_VIOLATION if hasattr(KnowledgeCategory, "SECURITY_VIOLATION") else category
        return LearningSignal(
            signal_type="write_rejected",
            source_layer=layer,
            content_summary=content[:200],
            category=category,
            confidence=0.7,
        )

    def _extract_success_signal(self, content: str, layer: str, result: dict) -> Optional[LearningSignal]:
        tags = result.get("metadata", {}).get("tags", [])
        if any(t in ["enforcement_hook", "auto_record"] for t in tags):
            category = KnowledgeCategory.TOOL_USAGE_PATTERN
        elif any(t in ["trae", "conversation"] for t in tags):
            category = KnowledgeCategory.USER_PREFERENCE
        else:
            category = KnowledgeCategory.SUCCESS_PATTERN
        return LearningSignal(
            signal_type="successful_write",
            source_layer=layer,
            content_summary=content[:200],
            category=category,
            confidence=0.6,
            metadata={"tags": tags},
        )

    def _extract_conflict_signal(self, content: str, layer: str, result: dict) -> Optional[LearningSignal]:
        return LearningSignal(
            signal_type="conflict_detected",
            source_layer=layer,
            content_summary=f"Conflict at {layer}: {content[:150]}",
            category=KnowledgeCategory.OPTIMIZATION_HINT,
            confidence=0.8,
            metadata=result,
        )

    def _check_batch_store(self):
        now = time.time()
        if (len(self._signal_buffer) >= 10 or
            now - self._last_batch_store_time >= self._batch_interval_seconds):
            self._batch_store_knowledge()

    def _batch_store_knowledge(self):
        if not self._signal_buffer or not self._engine:
            return

        stored = 0
        for signal in self._signal_buffer[-50:]:
            try:
                cat = signal.category.value
                self._stats["category_distribution"][cat] =                     self._stats["category_distribution"].get(cat, 0) + 1

                knowledge_content = (
                    f"[Learning Signal @ {signal.signal_type}] "
                    f"{signal.content_summary}\n"
                    f"Source: {signal.source_layer} | "
                    f"Category: {cat} | "
                    f"Confidence: {signal.confidence:.2f}"
                )

                result = self._engine.remember(
                    content=knowledge_content,
                    layer="semantic",
                    tags=["learning_signal", cat, f"src:{signal.source_layer}", signal.signal_type],
                    priority="medium" if signal.confidence > 0.7 else "low",
                )

                if result.get("status") in ("stored", "downgraded"):
                    stored += 1
                    self._stats["knowledge_stored"] += 1
            except Exception as e:
                logger.warning(f"Learning bridge store error: {e}")

        self._signal_buffer.clear()
        self._last_batch_store_time = time.time()
        logger.info(f"Learning bridge batch stored: {stored} knowledge items")

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "buffer_size": len(self._signal_buffer),
            "uptime_seconds": time.time() - (self._last_batch_store_time or time.time()),
        }

    def force_flush(self):
        """强制刷新缓冲区到记忆系统"""
        if self._signal_buffer:
            self._batch_store_knowledge()
