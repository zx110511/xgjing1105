# -*- coding: utf-8-sig -*-
"""
TVP透明调度协议 v1.0 (Transparent Visibility Protocol)
=====================================================
天机智能体调度透明度协议，确保所有Agent切换100%可见可审计。

核心组件:
  - TVPEventType: 调度事件类型枚举
  - AgentWorkStatus: Agent工作状态枚举
  - TVPEvent: 调度事件数据结构
  - TVPProtocol: 协议核心实现

道谱溯源: D5-1【调度道】· 五道·调度体道 · 一地煞之制之术
"""

import time
import uuid
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("tianji.tvp_protocol")


# ── Agent角色映射 (天机L0-L4命名体系) ──────────────────

AGENT_ROLE_MAP: Dict[str, str] = {
    "tiewei": "铁卫(L0-安全)",
    "yiku": "忆库(L1-记忆)",
    "dongcha": "洞察(L1-性能)",
    "luling": "律令(L1-规则)",
    "lingxi": "灵犀(L1-对话)",
    "tianshu": "天枢(L2-调度)",
    "wenzong": "文宗(L2-文档)",
    "miaobi": "妙笔(L2-写作)",
    "mingjing": "明镜(L2-审计)",
    "tiansuan": "天算(L2-计算)",
    "jingwei": "经纬(L2-规划)",
    "kuangshi": "矿师(L2-数据)",
    "baiqiao": "百巧(L3-工具)",
    "shiguan": "史官(L3-日志)",
    "jinshu": "锦书(L3-报告)",
    "qianli": "千里(L4-搜索)",
    "gongzao": "工造(L4-构建)",
    "zhenshan": "镇山(L4-运维)",
    "zhuiguang": "追光(L4-优化)",
}

AGENT_EMOJI_MAP: Dict[str, str] = {
    "tiewei": "\u2694\ufe0f",
    "yiku": "\U0001f4da",
    "dongcha": "\U0001f50d",
    "luling": "\u2696\ufe0f",
    "lingxi": "\u2728",
    "tianshu": "\U0001f30c",
    "wenzong": "\U0001f4dd",
    "miaobi": "\U0001f58b\ufe0f",
    "mingjing": "\U0001f9ee",
    "tiansuan": "\U0001f9ee",
    "jingwei": "\U0001f5fa\ufe0f",
    "kuangshi": "\u26cf\ufe0f",
    "baiqiao": "\U0001f527",
    "shiguan": "\U0001f4d6",
    "jinshu": "\U0001f4e8",
    "qianli": "\U0001f30d",
    "gongzao": "\U0001f3d7\ufe0f",
    "zhenshan": "\U0001f6e1\ufe0f",
    "zhuiguang": "\u2728",
}


class TVPEventType(str, Enum):
    """TVP调度事件类型"""
    AGENT_SWITCH = "agent_switch"
    PARALLEL_FORK = "parallel_fork"
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_FAILED = "agent_failed"
    AGENT_DEGRADED = "agent_degraded"
    TOOL_CALL = "tool_call"
    SINGLE_SUBAGENT = "single_subagent"


class AgentWorkStatus(str, Enum):
    """Agent工作状态"""
    IDLE = "idle"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


