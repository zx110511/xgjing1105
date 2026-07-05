# -*- coding: utf-8-sig -*-
"""天机v10.0.1 门禁反向过滤器 NoiseFilter  [v10-ready]

三问推演 Q3 — 不要元素的反向过滤:
    冗余(redundancy) / 矛盾(conflict) / 过期(staleness) / 噪声(noise)

从 core/quality_gate.py 提取的反向过滤逻辑，作为独立可复用组件。
本地实现，被 LocalGateStrategy 与兼容层 QualityGate 共同委托使用。

架构定位: core/gate/ 门禁策略子包 — 反向过滤算法层
版本: 1.0.0
"""
from __future__ import annotations

import time
from typing import Any, List, Optional

try:
    from ..config import QualityGateConfig, DEFAULT_CONFIG
except ImportError:  # pragma: no cover - 兼容直接执行
    from core.shared.config import QualityGateConfig, DEFAULT_CONFIG  # type: ignore


def _resolve_config(config: Any | None) -> Any:
    """解析门禁配置对象  [v10-ready]"""
    cfg = config or DEFAULT_CONFIG.quality_gate
    if hasattr(cfg, "quality_gate"):
        cfg = cfg.quality_gate
    return cfg


def has_semantic_overlap(text1: str, text2: str) -> bool:
    """判断两段文本是否存在语义重叠 (词级 Jaccard 近似)  [v10-ready]"""
    words1 = set(text1.split())
    words2 = set(text2.split())
    if not words1 or not words2:
        return False
    overlap = len(words1 & words2)
    return overlap >= min(2, len(words1) * 0.2)


def longest_common_substring(s1: str, s2: str) -> int:
    """最长公共子串长度 (动态规划, O(mn) 滚动数组)  [v10-ready]"""
    if not s1 or not s2:
        return 0
    m, n = len(s1), len(s2)
    max_len = 0
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                curr[j] = prev[j - 1] + 1
                max_len = max(max_len, curr[j])
        prev = curr
    return max_len


def char_ngrams(text: str, n: int = 4) -> set:
    """字符级 n-gram 集合 (用于去重相似度)  [v10-ready]"""
    if len(text) < n:
        return {text}
    return {text[i:i + n] for i in range(len(text) - n + 1)}


