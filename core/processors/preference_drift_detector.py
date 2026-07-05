# -*- coding: utf-8-sig -*-
r"""天机偏好漂移检测器 (Preference Drift Detector) v1.0
======================================================
道四·治理道 · 地煞-12 偏好漂移检测模块

持续追踪用户偏好/标签/主题的分布变化，检测语义漂移信号。

漂移类型:
  - GRADUAL: 渐进式漂移 (偏好缓慢转移)
  - SUDDEN: 突变式漂移 (偏好急剧变化)
  - CYCLICAL: 周期式漂移 (偏好周期性波动)
  - CONVERGENT: 收敛式漂移 (偏好趋于稳定)

检测机制:
  - 滑动窗口统计标签/主题频率分布
  - 计算相邻窗口间的分布差异 (KL散度近似)
  - 超过阈值时生成漂移信号

架构位置: core/processors/preference_drift_detector.py
依赖: 无外部依赖 (纯逻辑模块)
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("tianji.preference_drift")


class DriftType(str, Enum):
    """漂移类型枚举"""
    GRADUAL = "gradual"
    SUDDEN = "sudden"
    CYCLICAL = "cyclical"
    CONVERGENT = "convergent"


@dataclass
class DriftSignal:
    """漂移信号"""
    topic: str
    drift_type: DriftType
    delta: float
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)


class PreferenceDriftDetector:
    """偏好漂移检测器 — 语义漂移信号检测

    核心逻辑:
      1. 维护滑动窗口内的标签/主题频率分布
      2. update() 记录新的观察值
      3. detect() 计算分布变化并生成漂移信号
      4. 支持多种漂移类型的识别

    使用方式:
      detector = PreferenceDriftDetector(window_size=100, threshold=0.3)
      detector.update("python", 1.0)
      detector.update("rust", 1.0)
      signals = detector.detect()
    """

    def __init__(
        self,
        window_size: int = 100,
        threshold: float = 0.3,
        min_observations: int = 10,
    ):
        self._window_size = window_size
        self._threshold = threshold
        self._min_observations = min_observations

        # 当前窗口和前一窗口的频率分布
        self._current_window: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._previous_dist: dict[str, float] = {}
        self._total_updates: int = 0
        self._history: list[dict[str, float]] = []

    def update(self, topic: str, weight: float = 1.0) -> None:
        """记录新的观察值

        Args:
            topic: 标签/主题名称
            weight: 观察权重
        """
        now = time.time()
        self._current_window[topic].append((now, weight))
        self._total_updates += 1

        # 裁剪超出窗口的旧记录
        cutoff = now - self._window_size * 60  # window_size分钟
        for topic_key in self._current_window:
            self._current_window[topic_key] = [
                (ts, w) for ts, w in self._current_window[topic_key] if ts >= cutoff
            ]

    def detect(self) -> list[DriftSignal]:
        """检测漂移信号

        Returns:
            漂移信号列表，按delta绝对值降序排列
        """
        if self._total_updates < self._min_observations:
            return []

        current_dist = self._get_current_distribution()
        if not current_dist:
            return []

        signals = []
        all_topics = set(current_dist.keys()) | set(self._previous_dist.keys())

        for topic in all_topics:
            current_freq = current_dist.get(topic, 0.0)
            previous_freq = self._previous_dist.get(topic, 0.0)
            delta = current_freq - previous_freq

            if abs(delta) >= self._threshold:
                drift_type = self._classify_drift(topic, delta, current_freq, previous_freq)
                signals.append(DriftSignal(
                    topic=topic,
                    drift_type=drift_type,
                    delta=round(delta, 4),
                    confidence=min(1.0, abs(delta) * 2),
                ))

        # 更新前一窗口分布
        self._previous_dist = dict(current_dist)
        self._history.append(current_dist)
        if len(self._history) > 10:
            self._history = self._history[-10:]

        signals.sort(key=lambda s: abs(s.delta), reverse=True)
        return signals

    def _get_current_distribution(self) -> dict[str, float]:
        """计算当前窗口的频率分布"""
        total_weight = 0.0
        topic_weights: dict[str, float] = defaultdict(float)

        for topic, records in self._current_window.items():
            weight = sum(w for _, w in records)
            topic_weights[topic] = weight
            total_weight += weight

        if total_weight <= 0:
            return {}

        return {t: w / total_weight for t, w in topic_weights.items()}

    def _classify_drift(
        self,
        topic: str,
        delta: float,
        current_freq: float,
        previous_freq: float,
    ) -> DriftType:
        """分类漂移类型"""
        # 检查历史模式
        if len(self._history) >= 3:
            # 检查周期性
            freqs = [h.get(topic, 0.0) for h in self._history[-3:]]
            if len(freqs) >= 3:
                # 频率交替升降 → 周期性
                if (freqs[0] < freqs[1] > freqs[2]) or (freqs[0] > freqs[1] < freqs[2]):
                    return DriftType.CYCLICAL

        # 突变检测
        if abs(delta) >= self._threshold * 2:
            return DriftType.SUDDEN

        # 收敛检测
        if current_freq > 0 and previous_freq > 0:
            ratio = current_freq / previous_freq if previous_freq > 0 else float('inf')
            if 0.9 <= ratio <= 1.1:
                return DriftType.CONVERGENT

        return DriftType.GRADUAL

    def get_stats(self) -> dict[str, Any]:
        """获取检测器统计信息"""
        return {
            "total_updates": self._total_updates,
            "tracked_topics": len(self._current_window),
            "window_size": self._window_size,
            "threshold": self._threshold,
            "history_depth": len(self._history),
        }
