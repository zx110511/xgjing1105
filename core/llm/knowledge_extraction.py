# -*- coding: utf-8-sig -*-
"""知识提取引擎 — KnowledgeExtractionEngine  [v10-ready]

从 core/llm_bridge.py 提取的知识提取逻辑：
    - extract_knowledge : 从内容提取知识三元组 (委托 MemoryDecisionEngine.extract_knowledge)

设计原则:
    - 降级友好: 决策引擎不可用 (engine=None) 或调用异常时返回空列表而非异常
    - 线程安全: 使用 threading.RLock 保护内部统计
    - 零阻塞感知: 任意底层异常均被吞掉并回退

架构定位: core/llm/ LLM策略子包 — 知识提取能力单元
版本: 1.0.0
"""
from __future__ import annotations

import threading
from typing import Any, Optional


class KnowledgeExtractionEngine:
    """知识提取引擎  [v10-ready]

    包装 MemoryDecisionEngine 的知识三元组提取能力，对外提供降级友好的同步接口。
    当底层决策引擎不可用时，所有方法返回安全的空结果。
    """

    def __init__(self, engine: Optional[Any] = None):
        """初始化知识提取引擎。

        Args:
            engine: MemoryDecisionEngine 实例；为 None 时进入降级模式。
        """
        self._engine = engine
        self._lock = threading.RLock()
        self._stats = {
            "extract_ops": 0,
            "triples_extracted": 0,
            "fallback_ops": 0,
        }

    @property
    def is_ready(self) -> bool:
        """决策引擎是否就绪。  [v10-ready]"""
        return self._engine is not None

    def _bump(self, key: str, n: int = 1) -> None:
        with self._lock:
            self._stats[key] = self._stats.get(key, 0) + n

    def extract_knowledge(self, content: str) -> list[dict[str, Any]]:
        """从内容提取知识三元组。  [v10-ready]

        Args:
            content: 待提取内容文本。

        Returns:
            三元组字典列表 (subject/relation/object/confidence)；
            引擎不可用或异常时返回空列表。
        """
        self._bump("extract_ops")
        if self._engine is None:
            self._bump("fallback_ops")
            return []
        try:
            result = self._engine.extract_knowledge(content)
            if isinstance(result, list):
                self._bump("triples_extracted", len(result))
                return result
            return []
        except Exception:
            self._bump("fallback_ops")
            return []

    def get_stats(self) -> dict[str, Any]:
        """获取知识提取引擎统计。  [v10-ready]"""
        with self._lock:
            return {"is_ready": self.is_ready, **self._stats}
