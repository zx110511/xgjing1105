"""
千里 — L4 系统监控Agent
==========================
实时监控、性能采集、智能告警、趋势分析。

灵境道谱溯源: D9-3【监控盲区煞】· 道九·进化体道
位置: agents/qianli.py
MCP归属: performance-profiler
绑定工具: system_status, ops-engine, performance-profiler, memory_recall, tianji_health
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class QianliAgent:

    AGENT_ID = "qianli"

    ALERT_THRESHOLDS = {
        "cpu_percent": 80,
        "memory_percent": 85,
        "disk_percent": 90,
        "response_time_ms": 5000,
        "error_rate": 0.05,
    }

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._metrics: List[Dict[str, Any]] = []
        self._alerts: List[Dict[str, Any]] = []
        self._component_status: Dict[str, str] = {}

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "monitor")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L4) 监控: {action}")

        handlers = {
            "monitor": self.monitor_realtime,
            "collect": self.collect_performance,
            "alert": self.alert_smart,
            "trend": self.analyze_trend,
        }
        handler = handlers.get(action, self.monitor_realtime)
        return handler(payload)

    def monitor_realtime(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        components = ["M29_MCP", "M35_EvolutionBus", "M34_AgentOrchestrator", "M37_AMIM"]
        status = {}
        for comp in components:
            status[comp] = self._component_status.get(comp, "unknown")

        snapshot = {
            "timestamp": time.time(),
            "components": status,
            "active_alerts": len([a for a in self._alerts if not a.get("resolved")]),
            "metrics_count": len(self._metrics),
        }
        self._metrics.append(snapshot)
        return {"status": "monitoring", "snapshot": snapshot}

    def collect_performance(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        perf = {
            "timestamp": time.time(),
            "metrics": {
                "agent_count": self.amim.agent_count,
                "tool_count": self.amim.tool_count,
                "mcp_servers": len(set(a.mcp_server for a in self.amim.AGENT_DEFINITIONS)),
            },
        }
        self._metrics.append(perf)
        return {"status": "collected", "performance": perf}

    def alert_smart(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        alerts_triggered = []
        for key, threshold in self.ALERT_THRESHOLDS.items():
            current = payload.get(key, threshold - 1) if payload else threshold - 1
            if current >= threshold:
                alert = {
                    "type": key,
                    "current_value": current,
                    "threshold": threshold,
                    "timestamp": time.time(),
                    "severity": "critical" if current >= threshold * 1.2 else "warning",
                    "resolved": False,
                }
                self._alerts.append(alert)
                alerts_triggered.append(alert)
                print(f"[TVP] {self.emoji} 千里: ⚠️ {key} 告警: {current} >= {threshold}")

        return {
            "status": "alert_check",
            "alerts_triggered": len(alerts_triggered),
            "total_alerts": len(self._alerts),
            "active_alerts": len([a for a in self._alerts if not a.get("resolved")]),
        }

    def analyze_trend(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        recent = self._metrics[-50:] if len(self._metrics) > 50 else self._metrics
        if len(recent) < 3:
            return {"status": "insufficient_data", "data_points": len(recent)}

        timestamps = [m.get("timestamp", 0) for m in recent]
        time_span = max(timestamps) - min(timestamps) if timestamps else 0

        return {
            "status": "analyzed",
            "data_points": len(recent),
            "time_span_seconds": round(time_span, 1),
            "sampling_rate": round(len(recent) / max(1, time_span), 2),
        }

    def check_health(self) -> Dict[str, Any]:
        issues = self.amim.validate()
        for agent in self.amim.AGENT_DEFINITIONS:
            self._component_status[f"MCP_{agent.mcp_server}"] = "healthy"
        return {
            "status": "healthy" if len(issues) == 0 else "degraded",
            "components": len(self._component_status),
            "issues": issues,
        }

    def health(self) -> Dict[str, Any]:
        active_alerts = len([a for a in self._alerts if not a.get("resolved")])
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "metrics_collected": len(self._metrics),
            "active_alerts": active_alerts,
            "components_monitored": len(self._component_status),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
