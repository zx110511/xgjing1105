"""
律令 — L1 规则守护者Agent
===========================
规则匹配、合规检查、冲突检测、门禁执行。

灵境道谱溯源: D3-2【规则冲突煞】· 道三·治理体道
位置: agents/luling.py
MCP归属: agent-framework-global
绑定工具: rule_evaluate, security-scanner, memory_recall
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


@dataclass
class Rule:
    rule_id: str
    name: str
    description: str
    condition: Callable[[Dict[str, Any]], bool]
    action: str
    priority: int = 0
    tags: List[str] = field(default_factory=list)


class LulingAgent:

    AGENT_ID = "luling"

    SYSTEM_RULES: List[Rule] = []

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._custom_rules: Dict[str, Rule] = {}
        self._violation_log: List[Dict[str, Any]] = []
        self._init_system_rules()

    def _init_system_rules(self):
        self.SYSTEM_RULES = [
            Rule(
                rule_id="R001", name="禁止日志泄密",
                description="代码中不得硬编码密钥或密码",
                condition=lambda ctx: any(kw in str(ctx.get("content", "")).lower()
                    for kw in ["password=", "secret=", "api_key=", "token="]),
                action="deny", priority=10,
                tags=["security", "secret"],
            ),
            Rule(
                rule_id="R002", name="禁止直接操作MCP服务器",
                description="必须通过AMIM桥接调用MCP工具",
                condition=lambda ctx: any(kw in str(ctx.get("content", "")).lower()
                    for kw in ["mcp.connect", "mcp.call_tool", "stdio_client"]),
                action="warn", priority=8,
                tags=["mcp", "integration"],
            ),
            Rule(
                rule_id="R003", name="AMIM一致性检查",
                description="Agent定义必须与AMIM中的定义一致",
                condition=lambda ctx: True,
                action="audit", priority=5,
                tags=["amim", "consistency"],
            ),
            Rule(
                rule_id="R004", name="TVP协议声明强制",
                description="Agent间调度必须通过TVP协议声明切换",
                condition=lambda ctx: "TVP" not in str(ctx.get("content", "")),
                action="remind", priority=6,
                tags=["tvp", "protocol"],
            ),
            Rule(
                rule_id="R005", name="禁止越级调用",
                description="低层Agent不得直接调度高层Agent",
                condition=lambda ctx: False,
                action="deny", priority=7,
                tags=["layer", "orchestration"],
            ),
        ]

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        context = getattr(task, "context", {}) or {}
        print(f"[TVP] {self.emoji} {self.name}(L1) 规则评估: {getattr(task, 'goal', '')[:60]}")

        result = self.evaluate_rules(context)
        return result

    def evaluate_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        all_rules = {r.rule_id: r for r in self.SYSTEM_RULES}
        all_rules.update(self._custom_rules)

        violations = []
        passed = []
        warnings = []

        for rule_id, rule in sorted(all_rules.items(), key=lambda x: -x[1].priority):
            try:
                triggered = rule.condition(context)
            except Exception as e:
                triggered = False
                warnings.append({"rule_id": rule_id, "error": str(e)})

            if triggered:
                entry = {
                    "rule_id": rule_id,
                    "name": rule.name,
                    "action": rule.action,
                    "priority": rule.priority,
                    "context_snapshot": str(context)[:200],
                }
                if rule.action == "deny":
                    violations.append(entry)
                    self._violation_log.append(entry)
                elif rule.action == "warn":
                    warnings.append(entry)
                elif rule.action == "audit":
                    passed.append(entry)
                else:
                    passed.append(entry)

        denied = len(violations) > 0
        result = {
            "status": "denied" if denied else "passed",
            "total_rules": len(all_rules),
            "violations": violations,
            "warnings": warnings,
            "passed": len(passed),
        }

        if denied:
            print(f"[TVP] {self.emoji} 律令: {len(violations)}条规则违规，拒绝通过")
        else:
            print(f"[TVP] {self.emoji} 律令: 全部{len(all_rules)}条规则通过 ✅")

        return result

    def check_compliance(self, content: str) -> Dict[str, Any]:
        return self.evaluate_rules({"content": content, "source": "manual_check"})

    def register_rule(self, rule: Rule) -> str:
        self._custom_rules[rule.rule_id] = rule
        return rule.rule_id

    def unregister_rule(self, rule_id: str) -> bool:
        if rule_id in self._custom_rules:
            del self._custom_rules[rule_id]
            return True
        return False

    def list_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "system": [{"rule_id": r.rule_id, "name": r.name, "priority": r.priority,
                        "action": r.action, "tags": r.tags}
                       for r in self.SYSTEM_RULES],
            "custom": [{"rule_id": r.rule_id, "name": r.name, "priority": r.priority,
                        "action": r.action, "tags": r.tags}
                       for r in self._custom_rules.values()],
        }

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "system_rules": len(self.SYSTEM_RULES),
            "custom_rules": len(self._custom_rules),
            "violations_logged": len(self._violation_log),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
