r"""
天机A2A互操作网关 (Tianji A2A Gateway) v1.0
============================================
遵循 Google A2A Protocol v1.0 (Linux Foundation, 150+组织采纳)，
为天机v9.1提供Agent间标准化互操作能力。

核心能力:
  1. AgentCard — 每个Agent暴露A2A标准能力卡片
  2. Task生命周期 — submitted→working→completed/failed (A2A标准)
  3. SSE流式推送 — Server-Sent Events实时推送任务进度
  4. 多模态Part — 支持TextPart/FilePart/DataPart
  5. 跨平台互操作 — 与LangGraph/CrewAI/ADK Agent互操作

A2A v1.0 核心概念:
  - Agent Card: /.well-known/agent-card.json — Agent能力声明
  - Task: 状态机 — submitted→working→input-required→completed→failed→canceled
  - Message: Role + Parts[]  — user/agent角色 + 内容片段
  - Part: TextPart | FilePart | DataPart — 多模态内容块
  - Artifact: Task产出的结构化结果

参考规范:
  - A2A Protocol v1.0: https://a2a-protocol.org
  - Google ADK: A2A原生支持的Agent开发套件

位置: 天机/core/a2a_gateway.py
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("tianji.a2a_gateway")


# ═══════════════════════════════════════════════════════════════
# A2A 数据模型 (遵循 A2A v1.0 规范)
# ═══════════════════════════════════════════════════════════════


class PartType(str, Enum):
    TEXT = "text"
    FILE = "file"
    DATA = "data"


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class MessageRole(str, Enum):
    USER = "user"
    AGENT = "agent"


@dataclass
class TextPart:
    type: str = "text"
    text: str = ""


@dataclass
class FilePart:
    type: str = "file"
    file: dict = field(default_factory=dict)  # {name, mimeType, uri}


@dataclass
class DataPart:
    type: str = "data"
    data: dict[str, Any] = field(default_factory=dict)


Part = TextPart | FilePart | DataPart


@dataclass
class A2AMessage:
    """A2A消息"""

    message_id: str = ""
    role: MessageRole = MessageRole.USER
    parts: list[dict] = field(default_factory=list)  # [{type, text/file/data}]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_text(cls, text: str, role: MessageRole = MessageRole.USER) -> A2AMessage:
        return cls(
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            role=role,
            parts=[{"type": "text", "text": text}],
        )

    def to_dict(self) -> dict:
        return {
            "messageId": self.message_id,
            "role": self.role.value,
            "parts": self.parts,
            "metadata": self.metadata,
        }


@dataclass
class A2ATask:
    """A2A任务"""

    task_id: str
    state: TaskState = TaskState.SUBMITTED
    messages: list[A2AMessage] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    context_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str | None = None

    def add_message(self, msg: A2AMessage):
        self.messages.append(msg)
        self.updated_at = time.time()

    def add_artifact(self, name: str, parts: list[dict]):
        self.artifacts.append({"name": name, "parts": parts})
        self.updated_at = time.time()

    def transition(self, new_state: TaskState, error: str = None):
        self.state = new_state
        self.updated_at = time.time()
        if error:
            self.error = error

    def to_dict(self) -> dict:
        return {
            "id": self.task_id,
            "contextId": self.context_id,
            "status": {"state": self.state.value},
            "history": [m.to_dict() for m in self.messages],
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════
# Agent Card (A2A v1.0 能力声明)
# ═══════════════════════════════════════════════════════════════


@dataclass
class AgentSkill:
    """Agent技能声明"""

    id: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    input_modes: list[str] = field(default_factory=lambda: ["text"])
    output_modes: list[str] = field(default_factory=lambda: ["text"])


@dataclass
class AgentCard:
    """A2A Agent Card — 遵循 A2A v1.0 规范"""

    agent_id: str
    name: str
    description: str = ""
    url: str = ""  # Agent服务URL
    version: str = "1.0.0"
    capabilities: dict = field(default_factory=dict)
    skills: list[AgentSkill] = field(default_factory=list)
    default_input_modes: list[str] = field(default_factory=lambda: ["text"])
    default_output_modes: list[str] = field(default_factory=lambda: ["text"])
    provider: dict = field(default_factory=dict)  # {organization, url}
    documentation_url: str = ""
    icon_url: str = ""
    authentication: dict | None = None

    def to_a2a_json(self) -> dict:
        """输出A2A v1.0标准JSON"""
        return {
            "protocolVersion": "1.0.0",
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities,
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "tags": s.tags,
                    "examples": s.examples,
                    "inputModes": s.input_modes,
                    "outputModes": s.output_modes,
                }
                for s in self.skills
            ],
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
            "provider": self.provider,
            "documentationUrl": self.documentation_url,
            "iconUrl": self.icon_url,
        }


# ═══════════════════════════════════════════════════════════════
# A2A 网关核心
# ═══════════════════════════════════════════════════════════════


class A2AGateway:
    """
    A2A互操作网关

    使用:
      gateway = A2AGateway()
      card = gateway.get_agent_card("dongcha")
      task = gateway.create_task("分析天机系统架构")
      gateway.send_message(task.task_id, "请分析当前架构的优缺点")
    """

    VERSION = "1.0.0-A2A"

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._tasks: dict[str, A2ATask] = {}
        self._agent_cards: dict[str, AgentCard] = {}
        self._lock = threading.Lock()
        self._sse_subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._build_default_cards()

    def _build_default_cards(self):
        """构建天机全部Agent的A2A Agent Card"""
        from core.orchestration.agent_orchestrator import AGENT_CAPABILITY_MATRIX
        from core.orchestration.task_planner import AGENT_DESCRIPTIONS

        for agent_id, info in AGENT_CAPABILITY_MATRIX.items():
            desc = AGENT_DESCRIPTIONS.get(agent_id, "")
            card = AgentCard(
                agent_id=agent_id,
                name=info.get("name", agent_id),
                description=desc,
                url=f"a2a://tianji/agents/{agent_id}",
                version="9.1.0",
                capabilities={
                    "streaming": True,
                    "pushNotifications": True,
                    "stateTransitionHistory": True,
                },
                skills=[
                    AgentSkill(
                        id=f"{agent_id}-default",
                        name=f"{info.get('name', agent_id)} 标准能力",
                        description=desc,
                        tags=[agent_id],
                    )
                ],
                default_input_modes=["text"],
                default_output_modes=["text"],
                provider={
                    "organization": "天机 (Tianji Memory Engine)",
                    "url": "https://tianji.local",
                },
            )
            self._agent_cards[agent_id] = card

    def get_agent_card(self, agent_id: str) -> AgentCard | None:
        """获取Agent的A2A能力卡片"""
        return self._agent_cards.get(agent_id)

    def list_agent_cards(self) -> list[dict]:
        """列出所有Agent Card"""
        return [card.to_a2a_json() for card in self._agent_cards.values()]

    def create_task(
        self,
        description: str,
        context_id: str = None,
        metadata: dict = None,
    ) -> A2ATask:
        """创建A2A任务"""
        task_id = f"a2a-task-{uuid.uuid4().hex[:12]}"
        task = A2ATask(
            task_id=task_id,
            context_id=context_id,
            metadata=metadata or {},
        )
        task.add_message(A2AMessage.from_text(description, MessageRole.USER))

        with self._lock:
            self._tasks[task_id] = task

        logger.info(f"[A2A] 📝 Task created: {task_id}")
        self._emit_sse(task_id, {"type": "task_created", "task_id": task_id})
        return task

    def send_message(
        self,
        task_id: str,
        text: str,
        role: MessageRole = MessageRole.USER,
        parts: list[dict] = None,
    ) -> A2AMessage | None:
        """向A2A任务发送消息"""
        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"[A2A] Task not found: {task_id}")
            return None

        if parts:
            msg = A2AMessage(
                message_id=f"msg-{uuid.uuid4().hex[:8]}",
                role=role,
                parts=parts,
            )
        else:
            msg = A2AMessage.from_text(text, role)

        task.add_message(msg)
        task.transition(TaskState.WORKING)

        self._emit_sse(
            task_id,
            {
                "type": "message_added",
                "task_id": task_id,
                "message": msg.to_dict(),
            },
        )
        return msg

    def add_artifact(self, task_id: str, name: str, parts: list[dict]):
        """向任务添加产出物"""
        task = self._tasks.get(task_id)
        if task:
            task.add_artifact(name, parts)
            self._emit_sse(
                task_id,
                {"type": "artifact_added", "task_id": task_id, "name": name},
            )

    def complete_task(self, task_id: str):
        """完成任务"""
        task = self._tasks.get(task_id)
        if task:
            task.transition(TaskState.COMPLETED)
            self._emit_sse(
                task_id,
                {"type": "task_completed", "task_id": task_id},
            )

    def fail_task(self, task_id: str, error: str):
        """标记任务失败"""
        task = self._tasks.get(task_id)
        if task:
            task.transition(TaskState.FAILED, error)
            self._emit_sse(
                task_id,
                {"type": "task_failed", "task_id": task_id, "error": error},
            )

    def get_task(self, task_id: str) -> A2ATask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, state: TaskState = None, limit: int = 50) -> list[A2ATask]:
        with self._lock:
            tasks = list(self._tasks.values())
            if state:
                tasks = [t for t in tasks if t.state == state]
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return tasks[:limit]

    def subscribe_sse(self, task_id: str, callback: Callable):
        """订阅SSE事件"""
        self._sse_subscribers[task_id].append(callback)

    def unsubscribe_sse(self, task_id: str, callback: Callable):
        subscribers = self._sse_subscribers.get(task_id, [])
        if callback in subscribers:
            subscribers.remove(callback)

    def _emit_sse(self, task_id: str, data: dict):
        """向订阅者推送SSE事件"""
        subscribers = self._sse_subscribers.get(task_id, [])
        for cb in subscribers:
            try:
                cb(data)
            except Exception as e:
                logger.error(f"[A2A] SSE callback error: {e}")

    def get_stats(self) -> dict:
        with self._lock:
            tasks_by_state: dict[str, int] = defaultdict(int)
            for t in self._tasks.values():
                tasks_by_state[t.state.value] += 1
            return {
                "version": self.VERSION,
                "total_tasks": len(self._tasks),
                "tasks_by_state": dict(tasks_by_state),
                "agent_cards": len(self._agent_cards),
                "sse_subscribers": sum(len(v) for v in self._sse_subscribers.values()),
            }


# ═══════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════

_a2a_gateway: A2AGateway | None = None
_a2a_lock = threading.Lock()


def get_a2a_gateway(event_bus=None) -> A2AGateway:
    global _a2a_gateway
    with _a2a_lock:
        if _a2a_gateway is None:
            _a2a_gateway = A2AGateway(event_bus=event_bus)
        return _a2a_gateway
