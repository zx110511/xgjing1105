r"""
DeepSeek驾驶者引擎 (DeepSeek Driver Engine) v2.2 — SSS级进化版 · 路由层  [v10-ready]
====================================================================================
让DeepSeek从"被调用的工具"变成"主动驾驶者+自我进化者"

v1.0: Perceive → Decide → Act (反应式)
v2.0: 三循环并行驾驶 + OBSERVE因果对 + EVOLVE自修改
v2.1: 进化总线 + 模块闭环注册 + 离线补课
v2.2: M15升级 — EvolutionLoop(共享) record_action喂入 + recorder/learning_engine双注入 + health()

P1-02 拆分: 本文件瘦身为"路由层"，DeepSeekDriver 组合调用 core/driver/ 子包:
  - core/driver/decision.py     : 决策引擎 + 事件/决策数据模型
  - core/driver/causal.py       : 因果对记录 + 离线补课
  - core/driver/urgency.py      : 紧迫度累积 + 效果看门狗
  - core/driver/orchestrator.py : 三循环编排 + 触发管理 + 进化集成

兼容性: 历史符号 (DeepSeekDriver / EventBus / TianjiEvent / EventType /
        CausalPairRecorder / CausalPair / EvolutionSignal / DriverDecision /
        TraeConversationCapture / UrgencyAccumulator / EffectWatchdog /
        OfflineCatchup / ThreeCycleOrchestrator) 继续从本模块对外暴露。

灵境道谱溯源: D2-1【三循环驾驶煞】· 道二·认知体 · 四地煞之智之术

# TODO: [v10-ready] EventBus/TianjiEvent/EventType 与 core.shared.events.LocalEventBus
#       (DomainEvent) 模型差异较大(本模块为强类型枚举事件 + 队列 drain 驱动)，
#       暂保留内建实现；后续统一迁移至 core.shared.events。
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

try:
    from .config import MEMORY_DATA_PATH
except ImportError:
    from core.shared.config import MEMORY_DATA_PATH

_DATA_DIR = MEMORY_DATA_PATH  # v9.1: 统一到 data/.memory

try:
    from ..processors.evolution_loop import CausalPairRecorder as SharedCausalPairRecorder
    from ..processors.evolution_loop import EvolutionLoop as EvolutionLoopShared
except ImportError:
    EvolutionLoopShared = None
    SharedCausalPairRecorder = None

# === 子包符号导入(组合 + 兼容再导出) ===  [v10-ready]
from .driver.causal import CausalPair, CausalPairRecorder, OfflineCatchup
from .driver.decision import (
    DRIVER_SYSTEM_PROMPT,
    EVOLUTION_EVAL_PROMPT,
    DecisionEngine,
    DriverDecision,
    EventType,
    EvolutionSignal,
    TianjiEvent,
)
from .driver.orchestrator import DriverOrchestrator, TriggerFrequencyTracker
from .driver.urgency import EffectWatchdog, UrgencyAccumulator

logger = logging.getLogger("tianji.driver")


# [FIX-driver-001] boot_registry调用DeepSeekDriver()无参时提供默认EventBus
# 避免NameError/TypeError, 实际使用时由server/main.py注入完整实例
_default_event_bus = None


def get_or_create_event_bus():
    """获取或创建全局EventBus单例"""
    global _default_event_bus
    if _default_event_bus is None:
        _default_event_bus = EventBus()
    return _default_event_bus


class EventBus:
    """事件总线 — 天机的感知神经系统

    # TODO: [v10-ready] 迁移至 core.shared.events.LocalEventBus
    #       (当前为队列 drain 模型，与 LocalEventBus 的 handler 派发模型差异较大，暂保留)
    """

    def __init__(self, max_queue: int = 1000):
        self._queue: list[TianjiEvent] = []
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Callable]] = {}
        self._max_queue = max_queue
        self._event_count = 0

    def publish(self, event: TianjiEvent):
        with self._lock:
            if len(self._queue) >= self._max_queue:
                self._queue = self._queue[-self._max_queue // 2 :]
            self._queue.append(event)
            self._event_count += 1

        for sub_id, callbacks in self._subscribers.items():
            for cb in callbacks:
                try:
                    cb(event)
                except Exception as e:
                    logger.warning(f"Subscriber {sub_id} error: {e}")

    def subscribe(self, subscriber_id: str, callback: Callable):
        with self._lock:
            if subscriber_id not in self._subscribers:
                self._subscribers[subscriber_id] = []
            self._subscribers[subscriber_id].append(callback)

    def drain(self, max_items: int = 50) -> list[TianjiEvent]:
        with self._lock:
            items = self._queue[:max_items]
            self._queue = self._queue[max_items:]
            return items

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def total_count(self) -> int:
        return self._event_count

    def register_module_loop(self, module_name: str, loop: Any):
        self.subscribe(f"evo_loop_{module_name}", lambda evt: None)

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total_callbacks = sum(len(cbs) for cbs in self._subscribers.values())
            return {
                "version": "1.0",
                "event_count": self._event_count,
                "pending_count": len(self._queue),
                "max_queue": self._max_queue,
                "subscriber_count": len(self._subscribers),
                "callback_count": total_callbacks,
                "queue_utilization": round(
                    len(self._queue) / max(self._max_queue, 1), 4
                ),
                "dropped_events": getattr(self, "_dropped_events", 0),
            }


class DeepSeekDriver:
    """
    DeepSeek驾驶者 v2.2 — 天机的主动大脑 + 自我进化者 · 路由层  [v10-ready]

    v1.0: 被动感知-决策-行动
    v2.0: 三循环并行驾驶 + OBSERVE因果对 + LEARN+EVOLVE闭环

    路由层职责: 持有并组合各子组件，公开方法委托至:
      - self._decision     : DecisionEngine    (decision.py)
      - self._orchestrator : DriverOrchestrator (orchestrator.py)
      - self._causal_recorder / self._urgency_accumulator /
        self._effect_watchdog / self._offline_catchup : 因果/紧迫度组件

    循环A: 快速反应环 (< 100ms) — 事件到达 → quick_decide → act
    循环B: 深度思考环 (每5分钟) — 扫描盲区 → 评估进化价值 → 执行优化 → 记录因果对
    循环C: 进化反思环 (每天1次) — 汇总因果对 → 三层学习 → 修改规则
    """

    def __init__(
        self,
        event_bus: EventBus,
        memory_engine=None,
        decision_engine=None,
        config: dict | None = None,
        recorder: Any | None = None,
        learning_engine: Any | None = None,
    ):
        self.event_bus = event_bus
        self.memory_engine = memory_engine
        self.decision_engine = decision_engine
        self._config = config or {}
        self._running = False
        self._thread = None
        self._deep_think_interval = self._config.get("deep_think_interval", 300.0)
        self._evolution_interval = self._config.get("evolution_interval", 86400.0)

        self._recorder = recorder
        self._shared_learning_engine = learning_engine

        self._causal_recorder = CausalPairRecorder(
            max_pairs=self._config.get("max_causal_pairs", 5000),
            persist_dir=Path(
                self._config.get("causal_persist_dir", str(_DATA_DIR / "causal_pairs"))
            ),
        )

        from ..processors.evolution_engine import EvolutionEngine

        self._evolution_engine = EvolutionEngine(
            config=self._config.get("evolution", {}),
            persist_dir=Path(
                self._config.get(
                    "evolution_persist_dir", str(_DATA_DIR / "evolution_history")
                )
            ),
        )
        self._learning_engine = self._shared_learning_engine

        self._evo_loop = None
        if EvolutionLoopShared is not None:
            try:
                self._evo_loop = EvolutionLoopShared(
                    module_name="deepseek_driver",
                    effectiveness_fn=self._calc_driver_effectiveness,
                    learn_fn=self._learn_from_driver,
                    evolve_fn=self._evolve_driver_config,
                    mutable_config={
                        "deep_think_interval": self._deep_think_interval,
                        "evolution_interval": self._evolution_interval,
                        "driver_effectiveness_avg": 0.5,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception as e:
                logger.warning(f"EvolutionLoop init failed: {e}")

        self._urgency_accumulator = UrgencyAccumulator()
        self._effect_watchdog = EffectWatchdog(
            observe_window=self._config.get("effect_observe_window", 1800.0)
        )
        self._offline_catchup = OfflineCatchup(
            max_backlog=self._config.get("max_backlog", 500)
        )

        self._trigger_tracker = TriggerFrequencyTracker()

        self._evolution_bus = None
        self._module_loops: dict[str, Any] = {}

        self._last_deep_think = 0.0
        self._last_evolution_cycle = 0.0

        self._stats = {
            "events_perceived": 0,
            "decisions_made": 0,
            "actions_executed": 0,
            "deepseek_calls": 0,
            "errors": 0,
            "deep_think_cycles": 0,
            "evolution_cycles": 0,
            "causal_pairs_recorded": 0,
            "evolution_signals_detected": 0,
            "rules_modified": 0,
            "skills_auto_created": 0,
        }
        self._processed_ids = set()
        self._last_deepseek_call = 0.0
        self._min_deepseek_interval = self._config.get("min_deepseek_interval", 2.0)

        self._mutable_rules = {
            "error_target_layer": "episodic",
            "conversation_target_layer": "sensory",
            "complete_conversation_target_layer": "working",
            "deep_think_interval": 300.0,
            "evolution_interval": 86400.0,
            "complexity_threshold_mcp_calls": 5,
            "complexity_threshold_duration_ms": 30000,
        }

        # 组合子模块: 决策引擎(共享 mutable_rules / stats) + 三循环编排器
        self._decision = DecisionEngine(
            llm_engine=self.decision_engine,
            mutable_rules=self._mutable_rules,
            min_deepseek_interval=self._min_deepseek_interval,
            stats=self._stats,
        )
        self._orchestrator = DriverOrchestrator(self)

        self.event_bus.subscribe("deepseek_driver", self._on_event)

    def set_evolution_engine(self, engine):
        self._evolution_engine = engine

    def set_learning_engine(self, engine):
        self._learning_engine = engine

    # === EvolutionLoop 双注入回调 (保持兼容) ===  [v10-ready]

    def _calc_driver_effectiveness(
        self, action: str, state_before: dict[str, Any], state_after: dict[str, Any]
    ) -> float:
        if action == "driver_act":
            delta = state_after.get("actions_performed", 0) - state_before.get(
                "actions_performed", 0
            )
            errors = state_after.get("error_count", 0) - state_before.get(
                "error_count", 0
            )
            if errors > 0:
                return -0.3 * errors
            if delta > 0:
                return min(0.8, delta * 0.15)
            return 0.1
        elif action == "deep_think_cycle":
            signals = state_after.get("signals_detected", 0)
            processes = state_after.get("signals_processed", 0)
            if signals == 0:
                return 0.0
            return min(0.6, processes / max(signals, 1) * 0.5)
        elif action == "evolution_cycle":
            rules = state_after.get("rules_modified", 0)
            skills = state_after.get("skills_created", 0)
            score = rules * 0.3 + skills * 0.2
            return min(0.8, max(-0.4, score))
        return 0.0

    def _learn_from_driver(
        self, causal_pairs: list[Any], effectiveness_summary: dict[str, Any]
    ) -> dict[str, Any]:
        avg_eff = effectiveness_summary.get("avg_effectiveness", 0.0)
        return {
            "patterns_found": len(causal_pairs),
            "driver_effectiveness_avg": avg_eff,
            "strategies_optimized": 1 if avg_eff < 0 else 0,
        }

    def _evolve_driver_config(
        self, learn_result: dict[str, Any], mutable_config: dict[str, Any]
    ) -> dict[str, Any]:
        changes = {}
        avg_eff = learn_result.get("driver_effectiveness_avg", 0.5)
        if avg_eff < -0.2 and mutable_config.get("deep_think_interval", 300) > 120:
            changes["deep_think_interval"] = max(
                120, mutable_config["deep_think_interval"] - 60
            )
        if avg_eff > 0.3 and mutable_config.get("deep_think_interval", 300) < 600:
            changes["deep_think_interval"] = min(
                600, mutable_config["deep_think_interval"] + 60
            )
        return {"rules_modified": changes, "skills_created": []}

    def _on_event(self, event: TianjiEvent):
        if event.event_id in self._processed_ids:
            return
        self._processed_ids.add(event.event_id)
        if len(self._processed_ids) > 10000:
            self._processed_ids = set(list(self._processed_ids)[-5000:])

    # === 感知 → 决策 → 行动 (委托子模块) ===  [v10-ready]

    def _can_call_deepseek(self) -> bool:
        return self._decision.can_call_deepseek()

    def perceive(self, event: TianjiEvent) -> DriverDecision | None:
        self._stats["events_perceived"] += 1

        quick_decision = self._decision.quick_decide(event)
        if quick_decision is not None:
            self._stats["decisions_made"] += 1
            return quick_decision

        if not self._decision.can_call_deepseek():
            return self._decision.fallback_decide(event)

        decision = self._decision.deepseek_decide(event)
        if decision:
            self._stats["decisions_made"] += 1
            self._stats["deepseek_calls"] += 1
            self._decision.mark_deepseek_called()
            self._last_deepseek_call = time.time()
        return decision

    def act(self, decision: DriverDecision) -> bool:
        return self._orchestrator.act(decision)

    def perceive_decide_act(self, event: TianjiEvent) -> dict | None:
        decision = self.perceive(event)
        if decision is None:
            return None

        success = self.act(decision)
        return {
            "event_id": event.event_id,
            "decision": decision.to_dict(),
            "action_result": success,
        }

    # === 生命周期 ===  [v10-ready]

    def start(self):
        if self._running:
            return
        self._running = True
        self.evolution_loop = self._evo_loop
        self._thread = threading.Thread(
            target=self._orchestrator.run_main_loop, daemon=True
        )
        self._thread.start()
        logger.info(
            "DeepSeek Driver v2.2 started — 天机自我进化大脑已激活 · D2-1三循环驾驶煞"
        )

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("DeepSeek Driver stopped")

    # === 状态/健康 ===  [v10-ready]

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "version": "2.2",
            **self._stats,
            "pending_events": self.event_bus.pending_count,
            "total_events": self.event_bus.total_count,
            "deepseek_ready": (
                self.decision_engine.is_ready if self.decision_engine else False
            ),
            "causal_recorder": self._causal_recorder.get_stats(),
            "evolution_engine": self._evolution_engine.get_stats()
            if self._evolution_engine
            else {},
            "mutable_rules": dict(self._mutable_rules),
            "last_deep_think": self._last_deep_think,
            "last_evolution_cycle": self._last_evolution_cycle,
            "closed_loop_status": {
                "OBSERVE": "active" if self._causal_recorder else "inactive",
                "LEARN": "active" if self._learning_engine else "inactive",
                "EVOLVE": "active" if self._evolution_engine else "inactive",
            },
            "urgency_accumulator": self._urgency_accumulator.get_stats(),
            "effect_watchdog": self._effect_watchdog.get_stats(),
            "offline_catchup": self._offline_catchup.get_stats(),
            "evolution_bus": self._evolution_bus.get_stats()
            if self._evolution_bus
            else {},
            "module_loops": {
                name: loop.get_stats() for name, loop in self._module_loops.items()
            },
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
            "trigger_frequency": self._trigger_tracker.get_frequency(),
            "health": self.health(),
        }

    def health(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "version": "2.2",
            "deepseek_ready": (
                self.decision_engine.is_ready if self.decision_engine else False
            ),
            "memory_engine_attached": self.memory_engine is not None,
            "events_pending": self.event_bus.pending_count,
            "evolution_engine_active": self._evolution_engine is not None,
            "learning_engine_active": self._learning_engine is not None,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
            "urgency_level": self._urgency_accumulator.urgency,
            "causal_pairs_total": self._stats["causal_pairs_recorded"],
            "errors": self._stats["errors"],
            "closed_loop": (
                self._causal_recorder is not None
                and self._learning_engine is not None
                and self._evolution_engine is not None
            ),
        }

    def get_trigger_frequency(self, window_seconds: float = 3600) -> dict:
        return self._trigger_tracker.get_frequency(window_seconds)

    # === 手动触发 (委托编排器) ===  [v10-ready]

    def trigger_deep_think(self) -> dict | None:
        """手动触发深度思考 — 供外部调用"""
        self._last_deep_think = time.time()
        self._orchestrator.deep_think_cycle()
        return {"triggered": "deep_think", "stats": self.get_stats()}

    def trigger_evolution(self) -> dict | None:
        """手动触发进化反思 — 供外部调用"""
        self._last_evolution_cycle = time.time()
        self._orchestrator.evolution_cycle()
        return {"triggered": "evolution", "stats": self.get_stats()}

    # === 模块进化闭环注册 ===  [v10-ready]

    def register_module_loop(self, module_name: str, loop: Any):
        """
        注册模块进化闭环到全局总线

        当模块创建了EvolutionLoop后，通过此方法注册到Driver，
        Driver负责:
          1. 将模块的EvolutionLoop注册到EvolutionBus
          2. 在主循环中调用每个模块的tick()
          3. 汇总所有模块的进化状态
        """
        self._module_loops[module_name] = loop

        if self._evolution_bus is None:
            try:
                from ..processors.evolution_loop import EvolutionBus

                self._evolution_bus = EvolutionBus()
            except ImportError:
                return

        self._evolution_bus.register_loop(loop)
        logger.info(f"[DeepSeek Driver] 模块'{module_name}'进化闭环已注册到全局总线")

    def _tick_all_module_loops(self):
        """驱动所有模块的进化闭环tick — 在主循环中调用"""
        results = []
        for module_name, loop in self._module_loops.items():
            try:
                loop_results = loop.tick()
                if loop_results:
                    results.extend(loop_results)
            except Exception as e:
                logger.debug(
                    f"[DeepSeek Driver] Module loop tick error ({module_name}): {e}"
                )
        return results


class TraeConversationCapture:
    """
    Trae对话捕获器 — 天机的"眼睛"
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._session_context = {}

    def on_user_input(
        self,
        user_input: str,
        session_id: str = "",
        platform: str = "trae",
        context: dict | None = None,
    ):
        self.event_bus.publish(
            TianjiEvent(
                event_type=EventType.CONVERSATION_INPUT,
                source=platform,
                payload={
                    "content": user_input,
                    "session_id": session_id,
                    "context": context or {},
                },
            )
        )
        self._session_context[session_id] = {
            "user_input": user_input,
            "timestamp": time.time(),
            "context": context or {},
        }

    def on_ai_response(
        self,
        ai_response: str,
        session_id: str = "",
        platform: str = "trae",
        agent_id: str = "",
    ):
        self.event_bus.publish(
            TianjiEvent(
                event_type=EventType.CONVERSATION_OUTPUT,
                source=platform,
                payload={
                    "content": ai_response,
                    "session_id": session_id,
                    "agent_id": agent_id,
                },
            )
        )

    def on_conversation_complete(
        self,
        user_input: str,
        ai_response: str,
        session_id: str = "",
        platform: str = "trae",
    ):
        full_conv = f"用户: {user_input}\n\nAI: {ai_response}"
        self.event_bus.publish(
            TianjiEvent(
                event_type=EventType.CONVERSATION_COMPLETE,
                source=platform,
                payload={
                    "full_conversation": full_conv,
                    "user_input": user_input,
                    "ai_response": ai_response,
                    "session_id": session_id,
                },
            )
        )


