# -*- coding: utf-8 -*-
"""
天机v9.1 专业级审计引擎 (Tianji Professional Audit Engine) v2.0
================================================================
[SSS-PhaseB] 已瘦身: 1886行 → ~180行 (主引擎+re-export兼容层)

原始文件已拆分为:
- audit_models.py         → 数据模型 (Severity/Status/Result/Context等)
- audit_base.py           → BaseAuditor基类
- audit_functionality.py  → FunctionalityAuditor (功能完整性)
- audit_stability_perf.py → StabilityAuditor + PerformanceAuditor
- audit_security_data.py  → SecurityAuditor + DataAccuracyAuditor

5维审计: 功能完整性 / 系统稳定性 / 性能指标 / 安全合规 / 数据准确性
流程编排: 预检→执行→异常处理→结果评估→报告生成

Usage (向后兼容):
    from core.enforcement.audit_engine import TianjiAuditEngine, FunctionalityAuditor, ...
    engine = TianjiAuditEngine()
    results = engine.run(rounds=3)
"""

import json
import os
import shutil
import tempfile
import time
import traceback
from typing import List, Optional, Tuple

# === 导入拆分后的模块 ===
from .audit_models import (
    AuditContext,
    AuditResult,
    AuditSeverity,
    AuditStatus,
    AuditDimensionReport,
)
from .audit_base import BaseAuditor
from .audit_functionality import FunctionalityAuditor
from .audit_stability_perf import StabilityAuditor, PerformanceAuditor
from .audit_security_data import SecurityAuditor, DataAccuracyAuditor


