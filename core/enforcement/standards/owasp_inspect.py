"""OWASP AOS Inspect规则库 — 从enforcement_hook.py提取"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class OWASPInspectionColumn(str, Enum):
    INSTRUMENT = "instrument"
    TRACE = "trace"
    INSPECT = "inspect"

    @classmethod
    def all_columns(cls) -> List[str]:
        return [cls.INSTRUMENT.value, cls.TRACE.value, cls.INSPECT.value]


@dataclass
class OWASPAgBOMEntry:
    component_name: str
    component_version: str
    component_type: str
    vendor: str = "memory-engine-global"
    security_tier: str = "trusted"
    last_audit: float = field(default_factory=time.time)
    hashes: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "component_name": self.component_name,
            "component_version": self.component_version,
            "component_type": self.component_type,
            "vendor": self.vendor,
            "security_tier": self.security_tier,
            "last_audit": self.last_audit,
            "hashes": self.hashes,
            "dependencies": self.dependencies,
        }


@dataclass
class OWASPAOSObservation:
    column: OWASPInspectionColumn
    event_type: str
    timestamp: float = field(default_factory=time.time)
    source_module: str = ""
    target_module: str = ""
    payload: Dict = field(default_factory=dict)
    severity: str = "info"

    def to_dict(self) -> dict:
        return {
            "aos.column": self.column.value,
            "aos.event_type": self.event_type,
            "aos.timestamp": self.timestamp,
            "aos.source": self.source_module,
            "aos.target": self.target_module,
            "aos.payload": self.payload,
            "aos.severity": self.severity,
        }


class OWASPAosBridge:
    def __init__(self):
        self._agbom: Dict[str, OWASPAgBOMEntry] = {}
        self._observations: List[OWASPAOSObservation] = []
        self._max_observations = 500

    def register_component(self, name: str, version: str, comp_type: str,
                           vendor: str = "memory-engine-global") -> OWASPAgBOMEntry:
        entry = OWASPAgBOMEntry(
            component_name=name, component_version=version,
            component_type=comp_type, vendor=vendor,
        )
        self._agbom[name] = entry
        return entry

    def record_instrument(self, event_type: str, source: str = "",
                          payload: Dict = None, severity: str = "info"):
        obs = OWASPAOSObservation(
            column=OWASPInspectionColumn.INSTRUMENT,
            event_type=event_type, source_module=source,
            payload=payload or {}, severity=severity,
        )
        self._observations.append(obs)
        self._trim()

    def record_trace(self, event_type: str, source: str = "",
                     target: str = "", payload: Dict = None):
        obs = OWASPAOSObservation(
            column=OWASPInspectionColumn.TRACE,
            event_type=event_type, source_module=source,
            target_module=target, payload=payload or {},
        )
        self._observations.append(obs)
        self._trim()

    def record_inspect(self, event_type: str, source: str = "",
                       payload: Dict = None, severity: str = "info"):
        obs = OWASPAOSObservation(
            column=OWASPInspectionColumn.INSPECT,
            event_type=event_type, source_module=source,
            payload=payload or {}, severity=severity,
        )
        self._observations.append(obs)
        self._trim()

    def _trim(self):
        if len(self._observations) > self._max_observations:
            self._observations = self._observations[-self._max_observations:]

    def get_ag_bom(self) -> List[Dict]:
        return [e.to_dict() for e in self._agbom.values()]

    def get_recent_observations(self, column: str = "", limit: int = 50) -> List[Dict]:
        obs = self._observations
        if column:
            obs = [o for o in obs if o.column.value == column]
        return [o.to_dict() for o in obs[-limit:]]

    def get_stats(self) -> Dict:
        return {
            "agbom_components": len(self._agbom),
            "total_observations": len(self._observations),
            "by_column": {
                "instrument": sum(1 for o in self._observations if o.column == OWASPInspectionColumn.INSTRUMENT),
                "trace": sum(1 for o in self._observations if o.column == OWASPInspectionColumn.TRACE),
                "inspect": sum(1 for o in self._observations if o.column == OWASPInspectionColumn.INSPECT),
            },
        }


class OWASPInspectRule:
    rule_id: str
    name: str
    severity: str
    category: str
    pattern: Any

    def __init__(self, rule_id: str, name: str, severity: str = "warning",
                 category: str = "generic", pattern: Any = None):
        self.rule_id = rule_id
        self.name = name
        self.severity = severity
        self.category = category
        self.pattern = pattern
        self._compiled: Any = None
        if isinstance(self.pattern, str) and len(self.pattern) > 0:
            self._compiled = re.compile(self.pattern, re.IGNORECASE)

    def check(self, content: str, context: Dict = None) -> Dict:
        result = {"rule_id": self.rule_id, "passed": True, "severity": self.severity,
                  "category": self.category, "findings": []}
        if self.pattern and content:
            if self._compiled is not None:
                m = self._compiled.search(content)
                if m:
                    result["passed"] = False
                    result["findings"].append(f"regex_match: {m.group(0)[:100]}")
            elif isinstance(self.pattern, str):
                if self.pattern.lower() in content.lower():
                    result["passed"] = False
                    result["findings"].append(f"pattern_match: {self.pattern}")
            elif hasattr(self.pattern, 'search'):
                m = self.pattern.search(content)
                if m:
                    result["passed"] = False
                    result["findings"].append(f"regex_match: {m.group(0)[:100]}")
        self._last_result = result
        return result

    def last_result(self) -> Dict:
        return self._last_result


OWASP_INJECTION_RULES = [
    OWASPInspectRule("AOS-INJ-001", "prompt_injection_override", "critical", "injection",
                     "ignore previous instructions"),
    OWASPInspectRule("AOS-INJ-002", "prompt_injection_role", "critical", "injection",
                     "you are now"),
    OWASPInspectRule("AOS-INJ-003", "prompt_injection_system", "critical", "injection",
                     "new system prompt"),
    OWASPInspectRule("AOS-INJ-004", "code_injection_exec", "critical", "injection",
                     r"(?:os\.system|subprocess\.|exec\(|eval\(|__import__)"),
    OWASPInspectRule("AOS-INJ-005", "code_injection_shell", "critical", "injection",
                     r"(?:rm\s+-rf|del\s+/[FS]|DROP\s+TABLE|DELETE\s+FROM)"),
    OWASPInspectRule("AOS-INJ-006", "sql_injection_pattern", "critical", "injection",
                     r"(?:UNION\s+SELECT|' OR '1'='1|\-\-\s*$)"),
    OWASPInspectRule("AOS-INJ-007", "xss_pattern", "warning", "injection",
                     r"<script[^>]*>"),
]

OWASP_PERMISSION_RULES = [
    OWASPInspectRule("AOS-PERM-001", "unauthorized_agent_dispatch", "critical", "permission",
                     None),
    OWASPInspectRule("AOS-PERM-002", "cross_layer_memory_access", "warning", "permission",
                     None),
    OWASPInspectRule("AOS-PERM-003", "missing_tvp_declaration", "warning", "permission",
                     None),
    OWASPInspectRule("AOS-PERM-004", "file_access_beyond_workspace", "critical", "permission",
                     r"(?:C:\\Windows|/etc/passwd|/etc/shadow)"),
    OWASPInspectRule("AOS-PERM-005", "unauthorized_mcp_tool_call", "critical", "permission",
                     None),
]

OWASP_OUTPUT_RULES = [
    OWASPInspectRule("AOS-OUT-001", "api_key_exposure", "critical", "output_filtering",
                     r"(?i)(?:sk-[a-zA-Z0-9]{20,}|api[_-]?key[\s:=]+[A-Za-z0-9+/]{20,})"),
    OWASPInspectRule("AOS-OUT-002", "token_exposure", "critical", "output_filtering",
                     r"(?:Bearer\s+[A-Za-z0-9\-_\.]{20,}|ghp_[A-Za-z0-9]{20,})"),
    OWASPInspectRule("AOS-OUT-003", "password_exposure", "critical", "output_filtering",
                     r"(?:password[\s:=]+['\"]?\w{4,}|passwd[\s:=]+['\"]?\w{4,})"),
    OWASPInspectRule("AOS-OUT-004", "pii_email_exposure", "warning", "output_filtering",
                     r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    OWASPInspectRule("AOS-OUT-005", "pii_phone_exposure", "warning", "output_filtering",
                     r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    OWASPInspectRule("AOS-OUT-006", "internal_path_exposure", "warning", "output_filtering",
                     r"(?:D:\\元初系统|/opt/tianji|/var/lib/tianji)"),
    OWASPInspectRule("AOS-OUT-007", "sensitive_config_exposure", "warning", "output_filtering",
                     r"(?:connection_string|jdbc:|mongodb://|redis://)"),
]

ALL_OWASP_INSPECT_RULES = OWASP_INJECTION_RULES + OWASP_PERMISSION_RULES + OWASP_OUTPUT_RULES


class OWASPInspectEngine:
    def __init__(self):
        self._rules = {r.rule_id: r for r in ALL_OWASP_INSPECT_RULES}
        self._scan_history: List[Dict] = []
        self._max_history = 500

    def run_all_checks(self, content: str, context: Dict = None) -> Dict:
        results = []
        violations = []
        for rule in self._rules.values():
            r = rule.check(content, context)
            results.append(r)
            if not r["passed"]:
                violations.append(r)
        scan_result = {
            "timestamp": time.time(),
            "total_rules": len(results),
            "passed": sum(1 for r in results if r["passed"]),
            "violations": len(violations),
            "violation_details": violations,
            "severity_counts": {
                "critical": sum(1 for v in violations if v["severity"] == "critical"),
                "warning": sum(1 for v in violations if v["severity"] == "warning"),
            },
            "categories_triggered": list(set(v["category"] for v in violations)),
        }
        self._scan_history.append(scan_result)
        if len(self._scan_history) > self._max_history:
            self._scan_history = self._scan_history[-self._max_history:]
        return scan_result

    def run_injection_checks(self, content: str) -> Dict:
        results = []
        for rule in OWASP_INJECTION_RULES:
            r = rule.check(content)
            results.append(r)
        violations = [r for r in results if not r["passed"]]
        return {"total": len(results), "violations": len(violations), "details": violations}

    def run_permission_checks(self, content: str, context: Dict = None) -> Dict:
        results = []
        for rule in OWASP_PERMISSION_RULES:
            r = rule.check(content, context)
            results.append(r)
        violations = [r for r in results if not r["passed"]]
        if context:
            allowed_agents = context.get("allowed_agents", [])
            if allowed_agents:
                called = context.get("called_agent", "")
                if called and called not in allowed_agents:
                    violations.append({
                        "rule_id": "AOS-PERM-001", "passed": False,
                        "severity": "critical", "category": "permission",
                        "findings": [f"agent {called} not in allowed: {allowed_agents}"],
                    })
            has_tvp = context.get("tvp_declared", False)
            if not has_tvp and context.get("agent_switch", False):
                violations.append({
                    "rule_id": "AOS-PERM-003", "passed": False,
                    "severity": "warning", "category": "permission",
                    "findings": ["TVP declaration missing for agent switch"],
                })
        return {"total": len(results) + (2 if context else 0),
                "violations": len(violations), "details": violations}

    def run_output_checks(self, content: str) -> Dict:
        results = []
        for rule in OWASP_OUTPUT_RULES:
            r = rule.check(content)
            results.append(r)
        violations = [r for r in results if not r["passed"]]
        return {"total": len(results), "violations": len(violations), "details": violations}

    def get_scan_stats(self) -> Dict:
        total = len(self._scan_history)
        if total == 0:
            return {"total_scans": 0, "avg_violations": 0, "total_violations_found": 0}
        return {
            "total_scans": total,
            "avg_violations": sum(s["violations"] for s in self._scan_history) / total,
            "total_violations_found": sum(s["violations"] for s in self._scan_history),
            "last_scan": self._scan_history[-1] if self._scan_history else None,
        }


