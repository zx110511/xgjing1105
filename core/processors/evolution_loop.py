# -*- coding: utf-8-sig -*-
r"""
天机进化闭环协议 (Tianji Evolution Loop Protocol) v9.1
========================================================
让天机的每个模块都具备 OBSERVE → LEARN → EVOLVE 闭环能力。

SSS-PhaseB拆分: 本文件保留EvolutionLoop主类 + re-export兼容层
实际定义已拆分至:
- evolution_loop_models.py: 枚举+数据模型
- evolution_loop_recorder.py: CausalPairRecorder
- evolution_loop_challenger.py: ModuleChallenger
- evolution_loop_bus.py: EvolutionBus + CausalGraphStore
"""

import hashlib
import json
import logging
import threading
import time
import urllib.request
import urllib.error

# P0-fix: 递归保护
_persist_thread_local = threading.local()

# P0-MetaFix: 进化闭环写入限流 + 去重 (防止Meta层疯涨)
_PERSIST_COOLDOWN_SEC = 300.0  # 5分钟冷却 (从0秒→300秒, 减少写入频率97%)
_META_LAYER_HARD_CAP = 80000   # Meta层硬上限 (与cleanup_meta_layer.py一致)
_last_persist_time = 0.0
_last_persist_key = ""  # 去重键: module+action+effectiveness_rounded
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 从拆分模块导入
from .evolution_loop_models import (
    LoopPhase,
    EvolutionSignalType,
    ModuleCausalPair,
    EvolutionSignal,
    EvolutionResult,
)
from .evolution_loop_recorder import CausalPairRecorder
from .evolution_loop_challenger import ModuleChallenger
from .evolution_loop_bus import EvolutionBus, CausalGraphStore

