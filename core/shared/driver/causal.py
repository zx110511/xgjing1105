# -*- coding: utf-8-sig -*-
r"""
DeepSeek驾驶者 · 因果记录子模块 (Causal Recorder)  [v10-ready]
==============================================================
从 core/deepseek_driver.py 拆分而来 (P1-02)。

职责: OBSERVE闭环 — 行动前后状态快照 → 因果对 → 持久化
  - CausalPair         : 因果对数据模型 (行动→效果)
  - CausalPairRecorder : 因果对记录器 (capture_before/after + 持久化 + 统计)
  - CausalRecorder     : CausalPairRecorder 的简称别名
  - OfflineCatchup     : 离线补课机制 (积压事件/因果对缓冲)

设计约束:
  - 不直接 import core/ 顶层其他模块；持久化目录通过构造函数注入。
  - TianjiEvent 仅用于类型注解(借助 from __future__ import annotations 延迟求值)，
    OfflineCatchup 运行期不依赖其具体类型，保持子模块解耦。
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from .decision import EVOLUTION_EVAL_PROMPT

logger = logging.getLogger("tianji.driver")


@dataclass
class CausalPair:
    action_taken: str
    decision_reason: str
    state_before: dict[str, Any]
    state_after: dict[str, Any]
    delta: dict[str, Any]
    effectiveness: float
    side_effects: list[str]
    timestamp: float = field(default_factory=time.time)
    pair_id: str = ""
    deepseek_evaluated: bool = False
    deepseek_assessment: str = ""

    def __post_init__(self):
        if not self.pair_id:
            raw = f"{self.action_taken}:{self.timestamp}"
            self.pair_id = hashlib.md5(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "action_taken": self.action_taken,
            "decision_reason": self.decision_reason,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "delta": self.delta,
            "effectiveness": self.effectiveness,
            "side_effects": self.side_effects,
            "timestamp": self.timestamp,
            "deepseek_evaluated": self.deepseek_evaluated,
            "deepseek_assessment": self.deepseek_assessment[:500],
        }


class OfflineCatchup:
    """
    离线补课机制 — DeepSeek恢复后处理积压事件  [v10-ready]

    核心逻辑:
      DeepSeek离线期间，事件和因果对被标记为offline
      DeepSeek恢复后，扫描积压数据
      按urgency排序，优先处理高urgency事件
      批量补课，但不影响正常循环
    """

    def __init__(self, max_backlog: int = 500):
        self._backlog_events: list = []
        self._backlog_pairs: list[CausalPair] = []
        self._max_backlog = max_backlog
        self._lock = threading.Lock()
        self._was_online = True
        self._stats = {
            "events_backlogged": 0,
            "pairs_backlogged": 0,
            "catchups_performed": 0,
            "events_processed_in_catchup": 0,
        }

    def mark_offline(self):
        self._was_online = False

    def mark_online(self):
        self._was_online = True

    @property
    def is_online(self) -> bool:
        return self._was_online

    def backlog_event(self, event: Any):
        with self._lock:
            if len(self._backlog_events) >= self._max_backlog:
                self._backlog_events = self._backlog_events[-self._max_backlog // 2 :]
            self._backlog_events.append(event)
            self._stats["events_backlogged"] += 1

    def backlog_pair(self, pair: CausalPair):
        with self._lock:
            if len(self._backlog_pairs) >= self._max_backlog:
                self._backlog_pairs = self._backlog_pairs[-self._max_backlog // 2 :]
            self._backlog_pairs.append(pair)
            self._stats["pairs_backlogged"] += 1

    def has_backlog(self) -> bool:
        with self._lock:
            return len(self._backlog_events) > 0 or len(self._backlog_pairs) > 0

    def drain_backlog(self, max_items: int = 50) -> tuple[list, list[CausalPair]]:
        with self._lock:
            events = self._backlog_events[:max_items]
            pairs = self._backlog_pairs[:max_items]
            self._backlog_events = self._backlog_events[max_items:]
            self._backlog_pairs = self._backlog_pairs[max_items:]
            self._stats["catchups_performed"] += 1
            self._stats["events_processed_in_catchup"] += len(events)
            return events, pairs

    def get_stats(self) -> dict:
        with self._lock:
            return {
                **self._stats,
                "backlog_events": len(self._backlog_events),
                "backlog_pairs": len(self._backlog_pairs),
                "is_online": self._was_online,
            }


class CausalPairRecorder:
    """
    因果对记录器 — OBSERVE核心  [v10-ready]

    每次行动前后记录系统状态快照，形成"行动→效果"的因果对。
    这些因果对是LEARN和EVOLVE的原料。
    """

    def __init__(self, max_pairs: int = 5000, persist_dir: Path | None = None):
        self._pairs: list[CausalPair] = []
        self._max_pairs = max_pairs
        self._persist_dir = persist_dir
        self._lock = threading.Lock()
        self._snapshot_before: dict | None = None
        self._current_action: str | None = None
        self._current_reason: str | None = None
        self._stats = {
            "pairs_recorded": 0,
            "positive_outcomes": 0,
            "negative_outcomes": 0,
            "neutral_outcomes": 0,
            "deepseek_evaluations": 0,
        }

    def capture_before(
        self, action: str, reason: str, memory_engine=None
    ) -> dict[str, Any]:
        """行动前快照 — 记录当前系统状态"""
        snapshot = {
            "timestamp": time.time(),
            "action": action,
            "layer_counts": {},
            "total_entries": 0,
            "avg_value_scores": {},
        }

        if memory_engine and hasattr(memory_engine, "_layers"):
            try:
                for layer_name, entries in memory_engine._layers.items():
                    snapshot["layer_counts"][layer_name] = len(entries)
                    snapshot["total_entries"] += len(entries)
                    if entries:
                        scores = [e.value_score() for e in entries.values()]
                        snapshot["avg_value_scores"][layer_name] = round(
                            sum(scores) / len(scores), 4
                        )
            except Exception:
                pass

        self._snapshot_before = snapshot
        self._current_action = action
        self._current_reason = reason
        return snapshot

    def capture_after(
        self, memory_engine=None, side_effects: list[str] = None
    ) -> CausalPair | None:
        """行动后快照 — 记录效果并形成因果对"""
        if self._snapshot_before is None:
            return None

        snapshot_after = {
            "timestamp": time.time(),
            "layer_counts": {},
            "total_entries": 0,
            "avg_value_scores": {},
        }

        if memory_engine and hasattr(memory_engine, "_layers"):
            try:
                for layer_name, entries in memory_engine._layers.items():
                    snapshot_after["layer_counts"][layer_name] = len(entries)
                    snapshot_after["total_entries"] += len(entries)
                    if entries:
                        scores = [e.value_score() for e in entries.values()]
                        snapshot_after["avg_value_scores"][layer_name] = round(
                            sum(scores) / len(scores), 4
                        )
            except Exception:
                pass

        delta = self._compute_delta(self._snapshot_before, snapshot_after)
        effectiveness = self._compute_effectiveness(delta)

        pair = CausalPair(
            action_taken=self._current_action or "unknown",
            decision_reason=self._current_reason or "",
            state_before=self._snapshot_before,
            state_after=snapshot_after,
            delta=delta,
            effectiveness=effectiveness,
            side_effects=side_effects or [],
        )

        with self._lock:
            self._pairs.append(pair)
            if len(self._pairs) > self._max_pairs:
                self._pairs = self._pairs[-self._max_pairs // 2 :]
            self._stats["pairs_recorded"] += 1

            if effectiveness > 0.3:
                self._stats["positive_outcomes"] += 1
            elif effectiveness < -0.1:
                self._stats["negative_outcomes"] += 1
            else:
                self._stats["neutral_outcomes"] += 1

        self._snapshot_before = None
        self._current_action = None
        self._current_reason = None

        if self._persist_dir:
            self._persist_pair(pair)

        return pair

    def _compute_delta(self, before: dict, after: dict) -> dict[str, Any]:
        delta: dict[str, Any] = {"layer_deltas": {}, "total_delta": 0}
        before_counts = before.get("layer_counts", {})
        after_counts = after.get("layer_counts", {})
        all_layers = set(list(before_counts.keys()) + list(after_counts.keys()))

        for layer in all_layers:
            bc = before_counts.get(layer, 0)
            ac = after_counts.get(layer, 0)
            delta["layer_deltas"][layer] = ac - bc
            delta["total_delta"] += ac - bc

        before_scores = before.get("avg_value_scores", {})
        after_scores = after.get("avg_value_scores", {})
        delta["value_score_deltas"] = {}
        for layer in set(list(before_scores.keys()) + list(after_scores.keys())):
            bs = before_scores.get(layer, 0)
            as_ = after_scores.get(layer, 0)
            delta["value_score_deltas"][layer] = round(as_ - bs, 4)

        return delta

    def _compute_effectiveness(self, delta: dict) -> float:
        score_deltas = delta.get("value_score_deltas", {})
        if not score_deltas:
            total_delta = delta.get("total_delta", 0)
            return min(1.0, max(-1.0, total_delta * 0.1))

        positive = sum(v for v in score_deltas.values() if v > 0)
        negative = sum(abs(v) for v in score_deltas.values() if v < 0)
        total = positive + negative

        if total == 0:
            return 0.0
        return round((positive - negative) / total, 4)

    def evaluate_with_deepseek(
        self, pair: CausalPair, decision_engine=None
    ) -> CausalPair:
        """DeepSeek评估因果对 — 判断行动是否有效，为什么"""
        if not decision_engine or not decision_engine.is_ready:
            return pair

        try:
            prompt = f"""请评估以下行动的效果:

