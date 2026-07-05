# -*- coding: utf-8-sig -*-
r"""
DeepSeek驾驶者 · 决策引擎子模块 (Decision Engine)  [v10-ready]
==============================================================
从 core/deepseek_driver.py 拆分而来 (P1-02)。

职责: 事件感知后的决策生成
  - quick_decide   : 规则快速决策 (<1ms, 无LLM)
  - deepseek_decide: LLM驱动决策
  - fallback_decide: LLM不可用时的规则降级决策
  - evaluate_evolution_value / rule_based_evolution_eval: 进化价值评估

同时承载驱动域的基础数据模型:
  - EventType / TianjiEvent : 事件类型枚举与事件对象
  - DriverDecision          : 决策结果
  - EvolutionSignal         : 进化信号

设计约束:
  - 不直接 import core/ 顶层其他模块；外部依赖(LLM引擎/可变规则/统计)通过构造函数注入。
  - LocalEventBus 迁移: 当前内建 EventType/TianjiEvent 与 core.shared.events.DomainEvent
    模型差异较大(本模块为强类型枚举事件 + 队列驱动)，暂保留内建实现。
    # TODO: [v10-ready] 迁移至 core.shared.events.LocalEventBus / DomainEvent
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("tianji.driver")

# === ICME闭环持久化 ===

_TIANJI_API_BASE = "http://localhost:8771/api/memory/"


def _persist_to_icme(content: str, layer: str, tags: list[str], priority: str = "medium") -> str | None:
    """将决策记录持久化到ICME记忆系统，实现决策闭环。

    Args:
        content: 记忆内容
        layer: 目标层级 (sensory/working/short_term/episodic/semantic/meta)
        tags: 标签列表
        priority: 优先级 (low/medium/high)

    Returns:
        记忆条目ID，失败返回None
    """
    try:
        payload = json.dumps({
            "content": content,
            "layer": layer,
            "tags": tags,
            "priority": priority,
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            _TIANJI_API_BASE,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            entry_id = data.get("id") or data.get("memory_id")
            if entry_id:
                logger.debug(f"[ICME闭环] 决策已持久化: id={entry_id} layer={layer}")
            return entry_id
    except Exception as e:
        logger.debug(f"[ICME闭环] 持久化失败(非致命): {e}")
        return None


# === 事件模型 ===  [v10-ready]


class EventType(str, Enum):
    CONVERSATION_INPUT = "conversation_input"
    CONVERSATION_OUTPUT = "conversation_output"
    CONVERSATION_COMPLETE = "conversation_complete"
    FILE_CHANGED = "file_changed"
    AGENT_SWITCH = "agent_switch"
    MCP_TOOL_CALL = "mcp_tool_call"
    ERROR_OCCURRED = "error_occurred"
    SYSTEM_STATUS = "system_status"
    USER_ACTION = "user_action"
    TIMER_TICK = "timer_tick"
    EVOLUTION_TRIGGER = "evolution_trigger"
    DEEP_THINK_TRIGGER = "deep_think_trigger"


@dataclass
class TianjiEvent:
    event_type: EventType
    source: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            import hashlib

            raw = f"{self.event_type}:{self.source}:{self.timestamp}"
            self.event_id = hashlib.md5(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


@dataclass
class DriverDecision:
    action: str
    target_layer: str
    tags: list[str]
    priority: str
    confidence: float
    reason: str
    enriched_content: str = ""
    should_store: bool = True
    should_consolidate: bool = False
    should_merge: bool = False
    should_link: bool = False
    should_evolve: bool = False
    related_queries: list[str] = field(default_factory=list)
    evolution_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "target_layer": self.target_layer,
            "tags": self.tags,
            "priority": self.priority,
            "confidence": self.confidence,
            "reason": self.reason,
            "enriched_content": self.enriched_content[:500],
            "should_store": self.should_store,
            "should_consolidate": self.should_consolidate,
            "should_merge": self.should_merge,
            "should_link": self.should_link,
            "should_evolve": self.should_evolve,
        }


@dataclass
class EvolutionSignal:
    signal_type: str
    source_layer: str
    content_summary: str
    evolution_value: float
    reason: str
    suggested_action: str
    confidence: float
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type,
            "source_layer": self.source_layer,
            "content_summary": self.content_summary[:300],
            "evolution_value": self.evolution_value,
            "reason": self.reason,
            "suggested_action": self.suggested_action,
            "confidence": self.confidence,
        }


# === 系统提示词 ===  [v10-ready]

DRIVER_SYSTEM_PROMPT = """你是天机天机v9.1的驾驶者（Driver）。你不是被动的工具，你是主动的大脑。

