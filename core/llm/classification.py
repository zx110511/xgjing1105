# -*- coding: utf-8-sig -*-
"""内容分类引擎 — ClassificationEngine  [v10-ready]

从 core/llm_bridge.py 提取的内容分类逻辑：
    - classify_content : 判定记忆层级 (委托 MemoryDecisionEngine.classify_layer)
    - auto_tag         : 自动生成标签
    - assess_value     : 评估记忆价值 0.0-1.0
    - decide_storage   : 综合存储策略决策

设计原则:
    - 降级友好: 决策引擎不可用 (engine=None) 或调用异常时返回合理空结果而非异常
    - 线程安全: 使用 threading.RLock 保护内部统计
    - 零阻塞感知: 任意底层异常均被吞掉并回退

架构定位: core/llm/ LLM策略子包 — 分类能力单元
版本: 1.0.0
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Optional

# 分类统计计数器持久化文件 (P0-1: 重启不丢失)
CLASSIFICATION_STATS_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "data",
    ".memory",
    "llm_classification_counters.json",
)


class ClassificationEngine:
    """内容分类引擎  [v10-ready]

    包装 MemoryDecisionEngine 的分类相关能力，对外提供降级友好的同步接口。
    当底层决策引擎不可用时，所有方法返回安全的回退值。
    """

    def __init__(self, engine: Optional[Any] = None):
        """初始化分类引擎。

        Args:
            engine: MemoryDecisionEngine 实例；为 None 时进入降级模式。
        """
        self._engine = engine
        self._lock = threading.RLock()
        self._stats = {
            "classify_ops": 0,
            "tag_ops": 0,
            "assess_ops": 0,
            "decide_ops": 0,
            "fallback_ops": 0,
        }
        # P0-1: 持久化 — 重启不丢失分类累计计数
        self._persist_every = 5
        self._dirty_count = 0
        self._load_persisted_stats()

    def _load_persisted_stats(self) -> None:
        """从JSON恢复分类计数器 (P0-1)。"""
        try:
            if not os.path.exists(CLASSIFICATION_STATS_FILE):
                return
            with open(CLASSIFICATION_STATS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k in self._stats:
                v = saved.get(k)
                if isinstance(v, (int, float)):
                    self._stats[k] = v
        except Exception:
            pass

    def _persist_stats(self) -> None:
        """将分类计数器写入JSON持久化 (P0-1)。"""
        try:
            os.makedirs(os.path.dirname(CLASSIFICATION_STATS_FILE), exist_ok=True)
            with self._lock:
                data = {
                    k: v for k, v in self._stats.items() if isinstance(v, (int, float))
                }
            with open(CLASSIFICATION_STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    @property
    def is_ready(self) -> bool:
        """决策引擎是否就绪。  [v10-ready]"""
        return self._engine is not None

    def _bump(self, key: str) -> None:
        with self._lock:
            self._stats[key] = self._stats.get(key, 0) + 1
            self._dirty_count += 1
            do_persist = self._dirty_count >= self._persist_every
            if do_persist:
                self._dirty_count = 0
        if do_persist:
            self._persist_stats()

    def classify_content(
        self, content: str, context: Optional[dict] = None
    ) -> Optional[Any]:
        """判定内容应存储到的记忆层级。  [v10-ready]

        Args:
            content: 待分类内容文本。
            context: 可选上下文字典。

        Returns:
            ClassificationResult；引擎不可用或异常时返回 None。
        """
        self._bump("classify_ops")
        if self._engine is None:
            self._bump("fallback_ops")
            return None
        try:
            return self._engine.classify_layer(content, context)
        except Exception:
            self._bump("fallback_ops")
            return None

    def auto_tag(self, content: str) -> list[str]:
        """为内容自动生成标签。  [v10-ready]

        Args:
            content: 待打标内容文本。

        Returns:
            标签列表；引擎不可用或异常时返回空列表。
        """
        self._bump("tag_ops")
        if self._engine is None:
            self._bump("fallback_ops")
            return []
        try:
            result = self._engine.auto_tag(content)
            return result if isinstance(result, list) else []
        except Exception:
            self._bump("fallback_ops")
            return []

    def assess_value(self, content: str) -> float:
        """评估内容的记忆价值。  [v10-ready]

        Args:
            content: 待评估内容文本。

        Returns:
            价值评分 0.0-1.0；引擎不可用或异常时返回中性值 0.5。
        """
        self._bump("assess_ops")
        if self._engine is None:
            self._bump("fallback_ops")
            return 0.5
        try:
            result = self._engine.assess_value(content)
            if isinstance(result, dict):
                return float(result.get("value_score", 0.5))
            return 0.5
        except Exception:
            self._bump("fallback_ops")
            return 0.5

    def decide_storage(
        self, content: str, context: Optional[dict] = None
    ) -> Optional[Any]:
        """综合存储策略决策。  [v10-ready]

        Args:
            content: 待决策内容文本。
            context: 可选上下文字典。

        Returns:
            StorageDecision；引擎不可用或异常时返回 None。
        """
        self._bump("decide_ops")
        # [FIX-COUNTER-AUDIT] decide_storage内部调用引擎层的classify_layer和summarize
        # (见llm_integration/decision_engine.py:403,420)，这些操作实际发生了分类和摘要，
        # 但不会触发classify_content/generate_summary的计数器。
        # 修复: 在decide_storage中同步bump classify_ops，准确反映分类操作实际发生次数。
        self._bump("classify_ops")
        if self._engine is None:
            self._bump("fallback_ops")
            return None
        try:
            return self._engine.decide_storage(content, context)
        except Exception:
            self._bump("fallback_ops")
            return None

    def classify(self, content: str, context: Optional[dict] = None) -> dict[str, Any]:
        """统一分类入口 — 返回结构化字典 (ILLMStrategy.classify 语义)。  [v10-ready]

        Args:
            content: 待分类内容文本。
            context: 可选上下文字典。

        Returns:
            分类结果字典，至少包含 layer/tags/priority/value_score/
            llm_classified 字段；降级时返回安全默认值。
        """
        fallback = {
            "layer": "working",
            "tags": [],
            "priority": "medium",
            "value_score": 0.5,
            "reason": "",
            "related_concepts": [],
            "confidence": 0.0,
            "llm_classified": False,
        }
        result = self.classify_content(content, context)
        if result is None:
            return fallback
        if hasattr(result, "to_dict"):
            data = result.to_dict()
        elif isinstance(result, dict):
            data = dict(result)
        else:
            return fallback
        data["llm_classified"] = True
        return data

    def get_stats(self) -> dict[str, Any]:
        """获取分类引擎统计。  [v10-ready]"""
        with self._lock:
            return {"is_ready": self.is_ready, **self._stats}
