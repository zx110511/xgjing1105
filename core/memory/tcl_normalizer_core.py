# -*- coding: utf-8-sig -*-
"""TCL规范化 — 规范化器

从 tcl_normalizer.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-tcl-core-001] 延迟类型注解求值

import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field


from typing import Dict

# [FIX-tcl-core-002] 显式导入 NormalizeResult/TermEntry (避免 NameError)
from .tcl_models import NormalizeResult, TermEntry


class TCLNormalizer:
    """TCL归一化引擎 — Level 2实现"""

    def __init__(self, store: TerminologyStore, llm_bridge=None):
        self._store = store
        self._llm_bridge = llm_bridge
        self._stats = {
            "total_normalizations": 0,
            "exact_hits": 0,
            "alias_hits": 0,
            "fuzzy_hits": 0,
            "llm_hits": 0,
            "misses": 0,
        }

    def normalize(
        self, text: str, context: str = "", use_llm: bool = True
    ) -> NormalizeResult:
        """
        归一化文本中的术语

        Args:
            text: 待归一化的文本(可以是单词、短语或句子)
            context: 上下文(用于消歧)
            use_llm: 是否允许LLM语义匹配（Step 4），批量操作时应设为False

        Returns:
            NormalizeResult: 归一化结果
        """
        start = time.perf_counter()
        self._stats["total_normalizations"] += 1

        # Step 1: 精确匹配(规范术语名)
        result = self._exact_match(text)
        if result:
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result

        # Step 2: 别名匹配
        result = self._alias_match(text)
        if result:
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result

        # Step 3: 模糊匹配(子串/缩写)
        result = self._fuzzy_match(text)
        if result:
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result

        # Step 4: LLM语义归一化(可选，Level 2+) — 仅当use_llm=True且llm_bridge可用
        if use_llm and self._llm_bridge:
            result = self._llm_match(text, context)
            if result:
                result.latency_ms = (time.perf_counter() - start) * 1000
                return result

        # 未命中
        self._stats["misses"] += 1
        return NormalizeResult(
            original=text,
            confidence=0.0,
            method="miss",
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    def normalize_content(
        self, content: str, context: str = "", use_llm: bool = True
    ) -> tuple[str, list[str]]:
        """
        归一化内容中的所有术语

        Args:
            content: 待归一化的完整内容
            context: 上下文
            use_llm: 是否允许LLM语义匹配，批量操作时应设为False

        Returns:
            (归一化后的内容, canonical_ids列表)
        """
        canonical_ids: list[str] = []
        # 提取候选术语(中文词组 + 英文单词/缩写)
        candidates = self._extract_candidates(content)

        for candidate in candidates:
            result = self.normalize(candidate, context, use_llm=use_llm)
            if result.canonical_id and result.confidence >= 0.7:
                canonical_ids.append(result.canonical_id)
                self._store.increment_frequency(result.canonical_id)

        return content, list(set(canonical_ids))

    def _exact_match(self, text: str) -> NormalizeResult | None:
        """精确匹配规范术语名"""
        entry = self._store.lookup_by_term(text)
        if entry:
            self._stats["exact_hits"] += 1
            return NormalizeResult(
                original=text,
                canonical_id=entry.canonical_id,
                canonical_term=entry.canonical_term,
                confidence=1.0,
                method="exact",
            )
        return None

    def _alias_match(self, text: str) -> NormalizeResult | None:
        """别名匹配"""
        entry = self._store.lookup_by_alias(text)
        if entry:
            self._stats["alias_hits"] += 1
            # 别名匹配置信度根据别名位置递减
            alias_idx = -1
            for i, alias in enumerate(entry.aliases):
                if alias.lower() == text.lower():
                    alias_idx = i
                    break
            confidence = max(0.95 - alias_idx * 0.05, 0.7)
            return NormalizeResult(
                original=text,
                canonical_id=entry.canonical_id,
                canonical_term=entry.canonical_term,
                confidence=confidence,
                method="alias",
            )
        return None

    def _fuzzy_match(self, text: str) -> NormalizeResult | None:
        """模糊匹配(子串包含/缩写展开)"""
        text_lower = text.lower()
        best_entry: TermEntry | None = None
        best_score = 0.0

        for entry in self._store.get_all_terms():
            # 子串匹配: "ICME引擎" 包含 "ICME"
            if text_lower in entry.canonical_term.lower():
                score = len(text) / max(len(entry.canonical_term), 1)
                if score > best_score:
                    best_score = score
                    best_entry = entry
            # 反向子串: "引擎" in "ICME引擎"
            elif entry.canonical_term.lower() in text_lower:
                score = len(entry.canonical_term) / max(len(text), 1) * 0.8
                if score > best_score:
                    best_score = score
                    best_entry = entry
            # 缩写匹配: "ICME" 匹配 "ICME六层记忆架构"
            for alias in entry.aliases:
                if alias.lower() in text_lower or text_lower in alias.lower():
                    score = 0.75
                    if score > best_score:
                        best_score = score
                        best_entry = entry

        if best_entry and best_score >= 0.5:
            self._stats["fuzzy_hits"] += 1
            return NormalizeResult(
                original=text,
                canonical_id=best_entry.canonical_id,
                canonical_term=best_entry.canonical_term,
                confidence=best_score,
                method="fuzzy",
            )
        return None

    def _llm_match(self, text: str, context: str) -> NormalizeResult | None:
        """LLM语义归一化(通过DeepSeek)"""
        if not self._llm_bridge:
            return None
        try:
            all_terms = self._store.get_all_terms()
            if not all_terms:
                return None
            term_list = [
                f"- {e.canonical_term} ({e.canonical_id})" for e in all_terms[:50]
            ]
            prompt = (
                f'给定文本片段"{text}"，上下文"{context[:200]}"，\n'
                f"判断它是否等价于以下某个规范术语(只返回最匹配的canonical_id，无匹配返回NONE):\n"
                + "\n".join(term_list)
            )
            # 调用LLM桥接(如果可用)
            if hasattr(self._llm_bridge, "expand_query"):
                expansions = self._llm_bridge.expand_query(text)
                for exp in expansions:
                    entry = self._store.lookup_by_alias(exp)
                    if entry:
                        self._stats["llm_hits"] += 1
                        return NormalizeResult(
                            original=text,
                            canonical_id=entry.canonical_id,
                            canonical_term=entry.canonical_term,
                            confidence=0.8,
                            method="llm",
                        )
        except Exception as e:
            logger.warning(f"[TCL] LLM match failed: {e}")
        return None

    def _extract_candidates(self, content: str) -> list[str]:
        """从内容中提取候选术语（重叠匹配，确保子串不遗漏）"""
        candidates: list[str] = []
        # 英文术语(2+字符的连续英文，非重叠已足够)
        en_terms = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{1,}", content)
        candidates.extend(en_terms)
        # 中文术语: 使用前瞻断言实现重叠匹配，确保像"天机记忆引擎"这样的子串不被吞噬
        # (?=([\u4e00-\u9fff]{2,8})) 在每个位置前瞻捕获2-8个连续中文
        cn_terms = re.findall(r"(?=([\u4e00-\u9fff]{2,8}))", content)
        candidates.extend(cn_terms)
        # 去重并按长度降序(长术语优先匹配)
        seen: set[str] = set()
        unique = []
        for c in sorted(candidates, key=len, reverse=True):
            if c.lower() not in seen:
                seen.add(c.lower())
                unique.append(c)
        return unique

    def get_stats(self) -> dict:
        """获取归一化统计"""
        total = max(self._stats["total_normalizations"], 1)
        return {
            **self._stats,
            "hit_rate": round(
                (
                    self._stats["exact_hits"]
                    + self._stats["alias_hits"]
                    + self._stats["fuzzy_hits"]
                    + self._stats["llm_hits"]
                )
                / total,
                3,
            ),
        }


# ---------------------------------------------------------------------------
# 消歧引擎
# ---------------------------------------------------------------------------




__all__ = ["TCLNormalizer"]