class EvolutionLoop:
    """
    统一进化闭环骨架 — 每个模块复用的进化基础设施

    使用方式:
      1. 模块创建EvolutionLoop实例，传入module_name
      2. 模块实现3个回调: effectiveness_fn, learn_fn, evolve_fn
      3. 模块在关键操作后调用record_action()
      4. 模块在主循环中调用tick()
      5. EvolutionLoop自动完成OBSERVE→LEARN→EVOLVE→VALIDATE

    回调接口:
      effectiveness_fn(action, state_before, state_after) → float
        计算一次行动的效果分数 (-1.0 ~ 1.0)

      learn_fn(causal_pairs, effectiveness_summary) → Dict
        从因果对中提炼知识，返回学习结果

      evolve_fn(learn_result, mutable_config) → Dict
        基于学习结果修改模块配置，返回变更记录

    示例:
      class QualityGate:
          def __init__(self):
              self._evo_loop = EvolutionLoop(
                  module_name="quality_gate",
                  effectiveness_fn=self._calc_effectiveness,
                  learn_fn=self._learn_from_gates,
                  evolve_fn=self._evolve_thresholds,
              )

          def check(self, content, ...):
              state_before = {"rejection_rate": self._rejection_rate}
              result = self._do_check(content, ...)
              self._evo_loop.record_action(
                  action="gate_check",
                  state_before=state_before,
                  state_after={"verdict": result.verdict.value},
              )
              return result

          def _calc_effectiveness(self, action, before, after):
              if after.get("verdict") == "reject" and "important" in after.get("tags", []):
                  return -0.5
              return 0.3
    """

    DEEP_THINK_THRESHOLD = 5.0
    EVOLUTION_THRESHOLD = 10.0
    DECAY_FACTOR = 0.6
    # [FIX-v9.1-mem-leak] 从2000降至200，减少97%内存占用 (97模块×200×1.5KB≈29MB vs 原145MB)
    MAX_CAUSAL_PAIRS = 200
    # LRU淘汰时保留最近50条（非原1000条）
    CAUSAL_PAIR_KEEP_AFTER_TRIM = 50
    OBSERVE_WINDOW = 1800.0

    def __init__(
        self,
        module_name: str,
        effectiveness_fn: Optional[Callable] = None,
        learn_fn: Optional[Callable] = None,
        evolve_fn: Optional[Callable] = None,
        mutable_config: Optional[Dict[str, Any]] = None,
        health_metrics_fn: Optional[Callable] = None,
        challenger_scan_interval: float = 300.0,
        persist_dir: Optional[Path] = None,
        recorder: Optional[CausalPairRecorder] = None,
        learning_engine: Optional[Any] = None,
    ):
        self._module_name = module_name
        self._effectiveness_fn = effectiveness_fn
        self._recorder = recorder
        self._learn_fn = learn_fn
        self._evolve_fn = evolve_fn
        self._mutable_config = mutable_config or {}
        self._health_metrics_fn = health_metrics_fn
        self._persist_dir = persist_dir
        self._learning_engine = learning_engine

        self._urgency = 0.0
        self._consecutive_negative = 0
        self._phase = LoopPhase.IDLE
        self._causal_pairs: List[ModuleCausalPair] = []
        self._active_watches: Dict[str, Dict] = {}
        self._last_learn = 0.0
        self._last_evolve = 0.0
        self._learn_interval = 300.0
        self._evolve_interval = 3600.0

        self._challenger = ModuleChallenger(
            module_name=module_name,
            scan_interval=challenger_scan_interval,
        )

        self._signal_subscribers: List[Callable[[EvolutionSignal], None]] = []
        self._lock = threading.Lock()
        self._stats = {
            "actions_recorded": 0,
            "observe_cycles": 0,
            "learn_cycles": 0,
            "evolve_cycles": 0,
            "rollbacks": 0,
            "challenges_from_challenger": 0,
            "signals_broadcasted": 0,
            "config_changes": 0,
        }

    def record_action(
        self,
        action: str,
        state_before: Dict[str, Any],
        state_after: Dict[str, Any],
        metadata: Optional[Dict] = None,
    ) -> ModuleCausalPair:
        effectiveness = 0.0
        if self._effectiveness_fn:
            try:
                effectiveness = self._effectiveness_fn(
                    action, state_before, state_after
                )
            except Exception as e:
                logger.debug(f"[{self._module_name}] effectiveness_fn error: {e}")
                effectiveness = 0.0

        pair = ModuleCausalPair(
            module_name=self._module_name,
            action=action,
            state_before=state_before,
            state_after=state_after,
            effectiveness=effectiveness,
            metadata=metadata or {},
        )

        if self._recorder:
            try:
                self._recorder.record(
                    action=action,
                    state_before=state_before,
                    state_after=state_after,
                    effect_score=effectiveness,
                    module_name=self._module_name,
                    metadata=metadata,
                )
            except Exception:
                pass

        with self._lock:
            self._causal_pairs.append(pair)
            # [FIX-v9.1-mem-leak] LRU淘汰: 保留最近50条而非原1000条，减少95%内存
            if len(self._causal_pairs) > self.MAX_CAUSAL_PAIRS:
                self._causal_pairs = self._causal_pairs[-self.CAUSAL_PAIR_KEEP_AFTER_TRIM:]
                logger.debug(f"[{self._module_name}] CausalPair LRU trim to {self.CAUSAL_PAIR_KEEP_AFTER_TRIM}")

            self._stats["actions_recorded"] += 1

            urgency_delta = max(0.0, -effectiveness) * 2.0
            self._urgency += urgency_delta

            if effectiveness < 0:
                self._consecutive_negative += 1
                if self._consecutive_negative >= 3:
                    self._urgency += 5.0
            else:
                self._consecutive_negative = 0

            self._phase = LoopPhase.OBSERVING

        self._feed_watches(pair)

        # ICME闭环: 将进化动作持久化到记忆系统
        self._persist_action_to_icme(pair)

        return pair

    def _persist_action_to_icme(self, pair: ModuleCausalPair) -> None:
        """将进化动作因果对持久化到ICME记忆系统，实现修复闭环。

        P0-fix: 直接写SQLite，不走engine.remember()或HTTP API，
        避免递归调用导致7秒超时和内存膨胀。
        P0-MetaFix: 添加容量保护+冷却+去重，防止Meta层疯涨正反馈循环
        """
        global _last_persist_time, _last_persist_key

        # P0-fix: 递归保护 — 如果当前线程已在持久化中，跳过避免死循环
        if getattr(_persist_thread_local, 'in_persist', False):
            logger.debug(f"[ICME闭环] 跳过递归持久化: module={pair.module_name} action={pair.action}")
            return

        # P0-MetaFix-1: 冷却时间保护 (5分钟内不重复写入)
        now = time.time()
        if now - _last_persist_time < _PERSIST_COOLDOWN_SEC:
            return

        # P0-MetaFix-2: 去重保护 (相同module+action+effectiveness_rounded 5分钟内只写1次)
        eff_rounded = round(pair.effectiveness, 2)
        dedup_key = f"{pair.module_name}|{pair.action}|{eff_rounded}"
        if dedup_key == _last_persist_key:
            return

        _persist_thread_local.in_persist = True
        try:
            content = (
                f"[进化闭环] module={pair.module_name} action={pair.action} "
                f"effectiveness={pair.effectiveness:.2f}"
            )
            # P0-fix: 直接写SQLite，不走完整remember流程
            try:
                from server.deps import get_engine
                engine = get_engine()
                if engine is not None and hasattr(engine, '_store') and engine._store is not None:
                    # P0-MetaFix-3: Meta层硬上限保护 — 防止写入episodic后通过整合晋升撑爆Meta
                    try:
                        if hasattr(engine._store, 'get_layer_stats'):
                            layer_stats = engine._store.get_layer_stats()
                            meta_count = layer_stats.get("meta", {}).get("entry_count", 0)
                            if meta_count >= _META_LAYER_HARD_CAP:
                                logger.warning(
                                    f"[ICME闭环] Meta层已{meta_count}条≥{_META_LAYER_HARD_CAP}，"
                                    f"跳过进化记录写入防止正反馈循环"
                                )
                                return
                    except Exception as e:
                        logger.debug(f"[ICME闭环] Meta容量检查跳过: {e}")

                    import hashlib
                    import uuid
                    entry_id = hashlib.sha256(
                        f"{content}{time.time()}{uuid.uuid4()}".encode()
                    ).hexdigest()[:16]
                    entry_dict = {
                        "id": entry_id,
                        "content": content,
                        "layer": "episodic",
                        "tags": ["evolution", pair.module_name, pair.action],
                        "priority": "high" if pair.effectiveness < 0 else "medium",
                        "value_score": 0.3,
                        "access_count": 0,
                        "created_at": time.time(),
                        "last_accessed": time.time(),
                        "size_bytes": len(content.encode("utf-8")),
                        "metadata": {"source": "evo_loop_persist"},
                        "related_ids": [],
                        "changelog": [],
                    }
                    ok = engine._store.insert(entry_dict)
                    if ok:
                        _last_persist_time = now
                        _last_persist_key = dedup_key
                        logger.debug(f"[ICME闭环] 进化动作已持久化(SQLite直写): id={entry_id} module={pair.module_name}")
                    return
            except Exception as e:
                logger.debug(f"[ICME闭环] SQLite直写失败: {e}")
        except Exception as e:
            logger.debug(f"[ICME闭环] 进化动作持久化失败(非致命): {e}")
        finally:
            _persist_thread_local.in_persist = False

    def tick(self) -> List[EvolutionResult]:
        results = []
        now = time.time()

        challenge_signals = self._run_challenger()
        for sig in challenge_signals:
            self._urgency += sig.severity * 5.0
            self._broadcast_signal(sig)
            self._stats["challenges_from_challenger"] += 1

        if self._urgency >= self.EVOLUTION_THRESHOLD or (
            now - self._last_evolve >= self._evolve_interval
            and len(self._causal_pairs) >= 5
        ):
            evolve_result = self._run_evolve_cycle()
            if evolve_result:
                results.append(evolve_result)
            self._last_evolve = now

        elif self._urgency >= self.DEEP_THINK_THRESHOLD or (
            now - self._last_learn >= self._learn_interval
            and len(self._causal_pairs) >= 3
        ):
            learn_result = self._run_learn_cycle()
            if learn_result:
                results.append(learn_result)
            self._last_learn = now

        self._check_watches()

        with self._lock:
            self._urgency *= self.DECAY_FACTOR

        return results

    def _run_challenger(self) -> List[EvolutionSignal]:
        if not self._health_metrics_fn:
            return []
        try:
            metrics = self._health_metrics_fn()
            if not metrics:
                return []
            return self._challenger.scan(metrics)
        except Exception as e:
            logger.debug(f"[{self._module_name}] Challenger scan error: {e}")
            return []

    def _run_learn_cycle(self) -> Optional[EvolutionResult]:
        if not self._learn_fn:
            return None

        self._phase = LoopPhase.LEARNING
        self._stats["learn_cycles"] += 1

        with self._lock:
            pairs = list(self._causal_pairs[-100:])

        if not pairs:
            self._phase = LoopPhase.IDLE
            return None

        effectiveness_summary = self._get_effectiveness_summary(pairs)

        try:
            learn_result = self._learn_fn(pairs, effectiveness_summary)
            self._phase = LoopPhase.IDLE
            return EvolutionResult(
                module_name=self._module_name,
                phase=LoopPhase.LEARNING,
                summary=f"LEARN完成: {learn_result}",
            )
        except Exception as e:
            logger.error(f"[{self._module_name}] LEARN failed: {e}")
            self._phase = LoopPhase.IDLE
            return None

    def _run_evolve_cycle(self) -> Optional[EvolutionResult]:
        if not self._evolve_fn:
            return None

        self._phase = LoopPhase.EVOLVING
        self._stats["evolve_cycles"] += 1

        with self._lock:
            pairs = list(self._causal_pairs[-200:])

        effectiveness_summary = self._get_effectiveness_summary(pairs)

        learn_result = {}
        if self._learn_fn:
            try:
                learn_result = self._learn_fn(pairs, effectiveness_summary)
            except Exception as e:
                logger.error(f"[{self._module_name}] LEARN in EVOLVE cycle failed: {e}")

        config_snapshot = dict(self._mutable_config)

        try:
            evolve_result = self._evolve_fn(learn_result, self._mutable_config)
            changes = evolve_result.get("changes", [])

            for change in changes:
                rule_name = change.get("rule")
                new_value = change.get("new_value")
                if rule_name and rule_name in self._mutable_config:
                    old_value = config_snapshot.get(rule_name)
                    self._mutable_config[rule_name] = new_value
                    self._stats["config_changes"] += 1

                    self._start_watch(
                        rule_name=rule_name,
                        old_value=old_value,
                        old_avg_effectiveness=effectiveness_summary.get("avg", 0.5),
                        rollback_fn=self._make_rollback(rule_name, old_value),
                    )

            self._phase = LoopPhase.VALIDATING
            return EvolutionResult(
                module_name=self._module_name,
                phase=LoopPhase.EVOLVING,
                changes_made=changes,
                rules_modified=changes,
                rollback_available=True,
                summary=f"EVOLVE完成: {len(changes)}项变更",
            )
        except Exception as e:
            logger.error(f"[{self._module_name}] EVOLVE failed: {e}")
            self._phase = LoopPhase.IDLE
            return None

    def _start_watch(
        self,
        rule_name: str,
        old_value: Any,
        old_avg_effectiveness: float,
        rollback_fn: Optional[Callable] = None,
    ) -> str:
        watch_id = hashlib.md5(
            f"{self._module_name}:{rule_name}:{time.time()}".encode()
        ).hexdigest()[:12]

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
        return watch_id

    def _feed_watches(self, pair: ModuleCausalPair):
        with self._lock:
            for watch_id, watch in self._active_watches.items():
                if watch["status"] == "observing":
                    watch["new_effectivenesses"].append(pair.effectiveness)

    def _check_watches(self):
        now = time.time()
        with self._lock:
            for watch_id, watch in self._active_watches.items():
                if watch["status"] != "observing":
                    continue

                elapsed = now - watch["start_time"]
                new_effs = watch["new_effectivenesses"]

                if elapsed >= self.OBSERVE_WINDOW and len(new_effs) >= 3:
                    new_avg = sum(new_effs) / len(new_effs)
                    old_avg = watch["old_avg_effectiveness"]

                    if new_avg < old_avg - 0.1:
                        watch["status"] = "rolled_back"
                        if watch["rollback_fn"]:
                            try:
                                watch["rollback_fn"]()
                            except Exception:
                                pass
                        self._stats["rollbacks"] += 1
                        logger.warning(
                            f"[{self._module_name}] EffectWatchdog回滚: "
                            f"规则'{watch['rule_name']}' "
                            f"新效果{new_avg:.2f} < 旧效果{old_avg:.2f}"
                        )
                    else:
                        watch["status"] = "confirmed"

    def _make_rollback(self, rule_name: str, old_value: Any) -> Callable:
        def rollback():
            self._mutable_config[rule_name] = old_value
            logger.info(f"[{self._module_name}] 回滚规则'{rule_name}' → {old_value}")

        return rollback

    def _get_effectiveness_summary(self, pairs: List[ModuleCausalPair]) -> Dict:
        if not pairs:
            return {
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "negative_ratio": 0.0,
                "count": 0,
            }

        effs = [p.effectiveness for p in pairs]
        negative_count = sum(1 for e in effs if e < 0)
        return {
            "avg": sum(effs) / len(effs),
            "min": min(effs),
            "max": max(effs),
            "negative_ratio": negative_count / len(effs),
            "count": len(effs),
        }

    def subscribe_signals(self, callback: Callable[[EvolutionSignal], None]):
        self._signal_subscribers.append(callback)

    def _broadcast_signal(self, signal: EvolutionSignal):
        self._stats["signals_broadcasted"] += 1
        for callback in self._signal_subscribers:
            try:
                callback(signal)
            except Exception as e:
                logger.debug(f"[{self._module_name}] Signal subscriber error: {e}")

    def receive_signal(self, signal: EvolutionSignal):
        with self._lock:
            self._urgency += signal.severity * 3.0
        logger.info(
            f"[{self._module_name}] 收到进化信号: "
            f"{signal.signal_type.value} from {signal.source_module} "
            f"severity={signal.severity:.2f}"
        )

    @property
    def urgency(self) -> float:
        with self._lock:
            return round(self._urgency, 2)

    @property
    def phase(self) -> LoopPhase:
        return self._phase

    @property
    def mutable_config(self) -> Dict[str, Any]:
        return self._mutable_config

    @property
    def recorder(self) -> Optional[CausalPairRecorder]:
        return self._recorder

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "module_name": self._module_name,
                "phase": self._phase.value,
                "urgency": round(self._urgency, 2),
                "causal_pairs": len(self._causal_pairs),
                "active_watches": len(
                    [
                        w
                        for w in self._active_watches.values()
                        if w["status"] == "observing"
                    ]
                ),
                **self._stats,
                "challenger": self._challenger.get_stats(),
            }




# ============================================================================
# 公开导出符号 (兼容层)
# ============================================================================

__all__ = [
    "LoopPhase",
    "EvolutionSignalType",
    "ModuleCausalPair",
    "EvolutionSignal",
    "EvolutionResult",
    "CausalPairRecorder",
    "ModuleChallenger",
    "EvolutionLoop",
    "EvolutionBus",
    "CausalGraphStore",
]
