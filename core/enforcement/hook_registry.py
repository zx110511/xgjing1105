# -*- coding: utf-8-sig -*-
"""对话注册表 — 从hook_core.py拆分 [SSS-PhaseB]

包含: ConversationRegistry (FIFO对话记录管理)
"""

from __future__ import annotations

import threading
from typing import Any

from .hook_models import ConversationRecord


class ConversationRegistry:
    """对话注册表 — 借鉴Hermes的工具自注册模式

    每个对话轮次自动注册，无需手动调用。
    FIFO上限max_size，超龄自动淘汰最旧会话。
    """

    def __init__(self, max_size: int = 1000):
        self._conversations: dict[str, list[ConversationRecord]] = {}
        self._lock = threading.Lock()
        self._total_turns: int = 0
        self._recorded_turns: int = 0
        self._max_size = max_size

    def register(self, record: ConversationRecord) -> None:
        with self._lock:
            if record.session_id not in self._conversations:
                self._conversations[record.session_id] = []
            self._conversations[record.session_id].append(record)
            self._total_turns += 1
            if record.recorded:
                self._recorded_turns += 1
            # FIFO淘汰
            if len(self._conversations) > self._max_size:
                oldest = min(
                    self._conversations.keys(),
                    key=lambda k: (
                        self._conversations[k][0].timestamp
                        if self._conversations[k] else float("inf")
                    ),
                )
                del self._conversations[oldest]

    def get_unrecorded(self, session_id: str | None = None) -> list[ConversationRecord]:
        with self._lock:
            if session_id:
                convs = self._conversations.get(session_id, [])
                return [c for c in convs if not c.recorded]
            unrecorded = []
            for convs in self._conversations.values():
                unrecorded.extend(c for c in convs if not c.recorded)
            return unrecorded

    def mark_recorded(self, session_id: str, turn_number: int, memory_id: str) -> None:
        with self._lock:
            convs = self._conversations.get(session_id, [])
            for c in convs:
                if c.turn_number == turn_number:
                    c.recorded = True
                    c.memory_id = memory_id
                    self._recorded_turns += 1
                    break

    @property
    def compliance_rate(self) -> float:
        if self._total_turns == 0:
            return 1.0
        return self._recorded_turns / self._total_turns

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_turns": self._total_turns,
            "recorded_turns": self._recorded_turns,
            "unrecorded_turns": self._total_turns - self._recorded_turns,
            "compliance_rate": f"{self.compliance_rate:.1%}",
            "active_sessions": len(self._conversations),
        }
