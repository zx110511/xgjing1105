"""
忆库 — L1 记忆架构师Agent
===========================
ICME六层记忆系统管理：记忆写入、语义检索、容量监控、巩固晋升。

灵境道谱溯源: D4-1【记忆沉淀煞】· 道四·记忆体道
位置: agents/yiku.py
MCP归属: memory-engine-global
绑定工具: memory_remember, memory_recall, memory_forget, memory_stats,
          memory_capacity, memory_consolidate, search_memories, get_memory,
          list_memories, build_working_representation, run_reflective_cycle,
          get_session_digest, explain_memory_lineage
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class YikuAgent:

    AGENT_ID = "yiku"

    ICME_LAYERS = [
        "L0_SENSORY_BUFFER",
        "L1_WORKING_MEMORY",
        "L2_EPISODIC",
        "L3_SEMANTIC",
        "L4_PROCEDURAL",
        "L5_META",
    ]

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._memory_store: Dict[str, Any] = {}
        self._consolidation_log: List[Dict[str, Any]] = []

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "recall")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L1) 记忆操作: {action}")

        handlers = {
            "remember": self.remember,
            "recall": self.recall,
            "forget": self.forget,
            "stats": self.stats,
            "consolidate": self.consolidate,
            "build_working": self.build_working_representation,
            "reflect": self.run_reflective_cycle,
            "session_digest": self.get_session_digest,
            "lineage": self.explain_memory_lineage,
        }

        handler = handlers.get(action)
        if handler:
            return handler(payload)
        return {"status": "unknown_action", "action": action, "available": list(handlers.keys())}

    def remember(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        key = payload.get("key") or payload.get("id") or str(len(self._memory_store))
        entry = {
            "key": key,
            "content": payload.get("content", ""),
            "tags": payload.get("tags", []),
            "layer": payload.get("layer", "L1_WORKING_MEMORY"),
            "timestamp": payload.get("timestamp", ""),
            "source": payload.get("source", ""),
        }
        self._memory_store[key] = entry
        print(f"[TVP] {self.emoji} 忆库: 记忆已写入 [{key}] → {entry['layer']}")
        return {"status": "stored", "key": key, "entry": entry}

    def recall(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        query = payload.get("query", "")
        key = payload.get("key") or payload.get("id")
        limit = payload.get("limit", 10)

        if key and key in self._memory_store:
            return {"status": "found", "key": key, "entry": self._memory_store[key]}

        results = []
        for k, v in self._memory_store.items():
            if query and query.lower() in str(v).lower():
                results.append({"key": k, "entry": v})
            elif not query:
                results.append({"key": k, "entry": v})

        results = results[:limit]
        return {"status": "found", "count": len(results), "results": results, "query": query}

    def forget(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        key = payload.get("key") or payload.get("id")
        if key and key in self._memory_store:
            del self._memory_store[key]
            return {"status": "forgotten", "key": key}
        return {"status": "not_found", "key": key}

    def stats(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        layer_counts: Dict[str, int] = {}
        for entry in self._memory_store.values():
            layer = entry.get("layer", "unknown")
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        return {
            "status": "ok",
            "total_entries": len(self._memory_store),
            "layer_distribution": layer_counts,
            "icme_layers": self.ICME_LAYERS,
            "consolidations": len(self._consolidation_log),
        }

    def consolidate(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        promoted = []
        for key, entry in list(self._memory_store.items()):
            current_layer = entry.get("layer", "L1_WORKING_MEMORY")
            layer_idx = self._get_layer_index(current_layer)
            if layer_idx is not None and layer_idx < len(self.ICME_LAYERS) - 1:
                new_layer = self.ICME_LAYERS[layer_idx + 1]
                entry["layer"] = new_layer
                promoted.append({"key": key, "from": current_layer, "to": new_layer})

        log_entry = {"timestamp": "", "promoted": len(promoted), "items": promoted}
        self._consolidation_log.append(log_entry)

        print(f"[TVP] {self.emoji} 忆库: 巩固完成，晋升 {len(promoted)} 条记忆")
        return {"status": "consolidated", "promoted_count": len(promoted), "promoted": promoted}

    def build_working_representation(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        working = {k: v for k, v in self._memory_store.items()
                   if v.get("layer") == "L1_WORKING_MEMORY"}
        return {"status": "ok", "working_set_size": len(working), "items": list(working.keys())}

    def run_reflective_cycle(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        self.consolidate({})
        return {"status": "reflected", "memory_count": len(self._memory_store),
                "consolidation_count": len(self._consolidation_log)}

    def get_session_digest(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "status": "ok",
            "session_summary": {
                "total_memories": len(self._memory_store),
                "recent_consolidations": self._consolidation_log[-5:] if self._consolidation_log else [],
                "layer_distribution": self.stats().get("layer_distribution", {}),
            },
        }

    def explain_memory_lineage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        key = payload.get("key", "")
        entry = self._memory_store.get(key)
        if not entry:
            return {"status": "not_found", "key": key}
        return {
            "status": "ok",
            "key": key,
            "entry": entry,
            "lineage": {"parent": None, "children": [], "merged_from": []},
        }

    def _get_layer_index(self, layer_name: str) -> Optional[int]:
        try:
            return self.ICME_LAYERS.index(layer_name)
        except ValueError:
            return None

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "memory_count": len(self._memory_store),
            "consolidations": len(self._consolidation_log),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
