"""
百巧 — L3 技能代理Agent
==========================
技能调用、工作流编排、参数验证、结果格式化。

灵境道谱溯源: D5-3【技能路由煞】· 道五·编排体道
位置: agents/baiqiao.py
MCP归属: command-executor
绑定工具: execute_command, agent_dispatch
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class BaiqiaoAgent:

    AGENT_ID = "baiqiao"

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._skill_registry: Dict[str, Callable] = {}
        self._invocation_log: List[Dict[str, Any]] = []

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "invoke")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L3) 技能调用: {action}")

        handlers = {
            "invoke": self.invoke_skill,
            "workflow": self.orchestrate_workflow,
            "validate": self.validate_params,
            "format": self.format_result,
        }
        handler = handlers.get(action, self.invoke_skill)
        return handler(payload)

    def invoke_skill(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        skill_id = payload.get("skill_id", "")
        params = payload.get("params", {})

        if skill_id in self._skill_registry:
            try:
                result = self._skill_registry[skill_id](**params)
                entry = {"skill_id": skill_id, "params": params, "status": "success", "timestamp": time.time()}
                self._invocation_log.append(entry)
                return {"status": "invoked", "skill_id": skill_id, "result": result}
            except Exception as e:
                entry = {"skill_id": skill_id, "params": params, "status": "error", "error": str(e), "timestamp": time.time()}
                self._invocation_log.append(entry)
                return {"status": "error", "skill_id": skill_id, "error": str(e)}

        skills = self.defn.skill_ids if hasattr(self.defn, 'skill_ids') else []
        return {
            "status": "not_found",
            "skill_id": skill_id,
            "available_skills": skills,
            "registry_count": len(self._skill_registry),
        }

    def orchestrate_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        steps = payload.get("steps", [])
        results = []
        for i, step in enumerate(steps):
            skill_id = step.get("skill_id", "")
            params = step.get("params", {})
            result = self.invoke_skill({"skill_id": skill_id, "params": params})
            results.append({"step": i, "skill_id": skill_id, "result": result})
            if result["status"] == "error":
                break
        return {"status": "workflow_complete" if all(r["result"]["status"] != "error" for r in results) else "workflow_failed",
                "steps": len(steps), "completed": len(results), "results": results}

    def validate_params(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        skill_id = payload.get("skill_id", "")
        params = payload.get("params", {})
        validation = {"skill_id": skill_id, "valid": True, "issues": []}
        if not skill_id:
            validation["valid"] = False
            validation["issues"].append("skill_id不能为空")
        if not isinstance(params, dict):
            validation["valid"] = False
            validation["issues"].append("params必须是字典")
        return validation

    def format_result(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = payload.get("result", {})
        format_type = payload.get("format", "json")
        formatted = {
            "json": lambda r: r,
            "summary": lambda r: {"status": r.get("status", "unknown"), "keys": list(r.keys()) if isinstance(r, dict) else []},
        }
        formatter = formatted.get(format_type, formatted["json"])
        return {"status": "formatted", "format": format_type, "output": formatter(result)}

    def register_skill(self, skill_id: str, handler: Callable):
        self._skill_registry[skill_id] = handler

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "registered_skills": len(self._skill_registry),
            "invocations": len(self._invocation_log),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
