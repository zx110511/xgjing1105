r"""

工具调用追踪器 (Tool Tracker) — [v10-ready]

=====================================================

天机Agent编排子包·职责2: 工具调用追踪



职责边界:

  - AgentTask / ToolCallRecord 数据结构

  - ToolCallTracker — 每次工具调用强制标注执行Agent

  - 调用统计、按Agent/阶段聚合、TVP流水线可视化



依赖: registry (AGENT_CAPABILITY_MATRIX, PipelineStage)



位置: 天机/core/orchestration/tracker.py

"""



from __future__ import annotations



import threading

import time

import uuid

from collections.abc import Callable

from dataclasses import dataclass, field



from .registry import AGENT_CAPABILITY_MATRIX, PipelineStage



# ═══════════════════════════════════════════════════════════════

# 数据结构

# ═══════════════════════════════════════════════════════════════





@dataclass

class AgentTask:

    task_id: str

    agent_id: str

    agent_name: str

    agent_emoji: str

    stage: PipelineStage

    goal: str

    context: str

    tools_allowed: list[str] = field(default_factory=list)

    priority: str = "high"

    timeout_s: int = 300

    depends_on: list[str] = field(default_factory=list)

    status: str = "pending"





@dataclass

class ToolCallRecord:

    call_id: str

    agent_id: str

    agent_name: str

    agent_emoji: str

    tool_name: str

    stage: PipelineStage

    task_id: str

    timestamp: float

    duration_ms: float = 0

    success: bool = True

    output_summary: str = ""



    def to_tvp(self) -> str:

        return f"[TVP] 🔧 {self.agent_emoji}@{self.agent_name}({self.agent_id}) → {self.tool_name}"





# ═══════════════════════════════════════════════════════════════

# ToolCallTracker — 每次调用强制标注Agent — [v10-ready]

# ═══════════════════════════════════════════════════════════════





class ToolCallTracker:

    """

    工具调用追踪器 — 核心升级: 每次工具调用必须标注执行Agent



    SSS级标准:

      ✅ 每次调用 → 记录agent_id + agent_name + agent_emoji

      ✅ TVP声明 → [TVP] 🔧 @AgentName → tool_name

      ✅ 阶段标记 → 标注当前在哪个PipelineStage

      ✅ 性能统计 → 每阶段工具调用次数/耗时

    """



    def __init__(self, event_bus=None):

        self._calls: list[ToolCallRecord] = []

        self._lock = threading.RLock()

        self._current_agent: dict | None = None

        self._current_stage: PipelineStage | None = None

        self._current_task: str | None = None

        self._event_bus = event_bus

        self._output_handler: Callable | None = None



    def set_output_handler(self, handler: Callable[[str], None]):

        self._output_handler = handler



    def set_context(self, agent_id: str, stage: PipelineStage, task_id: str):

        info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})

        self._current_agent = {

            "agent_id": agent_id,

            "agent_name": info.get("name", agent_id),

            "agent_emoji": info.get("emoji", "🤖"),

        }

        self._current_stage = stage

        self._current_task = task_id



    def track(

        self,

        tool_name: str,

        success: bool = True,

        duration_ms: float = 0,

        output_summary: str = "",

    ) -> ToolCallRecord:

        """记录一次工具调用 — 强制执行Agent标注"""

        if not self._current_agent:

            self._current_agent = {

                "agent_id": "tianshu",

                "agent_name": "天枢",

                "agent_emoji": "🎯",

            }



        record = ToolCallRecord(

            call_id=f"call-{uuid.uuid4().hex[:8]}",

            agent_id=self._current_agent["agent_id"],

            agent_name=self._current_agent["agent_name"],

            agent_emoji=self._current_agent["agent_emoji"],

            tool_name=tool_name,

            stage=self._current_stage or PipelineStage.EXECUTE,

            task_id=self._current_task or "",

            timestamp=time.time(),

            duration_ms=duration_ms,

            success=success,

            output_summary=output_summary,

        )



        with self._lock:

            self._calls.append(record)



        tvp = record.to_tvp()

        if self._output_handler:

            self._output_handler(tvp)



        if self._event_bus:

            try:

                from core.shared.deepseek_driver import EventType, TianjiEvent



                self._event_bus.publish(

                    TianjiEvent(

                        event_type=EventType.MCP_TOOL_CALL,

                        source="agent_orchestrator",

                        payload={

                            "agent_id": record.agent_id,

                            "agent_name": record.agent_name,

                            "tool_name": tool_name,

                            "stage": record.stage.value,

                        },

                    )

                )

            except Exception:

                pass



        return record



    def get_calls_by_agent(self, agent_id: str) -> list[ToolCallRecord]:

        with self._lock:

            return [c for c in self._calls if c.agent_id == agent_id]



    def get_calls_by_stage(self, stage: PipelineStage) -> list[ToolCallRecord]:

        with self._lock:

            return [c for c in self._calls if c.stage == stage]



    def get_summary(self) -> dict:

        with self._lock:

            agents_used = {}

            for c in self._calls:

                k = f"{c.agent_emoji} {c.agent_name}"

                if k not in agents_used:

                    agents_used[k] = {"count": 0, "tools": set()}

                agents_used[k]["count"] += 1

                agents_used[k]["tools"].add(c.tool_name)



            return {

                "total_calls": len(self._calls),

                "agents_used": {

                    k: {"count": v["count"], "tools": list(v["tools"])}

                    for k, v in agents_used.items()

                },

                "stages": {

                    s.value: len(self.get_calls_by_stage(s)) for s in PipelineStage

                },

            }



    def get_tvp_pipeline_view(self) -> str:

        """生成TVP流水线可视化"""

        lines = ["[TVP] 🏁 Agent调度流水线全景:"]

        stage_calls = {}

        for c in self._calls:

            s = c.stage.value

            if s not in stage_calls:

                stage_calls[s] = []

            stage_calls[s].append(c)



        for stage, calls in stage_calls.items():

            agents = list(set(f"{c.agent_emoji}{c.agent_name}" for c in calls))

            lines.append(f"├─ [{stage}] {', '.join(agents)} ({len(calls)}次调用)")

        lines.append(f"└─ 总计: {len(self._calls)}次工具调用, {len(stage_calls)}个阶段")

        return "\n".join(lines)





# 向后兼容/任务约定别名: ToolTracker

ToolTracker = ToolCallTracker

