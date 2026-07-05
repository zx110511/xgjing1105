"""
天枢 — L2 总指挥Agent
========================
任务编排、决策树评估、Agent调度分发、全局状态管理。

灵境道谱溯源: D5-1【调度混沌煞】· 道五·编排体道
位置: agents/tianshu.py
MCP归属: agent-framework-global
绑定工具: agent_dispatch, system_status, context_extract,
          rule_evaluate, memory_remember, memory_recall, execute_command
"""

from __future__ import annotations

import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition, AgentLayer


class DecisionOutcome(Enum):
    APPROVE = "approve"
    DELEGATE = "delegate"
    ESCALATE = "escalate"
    REJECT = "reject"
    PENDING = "pending"


class TianshuAgent:

    AGENT_ID = "tianshu"

    DECISION_WEIGHTS = {"criticality": 0.4, "urgency": 0.3, "complexity": 0.2, "risk": 0.1}

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._decision_log: List[Dict[str, Any]] = []
        self._dispatch_queue: List[Dict[str, Any]] = []
        self._agent_status: Dict[str, str] = {}

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        goal = getattr(task, "goal", "")
        print(f"[TVP] {self.emoji} {self.name}(L2) 编排决策: {goal[:80]}")

        decision = self.evaluate_decision(task)
        result = {"goal": goal, "decision": decision["outcome"].value, "reasoning": decision["reasoning"]}

        if decision["outcome"] == DecisionOutcome.DELEGATE:
            target = decision.get("target_agent")
            dispatch_result = self.dispatch_agent(target, task)
            result["dispatch"] = dispatch_result
            print(f"[TVP] {self.emoji} 天枢: 委托 → @{target}")

        elif decision["outcome"] == DecisionOutcome.ESCALATE:
            result["escalation"] = "需要更高级别Agent介入"

        self._decision_log.append({"timestamp": time.time(), "goal": goal, "outcome": decision["outcome"].value})
        return result

    def evaluate_decision(self, task) -> Dict[str, Any]:
        criticality = getattr(task, "criticality", 5)
        urgency = getattr(task, "urgency", 5)
        complexity = getattr(task, "complexity", 3)
        risk = getattr(task, "risk", 3)

        score = (
            criticality * self.DECISION_WEIGHTS["criticality"] +
            urgency * self.DECISION_WEIGHTS["urgency"] +
            complexity * self.DECISION_WEIGHTS["complexity"] +
            risk * self.DECISION_WEIGHTS["risk"]
        )

        reasoning = {}
        if score >= 7.0:
            outcome = DecisionOutcome.ESCALATE
            reasoning["reason"] = "高权重任务，需要升级"
        elif score >= 4.5:
            outcome = DecisionOutcome.DELEGATE
            target = self._select_target(task)
            reasoning["reason"] = f"委托给 {target}"
            reasoning["target_agent"] = target
        elif score >= 2.0:
            outcome = DecisionOutcome.APPROVE
            reasoning["reason"] = "标准任务，批准执行"
        else:
            outcome = DecisionOutcome.REJECT
            reasoning["reason"] = "权重过低，拒绝"

        return {"outcome": outcome, "score": round(score, 2), "reasoning": reasoning}

    def _select_target(self, task) -> str:
        goal = getattr(task, "goal", "").lower()
        if any(kw in goal for kw in ["创建", "写", "创作", "生成"]):
            return "miaobi"
        if any(kw in goal for kw in ["检查", "审查", "审计", "质量"]):
            return "mingjing"
        if any(kw in goal for kw in ["架构", "设计", "技术选型"]):
            return "jingwei"
        if any(kw in goal for kw in ["分析", "数据", "统计"]):
            return "tiansuan"
        if any(kw in goal for kw in ["导入", "语料", "数据清洗"]):
            return "kuangshi"
        if any(kw in goal for kw in ["部署", "CI", "CD", "环境"]):
            return "gongzao"
        if any(kw in goal for kw in ["安全", "漏洞", "合规"]):
            return "zhenshan"
        if any(kw in goal for kw in ["性能", "优化", "基准"]):
            return "zhuiguang"
        return "wenzong"

    def dispatch_agent(self, target_id: str, task) -> Dict[str, Any]:
        target_agent = self.amim.get_agent(target_id)
        if not target_agent:
            return {"status": "failed", "reason": f"未知Agent: {target_id}"}

        entry = {
            "target": target_id,
            "target_name": target_agent.name,
            "task_goal": getattr(task, "goal", ""),
            "timestamp": time.time(),
            "status": "dispatched",
        }
        self._dispatch_queue.append(entry)
        print(f"[TVP] {self.emoji} → @{target_agent.name}({target_agent.emoji}) L{target_agent.layer.value}")
        return {"status": "dispatched", "target": target_id, "target_name": target_agent.name}

    def system_status(self) -> Dict[str, Any]:
        agents_by_layer = {}
        for layer in AgentLayer:
            agents = self.amim.get_agents_by_layer(layer)
            agents_by_layer[layer.name] = [a.agent_id for a in agents]

        return {
            "total_agents": self.amim.agent_count,
            "total_tools": self.amim.tool_count,
            "agents_by_layer": agents_by_layer,
            "dispatch_queue_depth": len(self._dispatch_queue),
            "decisions_made": len(self._decision_log),
        }

    def orchestrate(self, tasks: List[Any]) -> List[Dict[str, Any]]:
        print(f"[TVP] {self.emoji} 天枢: 编排 {len(tasks)} 个任务")
        results = []
        for task in sorted(tasks, key=lambda t: getattr(t, "criticality", 0), reverse=True):
            results.append(self.handle(task))
        return results

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "decisions_made": len(self._decision_log),
            "dispatch_queue_depth": len(self._dispatch_queue),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