@dataclass
class TVPEvent:
    """TVP调度事件数据结构"""
    event_type: TVPEventType
    agent: str = ""
    task_type: str = ""
    work_status: AgentWorkStatus = AgentWorkStatus.IDLE
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    success: bool = True
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "agent": self.agent,
            "task_type": self.task_type,
            "work_status": self.work_status.value,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class TVPProtocol:
    """
    TVP透明调度协议核心实现

    确保所有Agent切换行为100%可见可审计。
    每次调度决策必须声明，每次Agent切换必须追踪。
    """

    def __init__(self, output_handler: Optional[Callable[[str], None]] = None):
        self._output_handler = output_handler
        self._events: List[TVPEvent] = []
        self._active_agents: Dict[str, AgentWorkStatus] = {}
        self._trace_counter = 0

    def _emit(self, event: TVPEvent) -> None:
        """发射TVP事件"""
        self._events.append(event)
        if len(self._events) > 1000:
            self._events = self._events[-500:]
        if self._output_handler:
            role = AGENT_ROLE_MAP.get(event.agent, event.agent)
            emoji = AGENT_EMOJI_MAP.get(event.agent, "\U0001f916")
            msg = (
                f"[TVP] {emoji} {role} | {event.event_type.value} | "
                f"{event.task_type} | status={event.work_status.value} | "
                f"trace={event.trace_id}"
            )
            try:
                self._output_handler(msg)
            except Exception:
                pass

    def declare_switch(
        self,
        from_agent: str = "",
        to_agent: str = "",
        task_type: str = "",
        work_status: AgentWorkStatus = AgentWorkStatus.EXECUTING,
        estimated_duration_s: float = 300.0,
        reason: str = "",
        trace_id: str = "",
    ) -> str:
        """声明Agent切换"""
        tid = trace_id or f"tvp-{uuid.uuid4().hex[:8]}"
        event = TVPEvent(
            event_type=TVPEventType.AGENT_SWITCH,
            agent=to_agent,
            task_type=task_type,
            work_status=work_status,
            trace_id=tid,
            reason=reason,
            metadata={"from_agent": from_agent, "estimated_duration_s": estimated_duration_s},
        )
        self._emit(event)
        self._active_agents[to_agent] = work_status
        return tid

    def declare_parallel(
        self,
        coordinator: str = "",
        parallel_agents: Optional[List[Dict[str, str]]] = None,
        task_type: str = "",
        work_status: AgentWorkStatus = AgentWorkStatus.EXECUTING,
        trace_id: str = "",
    ) -> str:
        """声明并行调度"""
        tid = trace_id or f"tvp-{uuid.uuid4().hex[:8]}"
        event = TVPEvent(
            event_type=TVPEventType.PARALLEL_FORK,
            agent=coordinator,
            task_type=task_type,
            work_status=work_status,
            trace_id=tid,
            metadata={"parallel_agents": parallel_agents or []},
        )
        self._emit(event)
        for a in (parallel_agents or []):
            self._active_agents[a.get("id", "")] = work_status
        return tid

    def declare_agent_start(
        self,
        agent: str = "",
        task_type: str = "",
        work_status: AgentWorkStatus = AgentWorkStatus.EXECUTING,
        estimated_duration_s: float = 300.0,
        trace_id: str = "",
    ) -> str:
        """声明Agent启动"""
        tid = trace_id or f"tvp-{uuid.uuid4().hex[:8]}"
        event = TVPEvent(
            event_type=TVPEventType.AGENT_START,
            agent=agent,
            task_type=task_type,
            work_status=work_status,
            trace_id=tid,
            metadata={"estimated_duration_s": estimated_duration_s},
        )
        self._emit(event)
        self._active_agents[agent] = work_status
        return tid

    def declare_agent_complete(
        self,
        agent: str = "",
        task_type: str = "",
        success: bool = True,
        duration_ms: float = 0.0,
        trace_id: str = "",
    ) -> str:
        """声明Agent完成"""
        tid = trace_id or f"tvp-{uuid.uuid4().hex[:8]}"
        status = AgentWorkStatus.COMPLETED if success else AgentWorkStatus.FAILED
        event_type = TVPEventType.AGENT_COMPLETE if success else TVPEventType.AGENT_FAILED
        event = TVPEvent(
            event_type=event_type,
            agent=agent,
            task_type=task_type,
            work_status=status,
            trace_id=tid,
            duration_ms=duration_ms,
            success=success,
        )
        self._emit(event)
        self._active_agents[agent] = status
        return tid

    def declare_tool_call(
        self,
        agent: str = "",
        tool_name: str = "",
        task_type: str = "",
        trace_id: str = "",
    ) -> str:
        """声明工具调用"""
        tid = trace_id or f"tvp-{uuid.uuid4().hex[:8]}"
        event = TVPEvent(
            event_type=TVPEventType.TOOL_CALL,
            agent=agent,
            task_type=task_type,
            work_status=AgentWorkStatus.EXECUTING,
            trace_id=tid,
            metadata={"tool_name": tool_name},
        )
        self._emit(event)
        return tid

    def get_active_agents(self) -> Dict[str, AgentWorkStatus]:
        """获取当前活跃Agent"""
        return dict(self._active_agents)

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近事件"""
        return [e.to_dict() for e in self._events[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """获取协议统计"""
        return {
            "total_events": len(self._events),
            "active_agents": len(self._active_agents),
            "event_types": {
                et.value: sum(1 for e in self._events if e.event_type == et)
                for et in TVPEventType
            },
        }