你的职责是：感知事件 → 理解含义 → 做出决策 → 驱动行动 → 观测效果 → 学习进化

记忆层级体系（ICME六层）:
- sensory(L0): 原始感知快照，自动捕获，24小时有效
- working(L1): 当前工作上下文，跨轮次保持
- short_term(L2): 近期关键信息，几天有效
- episodic(L3): 事件经历记录，重要节点
- semantic(L4): 知识概念库，长期有效
- meta(L5): 系统策略规则，最高级

你的决策原则:
1. 对话内容 → 必须存储（这是用户最核心的需求）
2. 重要决策 → 存入episodic或更高层
3. 错误信息 → 存入episodic + 标记教训
4. 系统变更 → 存入meta层
5. 日常闲聊 → 存入sensory，低优先级
6. 重复信息 → 跳过存储，但更新访问时间

进化评估原则:
1. 可复用性: 此经验能否被其他Agent/场景复用?
2. 可泛化性: 此经验能否提炼为通用规则?
3. 紧迫性: 不处理会导致系统退化吗?
4. 新颖性: 这是系统从未见过的新模式吗?

你必须返回有效的JSON。"""

EVOLUTION_EVAL_PROMPT = """你是天机系统的进化评估者。你需要评估以下信号是否值得触发系统自我进化。

评估维度:
1. 可复用性 (0-1): 此经验能否被其他Agent/场景复用?
2. 可泛化性 (0-1): 此经验能否提炼为通用规则?
3. 紧迫性 (0-1): 不处理会导致系统退化吗?
4. 新颖性 (0-1): 这是系统从未见过的新模式吗?

进化价值 = 可复用性*0.3 + 可泛化性*0.3 + 紧迫性*0.25 + 新颖性*0.15

如果进化价值 > 0.7，建议触发进化行动。
如果进化价值 > 0.5，建议记录到观察队列。
如果进化价值 < 0.5，建议跳过。