class TianjiAuditEngine:
    """
    天机专业级审计引擎 — 统一入口

    流程: Precheck → Execute → Evaluate → Report
    """

    VERSION = "2.0.0"
    AUDITOR_CLASSES = [
        FunctionalityAuditor,
        StabilityAuditor,
        PerformanceAuditor,
        SecurityAuditor,
        DataAccuracyAuditor,
    ]

    def __init__(self, ctx: Optional[AuditContext] = None):
        if ctx is None:
            ctx = AuditContext()
        if not ctx.root_dir:
            ctx.root_dir = os.environ.get(
                "AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), "..")
            )
        self._ctx = ctx
        self._results: List[AuditResult] = []
        self._lines: List[str] = []

    def _L(self, msg: str):
        self._lines.append(msg)
        print(msg)

    def _precheck(self) -> Tuple[bool, List[str]]:
        """Phase 1: 预检"""
        self._L(f"\n{'─' * 70}")
        self._L("  Phase 1: 预检 (Precheck)")
        self._L(f"{'─' * 70}")
        issues = []
        root = self._ctx.root_dir
        if not os.path.exists(root):
            issues.append(f"Root not found: {root}")
        else:
            self._L(f"  ✅ Root: {root}")
        core_dir = os.path.join(root, "core")
        if os.path.exists(core_dir):
            py_count = len([f for f in os.listdir(core_dir) if f.endswith(".py")])
            self._L(f"  ✅ Core: {py_count} Python files")
        else:
            issues.append("Core directory missing")
        try:
            from core.shared.version import __version__
            self._L(f"  ✅ Version: v{__version__}")
        except Exception as e:
            issues.append(f"Version check failed: {e}")
        if issues:
            self._L(f"  ⚠️  Precheck: {len(issues)} issues")
        else:
            self._L("  ✅ Precheck passed")
        return len(issues) == 0, issues

    def _execute(self, round_num: int) -> AuditResult:
        """Phase 2: 执行审计"""
        result = AuditResult(round_num=round_num, start_time=time.time())
        self._L(f"\n{'─' * 70}")
        self._L(f"  Phase 2: 执行审计 (Execute) — Round {round_num}")
        self._L(f"{'─' * 70}")
        tmpdir = tempfile.mkdtemp(prefix=f"tianji_audit_r{round_num}_")
        self._ctx.tmpdir = tmpdir
        self._ctx.round_num = round_num
        try:
            for auditor_cls in self.AUDITOR_CLASSES:
                dim = auditor_cls.DIMENSION
                if hasattr(self._ctx, 'skip_dimensions') and dim in self._ctx.skip_dimensions:
                    self._L(f"\n  ⏭️  Skip: {dim}")
                    continue
                self._L(f"\n  🔍 {dim} (weight={auditor_cls.WEIGHT})")
                t0 = time.time()
                try:
                    auditor = auditor_cls(self._ctx)
                    report = auditor.run()
                    result.dimensions[dim] = report
                    elapsed = (time.time() - t0) * 1000
                    self._L(
                        f"    {report.passed}/{report.total_checks} PASS "
                        f"(score {report.score:.1f}/{report.max_score:.1f}, {elapsed:.0f}ms)"
                    )
                    for check in report.checks:
                        if check.status in (AuditStatus.FAIL, AuditStatus.WARN, AuditStatus.ERROR):
                            icon = {"FAIL": "❌", "WARN": "⚠️", "ERROR": "💥"}[check.status.value]
                            self._L(f"    {icon} {check.check_id}: {check.message}")
                except Exception as e:
                    self._L(f"    💥 {dim} crashed: {e}")
                    result.exceptions.append({"dimension": dim, "error": str(e), "traceback": traceback.format_exc()})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        result.end_time = time.time()
        return result

    def _evaluate(self, result: AuditResult) -> AuditResult:
        """Phase 3: 结果评估"""
        self._L(f"\n{'─' * 70}")
        self._L("  Phase 3: 结果评估 (Evaluate)")
        self._L(f"{'─' * 70}")
        total_score = 0.0; total_max = 0.0
        for dim_name, report in result.dimensions.items():
            weight = next((c.WEIGHT for c in self.AUDITOR_CLASSES if c.DIMENSION == dim_name), 1.0)
            ws = report.score * weight; wm = report.max_score * weight
            total_score += ws; total_max += wm
            self._L(
                f"  {dim_name:20s}: {report.passed}/{report.total_checks} PASS ({report.pass_rate:.1f}%) | "
                f"score {report.score:.1f}/{report.max_score:.1f} (×{weight}={ws:.1f}/{wm:.1f})"
            )
        result.overall_score = total_score
        result.overall_max_score = total_max
        score_rate = (total_score / total_max * 100) if total_max > 0 else 0
        result.overall_pass = result.total_failed == 0 and score_rate >= 90.0 and len(result.exceptions) == 0
        self._L(
            f"\n  {'OVERALL':20s}: {result.total_passed}/{result.total_checks} PASS "
            f"({result.overall_pass_rate:.1f}%) | score {total_score:.1f}/{total_max:.1f} ({score_rate:.1f}%)"
        )
        self._L(f"  Verdict: {'✅ PASS' if result.overall_pass else '❌ FAIL'}")
        return result

    def _report(self, results: List[AuditResult]):
        """Phase 4: 报告生成"""
        self._L(f"\n{'─' * 70}")
        self._L("  Phase 4: 报告生成 (Report)")
        self._L(f"{'─' * 70}")
        self._L("=" * 70)
        self._L("  天机v9.1 专业级审计报告")
        self._L(f"  Engine: v{self.VERSION} | {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self._L("=" * 70)
        for r in results:
            self._L(
                f"\n  Round {r.round_num}: {r.total_passed}/{r.total_checks} PASS "
                f"({r.overall_pass_rate:.1f}%) | score {r.overall_score:.1f}/{r.overall_max_score:.1f} | {r.duration_ms:.0f}ms"
            )
        final = results[-1] if results else None
        if final:
            self._L(f"\n  {'─' * 60}")
            self._L("  Dimension Breakdown:")
            for dn, rp in final.dimensions.items():
                self._L(
                    f"    {dn:20s}: {rp.pass_rate:6.1f}% | score {rp.score_rate:6.1f}% | "
                    f"{rp.passed}P/{rp.warned}W/{rp.failed}F/{rp.errored}E"
                )
            all_pass = all(r.overall_pass for r in results)
            self._L(f"\n  Final Verdict: {'✅ ALL ROUNDS PASS' if all_pass else '❌ SOME ROUNDS FAILED'}")

    def run(self, rounds: int = 3) -> List[AuditResult]:
        """执行完整审计流程"""
        self._L(f"\n{'=' * 70}")
        self._L(f"  天机v9.1 专业级审计引擎 v{self.VERSION}")
        self._L("  5维: 功能完整性/系统稳定性/性能指标/安全合规/数据准确性")
        self._L(f"  Rounds: {rounds} | Root: {self._ctx.root_dir}")
        self._L(f"{'=' * 70}")
        passed, _ = self._precheck()
        if not passed:
            self._L("  ❌ Precheck failed — aborting")
            return []
        self._results = []
        for r in range(1, rounds + 1):
            result = self._execute(r)
            result = self._evaluate(result)
            self._results.append(result)
        self._report(self._results)
        return self._results

    def to_json(self) -> str:
        """导出JSON格式报告"""
        data = []
        for r in self._results:
            rd = {
                "round": r.round_num, "start_time": r.start_time, "end_time": r.end_time,
                "duration_ms": r.duration_ms, "total_checks": r.total_checks,
                "total_passed": r.total_passed, "total_failed": r.total_failed,
                "overall_pass_rate": r.overall_pass_rate, "overall_score": r.overall_score,
                "overall_max_score": r.overall_max_score, "overall_pass": r.overall_pass,
                "exceptions": r.exceptions, "dimensions": {},
            }
            for dn, rp in r.dimensions.items():
                rd["dimensions"][dn] = {
                    "total_checks": rp.total_checks, "passed": rp.passed, "warned": rp.warned,
                    "failed": rp.failed, "skipped": rp.skipped, "errored": rp.errored,
                    "score": rp.score, "max_score": rp.max_score,
                    "pass_rate": rp.pass_rate, "score_rate": rp.score_rate,
                    "checks": [{"id": c.check_id, "status": c.status.value, "severity": c.severity.value,
                                "score": c.score, "threshold": c.threshold, "message": c.message}
                               for c in rp.checks],
                }
            data.append(rd)
        return json.dumps(data, ensure_ascii=False, indent=2)


__all__ = [
    # 主引擎
    "TianjiAuditEngine",
    # 审计器
    "BaseAuditor",
    "FunctionalityAuditor", "StabilityAuditor", "PerformanceAuditor",
    "SecurityAuditor", "DataAccuracyAuditor",
    # 数据模型
    "AuditSeverity", "AuditStatus", "AuditCheckResult",
    "AuditDimensionReport", "AuditContext", "AuditResult",
]
