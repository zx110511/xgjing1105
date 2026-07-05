# -*- coding: utf-8-sig -*-
"""进化闭环 — 因果对记录器 (CausalPairRecorder)

从 evolution_loop.py 拆分，负责因果对的存储、统计和查询。
"""

from typing import Any, Dict, List, Optional
from .evolution_loop_models import ModuleCausalPair


from typing import Dict

class CausalPairRecorder:
    """
    因果对记录器 — M6 核心模块

    独立于 EvolutionLoop 的因果对记录引擎，为所有模块提供统一的
    因果对存储、统计和查询能力。

    闭环功能:
      record() → 创建CausalPair → FIFO存储 (max_pairs=10000)
      _update_stats() → per-action 正面/负面/中性计数
      get_effectiveness_summary() → 按action分组统计
      get_pairs(action, limit) → 可按action过滤查询
    """

    MAX_PAIRS = 10000

    def __init__(self):
        self._pairs: List[ModuleCausalPair] = []
        self._action_stats: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._stats = {
            "total_pairs": 0,
            "positive_pairs": 0,
            "negative_pairs": 0,
            "neutral_pairs": 0,
            "total_effect": 0.0,
        }

    def record(
        self,
        action: str,
        state_before: Dict[str, Any],
        state_after: Dict[str, Any],
        effect_score: float = 0.0,
        module_name: str = "",
        metadata: Dict = None,
    ) -> ModuleCausalPair:
        pair = ModuleCausalPair(
            module_name=module_name,
            action=action,
            state_before=state_before,
            state_after=state_after,
            effectiveness=effect_score,
            metadata=metadata or {},
        )

        with self._lock:
            self._pairs.append(pair)
            if len(self._pairs) > self.MAX_PAIRS:
                self._pairs = self._pairs[-self.MAX_PAIRS // 2 :]
            self._update_stats(pair)

        return pair

    def _update_stats(self, pair: ModuleCausalPair):
        self._stats["total_pairs"] += 1
        self._stats["total_effect"] += pair.effectiveness

        if pair.effectiveness > 0.05:
            self._stats["positive_pairs"] += 1
        elif pair.effectiveness < -0.05:
            self._stats["negative_pairs"] += 1
        else:
            self._stats["neutral_pairs"] += 1

        action = pair.action
        if action not in self._action_stats:
            self._action_stats[action] = {
                "count": 0,
                "total_effect": 0.0,
                "positive_count": 0,
                "negative_count": 0,
            }
        self._action_stats[action]["count"] += 1
        self._action_stats[action]["total_effect"] += pair.effectiveness
        if pair.effectiveness > 0.05:
            self._action_stats[action]["positive_count"] += 1
        elif pair.effectiveness < -0.05:
            self._action_stats[action]["negative_count"] += 1

    def get_effectiveness_summary(self, action: str = None) -> Dict:
        with self._lock:
            if action and action in self._action_stats:
                s = self._action_stats[action]
                return {
                    "action": action,
                    "count": s["count"],
                    "total_effect": round(s["total_effect"], 4),
                    "avg_effectiveness": round(s["total_effect"] / s["count"], 4)
                    if s["count"]
                    else 0.0,
                    "positive_count": s["positive_count"],
                    "negative_count": s["negative_count"],
                    "positive_rate": round(s["positive_count"] / s["count"], 4)
                    if s["count"]
                    else 0.0,
                }

            if not self._pairs:
                return {
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "negative_ratio": 0.0,
                    "count": 0,
                    "by_action": {},
                }

            effs = [p.effectiveness for p in self._pairs]
            negative_count = sum(1 for e in effs if e < -0.05)
            by_action = {}
            for act, s in self._action_stats.items():
                by_action[act] = {
                    "count": s["count"],
                    "avg_effect": round(s["total_effect"] / s["count"], 4)
                    if s["count"]
                    else 0.0,
                    "positive_count": s["positive_count"],
                    "positive_rate": round(s["positive_count"] / s["count"], 4)
                    if s["count"]
                    else 0.0,
                }
            return {
                "avg": round(sum(effs) / len(effs), 4),
                "min": round(min(effs), 4),
                "max": round(max(effs), 4),
                "negative_ratio": round(negative_count / len(effs), 4),
                "count": len(effs),
                "by_action": by_action,
            }

    def get_pairs(self, action: str = None, limit: int = 50) -> List[ModuleCausalPair]:
        with self._lock:
            if action:
                filtered = [p for p in self._pairs if p.action == action]
                return filtered[-limit:]
            return self._pairs[-limit:]

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "total_pairs": self._stats["total_pairs"],
                "positive_pairs": self._stats["positive_pairs"],
                "negative_pairs": self._stats["negative_pairs"],
                "neutral_pairs": self._stats["neutral_pairs"],
                "avg_effect": round(
                    self._stats["total_effect"] / self._stats["total_pairs"], 4
                )
                if self._stats["total_pairs"]
                else 0.0,
                "actions_tracked": len(self._action_stats),
                "actions": list(self._action_stats.keys()),
            }

    def clear(self):
        with self._lock:
            self._pairs.clear()
            self._action_stats.clear()
            self._stats = {k: 0 for k in self._stats if k != "total_effect"}
            if "total_effect" in self._stats:
                self._stats["total_effect"] = 0.0




__all__ = ["CausalPairRecorder"]