行动: {pair.action_taken}
决策原因: {pair.decision_reason}
效果指标变化: {json.dumps(pair.delta, ensure_ascii=False)}
综合效果评分: {pair.effectiveness}
副作用: {pair.side_effects}

请判断:
1. 这个行动是否达到了预期效果?
2. 效果好/差的原因是什么?
3. 下次遇到类似情况，应该如何改进?

返回JSON:
{{"effective": true, "reason": "...", "improvement": "..."}}"""

            result = decision_engine.client.chat_sync(prompt, EVOLUTION_EVAL_PROMPT)
            pair.deepseek_evaluated = True
            pair.deepseek_assessment = json.dumps(result, ensure_ascii=False)[:500]
            self._stats["deepseek_evaluations"] += 1
        except Exception as e:
            logger.warning(f"DeepSeek causal eval failed: {e}")

        return pair

    def get_recent_pairs(self, limit: int = 50) -> list[CausalPair]:
        with self._lock:
            return self._pairs[-limit:]

    def get_effective_pairs(self, min_effectiveness: float = 0.3) -> list[CausalPair]:
        with self._lock:
            return [p for p in self._pairs if p.effectiveness >= min_effectiveness]

    def get_ineffective_pairs(
        self, max_effectiveness: float = -0.1
    ) -> list[CausalPair]:
        with self._lock:
            return [p for p in self._pairs if p.effectiveness <= max_effectiveness]

    def get_action_effectiveness_summary(self) -> dict[str, dict]:
        summary: dict[str, dict] = {}
        with self._lock:
            for pair in self._pairs:
                action = pair.action_taken
                if action not in summary:
                    summary[action] = {
                        "count": 0,
                        "avg_effectiveness": 0.0,
                        "positive_rate": 0.0,
                    }
                entry = summary[action]
                entry["count"] += 1
                old_avg = entry["avg_effectiveness"]
                entry["avg_effectiveness"] = round(
                    (old_avg * (entry["count"] - 1) + pair.effectiveness)
                    / entry["count"],
                    4,
                )
                if pair.effectiveness > 0.3:
                    entry["positive_rate"] = round(
                        (entry["positive_rate"] * (entry["count"] - 1) + 1)
                        / entry["count"],
                        4,
                    )

        return summary

    def _persist_pair(self, pair: CausalPair):
        try:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            pair_file = self._persist_dir / f"causal_{pair.pair_id}.json"
            pair_file.write_text(
                json.dumps(pair.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def get_stats(self) -> dict:
        with self._lock:
            return {
                **self._stats,
                "total_pairs": len(self._pairs),
            }


# 简称别名 — 与任务命名约定 (CausalRecorder) 对齐  [v10-ready]
CausalRecorder = CausalPairRecorder