class ThreeCycleOrchestrator:
    """
    三循环解耦编排器 — 将DeepSeek Driver的三个循环从紧密耦合改为事件驱动

    原本: 循环A/B/C在driver主线程中串行，耦合度高
    解耦后:
      - 循环A (快速反应): ThreadPool + 事件订阅，<100ms延迟
      - 循环B (深度思考): Timer每5分钟 + UrgencyThreshold触发
      - 循环C (进化反思): CRON每日+EvolutionThreshold累积触发
    """

    def __init__(self, driver: "DeepSeekDriver", max_workers: int = 4):
        self._driver = driver
        # 持有底层功能编排器(DriverOrchestrator)引用，用于兼容委托
        # (deep_think_cycle / evolution_cycle / act)。构造时 driver._orchestrator
        # 仍为原始 DriverOrchestrator(容器在本对象创建后才会改写该属性)。
        self._delegate = getattr(driver, "_orchestrator", None)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="tianji-cycle"
        )
        self._running = False
        self._lock = threading.Lock()
        self._loop_b_timer: threading.Timer | None = None
        self._loop_c_timer: threading.Timer | None = None
        self._stats = {
            "cycle_a_fast_reacts": 0,
            "cycle_b_deep_thinks": 0,
            "cycle_c_evolutions": 0,
            "events_processed": 0,
            "total_futures": 0,
        }

    def start(self, loop_b_interval: float = 300.0, loop_c_interval: float = 86400.0):
        with self._lock:
            if self._running:
                return
            self._running = True

        self._driver.event_bus.subscribe("*", self._on_event)

        self._schedule_loop_b(loop_b_interval)
        self._schedule_loop_c(loop_c_interval)

        return True

    def stop(self):
        with self._lock:
            self._running = False

        if self._loop_b_timer:
            self._loop_b_timer.cancel()
            self._loop_b_timer = None
        if self._loop_c_timer:
            self._loop_c_timer.cancel()
            self._loop_c_timer = None

        self._executor.shutdown(wait=False)

    def _on_event(self, event: TianjiEvent):
        if not self._running:
            return
        self._stats["events_processed"] += 1

        future = self._executor.submit(self._cycle_a_worker, event)
        self._stats["total_futures"] += 1

        urgency = self._driver._urgency_accumulator._urgency
        trigger_b = urgency >= self._driver._urgency_accumulator.DEEP_THINK_THRESHOLD
        trigger_c = urgency >= self._driver._urgency_accumulator.EVOLUTION_THRESHOLD

        if trigger_c:
            self._executor.submit(self._cycle_c_worker)
            self._stats["cycle_c_evolutions"] += 1
        if trigger_b:
            self._executor.submit(self._cycle_b_worker)
            self._stats["cycle_b_deep_thinks"] += 1

        if trigger_b or trigger_c:
            self._driver._urgency_accumulator.decay()

    def _cycle_a_worker(self, event: TianjiEvent):
        try:
            self._stats["cycle_a_fast_reacts"] += 1
            if event.event_type in (
                EventType.CONVERSATION_INPUT,
                EventType.CONVERSATION_OUTPUT,
            ):
                self._driver.process_event(event)
            elif event.event_type == EventType.DEEP_THINK_TRIGGER:
                self._executor.submit(self._cycle_b_worker)
        except Exception:
            pass

    def _cycle_b_worker(self):
        try:
            self._stats["cycle_b_deep_thinks"] += 1
            self._driver.run_loop_b()
        except Exception:
            pass

    def _cycle_c_worker(self):
        try:
            self._stats["cycle_c_evolutions"] += 1
            self._driver.run_loop_c()
        except Exception:
            pass

    def _schedule_loop_b(self, interval: float):
        if not self._running:
            return
        self._loop_b_timer = threading.Timer(
            interval, self._loop_b_tick, args=[interval]
        )
        self._loop_b_timer.daemon = True
        self._loop_b_timer.start()

    def _loop_b_tick(self, interval: float):
        if self._running:
            self._executor.submit(self._cycle_b_worker)
            self._schedule_loop_b(interval)

    def _schedule_loop_c(self, interval: float):
        if not self._running:
            return
        self._loop_c_timer = threading.Timer(
            interval, self._loop_c_tick, args=[interval]
        )
        self._loop_c_timer.daemon = True
        self._loop_c_timer.start()

    def _loop_c_tick(self, interval: float):
        if self._running:
            self._executor.submit(self._cycle_c_worker)
            self._schedule_loop_c(interval)

    # === DriverOrchestrator 兼容委托接口 ===
    # 容器会将本对象赋给 driver._orchestrator，而 DeepSeekDriver 及其主循环会
    # 通过 _orchestrator 调用 deep_think_cycle / evolution_cycle / act。这里提供
    # 兼容方法，委托给底层 DriverOrchestrator 执行真实逻辑，避免 AttributeError
    # 导致主循环每5秒刷错误日志。

    def deep_think_cycle(self):
        """兼容接口: 委托底层编排器执行深度思考(循环B)；无委托时回退线程池工作线程。"""
        if self._delegate is not None and hasattr(self._delegate, "deep_think_cycle"):
            return self._delegate.deep_think_cycle()
        self._executor.submit(self._cycle_b_worker)
        return None

    def evolution_cycle(self):
        """兼容接口: 委托底层编排器执行进化反思(循环C)；无委托时回退线程池工作线程。"""
        if self._delegate is not None and hasattr(self._delegate, "evolution_cycle"):
            return self._delegate.evolution_cycle()
        self._executor.submit(self._cycle_c_worker)
        return None

    def act(self, decision):
        """兼容接口: 委托底层编排器执行ACT；无委托时返回安全默认值。"""
        if self._delegate is not None and hasattr(self._delegate, "act"):
            return self._delegate.act(decision)
        return True

    def get_stats(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "cycle_a_fast_reacts": self._stats["cycle_a_fast_reacts"],
            "cycle_b_deep_thinks": self._stats["cycle_b_deep_thinks"],
            "cycle_c_evolutions": self._stats["cycle_c_evolutions"],
            "events_processed": self._stats["events_processed"],
            "urgency": round(self._driver._urgency_accumulator._urgency, 2),
        }


__all__ = [
    "DeepSeekDriver",
    "EventBus",
    "TianjiEvent",
    "EventType",
    "DriverDecision",
    "CausalPair",
    "CausalPairRecorder",
    "EvolutionSignal",
    "TraeConversationCapture",
    "UrgencyAccumulator",
    "EffectWatchdog",
    "OfflineCatchup",
    "ThreeCycleOrchestrator",
    "TriggerFrequencyTracker",
    "DecisionEngine",
    "DriverOrchestrator",
    "DRIVER_SYSTEM_PROMPT",
    "EVOLUTION_EVAL_PROMPT",
]