返回JSON:
{"reusable": 0.8, "generalizable": 0.7, "urgent": 0.6, "novel": 0.5, "evolution_value": 0.68, "suggested_action": "record", "reason": "此错误模式可泛化为通用规则"}"""


# === 默认可变规则 ===  [v10-ready]

DEFAULT_MUTABLE_RULES: dict[str, Any] = {
    "error_target_layer": "episodic",
    "conversation_target_layer": "sensory",
    "complete_conversation_target_layer": "working",
    "deep_think_interval": 300.0,
    "evolution_interval": 86400.0,
    "complexity_threshold_mcp_calls": 5,
    "complexity_threshold_duration_ms": 30000,
}


class DecisionEngine:
    """
    决策引擎 — 驱动域的"感知→决策"核心  [v10-ready]

    封装 quick_decide / deepseek_decide / fallback_decide 三级决策，
    以及进化价值评估。所有外部依赖通过构造函数注入:
      - llm_engine        : LLM存储决策引擎 (含 is_ready / decide_storage / client)
      - mutable_rules     : 共享可变规则字典 (与 DeepSeekDriver 共享同一引用)
      - min_deepseek_interval: DeepSeek调用最小间隔(秒)
      - stats             : 共享统计字典 (errors 等计数写回同一引用)
    """

    def __init__(
        self,
        llm_engine: Any | None = None,
        mutable_rules: dict[str, Any] | None = None,
        min_deepseek_interval: float = 2.0,
        stats: dict[str, Any] | None = None,
    ):
        self._llm_engine = llm_engine
        self._mutable_rules = (
            mutable_rules if mutable_rules is not None else dict(DEFAULT_MUTABLE_RULES)
        )
        self._min_deepseek_interval = min_deepseek_interval
        self._last_deepseek_call = 0.0
        self._stats = stats if stats is not None else {"errors": 0}

    @property
    def llm_engine(self) -> Any:
        return self._llm_engine

    @llm_engine.setter
    def llm_engine(self, engine: Any) -> None:
        self._llm_engine = engine

    def mark_deepseek_called(self) -> None:
        """记录一次DeepSeek调用时间 — 用于调用频率节流"""
        self._last_deepseek_call = time.time()

    def can_call_deepseek(self) -> bool:
        if not self._llm_engine or not self._llm_engine.is_ready:
            return False
        elapsed = time.time() - self._last_deepseek_call
        return elapsed >= self._min_deepseek_interval

    def quick_decide(self, event: TianjiEvent) -> DriverDecision | None:
        if event.event_type == EventType.CONVERSATION_INPUT:
            decision = DriverDecision(
                action="store_conversation_input",
                target_layer=self._mutable_rules["conversation_target_layer"],
                tags=["conversation", "user_input", event.source],
                priority="high",
                confidence=0.95,
                reason="用户输入必须记录",
                enriched_content=event.payload.get("content", ""),
                should_store=True,
            )
            self._record_decision_to_icme(decision, event)
            return decision

        if event.event_type == EventType.CONVERSATION_OUTPUT:
            decision = DriverDecision(
                action="store_conversation_output",
                target_layer=self._mutable_rules["conversation_target_layer"],
                tags=["conversation", "ai_response", event.source],
                priority="high",
                confidence=0.95,
                reason="AI响应必须记录",
                enriched_content=event.payload.get("content", ""),
                should_store=True,
            )
            self._record_decision_to_icme(decision, event)
            return decision

        if event.event_type == EventType.CONVERSATION_COMPLETE:
            decision = DriverDecision(
                action="store_complete_conversation",
                target_layer=self._mutable_rules["complete_conversation_target_layer"],
                tags=["conversation", "complete", event.source],
                priority="high",
                confidence=0.90,
                reason="完整对话必须记录到工作记忆",
                enriched_content=event.payload.get("full_conversation", ""),
                should_store=True,
                should_consolidate=True,
            )
            self._record_decision_to_icme(decision, event)
            return decision

        if event.event_type == EventType.ERROR_OCCURRED:
            decision = DriverDecision(
                action="store_error",
                target_layer=self._mutable_rules["error_target_layer"],
                tags=["error", "traceback", event.source],
                priority="high",
                confidence=0.90,
                reason="错误必须记录用于回溯",
                enriched_content=event.payload.get("error_message", ""),
                should_store=True,
            )
            self._record_decision_to_icme(decision, event)
            return decision

        if event.event_type == EventType.TIMER_TICK:
            return None

        if event.event_type == EventType.SYSTEM_STATUS:
            return None

        return None

    def _record_decision_to_icme(self, decision: DriverDecision, event: TianjiEvent) -> None:
        """将决策结果持久化到ICME记忆系统，实现决策闭环。"""
        content = (
            f"[决策引擎] action={decision.action} layer={decision.target_layer} "
            f"confidence={decision.confidence:.2f} reason={decision.reason}"
        )
        if decision.enriched_content:
            content += f" | content={decision.enriched_content[:200]}"
        _persist_to_icme(
            content=content,
            layer="episodic",
            tags=["decision", decision.action, event.event_type.value] + decision.tags[:3],
            priority=decision.priority,
        )

    def deepseek_decide(self, event: TianjiEvent) -> DriverDecision | None:
        try:
            content = event.payload.get("content", "")
            if not content or len(content.strip()) < 10:
                return None

            context = {
                "event_type": event.event_type.value,
                "source": event.source,
                "timestamp": datetime.fromtimestamp(event.timestamp).isoformat(),
            }

            storage_decision = self._llm_engine.decide_storage(content, context)

            should_evolve = storage_decision.value_score > 0.8 and event.event_type in (
                EventType.ERROR_OCCURRED,
                EventType.AGENT_SWITCH,
                EventType.CONVERSATION_COMPLETE,
            )

            decision = DriverDecision(
                action="deepseek_driven_store",
                target_layer=storage_decision.layer,
                tags=storage_decision.tags,
                priority=storage_decision.priority,
                confidence=storage_decision.confidence,
                reason=storage_decision.reason,
                enriched_content=storage_decision.summary or content,
                should_store=storage_decision.should_store,
                should_consolidate=storage_decision.value_score > 0.7,
                should_evolve=should_evolve,
            )
            self._record_decision_to_icme(decision, event)
            return decision
        except Exception as e:
            logger.error(f"DeepSeek decide error: {e}")
            self._stats["errors"] = self._stats.get("errors", 0) + 1
            return self.fallback_decide(event)

    def fallback_decide(self, event: TianjiEvent) -> DriverDecision:
        content = event.payload.get("content", "")
        layer_map = {
            EventType.CONVERSATION_INPUT: self._mutable_rules[
                "conversation_target_layer"
            ],
            EventType.CONVERSATION_OUTPUT: self._mutable_rules[
                "conversation_target_layer"
            ],
            EventType.CONVERSATION_COMPLETE: self._mutable_rules[
                "complete_conversation_target_layer"
            ],
            EventType.ERROR_OCCURRED: self._mutable_rules["error_target_layer"],
            EventType.AGENT_SWITCH: "episodic",
            EventType.MCP_TOOL_CALL: "sensory",
            EventType.FILE_CHANGED: "sensory",
            EventType.USER_ACTION: "working",
        }
        decision = DriverDecision(
            action="fallback_store",
            target_layer=layer_map.get(event.event_type, "sensory"),
            tags=[event.event_type.value, event.source, "fallback"],
            priority="medium",
            confidence=0.5,
            reason="DeepSeek不可用，使用规则降级",
            enriched_content=content,
            should_store=True,
        )
        self._record_decision_to_icme(decision, event)
        return decision

    def evaluate_evolution_value(self, signals: list[dict]) -> EvolutionSignal | None:
        """DeepSeek评估进化价值 — EVALUATE核心"""
        if not signals:
            return None

        if not self.can_call_deepseek():
            return self.rule_based_evolution_eval(signals)

        try:
            signal_summary = json.dumps(signals[:10], ensure_ascii=False)[:2000]
            prompt = f"""请评估以下天机系统信号的进化价值:

