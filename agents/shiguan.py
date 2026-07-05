"""
史官 — L3 版本追踪Agent
==========================
版本管理、历史归档、变更分析、回滚支持。

灵境道谱溯源: D4-3【版本断裂煞】· 道四·记忆体道
位置: agents/shiguan.py
MCP归属: memory-engine-global
绑定工具: memory_recall, memory_remember, tianji_export
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class ShiguanAgent:

    AGENT_ID = "shiguan"

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._versions: Dict[str, List[Dict[str, Any]]] = {}
        self._change_log: List[Dict[str, Any]] = []

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "track")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L3) 版本管理: {action}")

        handlers = {
            "track": self.track_version,
            "archive": self.archive_history,
            "analyze": self.analyze_change,
            "rollback": self.rollback_support,
        }
        handler = handlers.get(action, self.track_version)
        return handler(payload)

    def track_version(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = payload.get("entity_id", "global")
        content = payload.get("content", "")
        author = payload.get("author", "unknown")

        content_hash = hashlib.sha256(str(content).encode()).hexdigest()[:16]

        if entity_id not in self._versions:
            self._versions[entity_id] = []

        version_num = len(self._versions[entity_id]) + 1
        snapshot = {
            "version": version_num,
            "hash": content_hash,
            "content_snippet": str(content)[:200],
            "author": author,
            "timestamp": time.time(),
            "size": len(str(content)),
        }
        self._versions[entity_id].append(snapshot)
        print(f"[TVP] {self.emoji} 史官: {entity_id} v{version_num} ({content_hash})")
        return {"status": "tracked", "entity_id": entity_id, "version": version_num, "hash": content_hash}

    def archive_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = payload.get("entity_id", "global")
        versions = self._versions.get(entity_id, [])
        if not versions:
            return {"status": "empty", "entity_id": entity_id}
        archive = {
            "entity_id": entity_id,
            "total_versions": len(versions),
            "first_version": versions[0],
            "latest_version": versions[-1],
            "archived_at": time.time(),
        }
        return {"status": "archived", "archive": archive}

    def analyze_change(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = payload.get("entity_id", "global")
        v1 = payload.get("v1", 1)
        v2 = payload.get("v2", None)
        versions = self._versions.get(entity_id, [])
        if not versions:
            return {"status": "no_data", "entity_id": entity_id}

        if v2 is None:
            v2 = len(versions)
        idx1 = max(0, v1 - 1)
        idx2 = max(0, v2 - 1)
        if idx1 >= len(versions):
            idx1 = 0
        if idx2 >= len(versions):
            idx2 = len(versions) - 1

        snap1 = versions[idx1]
        snap2 = versions[idx2]
        return {
            "status": "analyzed",
            "entity_id": entity_id,
            "from_version": snap1["version"],
            "to_version": snap2["version"],
            "from_hash": snap1["hash"],
            "to_hash": snap2["hash"],
            "versions_between": abs(idx2 - idx1),
        }

    def rollback_support(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = payload.get("entity_id", "global")
        target_version = payload.get("target_version")
        versions = self._versions.get(entity_id, [])
        if not versions:
            return {"status": "no_data", "entity_id": entity_id}

        if target_version is None:
            target_version = max(1, len(versions) - 1)

        idx = max(0, min(target_version - 1, len(versions) - 1))
        target = versions[idx]
        return {
            "status": "rollback_ready",
            "entity_id": entity_id,
            "target_version": target["version"],
            "target_hash": target["hash"],
            "current_version": len(versions),
        }

    def health(self) -> Dict[str, Any]:
        total_versions = sum(len(v) for v in self._versions.values())
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "tracked_entities": len(self._versions),
            "total_versions": total_versions,
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
