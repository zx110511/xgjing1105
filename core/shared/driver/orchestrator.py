# -*- coding: utf-8-sig -*-
r"""
DeepSeek驾驶者 · 三循环编排子模块 (Driver Orchestrator)  [v10-ready]
====================================================================
从 core/deepseek_driver.py 拆分而来 (P1-02)。

职责: 三循环并行驾驶 + 触发管理 + 进化集成
  - TriggerFrequencyTracker : 循环触发频率实时追踪器
  - DriverOrchestrator      : ACT执行 + 盲区扫描 + 深度思考(循环B) +
                              进化反思(循环C) + 主循环(循环A) 编排

设计约束:
  - 不直接 import core/ 顶层其他模块；运行所需的全部组件
    (memory_engine / causal_recorder / urgency / watchdog / 进化引擎 等)
    经由构造函数注入的 driver 上下文统一访问。
  - DriverOrchestrator(driver) 仅持有对 DeepSeekDriver 的引用，
    通过该引用复用 driver 持有的各子组件，保持单一数据源。
"""
from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Any

from .decision import DriverDecision, EvolutionSignal

logger = logging.getLogger("tianji.driver")


class TriggerFrequencyTracker:
    """循环触发频率实时追踪器 — 环形缓冲区+统计  [v10-ready]"""

    def __init__(self, ring_size: int = 200):
        self._ring_size = ring_size
        self._ring: collections.deque = collections.deque(maxlen=ring_size)
        self._counts = {
            "loop_a": 0,
            "loop_b_timed": 0,
            "loop_b_urgency": 0,
            "loop_c_timed": 0,
            "loop_c_urgency": 0,
            "watchdog": 0,
            "catchup": 0,
            "module_tick": 0,
            "idle": 0,
        }
        self._last_trigger: dict[str, float] = {}
        self._lock = threading.Lock()

    def record(self, trigger_type: str, detail: str = ""):
        now = time.time()
        with self._lock:
            self._ring.append({"type": trigger_type, "detail": detail, "time": now})
            if trigger_type in self._counts:
                self._counts[trigger_type] += 1
            self._last_trigger[trigger_type] = now

    def get_frequency(self, window_seconds: float = 3600) -> dict:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            recent = [e for e in self._ring if e["time"] >= cutoff]
            return {
                "window_seconds": window_seconds,
                "total_triggers_window": len(recent),
                "triggers_per_hour": len(recent) / (window_seconds / 3600)
                if window_seconds > 0
                else 0,
                "counts": dict(self._counts),
                "last_trigger": dict(self._last_trigger),
                "recent_20": list(self._ring)[-20:],
            }

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "ring_entries": len(self._ring),
                "counts": dict(self._counts),
                "last_trigger": dict(self._last_trigger),
            }


