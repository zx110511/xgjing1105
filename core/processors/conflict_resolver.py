# -*- coding: utf-8-sig -*-
r"""天机冲突消解器 (Conflict Resolver) v1.0
============================================
道四·治理道 · 地煞-11 冲突消解模块

当新写入内容与已有记忆产生语义冲突时，自动判定冲突类型并执行消解策略。

冲突类型:
  - CONTRADICTION: 新旧内容直接矛盾
  - DUPLICATE: 新旧内容高度重复
  - UPDATE: 新内容是旧内容的更新版本
  - COMPLEMENTARY: 新旧内容互补，不冲突

消解策略:
  - KEEP_NEW: 保留新内容，归档旧内容
  - KEEP_OLD: 保留旧内容，拒绝新内容
  - MERGE: 合并新旧内容
  - SPLIT: 两者都保留，标记为不同视角
  - ESCALATE: 升级到人工决策

架构位置: core/processors/conflict_resolver.py
依赖: 无外部依赖 (纯逻辑模块)
"""

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("tianji.conflict_resolver")


class ConflictType(str, Enum):
    """冲突类型枚举"""
    CONTRADICTION = "contradiction"
    DUPLICATE = "duplicate"
    UPDATE = "update"
    COMPLEMENTARY = "complementary"


class ResolutionStrategy(str, Enum):
    """消解策略枚举"""
    KEEP_NEW = "keep_new"
    KEEP_OLD = "keep_old"
    MERGE = "merge"
    SPLIT = "split"
    ESCALATE = "escalate"


@dataclass
class ResolutionVerdict:
    """消解判决结果"""
    conflict_type: ConflictType
    strategy: ResolutionStrategy
    confidence: float = 0.5
    reason: str = ""
    merged_content: Optional[str] = None


class ConflictResolver:
    """冲突消解器 — 语义冲突检测与自动消解

    核心逻辑:
      1. 计算新旧内容的相似度 (字符级n-gram)
      2. 判定冲突类型 (矛盾/重复/更新/互补)
      3. 选择消解策略 (保留/合并/拆分/升级)
      4. 返回消解判决

    使用方式:
      resolver = ConflictResolver()
      verdict = resolver.resolve(new_content="...", existing_content="...")
    """

    # 相似度阈值
    DUPLICATE_THRESHOLD = 0.85
    UPDATE_THRESHOLD = 0.65
    CONTRADICTION_KEYWORDS = {
        "不", "非", "无", "否", "错", "反", "未", "没",
        "not", "no", "never", "false", "wrong", "anti",
        "相反", "否定", "拒绝", "禁止", "排除",
    }

    def detect_conflict_by_content(
        self,
        new_content: str,
        existing_content: str,
    ) -> Optional[ConflictType]:
        """基于内容检测冲突类型

        Args:
            new_content: 新写入内容
            existing_content: 已有内容

        Returns:
            ConflictType 如果存在冲突，否则 None
        """
        if not new_content or not existing_content:
            return None

        similarity = self._calc_similarity(new_content, existing_content)

        if similarity >= self.DUPLICATE_THRESHOLD:
            return ConflictType.DUPLICATE
        elif similarity >= self.UPDATE_THRESHOLD:
            if self._has_contradiction_signals(new_content, existing_content):
                return ConflictType.CONTRADICTION
            return ConflictType.UPDATE
        elif self._has_contradiction_signals(new_content, existing_content):
            return ConflictType.CONTRADICTION

        return None

    def resolve(
        self,
        new_content: str,
        existing_content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ResolutionVerdict:
        """执行冲突检测与消解

        Args:
            new_content: 新写入内容
            existing_content: 已有内容
            metadata: 可选的元数据上下文

        Returns:
            ResolutionVerdict: 消解判决结果
        """
        if not new_content or not existing_content:
            return ResolutionVerdict(
                conflict_type=ConflictType.COMPLEMENTARY,
                strategy=ResolutionStrategy.KEEP_NEW,
                confidence=0.9,
                reason="empty_content_no_conflict",
            )

        similarity = self._calc_similarity(new_content, existing_content)

        # 判定冲突类型
        if similarity >= self.DUPLICATE_THRESHOLD:
            conflict_type = ConflictType.DUPLICATE
            strategy = ResolutionStrategy.KEEP_OLD
            reason = f"high_similarity({similarity:.2f})"
        elif similarity >= self.UPDATE_THRESHOLD:
            if self._has_contradiction_signals(new_content, existing_content):
                conflict_type = ConflictType.CONTRADICTION
                strategy = ResolutionStrategy.ESCALATE
                reason = f"update_with_contradiction({similarity:.2f})"
            else:
                conflict_type = ConflictType.UPDATE
                strategy = ResolutionStrategy.KEEP_NEW
                reason = f"likely_update({similarity:.2f})"
        elif self._has_contradiction_signals(new_content, existing_content):
            conflict_type = ConflictType.CONTRADICTION
            strategy = ResolutionStrategy.SPLIT
            reason = "contradiction_detected"
        else:
            conflict_type = ConflictType.COMPLEMENTARY
            strategy = ResolutionStrategy.KEEP_NEW
            reason = f"low_overlap_complementary({similarity:.2f})"

        confidence = min(1.0, abs(similarity - 0.5) * 2) if similarity > 0.3 else 0.9

        return ResolutionVerdict(
            conflict_type=conflict_type,
            strategy=strategy,
            confidence=round(confidence, 3),
            reason=reason,
        )

    def _calc_similarity(self, text_a: str, text_b: str) -> float:
        """基于字符n-gram的Jaccard相似度"""
        def _ngrams(text: str, n: int = 4) -> set:
            return {text[i:i+n] for i in range(len(text) - n + 1)} if len(text) >= n else {text}

        set_a = _ngrams(text_a.lower().strip())
        set_b = _ngrams(text_b.lower().strip())

        if not set_a or not set_b:
            return 0.0

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _has_contradiction_signals(self, new_content: str, existing_content: str) -> bool:
        """检测矛盾信号"""
        new_words = set(new_content.lower().split())
        existing_words = set(existing_content.lower().split())

        new_negation = new_words & self.CONTRADICTION_KEYWORDS
        existing_negation = existing_words & self.CONTRADICTION_KEYWORDS

        # 一方有否定词而另一方没有，可能是矛盾
        if (new_negation and not existing_negation) or (existing_negation and not new_negation):
            return True

        return False
