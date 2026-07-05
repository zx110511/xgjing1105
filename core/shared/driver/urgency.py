# -*- coding: utf-8-sig -*-
r"""
DeepSeek驾驶者 · 紧迫度子模块 (Urgency & Watchdog)  [v10-ready]
==============================================================
从 core/deepseek_driver.py 拆分而来 (P1-02)。

职责: 异常感知触发 + 进化效果验证
  - UrgencyAccumulator : 紧迫度累积器 (因果对喂入 → 衰减 → 触发判定)
  - EffectWatchdog     : 效果看门狗 (EVOLVE规则修改后自动验证/回滚)

设计约束:
  - 不直接 import core/ 顶层其他模块；CausalPair 仅用于类型注解(延迟求值)。
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from typing import Any


class UrgencyAccumulator:
    """
    异常感知触发器 — 让DeepSeek自己决定何时主动思考  [v10-ready]

    核心逻辑: 每个因果对写入时计算urgency_score
      effectiveness < -0.3 → urgency += 3 (严重负面)
      effectiveness < -0.1 → urgency += 1 (轻微负面)
      fallback行动        → urgency += 2 (降级决策)
      连续2次负面         → urgency += 5 (趋势恶化)
      urgency > 2.5       → 立即触发循环B (不等5分钟)
      urgency > 7.0       → 立即触发循环C (不等24小时)
      每次循环执行后       → urgency *= 0.85 (缓衰减)
      空闲15次无人喂入    → 触发主动扫描
    """

    DEEP_THINK_THRESHOLD = 2.5
    EVOLUTION_THRESHOLD = 7.0
    DECAY_FACTOR = 0.85
    CONSECUTIVE_NEGATIVE_LIMIT = 2
    IDLE_PROACTIVE_TICKS = 15

    def __init__(self):
        self._urgency = 0.0
        self._consecutive_negative = 0
        self._idle_ticks = 0
        self._lock = threading.Lock()
        self._stats = {
            "total_urgency_added": 0.0,
            "deep_think_triggers": 0,
            "evolution_triggers": 0,
            "decays": 0,
            "idle_proactive_triggers": 0,
        }

    def feed_causal_pair(self, pair: Any) -> dict[str, bool]:
        result = {"trigger_deep_think": False, "trigger_evolution": False}

        with self._lock:
            self._idle_ticks = 0
            increment = 0.0

            if pair.effectiveness < -0.3:
                increment += 3.0
            elif pair.effectiveness < -0.1:
                increment += 1.0

            if "fallback" in pair.action_taken:
                increment += 2.0

            if pair.effectiveness < -0.1:
                self._consecutive_negative += 1
                if self._consecutive_negative >= self.CONSECUTIVE_NEGATIVE_LIMIT:
                    increment += 5.0
            else:
                self._consecutive_negative = 0

            self._urgency += increment
            self._stats["total_urgency_added"] += increment

            if self._urgency >= self.EVOLUTION_THRESHOLD:
                result["trigger_evolution"] = True
                self._stats["evolution_triggers"] += 1
            elif self._urgency >= self.DEEP_THINK_THRESHOLD:
                result["trigger_deep_think"] = True
                self._stats["deep_think_triggers"] += 1

        return result

    def decay(self):
        with self._lock:
            self._urgency *= self.DECAY_FACTOR
            self._stats["decays"] += 1
            self._idle_ticks += 1

    def tick_idle(self) -> dict[str, bool]:
        with self._lock:
            self._idle_ticks += 1
            if self._idle_ticks >= self.IDLE_PROACTIVE_TICKS:
                self._idle_ticks = 0
                self._stats["idle_proactive_triggers"] += 1
                return {"trigger_deep_think": True, "trigger_evolution": False}
            return {"trigger_deep_think": False, "trigger_evolution": False}

    @property
    def urgency(self) -> float:
        with self._lock:
            return round(self._urgency, 2)

    def should_trigger_deep_think(self) -> bool:
        with self._lock:
            return (
                self._urgency >= self.DEEP_THINK_THRESHOLD
                or self._idle_ticks >= self.IDLE_PROACTIVE_TICKS
            )

    def should_trigger_evolution(self) -> bool:
        with self._lock:
            return self._urgency >= self.EVOLUTION_THRESHOLD

    def get_stats(self) -> dict:
        with self._lock:
            return {**self._stats, "current_urgency": round(self._urgency, 2)}


class EffectWatchdog:
    """
    效果看门狗 — EVOLVE修改规则后自动验证效果  [v10-ready]

    核心逻辑:
      EVOLVE修改规则后，启动观察窗口(默认30分钟)
      窗口内新规则产生的因果对效果 vs 旧规则平均效果
      新效果 < 旧效果 → 自动rollback + 记录到L3
      窗口结束，新效果 >= 旧效果 → 确认变更
    """

    DEFAULT_OBSERVE_WINDOW = 1800.0

    def __init__(self, observe_window: float = None):
        self._observe_window = observe_window or self.DEFAULT_OBSERVE_WINDOW
        self._active_watches: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._stats = {
            "watches_started": 0,
            "watches_confirmed": 0,
            "watches_rolled_back": 0,
        }

    def start_watch(
        self,
        rule_name: str,
        old_value: Any,
        old_avg_effectiveness: float,
        rollback_fn: Callable | None = None,
    ) -> str:
        watch_id = hashlib.md5(f"{rule_name}:{time.time()}".encode()).hexdigest()[:12]

        with self._lock:
            self._active_watches[watch_id] = {
                "rule_name": rule_name,
                "old_value": old_value,
                "old_avg_effectiveness": old_avg_effectiveness,
                "start_time": time.time(),
                "new_effectivenesses": [],
                "rollback_fn": rollback_fn,
                "status": "observing",
            }
            self._stats["watches_started"] += 1

        return watch_id

    def feed_causal_pair(self, pair: Any):
        with self._lock:
            for watch_id, watch in self._active_watches.items():
                if watch["status"] != "observing":
                    continue
                watch["new_effectivenesses"].append(pair.effectiveness)

    def check_watches(self) -> list[dict]:
        results = []
        now = time.time()

        with self._lock:
            expired_ids = []

            for watch_id, watch in self._active_watches.items():
                if watch["status"] != "observing":
                    continue

                elapsed = now - watch["start_time"]
                new_effs = watch["new_effectivenesses"]

                if elapsed >= self._observe_window and len(new_effs) >= 3:
                    new_avg = sum(new_effs) / len(new_effs)
                    old_avg = watch["old_avg_effectiveness"]

                    if new_avg < old_avg - 0.1:
                        watch["status"] = "rolled_back"
                        if watch["rollback_fn"]:
                            try:
                                watch["rollback_fn"]()
                            except Exception:
                                pass
                        self._stats["watches_rolled_back"] += 1
                        results.append(
                            {
                                "watch_id": watch_id,
                                "rule_name": watch["rule_name"],
                                "verdict": "rolled_back",
                                "old_avg": old_avg,
                                "new_avg": round(new_avg, 4),
                                "reason": f"新规则平均效果{new_avg:.2f} < 旧规则{old_avg:.2f}",
                            }
                        )
                    else:
                        watch["status"] = "confirmed"
                        self._stats["watches_confirmed"] += 1
                        results.append(
                            {
                                "watch_id": watch_id,
                                "rule_name": watch["rule_name"],
                                "verdict": "confirmed",
                                "old_avg": old_avg,
                                "new_avg": round(new_avg, 4),
                            }
                        )

                    expired_ids.append(watch_id)

        return results

    def get_active_watches(self) -> list[dict]:
        with self._lock:
            return [
                {"watch_id": wid, **{k: v for k, v in w.items() if k != "rollback_fn"}}
                for wid, w in self._active_watches.items()
                if w["status"] == "observing"
            ]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                **self._stats,
                "active_watches": len(
                    [
                        w
                        for w in self._active_watches.values()
                        if w["status"] == "observing"
                    ]
                ),
            }
