r"""
天机记忆状态管理器 (Tianji Memory State Manager) v1.0
========================================================
Active/Paused/Archived 三级生命周期管理

设计哲学:
  Active:   主动使用，参与检索和巩固
  Paused:   暂停使用，保留但排除检索
  Archived: 归档存储，长期保留但完全排除

架构位置: 天机/core/memory_state_manager.py

灵境道谱溯源: D4-4【状态管理煞】· 道四·质量体道 · 四地煞之制之术
"""

import time
import json
import logging
import threading
from typing import Any, Optional, Dict, List, Set
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class MemoryState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"

    @classmethod
    def valid_transitions(cls, current: "MemoryState") -> Set["MemoryState"]:
        transitions = {
            cls.ACTIVE: {cls.PAUSED, cls.ARCHIVED},
            cls.PAUSED: {cls.ACTIVE, cls.ARCHIVED},
            cls.ARCHIVED: {cls.ACTIVE},
        }
        return transitions.get(current, set())


@dataclass
class StateTransition:
    entry_id: str
    from_state: MemoryState
    to_state: MemoryState
    reason: str
    changed_by: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "changed_by": self.changed_by,
            "timestamp": self.timestamp
        }


class MemoryStateManager:
    """记忆状态管理器"""

    AUTO_PAUSE_DAYS = 30
    AUTO_ARCHIVE_DAYS = 90

    def __init__(self, storage_path: str = "data/memory_states"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._states: Dict[str, MemoryState] = {}
        self._transition_log: List[StateTransition] = []
        self._lock = threading.RLock()
        self._load()

        logger.info(f"记忆状态管理器初始化: {len(self._states)} 条记忆状态")

    def _load(self):
        state_file = self.storage_path / "memory_states.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._states = {k: MemoryState(v) for k, v in data.get("states", {}).items()}

                for t in data.get("transition_log", []):
                    self._transition_log.append(StateTransition(
                        entry_id=t["entry_id"],
                        from_state=MemoryState(t["from_state"]),
                        to_state=MemoryState(t["to_state"]),
                        reason=t["reason"],
                        changed_by=t["changed_by"],
                        timestamp=t["timestamp"]
                    ))
            except Exception as e:
                logger.error(f"加载状态失败: {e}")

    def _save(self):
        state_file = self.storage_path / "memory_states.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump({
                "states": {k: v.value for k, v in self._states.items()},
                "transition_log": [t.to_dict() for t in self._transition_log[-500:]]
            }, f, ensure_ascii=False, indent=2)

    def get_state(self, entry_id: str) -> MemoryState:
        return self._states.get(entry_id, MemoryState.ACTIVE)

    def set_state(self, entry_id: str, new_state: MemoryState, reason: str, changed_by: str) -> bool:
        with self._lock:
            current = self._states.get(entry_id, MemoryState.ACTIVE)

            valid = MemoryState.valid_transitions(current)
            if new_state not in valid:
                logger.warning(f"非法状态转换: {current.value} → {new_state.value} (有效: {[v.value for v in valid]})")
                return False

            self._states[entry_id] = new_state

            transition = StateTransition(
                entry_id=entry_id,
                from_state=current,
                to_state=new_state,
                reason=reason,
                changed_by=changed_by
            )
            self._transition_log.append(transition)
            self._save()

            logger.info(f"[状态] {entry_id[:12]}...  {current.value} → {new_state.value} ({reason})")
            return True

    def pause_memory(self, entry_id: str, reason: str, changed_by: str = "system") -> bool:
        return self.set_state(entry_id, MemoryState.PAUSED, reason, changed_by)

    def archive_memory(self, entry_id: str, reason: str, changed_by: str = "system") -> bool:
        return self.set_state(entry_id, MemoryState.ARCHIVED, reason, changed_by)

    def restore_memory(self, entry_id: str, reason: str, changed_by: str = "system") -> bool:
        return self.set_state(entry_id, MemoryState.ACTIVE, reason, changed_by)

    def get_active_ids(self) -> Set[str]:
        return {eid for eid, s in self._states.items() if s == MemoryState.ACTIVE}

    def get_paused_ids(self) -> Set[str]:
        return {eid for eid, s in self._states.items() if s == MemoryState.PAUSED}

    def get_archived_ids(self) -> Set[str]:
        return {eid for eid, s in self._states.items() if s == MemoryState.ARCHIVED}

    def filter_by_state(self, entry_ids: List[str], allowed_states: Optional[List[MemoryState]] = None) -> List[str]:
        if allowed_states is None:
            allowed_states = [MemoryState.ACTIVE]
        return [eid for eid in entry_ids if self.get_state(eid) in allowed_states]

    def auto_manage(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """自动状态管理"""
        now = time.time()
        stats = {"paused": 0, "archived": 0}

        for mem in memories:
            entry_id = mem.get("id", "")
            if not entry_id:
                continue

            last_accessed = mem.get("last_accessed", now)
            days_since_access = (now - last_accessed) / 86400

            current_state = self.get_state(entry_id)

            if current_state == MemoryState.ACTIVE and days_since_access > self.AUTO_ARCHIVE_DAYS:
                self.archive_memory(entry_id, f"自动归档: {days_since_access:.0f}天未访问", "auto-manager")
                stats["archived"] += 1
            elif current_state == MemoryState.ACTIVE and days_since_access > self.AUTO_PAUSE_DAYS:
                self.pause_memory(entry_id, f"自动暂停: {days_since_access:.0f}天未访问", "auto-manager")
                stats["paused"] += 1

        return stats

    def get_transition_history(self, entry_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        log = self._transition_log
        if entry_id:
            log = [t for t in log if t.entry_id == entry_id]
        return [t.to_dict() for t in log[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        active = len(self.get_active_ids())
        paused = len(self.get_paused_ids())
        archived = len(self.get_archived_ids())
        total = len(self._states)

        return {
            "total_states": total,
            "active_count": active,
            "paused_count": paused,
            "archived_count": archived,
            "active_pct": round(active / max(total, 1) * 100, 1),
            "transition_count": len(self._transition_log),
            "auto_pause_days": self.AUTO_PAUSE_DAYS,
            "auto_archive_days": self.AUTO_ARCHIVE_DAYS
        }
