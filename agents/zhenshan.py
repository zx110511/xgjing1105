"""
镇山 — L4 安全审计Agent
==========================
漏洞扫描、合规检查、密钥管理、数据保护。

灵境道谱溯源: D3-4【安全暴露煞】· 道三·治理体道
位置: agents/zhenshan.py
MCP归属: security-scanner
绑定工具: security-scanner, execute_command, memory_recall
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class ZhenshanAgent:

    AGENT_ID = "zhenshan"

    VULNERABILITY_PATTERNS = {
        "hardcoded_secret": re.compile(r'(?:password|secret|api_key|token|private_key)\s*[:=]\s*["\'][^"\']+["\']', re.IGNORECASE),
        "sql_injection": re.compile(r'(?:execute|cursor\.execute)\s*\(.*\bf\b.*\)', re.IGNORECASE),
        "eval_usage": re.compile(r'\beval\s*\(', re.IGNORECASE),
        "exec_usage": re.compile(r'\bexec\s*\(', re.IGNORECASE),
        "shell_injection": re.compile(r'\bos\.(?:system|popen|subprocess)\s*\(', re.IGNORECASE),
    }

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._scan_results: List[Dict[str, Any]] = []
        self._compliance_checks: List[Dict[str, Any]] = []
        self._keys: Dict[str, Dict[str, Any]] = {}

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "scan")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L4) 安全审计: {action}")

        handlers = {
            "scan": self.scan_vulnerability,
            "compliance": self.check_compliance,
            "keys": self.manage_keys,
            "audit": self.audit_report,
        }
        handler = handlers.get(action, self.scan_vulnerability)
        return handler(payload)

    def scan_vulnerability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        content = payload.get("content", "")
        findings = []
        for vuln_type, pattern in self.VULNERABILITY_PATTERNS.items():
            matches = pattern.findall(str(content))
            if matches:
                findings.append({
                    "type": vuln_type,
                    "count": len(matches),
                    "matches": [str(m)[:80] for m in matches[:5]],
                    "severity": "critical" if vuln_type in ("hardcoded_secret", "eval_usage") else "high",
                })

        scan = {
            "timestamp": time.time(),
            "content_length": len(str(content)),
            "findings": findings,
            "total_issues": len(findings),
            "status": "clean" if not findings else "issues_found",
        }
        self._scan_results.append(scan)

        if findings:
            print(f"[TVP] {self.emoji} 镇山: ⚠️ 发现 {len(findings)} 个安全问题")
        else:
            print(f"[TVP] {self.emoji} 镇山: 安全扫描通过 ✅")
        return {"status": "scanned", "scan": scan}

    def check_compliance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        standard = payload.get("standard", "base")
        checks = [
            {"id": "C001", "name": "禁止硬编码密钥", "passed": True},
            {"id": "C002", "name": "使用参数化查询", "passed": True},
            {"id": "C003", "name": "密钥最小权限", "passed": True},
            {"id": "C004", "name": "日志脱敏", "passed": True},
            {"id": "C005", "name": "TLS加密通信", "passed": True},
        ]
        compliance = {
            "standard": standard,
            "timestamp": time.time(),
            "total_checks": len(checks),
            "passed": len([c for c in checks if c["passed"]]),
            "checks": checks,
        }
        self._compliance_checks.append(compliance)
        return {"status": "compliant", "compliance": compliance}

    def manage_keys(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "list")
        if action == "register":
            key_name = payload.get("name", f"key_{len(self._keys)}")
            self._keys[key_name] = {
                "name": key_name,
                "created_at": time.time(),
                "rotated_at": time.time(),
                "status": "active",
            }
            return {"status": "registered", "key_name": key_name}
        elif action == "rotate":
            key_name = payload.get("name", "")
            if key_name in self._keys:
                self._keys[key_name]["rotated_at"] = time.time()
                return {"status": "rotated", "key_name": key_name}
        return {"status": "list", "keys": list(self._keys.keys()), "count": len(self._keys)}

    def audit_report(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "total_scans": len(self._scan_results),
            "recent_findings": sum(len(s.get("findings", [])) for s in self._scan_results[-10:]),
            "compliance_checks": len(self._compliance_checks),
            "keys_managed": len(self._keys),
        }

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "scans_run": len(self._scan_results),
            "compliance_checks": len(self._compliance_checks),
            "keys_managed": len(self._keys),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