class DriverOrchestrator:
    """
    三循环编排器 — DeepSeek Driver 的执行与进化中枢  [v10-ready]

    通过注入的 driver 上下文访问其各子组件:
      driver.memory_engine / driver._causal_recorder / driver._urgency_accumulator
      driver._effect_watchdog / driver._offline_catchup / driver._evolution_engine
      driver._learning_engine / driver._evo_loop / driver._mutable_rules
      driver._stats / driver._trigger_tracker / driver.decision_engine
      driver._decision (DecisionEngine) / driver._module_loops
    """

    def __init__(self, driver: Any):
        self._driver = driver

    # === ACT 执行 ===  [v10-ready]

    def act(self, decision: DriverDecision) -> bool:
        d = self._driver
        if not decision.should_store and not decision.should_evolve:
            return True

        d._causal_recorder.capture_before(
            action=decision.action,
            reason=decision.reason,
            memory_engine=d.memory_engine,
        )

        success = False
        side_effects: list[str] = []

        try:
            if decision.should_store:
                success = self._act_store(decision)
                if success:
                    side_effects.append(f"stored to {decision.target_layer}")

            if decision.should_merge:
                merge_result = self._act_merge(decision)
                if merge_result:
                    side_effects.append("merged similar memories")
                    success = True

            if decision.should_link:
                link_result = self._act_link(decision)
                if link_result:
                    side_effects.append("linked related memories")

            if decision.should_consolidate:
                try:
                    if hasattr(d.memory_engine, "consolidate"):
                        d.memory_engine.consolidate(from_layer=decision.target_layer)
                        side_effects.append(f"consolidated {decision.target_layer}")
                except Exception:
                    pass

            if decision.should_evolve and d._evolution_engine:
                try:
                    evolve_result = d._evolution_engine.process_evolution_signal(
                        EvolutionSignal(
                            signal_type="action_triggered",
                            source_layer=decision.target_layer,
                            content_summary=decision.enriched_content[:300],
                            evolution_value=decision.confidence,
                            reason=decision.reason,
                            suggested_action=decision.action,
                            confidence=decision.confidence,
                            payload=decision.evolution_payload,
                        )
                    )
                    if evolve_result:
                        side_effects.append(f"evolution: {evolve_result}")
                except Exception as e:
                    logger.warning(f"Evolution trigger failed: {e}")

        except Exception as e:
            logger.error(f"Act error: {e}")
            d._stats["errors"] += 1
            success = False

        pair = d._causal_recorder.capture_after(
            memory_engine=d.memory_engine,
            side_effects=side_effects,
        )

        if pair:
            d._stats["causal_pairs_recorded"] += 1
            if d._can_call_deepseek() and pair.effectiveness < 0:
                d._causal_recorder.evaluate_with_deepseek(pair, d.decision_engine)

            urgency_result = d._urgency_accumulator.feed_causal_pair(pair)
            d._effect_watchdog.feed_causal_pair(pair)

            if urgency_result.get("trigger_evolution"):
                logger.info(
                    f"[DeepSeek Driver] Urgency={d._urgency_accumulator.urgency:.1f} "
                    f"触发即时进化反思"
                )
                try:
                    self.evolution_cycle()
                    d._urgency_accumulator.decay()
                except Exception as e:
                    logger.error(f"Urgency-triggered evolution failed: {e}")
            elif urgency_result.get("trigger_deep_think"):
                logger.info(
                    f"[DeepSeek Driver] Urgency={d._urgency_accumulator.urgency:.1f} "
                    f"触发即时深度思考"
                )
                try:
                    self.deep_think_cycle()
                    d._urgency_accumulator.decay()
                except Exception as e:
                    logger.error(f"Urgency-triggered deep think failed: {e}")

            if not d._can_call_deepseek():
                d._offline_catchup.mark_offline()
                d._offline_catchup.backlog_pair(pair)
            else:
                if not d._offline_catchup.is_online:
                    d._offline_catchup.mark_online()

        if success:
            d._stats["actions_executed"] += 1

        if d._evo_loop is not None:
            try:
                d._evo_loop.record_action(
                    action="driver_act",
                    state_before={
                        "actions_performed": d._stats["actions_executed"] - 1,
                        "error_count": d._stats["errors"],
                    },
                    state_after={
                        "actions_performed": d._stats["actions_executed"],
                        "error_count": d._stats["errors"],
                        "last_action": decision.action,
                    },
                )
            except Exception:
                pass

        return success

    def _act_store(self, decision: DriverDecision) -> bool:
        d = self._driver
        if not d.memory_engine:
            return False
        content = decision.enriched_content
        if not content:
            return False
        if hasattr(d.memory_engine, "remember"):
            d.memory_engine.remember(
                content=content,
                layer=decision.target_layer,
                tags=decision.tags,
                priority=decision.priority,
            )
            return True
        return False

    def _act_merge(self, decision: DriverDecision) -> bool:
        d = self._driver
        if not d.memory_engine or not hasattr(d.memory_engine, "_layers"):
            return False
        try:
            target_layer = decision.target_layer
            entries = list(d.memory_engine._layers.get(target_layer, {}).values())
            merged_count = 0
            for i in range(len(entries)):
                for j in range(i + 1, min(i + 10, len(entries))):
                    if entries[i].content == entries[j].content:
                        continue
                    overlap = self._content_overlap(
                        entries[i].content, entries[j].content
                    )
                    if overlap > 0.85:
                        merged_content = entries[i].content
                        merged_tags = list(set(entries[i].tags + entries[j].tags))
                        entries[i].update_content(merged_content)
                        entries[i].tags = merged_tags
                        entries[i].access_count += entries[j].access_count
                        if hasattr(d.memory_engine, "_delete_entry_file"):
                            d.memory_engine._delete_entry_file(
                                entries[j].id, target_layer
                            )
                        del d.memory_engine._layers[target_layer][entries[j].id]
                        merged_count += 1
                        break
            return merged_count > 0
        except Exception as e:
            logger.warning(f"Merge action failed: {e}")
            return False

    def _act_link(self, decision: DriverDecision) -> bool:
        d = self._driver
        if not d.memory_engine or not hasattr(d.memory_engine, "_layers"):
            return False
        try:
            target_layer = decision.target_layer
            entries = list(d.memory_engine._layers.get(target_layer, {}).values())
            linked = 0
            for i in range(len(entries)):
                if entries[i].related_ids:
                    continue
                for j in range(len(entries)):
                    if i == j or entries[j].id in entries[i].related_ids:
                        continue
                    tag_overlap = len(set(entries[i].tags) & set(entries[j].tags))
                    if tag_overlap >= 2:
                        entries[i].related_ids.append(entries[j].id)
                        entries[j].related_ids.append(entries[i].id)
                        linked += 1
                        if linked >= 5:
                            break
                if linked >= 5:
                    break
            return linked > 0
        except Exception as e:
            logger.warning(f"Link action failed: {e}")
            return False

    def _content_overlap(self, content_a: str, content_b: str) -> float:
        if not content_a or not content_b:
            return 0.0
        set_a = set(content_a[:500])
        set_b = set(content_b[:500])
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    # === SENSE 盲区扫描 ===  [v10-ready]

    def _scan_undigested_memories(self) -> list[dict]:
        """扫描L0中未被决策使用过的"盲区记忆" — SENSE核心"""
        d = self._driver
        undigested = []
        if not d.memory_engine or not hasattr(d.memory_engine, "_layers"):
            return undigested

        sensory_layer = d.memory_engine._layers.get("sensory", {})
        for entry in list(sensory_layer.values())[-100:]:
            if entry.access_count == 0:
                undigested.append(
                    {
                        "id": entry.id,
                        "content": entry.content[:200],
                        "tags": entry.tags,
                        "age_hours": (time.time() - entry.created_at) / 3600,
                    }
                )

        return undigested

    def _scan_orphaned_contexts(self) -> list[dict]:
        """扫描L1中无关联的孤立工作记忆"""
        d = self._driver
        orphaned = []
        if not d.memory_engine or not hasattr(d.memory_engine, "_layers"):
            return orphaned

        working_layer = d.memory_engine._layers.get("working", {})
        for entry in list(working_layer.values())[-50:]:
            if not entry.related_ids:
                orphaned.append(
                    {
                        "id": entry.id,
                        "content": entry.content[:200],
                        "tags": entry.tags,
                    }
                )

        return orphaned

    def _scan_repeated_patterns(self) -> list[dict]:
        """扫描L3中重复出现但未提炼的模式"""
        d = self._driver
        patterns = []
        if not d.memory_engine or not hasattr(d.memory_engine, "_layers"):
            return patterns

        episodic_layer = d.memory_engine._layers.get("episodic", {})
        tag_clusters: dict[str, list[str]] = {}
        for entry in list(episodic_layer.values())[-100:]:
            tag_key = ",".join(sorted(set(entry.tags[:3])))
            if tag_key not in tag_clusters:
                tag_clusters[tag_key] = []
            tag_clusters[tag_key].append(entry.id)

        for tag_key, ids in tag_clusters.items():
            if len(ids) >= 3:
                patterns.append(
                    {
                        "tag_pattern": tag_key,
                        "occurrence_count": len(ids),
                        "entry_ids": ids[:5],
                    }
                )

        return patterns

    # === 循环B: 深度思考 ===  [v10-ready]

    def deep_think_cycle(self):
        """循环B: 深度思考 — SENSE → EVALUATE → DECIDE → ACT → OBSERVE"""
        d = self._driver
        d._stats["deep_think_cycles"] += 1
        logger.info("[DeepSeek Driver] 深度思考循环启动...")

        undigested = self._scan_undigested_memories()
        orphaned = self._scan_orphaned_contexts()
        repeated = self._scan_repeated_patterns()

        all_signals = []
        for item in undigested:
            all_signals.append({"type": "undigested", **item})
        for item in orphaned:
            all_signals.append({"type": "orphaned", **item})
        for item in repeated:
            all_signals.append({"type": "repeated_pattern", **item})

        if not all_signals:
            logger.info("[DeepSeek Driver] 深度思考: 无需处理的信号")
            return

        d._stats["evolution_signals_detected"] += len(all_signals)

        evolution_signal = d._decision.evaluate_evolution_value(all_signals)

        if evolution_signal is None:
            return

        decision = DriverDecision(
            action="deep_think_evolution",
            target_layer="episodic",
            tags=["deep_think", "evolution", "auto"],
            priority="medium",
            confidence=evolution_signal.confidence,
            reason=evolution_signal.reason,
            enriched_content=evolution_signal.content_summary,
            should_store=True,
            should_merge=len(repeated) > 0,
            should_link=len(orphaned) > 0,
            should_evolve=evolution_signal.evolution_value > 0.7,
            evolution_payload=evolution_signal.to_dict(),
        )

        self.act(decision)
        logger.info(
            f"[DeepSeek Driver] 深度思考完成: "
            f"处理{len(all_signals)}个信号, "
            f"进化价值={evolution_signal.evolution_value:.2f}"
        )

        if d._evo_loop is not None:
            try:
                d._evo_loop.record_action(
                    action="deep_think_cycle",
                    state_before={
                        "signals_detected": d._stats["evolution_signals_detected"]
                        - len(all_signals)
                    },
                    state_after={
                        "signals_detected": d._stats["evolution_signals_detected"],
                        "signals_processed": len(all_signals),
                        "evolution_value": evolution_signal.evolution_value,
                    },
                )
            except Exception:
                pass

    # === 循环C: 进化反思 ===  [v10-ready]

    def evolution_cycle(self):
        """循环C: 进化反思 — 汇总因果对 → LEARN → EVOLVE"""
        d = self._driver
        d._stats["evolution_cycles"] += 1
        _evo_start = time.time()
        logger.info("[DeepSeek Driver] 进化反思循环启动...")

        causal_pairs = d._causal_recorder.get_recent_pairs(limit=200)
        if not causal_pairs:
            logger.info("[DeepSeek Driver] 进化反思: 无因果对数据")
            d._stats.setdefault("evolution_last_latency_ms", 0)
            d._stats.setdefault("evolution_avg_latency_ms", 0)
            return

        effectiveness_summary = d._causal_recorder.get_action_effectiveness_summary()

        if d._learning_engine:
            try:
                learn_result = d._learning_engine.learn_from_causal_pairs(
                    causal_pairs=causal_pairs,
                    effectiveness_summary=effectiveness_summary,
                    decision_engine=d.decision_engine,
                )
                if learn_result:
                    logger.info(
                        f"[DeepSeek Driver] LEARN完成: "
                        f"模式={learn_result.get('patterns_found', 0)}, "
                        f"策略优化={learn_result.get('strategies_optimized', 0)}, "
                        f"能力发现={learn_result.get('capabilities_discovered', 0)}"
                    )
            except Exception as e:
                logger.error(f"LEARN failed: {e}")

        if d._evolution_engine:
            try:
                evolve_result = d._evolution_engine.evolve_from_learning(
                    causal_pairs=causal_pairs,
                    effectiveness_summary=effectiveness_summary,
                    mutable_rules=d._mutable_rules,
                    decision_engine=d.decision_engine,
                )
                if evolve_result and evolve_result.get("rules_modified"):
                    d._stats["rules_modified"] += len(evolve_result["rules_modified"])
                    for rule_change in evolve_result["rules_modified"]:
                        rule_name = rule_change.get("rule")
                        new_value = rule_change.get("new_value")
                        if rule_name in d._mutable_rules:
                            old_value = d._mutable_rules[rule_name]
                            d._mutable_rules[rule_name] = new_value
                            logger.info(
                                f"[DeepSeek Driver] EVOLVE: 规则'{rule_name}' "
                                f"从{old_value}→{new_value}"
                            )

                            def _make_rollback(name, val):
                                def rollback():
                                    d._mutable_rules[name] = val
                                    logger.info(
                                        f"[DeepSeek Driver] EffectWatchdog回滚: "
                                        f"规则'{name}' 恢复为{val}"
                                    )

                                return rollback

                            d._effect_watchdog.start_watch(
                                rule_name=rule_name,
                                old_value=old_value,
                                old_avg_effectiveness=effectiveness_summary.get(
                                    "avg_effectiveness", 0.5
                                ),
                                rollback_fn=_make_rollback(rule_name, old_value),
                            )

                if evolve_result and evolve_result.get("skills_created"):
                    d._stats["skills_auto_created"] += len(
                        evolve_result["skills_created"]
                    )

                logger.info(
                    f"[DeepSeek Driver] EVOLVE完成: "
                    f"规则修改={len(evolve_result.get('rules_modified', []))}, "
                    f"Skill创建={len(evolve_result.get('skills_created', []))}"
                )

                if d._evo_loop is not None:
                    try:
                        rules_before = d._stats["rules_modified"] - len(
                            evolve_result.get("rules_modified", [])
                        )
                        skills_before = d._stats["skills_auto_created"] - len(
                            evolve_result.get("skills_created", [])
                        )
                        d._evo_loop.record_action(
                            action="evolution_cycle",
                            state_before={
                                "rules_modified": rules_before,
                                "skills_created": skills_before,
                            },
                            state_after={
                                "rules_modified": d._stats["rules_modified"],
                                "skills_created": d._stats["skills_auto_created"],
                                "evolution_success": True,
                            },
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"EVOLVE failed: {e}")

        # [FIX-CYCLE-C] 记录进化反思环真实执行延迟
        _evo_elapsed_ms = round((time.time() - _evo_start) * 1000, 1)
        d._stats["evolution_last_latency_ms"] = _evo_elapsed_ms
        prev_avg = d._stats.get("evolution_avg_latency_ms", 0)
        d._stats["evolution_avg_latency_ms"] = round(
            (prev_avg * (d._stats["evolution_cycles"] - 1) + _evo_elapsed_ms)
            / d._stats["evolution_cycles"], 1
        )

    # === 循环A: 主循环 ===  [v10-ready]

    def run_main_loop(self):
        """三循环并行驾驶主循环 + 感知触发器"""
        d = self._driver
        while d._running:
            try:
                # 循环A: 快速反应
                events = d.event_bus.drain(max_items=20)
                for event in events:
                    d.perceive_decide_act(event)
                d._trigger_tracker.record("loop_a", f"events={len(events)}")

                # 感知触发器: UrgencyAccumulator驱动即时深度思考
                now = time.time()
                if d._urgency_accumulator.should_trigger_deep_think():
                    d._last_deep_think = now
                    d._trigger_tracker.record("loop_b_urgency")
                    try:
                        self.deep_think_cycle()
                        d._urgency_accumulator.decay()
                    except Exception as e:
                        logger.error(f"Urgency-triggered deep think error: {e}")
                elif now - d._last_deep_think >= d._deep_think_interval:
                    d._last_deep_think = now
                    d._trigger_tracker.record("loop_b_timed")
                    try:
                        self.deep_think_cycle()
                    except Exception as e:
                        logger.error(f"Deep think cycle error: {e}")

                # 感知触发器: UrgencyAccumulator驱动即时进化反思
                if d._urgency_accumulator.should_trigger_evolution():
                    d._last_evolution_cycle = now
                    d._trigger_tracker.record("loop_c_urgency")
                    try:
                        self.evolution_cycle()
                        d._urgency_accumulator.decay()
                    except Exception as e:
                        logger.error(f"Urgency-triggered evolution error: {e}")
                elif now - d._last_evolution_cycle >= d._evolution_interval:
                    d._last_evolution_cycle = now
                    d._trigger_tracker.record("loop_c_timed")
                    try:
                        self.evolution_cycle()
                    except Exception as e:
                        logger.error(f"Evolution cycle error: {e}")

                # EffectWatchdog: 检查规则修改效果
                watchdog_results = d._effect_watchdog.check_watches()
                for wr in watchdog_results:
                    if wr["verdict"] == "rolled_back":
                        logger.warning(
                            f"[DeepSeek Driver] EffectWatchdog: 规则'{wr['rule_name']}' "
                            f"效果回退({wr['new_avg']:.2f} < {wr['old_avg']:.2f}), 已自动回滚"
                        )
                    elif wr["verdict"] == "confirmed":
                        logger.info(
                            f"[DeepSeek Driver] EffectWatchdog: 规则'{wr['rule_name']}' "
                            f"效果确认({wr['new_avg']:.2f} >= {wr['old_avg']:.2f})"
                        )
                d._trigger_tracker.record(
                    "watchdog", f"checks={len(watchdog_results)}"
                )

                # OfflineCatchup: DeepSeek恢复后补课
                if d._can_call_deepseek() and d._offline_catchup.has_backlog():
                    backlog_events, backlog_pairs = d._offline_catchup.drain_backlog(
                        max_items=20
                    )
                    if backlog_events:
                        d._trigger_tracker.record(
                            "catchup", f"backlog={len(backlog_events)}"
                        )
                        logger.info(
                            f"[DeepSeek Driver] OfflineCatchup: 补课处理"
                            f"{len(backlog_events)}个积压事件"
                        )
                        for event in backlog_events:
                            d.perceive_decide_act(event)
                    if backlog_pairs and d._learning_engine:
                        try:
                            d._learning_engine.learn_from_causal_pairs(
                                causal_pairs=backlog_pairs,
                                effectiveness_summary=(
                                    d._causal_recorder.get_action_effectiveness_summary()
                                ),
                                decision_engine=d.decision_engine,
                            )
                        except Exception as e:
                            logger.error(f"OfflineCatchup LEARN failed: {e}")

                # 全系统进化闭环: 驱动所有模块的EvolutionLoop tick
                if d._module_loops:
                    module_results = d._tick_all_module_loops()
                    for mr in module_results:
                        if mr and mr.summary:
                            logger.info(
                                f"[DeepSeek Driver] 模块进化: {mr.module_name} "
                                f"{mr.phase.value} — {mr.summary}"
                            )
                    d._trigger_tracker.record(
                        "module_tick", f"modules={len(module_results)}"
                    )

                if d._evo_loop is not None:
                    try:
                        d._evo_loop.tick()
                    except Exception:
                        pass

                if not events:
                    idle_result = d._urgency_accumulator.tick_idle()
                    if idle_result.get("trigger_deep_think"):
                        logger.info("[DeepSeek Driver] 空闲超时触发主动深度思考")
                        d.trigger_deep_think()
                    d._trigger_tracker.record("idle")
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Driver main loop error: {e}")
                time.sleep(5)