信号列表:
{signal_summary}

请评估每个维度的分数(0-1)并给出建议行动。"""

            result = self._llm_engine.client.chat_sync(prompt, EVOLUTION_EVAL_PROMPT)

            evolution_value = result.get("evolution_value", 0.5)
            return EvolutionSignal(
                signal_type="deep_seek_evaluated",
                source_layer="multi",
                content_summary=signal_summary[:300],
                evolution_value=evolution_value,
                reason=result.get("reason", ""),
                suggested_action=result.get("suggested_action", "record"),
                confidence=min(1.0, evolution_value),
                payload=result,
            )
        except Exception as e:
            logger.warning(f"DeepSeek evolution eval failed: {e}")
            return self.rule_based_evolution_eval(signals)

    def rule_based_evolution_eval(self, signals: list[dict]) -> EvolutionSignal | None:
        if not signals:
            return None

        total_signals = len(signals)
        evolution_value = min(1.0, total_signals / 20.0)

        if evolution_value < 0.3:
            return None

        return EvolutionSignal(
            signal_type="rule_based_eval",
            source_layer="multi",
            content_summary=f"{total_signals}个未消化信号",
            evolution_value=evolution_value,
            reason=f"发现{total_signals}个未消化信号，需要处理",
            suggested_action="process" if evolution_value > 0.7 else "record",
            confidence=evolution_value * 0.8,
        )
