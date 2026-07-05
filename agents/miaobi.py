"""
妙笔 — L2 创作者Agent
========================
内容创作、创意生成、角色塑造、世界观构建。

灵境道谱溯源: D7-1【创作枯竭煞】· 道七·创作体道
位置: agents/miaobi.py
MCP归属: memory-engine-global
绑定工具: memory_recall, memory_remember, tianji_semantic_search, tianji_extract_knowledge
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class MiaobiAgent:

    AGENT_ID = "miaobi"

    CREATIVE_MODES = ["narrative", "descriptive", "expository", "persuasive", "technical"]

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._works: List[Dict[str, Any]] = []
        self._world_elements: Dict[str, Any] = {}

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "create")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L2) 创作: {action}")

        handlers = {
            "create": self.create_content,
            "build_world": self.build_world,
            "generate_creative": self.generate_creative,
            "expand": self.expand_content,
        }
        handler = handlers.get(action, self.create_content)
        return handler(payload)

    def create_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        topic = payload.get("topic", "")
        mode = payload.get("mode", "narrative")
        style = payload.get("style", "专业")

        work = {
            "id": f"work_{len(self._works)}",
            "topic": topic,
            "mode": mode,
            "style": style,
            "created_at": time.time(),
            "status": "draft",
        }
        self._works.append(work)
        print(f"[TVP] {self.emoji} 妙笔: 创作《{topic}》[{mode}/{style}]")
        return {"status": "created", "work": work}

    def build_world(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        world_name = payload.get("name", "新世界")
        elements = payload.get("elements", [])
        for elem in elements:
            elem_type = elem.get("type", "generic")
            if elem_type not in self._world_elements:
                self._world_elements[elem_type] = []
            self._world_elements[elem_type].append(elem)
        return {
            "status": "built",
            "world": world_name,
            "elements_count": len(elements),
            "total_elements": sum(len(v) for v in self._world_elements.values()),
        }

    def generate_creative(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = payload.get("prompt", "")
        count = payload.get("count", 3)
        ideas = []
        for i in range(count):
            ideas.append({
                "id": i,
                "concept": f"基于「{prompt}」的创意构想 #{i+1}",
                "angle": ["反转", "深化", "对比", "融合", "解构"][i % 5],
            })
        return {"prompt": prompt, "ideas": ideas, "count": len(ideas)}

    def expand_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        source = payload.get("source", "")
        direction = payload.get("direction", "深化")
        return {
            "status": "expanded",
            "source_length": len(source),
            "direction": direction,
            "techniques": ["细节描写", "感官放大", "情感注入", "背景补充"],
        }

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "works_count": len(self._works),
            "world_elements": sum(len(v) for v in self._world_elements.values()),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
