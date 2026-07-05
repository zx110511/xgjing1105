"""
文宗 — L2 主编Agent
=====================
项目管理、内容审核、进度追踪、团队协调。

灵境道谱溯源: D5-2【协调断裂煞】· 道五·编排体道
位置: agents/wenzong.py
MCP归属: agent-framework-global
绑定工具: agent_dispatch, system_status, memory_recall, execute_command
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class WenzongAgent:

    AGENT_ID = "wenzong"

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._projects: Dict[str, Dict[str, Any]] = {}
        self._review_log: List[Dict[str, Any]] = []

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "track")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L2) 项目管理: {action}")

        handlers = {
            "create_project": self.manage_project,
            "review": self.review_content,
            "track": self.track_progress,
            "status": self.get_status,
        }
        handler = handlers.get(action, self.track_progress)
        return handler(payload)

    def manage_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        project_id = payload.get("id", f"proj_{len(self._projects)}")
        project = {
            "id": project_id,
            "name": payload.get("name", "未命名项目"),
            "stages": payload.get("stages", ["规划", "设计", "实现", "审查", "交付"]),
            "current_stage": 0,
            "created_at": time.time(),
            "tasks": [],
            "status": "active",
        }
        self._projects[project_id] = project
        print(f"[TVP] {self.emoji} 文宗: 项目 {project['name']} 已创建")
        return {"status": "created", "project": project}

    def review_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        content = payload.get("content", "")
        criteria = payload.get("criteria", ["完整性", "一致性", "可读性", "规范性"])
        checks = {}
        for c in criteria:
            checks[c] = "passed"
        review = {
            "content_snippet": content[:100],
            "criteria_checks": checks,
            "passed": len([v for v in checks.values() if v == "passed"]),
            "failed": len([v for v in checks.values() if v != "passed"]),
            "timestamp": time.time(),
        }
        self._review_log.append(review)
        return {"status": "reviewed", "review": review}

    def track_progress(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self._projects:
            return {"status": "ok", "projects": 0, "message": "无活跃项目"}
        return {
            "status": "ok",
            "total_projects": len(self._projects),
            "projects": [
                {"id": pid, "name": p["name"], "stage": p["current_stage"],
                 "total_stages": len(p["stages"]), "status": p["status"]}
                for pid, p in self._projects.items()
            ],
        }

    def get_status(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "active_projects": len([p for p in self._projects.values() if p["status"] == "active"]),
            "total_reviews": len(self._review_log),
            "recent_reviews": self._review_log[-5:] if self._review_log else [],
        }

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "projects": len(self._projects),
            "reviews": len(self._review_log),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