class NoiseFilter:
    """门禁反向过滤器 — 冗余/矛盾/过期/噪声 四类检测  [v10-ready]

    本地实现: 进程内基于规则与字符串相似度的检测。
    远程实现: 灵境侧可由集中式过滤服务替换(见 RemoteGateStrategy)。

    每个检测方法返回结构化字典 (是否命中 + 评分 + 原因)，
    filter() 聚合四类检测，供 LocalGateStrategy 直接消费。
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        """初始化反向过滤器  [v10-ready]

        Args:
            config: QualityGateConfig 或含 quality_gate 属性的配置对象。
        """
        self.config = _resolve_config(config)

    # ------------------------------------------------------------------
    # 噪声检测
    # ------------------------------------------------------------------
    def check_noise(self, content: str) -> dict:
        """噪声检测 — 空内容/纯噪声模式/重复字符/无意义符号  [v10-ready]

        Args:
            content: 待检测文本。

        Returns:
            {is_noise, score, reason} 字典。
        """
        stripped = content.strip()
        if not stripped:
            return {"is_noise": True, "score": 0.0, "reason": "空内容"}
        for pattern in getattr(self.config, "noise_patterns", []):
            if stripped == pattern:
                return {"is_noise": True, "score": 0.0, "reason": f"纯噪声模式: '{pattern}'"}
        if len(set(stripped)) <= 2 and len(stripped) <= 10:
            return {"is_noise": True, "score": 0.0, "reason": "重复字符噪声"}
        if stripped in ("...", "---", "===", "***", "。。。", "，，，"):
            return {"is_noise": True, "score": 0.0, "reason": "符号噪声"}
        has_meaningful = any(
            c for c in stripped if "\u4e00" <= c <= "\u9fff" or c.isalpha()
        )
        if not has_meaningful:
            return {"is_noise": True, "score": 0.1, "reason": "无有意义字符"}
        return {"is_noise": False, "score": 0.9}

    # ------------------------------------------------------------------
    # 冗余(重复)检测
    # ------------------------------------------------------------------
    def check_duplicate(self, content: str, existing_entries: Optional[List]) -> dict:
        """冗余检测 — Jaccard + 最长公共子串双指标  [v10-ready]

        Args:
            content: 待检测文本。
            existing_entries: 现有记忆条目 (对象或字典)。

        Returns:
            {is_duplicate, similarity, matched_ids} 字典。
        """
        if not existing_entries:
            return {"is_duplicate": False, "similarity": 0.0, "matched_ids": []}
        content_words = set(content)
        best_similarity = 0.0
        best_id = None
        for entry in existing_entries:
            existing_content = (
                entry.content if hasattr(entry, "content") else entry.get("content", "")
            )
            existing_words = set(existing_content)
            if not content_words or not existing_words:
                continue
            intersection = content_words & existing_words
            union = content_words | existing_words
            jaccard = len(intersection) / len(union) if union else 0
            long_substr = longest_common_substring(content, existing_content)
            substr_ratio = long_substr / max(len(content), 1)
            similarity = max(jaccard, substr_ratio)
            if similarity > best_similarity:
                best_similarity = similarity
                best_id = entry.id if hasattr(entry, "id") else entry.get("id")
        threshold = getattr(self.config, "max_similarity_for_duplicate", 0.85)
        is_dup = best_similarity >= threshold
        return {
            "is_duplicate": is_dup,
            "similarity": round(best_similarity, 4),
            "matched_ids": [best_id] if best_id else [],
        }

    # ------------------------------------------------------------------
    # 矛盾检测
    # ------------------------------------------------------------------
    def check_conflict(
        self,
        content: str,
        existing_entries: Optional[List],
        conflict_resolver: Optional[Any] = None,
    ) -> dict:
        """矛盾检测 — 优先用 ConflictResolver，回退否定词启发式  [v10-ready]

        Args:
            content: 待检测文本。
            existing_entries: 现有记忆条目。
            conflict_resolver: 可选的冲突消解器实例。

        Returns:
            {has_conflict, reason, matched_ids} 字典。
        """
        if not getattr(self.config, "conflict_detection_enabled", True) or not existing_entries:
            return {"has_conflict": False, "reason": "", "matched_ids": []}

        if conflict_resolver is not None:
            conflicts = []
            last_conflict_type = None
            for entry in existing_entries[:50]:
                conflict_type = conflict_resolver.detect_conflict_by_content(
                    content,
                    entry.content if hasattr(entry, "content") else entry.get("content", ""),
                )
                if conflict_type is not None:
                    entry_id = entry.id if hasattr(entry, "id") else entry.get("id", "")
                    conflicts.append(entry_id)
                    last_conflict_type = conflict_type
            if conflicts:
                ct_label = (
                    last_conflict_type.value
                    if last_conflict_type and hasattr(last_conflict_type, "value")
                    else "未知"
                )
                return {
                    "has_conflict": True,
                    "reason": f"与{len(conflicts)}条记忆存在{ct_label}冲突",
                    "matched_ids": conflicts[:5],
                }
            return {"has_conflict": False, "reason": "", "matched_ids": []}

        negation_words = ["不", "没有", "错误", "推翻", "废弃", "不再", "删除", "移除", "替换"]
        content_has_negation = any(w in content for w in negation_words)
        if not content_has_negation:
            return {"has_conflict": False, "reason": "", "matched_ids": []}
        conflicts = []
        for entry in existing_entries[:50]:
            existing_content = (
                entry.content if hasattr(entry, "content") else entry.get("content", "")
            )
            if has_semantic_overlap(content, existing_content) and len(content) > 30:
                entry_id = entry.id if hasattr(entry, "id") else entry.get("id", "")
                conflicts.append(entry_id)
        max_retention = getattr(self.config, "max_conflict_retention", 5)
        if len(conflicts) > max_retention:
            return {
                "has_conflict": True,
                "reason": f"超过{max_retention}个冲突信号",
                "matched_ids": conflicts[:5],
            }
        if conflicts:
            return {
                "has_conflict": True,
                "reason": f"与{len(conflicts)}条记忆存在语义冲突",
                "matched_ids": conflicts[:3],
            }
        return {"has_conflict": False, "reason": "", "matched_ids": []}

    # ------------------------------------------------------------------
    # 过期检测
    # ------------------------------------------------------------------
    def check_staleness(self, content: str, metadata: Optional[dict] = None) -> dict:
        """过期检测 — 基于 metadata 时间戳与配置最大寿命  [v10-ready]

        Args:
            content: 待检测文本 (保留以统一签名)。
            metadata: 含 timestamp/created_at 的元数据。

        Returns:
            {is_stale, score, reason} 字典；未配置寿命时恒不过期。
        """
        md = metadata or {}
        ts = md.get("timestamp") or md.get("created_at")
        max_age = getattr(self.config, "max_age_seconds", 0) or 0
        if not ts or not max_age:
            return {"is_stale": False, "score": 1.0, "reason": ""}
        try:
            age = time.time() - float(ts)
        except (ValueError, TypeError):
            return {"is_stale": False, "score": 1.0, "reason": ""}
        if age > max_age:
            return {
                "is_stale": True,
                "score": 0.0,
                "reason": f"内容过期({int(age)}s>{int(max_age)}s)",
            }
        return {"is_stale": False, "score": round(1.0 - age / max_age, 4), "reason": ""}

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    def guess_upstream_topic(self, content: str) -> str:
        """猜测上游主题锚点 (因果指示词截取)  [v10-ready]"""
        indicators = ["因为", "基于", "根据", "参考", "参见", "关于", "针对"]
        for ind in indicators:
            if ind in content:
                idx = content.index(ind)
                end = min(idx + 30, len(content))
                return content[idx:end].strip()
        return content[:50] + "..."

    @staticmethod
    def char_ngrams(text: str, n: int = 4) -> set:
        """字符级 n-gram 集合 (静态委托)  [v10-ready]"""
        return char_ngrams(text, n)

    @staticmethod
    def longest_common_substring(s1: str, s2: str) -> int:
        """最长公共子串长度 (静态委托)  [v10-ready]"""
        return longest_common_substring(s1, s2)

    @staticmethod
    def has_semantic_overlap(text1: str, text2: str) -> bool:
        """语义重叠判定 (静态委托)  [v10-ready]"""
        return has_semantic_overlap(text1, text2)

    # ------------------------------------------------------------------
    # 聚合过滤
    # ------------------------------------------------------------------
    def filter(
        self,
        content: str,
        metadata: Optional[dict] = None,
        existing_entries: Optional[List] = None,
        conflict_resolver: Optional[Any] = None,
    ) -> dict:
        """聚合四类反向过滤，输出统一过滤结论  [v10-ready]

        Args:
            content: 待检测文本。
            metadata: 元数据 (可含 existing_entries)。
            existing_entries: 现有记忆条目；缺省时从 metadata 读取。
            conflict_resolver: 可选冲突消解器。

        Returns:
            {reject, conflict, stale, score, reason, conflicts_with, dimensions}。
        """
        metadata = metadata or {}
        if existing_entries is None:
            existing_entries = metadata.get("existing_entries")

        noise = self.check_noise(content)
        if noise["is_noise"]:
            return {
                "reject": True,
                "conflict": False,
                "stale": False,
                "score": noise["score"],
                "reason": f"噪声内容被拒绝: {noise['reason']}",
                "conflicts_with": [],
                "dimensions": {"noise": noise["score"]},
            }

        dup = self.check_duplicate(content, existing_entries)
        if dup["is_duplicate"]:
            return {
                "reject": True,
                "conflict": False,
                "stale": False,
                "score": dup["similarity"],
                "reason": f"与已有记忆高度重复 (相似度{dup['similarity']:.2f})",
                "conflicts_with": dup.get("matched_ids", []),
                "dimensions": {"redundancy": dup["similarity"]},
            }

        stale = self.check_staleness(content, metadata)
        if stale["is_stale"]:
            return {
                "reject": True,
                "conflict": False,
                "stale": True,
                "score": stale["score"],
                "reason": f"内容过期被拒绝: {stale['reason']}",
                "conflicts_with": [],
                "dimensions": {"staleness": stale["score"]},
            }

        conflict = self.check_conflict(content, existing_entries, conflict_resolver)
        if conflict["has_conflict"]:
            return {
                "reject": False,
                "conflict": True,
                "stale": False,
                "score": 0.5,
                "reason": f"检测到潜在知识冲突: {conflict['reason']}",
                "conflicts_with": conflict.get("matched_ids", []),
                "dimensions": {"conflict": 0.5},
            }

        return {
            "reject": False,
            "conflict": False,
            "stale": False,
            "score": 1.0,
            "reason": "通过反向过滤",
            "conflicts_with": [],
            "dimensions": {
                "noise": noise["score"],
                "redundancy": dup["similarity"],
                "staleness": stale["score"],
            },
        }
