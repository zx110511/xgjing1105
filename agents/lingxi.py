"""
灵犀 — L1 对话完整性守护者Agent
=================================
上下文追踪、漂移检测、语义断裂识别、对话恢复。

灵境道谱溯源: D1-2【上下文漂移煞】· 道一·对话体道
位置: agents/lingxi.py
MCP归属: agent-framework-global
绑定工具: context_extract, memory_recall, tianji_intercept
"""

from __future__ import annotations

import hashlib
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class DriftSeverity(Enum):
    NONE = 0
    MILD = 1
    MODERATE = 2
    SEVERE = 3


class RecoveryStrategy(Enum):
    NONE = "none"
    LIGHT_REPAIR = "light_repair"
    MODERATE_REBUILD = "moderate_rebuild"
    SEVERE_RESET = "severe_reset"


class LingxiAgent:

    AGENT_ID = "lingxi"

    DRIFT_THRESHOLDS = {
        DriftSeverity.MILD: 0.3,
        DriftSeverity.MODERATE: 0.55,
        DriftSeverity.SEVERE: 0.75,
    }

    TOPIC_TRANSITION_PENALTY = 0.15
    ENTITY_DECAY_RATE = 0.1

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._context_stack: List[Dict[str, Any]] = []
        self._topic_trail: List[str] = []
        self._entity_pool: Dict[str, float] = {}
        self._drift_log: List[Dict[str, Any]] = []
        self._recovery_count = 0

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        message = getattr(task, "message", "") or getattr(task, "goal", "")
        context = getattr(task, "context", {}) or {}
        print(f"[TVP] {self.emoji} {self.name}(L1) 上下文追踪: {message[:80]}...")

        snapshot = self._build_snapshot(message, context)
        self._context_stack.append(snapshot)

        drift_score, drift_severity = self.detect_drift(snapshot)
        result = {
            "snapshot": snapshot,
            "drift_score": drift_score,
            "drift_severity": drift_severity.name,
            "stack_depth": len(self._context_stack),
            "entity_pool_size": len(self._entity_pool),
        }

        if drift_severity != DriftSeverity.NONE:
            recovery = self._decide_recovery(drift_severity)
            result["needs_recovery"] = True
            result["recovery_strategy"] = recovery.value
            self._drift_log.append({
                "timestamp": time.time(),
                "severity": drift_severity.name,
                "score": drift_score,
                "strategy": recovery.value,
                "message_snippet": message[:100],
            })

            if drift_severity == DriftSeverity.SEVERE:
                print(f"[TVP] {self.emoji} 灵犀: ⚠️ 严重语义漂移({drift_score:.2f}) → 建议重定向")
        else:
            result["needs_recovery"] = False

        return result

    def _build_snapshot(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        digest = hashlib.sha256(message.encode()).hexdigest()[:16]

        new_entities = self._extract_topic_entities(message)
        for entity in new_entities:
            self._entity_pool[entity] = self._entity_pool.get(entity, 0) + 1.0

        for entity in list(self._entity_pool.keys()):
            if entity not in new_entities:
                self._entity_pool[entity] = max(0, self._entity_pool[entity] - self.ENTITY_DECAY_RATE)
                if self._entity_pool[entity] <= 0:
                    del self._entity_pool[entity]

        return {
            "digest": digest,
            "message_len": len(message),
            "entities": new_entities,
            "active_entities": list(self._entity_pool.keys()),
            "context_keys": list(context.keys()) if context else [],
            "timestamp": time.time(),
        }

    def _extract_topic_entities(self, text: str) -> List[str]:
        import re
        key_terms = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
        entities = []
        for term in key_terms:
            if any(kw in term for kw in ["天机", "模块", "Agent", "MCP", "灵境", "升级", "配置",
                                          "桥接", "路由", "记忆", "编排", "工具", "服务",
                                          "铁卫", "忆库", "洞察", "律令", "灵犀", "天枢", "文宗",
                                          "经纬", "妙笔", "明镜", "天算", "矿师", "百巧", "史官",
                                          "锦书", "千里", "工造", "镇山", "追光"]):
                entities.append(term)
        return entities

    def detect_drift(self, snapshot: Dict[str, Any]) -> Tuple[float, DriftSeverity]:
        if len(self._context_stack) < 2:
            return 0.0, DriftSeverity.NONE

        prev = self._context_stack[-2]
        prev_entities = set(prev.get("entities", []))
        curr_entities = set(snapshot.get("entities", []))

        if not prev_entities and not curr_entities:
            return 0.0, DriftSeverity.NONE

        if not prev_entities:
            return 0.3, DriftSeverity.MILD

        intersection = prev_entities & curr_entities
        union = prev_entities | curr_entities
        jaccard = len(intersection) / len(union) if union else 1.0
        drift_score = 1.0 - jaccard

        if len(self._topic_trail) >= 3:
            drift_score += self.TOPIC_TRANSITION_PENALTY

        drift_score = min(1.0, drift_score)

        severity = DriftSeverity.NONE
        for sev in [DriftSeverity.SEVERE, DriftSeverity.MODERATE, DriftSeverity.MILD]:
            if drift_score >= self.DRIFT_THRESHOLDS[sev]:
                severity = sev
                break

        return round(drift_score, 3), severity

    def _decide_recovery(self, severity: DriftSeverity) -> RecoveryStrategy:
        mapping = {
            DriftSeverity.NONE: RecoveryStrategy.NONE,
            DriftSeverity.MILD: RecoveryStrategy.LIGHT_REPAIR,
            DriftSeverity.MODERATE: RecoveryStrategy.MODERATE_REBUILD,
            DriftSeverity.SEVERE: RecoveryStrategy.SEVERE_RESET,
        }
        return mapping.get(severity, RecoveryStrategy.NONE)

    def monitor_context(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for session in sessions:
            score, severity = self._evaluate_session(session)
            results.append({
                "session_id": session.get("id", "unknown"),
                "drift_score": score,
                "severity": severity.name,
            })
        return {"total": len(results), "results": results, "anomalies": [r for r in results if r["severity"] != "NONE"]}

    def _evaluate_session(self, session: Dict[str, Any]) -> Tuple[float, DriftSeverity]:
        messages = session.get("messages", [])
        if len(messages) < 2:
            return 0.0, DriftSeverity.NONE

        # Simplified evaluation based on message count variance
        lens = [len(m) for m in messages if isinstance(m, str)]
        if not lens or len(lens) < 2:
            return 0.0, DriftSeverity.NONE

        avg = sum(lens) / len(lens)
        variance = sum((l - avg) ** 2 for l in lens) / len(lens)
        normalized = min(1.0, variance / (avg * avg + 1))

        severity = DriftSeverity.NONE
        for sev in [DriftSeverity.SEVERE, DriftSeverity.MODERATE, DriftSeverity.MILD]:
            if normalized >= self.DRIFT_THRESHOLDS[sev]:
                severity = sev
                break

        return round(normalized, 3), severity

    def intercept(self, content: str) -> Dict[str, Any]:
        snapshot = self._build_snapshot(content, {})
        drift_score, severity = self.detect_drift(snapshot)
        self._context_stack.append(snapshot)

        should_intercept = severity in (DriftSeverity.MODERATE, DriftSeverity.SEVERE)
        return {
            "should_intercept": should_intercept,
            "drift_score": drift_score,
            "severity": severity.name,
            "recommendation": self._decide_recovery(severity).value,
        }

    def health(self) -> Dict[str, Any]:
        recent_drifts = [d for d in self._drift_log if time.time() - d.get("timestamp", 0) < 3600]
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "context_depth": len(self._context_stack),
            "entity_pool_size": len(self._entity_pool),
            "drift_events_1h": len(recent_drifts),
            "total_recoveries": self._recovery_count,
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
