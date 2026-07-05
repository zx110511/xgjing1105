"""
经纬 — L2 架构师Agent
========================
架构设计、技术选型、路径规划、重构策略。

灵境道谱溯源: D6-1【架构腐败煞】· 道六·演化体道
位置: agents/jingwei.py
MCP归属: agent-framework-global
绑定工具: agent_dispatch, rule_evaluate, memory_recall, execute_command
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class JingweiAgent:

    AGENT_ID = "jingwei"

    ARCHITECTURE_PATTERNS = {
        "modular": "模块化单体 — 适用于天机v9.1当前架构",
        "microservices": "微服务 — 适用于灵境Phase 4+",
        "event_driven": "事件驱动 — 适用于EvolutionBus跨模块通信",
        "layered": "分层架构 — 适用于Agent L0-L4分层调度",
        "hexagonal": "六边形架构 — 适用于MCP多协议适配",
    }

    TECH_STACK = {
        "python": {"version": "3.12", "suitable_for": ["core", "agents", "mcp"]},
        "json_rpc": {"version": "2.0", "suitable_for": ["mcp_protocol"]},
        "dataclass": {"version": "native", "suitable_for": ["data_models"]},
        "event_bus": {"version": "M35", "suitable_for": ["inter_module_comm"]},
    }

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._designs: Dict[str, Dict[str, Any]] = {}

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "design")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L2) 架构决策: {action}")

        handlers = {
            "design": self.design_architecture,
            "select_tech": self.select_tech,
            "plan_path": self.plan_path,
            "refactor_strategy": self.refactor_strategy,
        }
        handler = handlers.get(action, self.design_architecture)
        return handler(payload)

    def design_architecture(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        requirements = payload.get("requirements", [])
        pattern = payload.get("pattern", "modular")

        design = {
            "pattern": pattern,
            "description": self.ARCHITECTURE_PATTERNS.get(pattern, "自定义模式"),
            "modules": self._identify_modules(requirements),
            "layers": ["L0_Infrastructure", "L1_Context", "L2_Decision", "L3_Execution", "L4_Operations"],
            "communication": {"internal": "EvolutionBus (M35)", "external": "MCP JSON-RPC 2.0"},
        }
        design_id = f"arch_{len(self._designs)}"
        self._designs[design_id] = design
        return {"status": "designed", "design_id": design_id, "design": design}

    def _identify_modules(self, requirements: List[str]) -> List[str]:
        mapping = {
            "记忆": ["M25", "M26", "M27", "M28"],
            "编排": ["M34", "M37"],
            "治理": ["M17", "M13", "M18"],
            "工具": ["M29", "M37"],
            "进化": ["M7", "M8", "M35"],
            "安全": ["M19", "M21"],
            "性能": ["M31", "M32"],
        }
        modules = set()
        for req in requirements:
            for keyword, mods in mapping.items():
                if keyword in req:
                    modules.update(mods)
        return sorted(modules) if modules else ["M1", "M34", "M37"]

    def select_tech(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        domain = payload.get("domain", "python")
        candidates = {k: v for k, v in self.TECH_STACK.items() if payload.get("domain", "python") in k}
        return {"domain": domain, "recommendations": candidates, "all_options": self.TECH_STACK}

    def plan_path(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from_state = payload.get("from", "天机v9.1")
        to_state = payload.get("to", "灵境")
        phases = [
            {"phase": 1, "name": "AMIM桥接", "action": "建立Agent-MCP统一映射"},
            {"phase": 2, "name": "EvolutionBus升级", "action": "事件总线支持跨进程通信"},
            {"phase": 3, "name": "Agent解耦", "action": "每个Agent独立进程"},
            {"phase": 4, "name": "MCP网关", "action": "MCP协议升级支持远程调用"},
            {"phase": 5, "name": "灵境就绪", "action": "分布式部署"},
        ]
        return {"from": from_state, "to": to_state, "phases": phases, "total_phases": len(phases)}

    def refactor_strategy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        target = payload.get("target", "agent_system")
        strategies = {
            "agent_system": [
                {"step": "extract_amim", "action": "提取Agent定义为AMIM单一来源"},
                {"step": "create_runtime_classes", "action": "为20个Agent创建运行类"},
                {"step": "decouple_mcp", "action": "MCP工具归属解耦至AMIM"},
                {"step": "add_validation", "action": "添加一致性验证"},
                {"step": "sync_registry", "action": "同步_AGENT_REGISTRY.json"},
            ],
        }
        return {"target": target, "strategy": strategies.get(target, [])}

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "designs_count": len(self._designs),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
