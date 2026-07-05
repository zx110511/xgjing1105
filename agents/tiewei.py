"""
铁卫 — L0 基础设施守护Agent
===============================
SG门禁链执行、功能验证、安全测试、覆盖率分析。

灵境道谱溯源: D5-3【多Agent调度煞】· 道五·编排体道
位置: agents/tiewei.py
MCP归属: security-scanner
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


@dataclass
class GateResult:
    stage: str
    status: str
    duration_ms: float
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)


class TieweiAgent:

    AGENT_ID = "tiewei"

    GATE_CHAIN = [
        "SG0_ENV_READY",
        "SG1_IMPORT_VERIFY",
        "SG2_FUNCTIONAL",
        "SG3_MCP_INTEGRATION",
        "SG4_REGRESSION",
    ]

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._gate_results: List[GateResult] = []

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> List[GateResult]:
        print(f"[TVP] {self.emoji} {self.name}(L0) 启动质量门禁链 | 目标: {getattr(task, 'goal', '未知')}")
        self._gate_results.clear()

        for stage in self.GATE_CHAIN:
            start = time.time()
            try:
                result = self._run_gate(stage)
            except Exception as e:
                result = GateResult(
                    stage=stage,
                    status="ERROR",
                    duration_ms=(time.time() - start) * 1000,
                    summary=f"门禁异常: {e}",
                )
            self._gate_results.append(result)

            if result.status in ("FAILED", "ERROR"):
                print(f"[TVP] {self.emoji} {self.name}(L0) 门禁链中断于 {stage}: {result.summary}")
                break

            print(f"[TVP] {self.emoji} {self.name}(L0) {stage} 通过 ({result.duration_ms:.0f}ms)")

        passed = all(r.status == "PASSED" for r in self._gate_results)
        if passed:
            print(f"[TVP] {self.emoji} {self.name}(L0) 全门禁链通过 ✅")
        return self._gate_results

    def _run_gate(self, stage: str) -> GateResult:
        start = time.time()
        handlers = {
            "SG0_ENV_READY": self._gate_env_ready,
            "SG1_IMPORT_VERIFY": self._gate_import_verify,
            "SG2_FUNCTIONAL": self._gate_functional,
            "SG3_MCP_INTEGRATION": self._gate_mcp_integration,
            "SG4_REGRESSION": self._gate_regression,
        }
        handler = handlers.get(stage)
        if handler:
            return handler(start)
        duration_ms = (time.time() - start) * 1000
        return GateResult(stage=stage, status="SKIPPED", duration_ms=duration_ms, summary="未实现的检查器")

    def _gate_env_ready(self, start: float) -> GateResult:
        checks = {}
        checks["python"] = sys.version_info >= (3, 9)
        checks["tianji_root"] = Path(__file__).parent.parent.exists()
        checks["amim_loaded"] = self.amim is not None
        all_ok = all(checks.values())
        duration_ms = (time.time() - start) * 1000
        return GateResult(
            stage="SG0_ENV_READY",
            status="PASSED" if all_ok else "FAILED",
            duration_ms=duration_ms,
            summary="环境就绪" if all_ok else f"环境检查失败: {[k for k, v in checks.items() if not v]}",
            details=checks,
        )

    def _gate_import_verify(self, start: float) -> GateResult:
        import_modules = ["core.amim", "core.agent_orchestrator", "core.evolution_loop", "core.config"]
        results = {}
        for mod_name in import_modules:
            try:
                __import__(mod_name)
                results[mod_name] = True
            except ImportError as e:
                results[mod_name] = str(e)
        all_ok = all(v is True for v in results.values())
        duration_ms = (time.time() - start) * 1000
        return GateResult(
            stage="SG1_IMPORT_VERIFY",
            status="PASSED" if all_ok else "FAILED",
            duration_ms=duration_ms,
            summary="核心模块导入验证通过" if all_ok else f"导入失败: {[k for k, v in results.items() if v is not True]}",
            details=results,
        )

    def _gate_functional(self, start: float) -> GateResult:
        checks = {}
        checks["agent_count"] = self.amim.agent_count == 20
        checks["tool_count"] = self.amim.tool_count >= 24
        checks["self_bound"] = self.amim.can_agent_use_tool(self.AGENT_ID, "security-scanner")
        checks["self_defined"] = self.defn is not None and self.defn.agent_id == self.AGENT_ID
        all_ok = all(checks.values())
        duration_ms = (time.time() - start) * 1000
        return GateResult(
            stage="SG2_FUNCTIONAL",
            status="PASSED" if all_ok else "FAILED",
            duration_ms=duration_ms,
            summary="功能验证通过" if all_ok else f"功能检查失败: {[k for k, v in checks.items() if not v]}",
            details=checks,
        )

    def _gate_mcp_integration(self, start: float) -> GateResult:
        tool_names = ["security-scanner", "performance-profiler", "memory_recall", "execute_command"]
        results = {}
        for tool in tool_names:
            results[tool] = self.amim.can_agent_use_tool(self.AGENT_ID, tool)
        all_ok = all(results.values())
        duration_ms = (time.time() - start) * 1000
        return GateResult(
            stage="SG3_MCP_INTEGRATION",
            status="PASSED" if all_ok else "FAILED",
            duration_ms=duration_ms,
            summary="MCP工具绑定验证通过" if all_ok else f"工具绑定缺失: {[k for k, v in results.items() if not v]}",
            details=results,
        )

    def _gate_regression(self, start: float) -> GateResult:
        issues = self.amim.validate()
        duration_ms = (time.time() - start) * 1000
        return GateResult(
            stage="SG4_REGRESSION",
            status="PASSED" if len(issues) == 0 else "FAILED",
            duration_ms=duration_ms,
            summary="AMIM一致性验证通过" if len(issues) == 0 else f"发现{len(issues)}个一致性问题",
            details={"issue_count": len(issues), "issues": issues},
        )

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "gate_chain": self.GATE_CHAIN,
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
