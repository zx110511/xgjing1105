# -*- coding: utf-8 -*-
"""
审计器基类
[SSS-PhaseB] 从audit_engine.py拆分

提供:
- BaseAuditor: 所有审计器的基类，提供_check/_pass/_warn/_fail/_skip/_error快捷方法
"""

import threading
from typing import Dict

from .audit_models import (
    AuditCheckResult,
    AuditContext,
    AuditDimensionReport,
    AuditSeverity,
    AuditStatus,
)


class BaseAuditor:
    """
    审计器基类 — 提供统一的检查结果记录接口

    子类需实现:
    - DIMENSION: 审计维度名称
    - WEIGHT: 维度权重
    - run(): 执行审计逻辑
    """

    DIMENSION = "base"
    WEIGHT = 1.0

    def __init__(self, ctx: AuditContext):
        self._ctx = ctx
        self._report = AuditDimensionReport(dimension=self.DIMENSION)
        self._lock = threading.Lock()

    def _check(
        self,
        check_id: str,
        status: AuditStatus,
        severity: AuditSeverity,
        score: float,
        threshold: float,
        message: str,
        detail: Dict = None,
        duration_ms: float = 0.0,
    ) -> AuditCheckResult:
        """记录一条检查结果"""
        result = AuditCheckResult(
            check_id=check_id,
            dimension=self.DIMENSION,
            status=status,
            severity=severity,
            score=score,
            threshold=threshold,
            message=message,
            detail=detail or {},
            duration_ms=duration_ms,
        )
        with self._lock:
            self._report.checks.append(result)
            self._report.total_checks += 1
            self._report.max_score += threshold
            self._report.score += score
            # 状态计数
            if status == AuditStatus.PASS:
                self._report.passed += 1
            elif status == AuditStatus.WARN:
                self._report.warned += 1
            elif status == AuditStatus.FAIL:
                self._report.failed += 1
            elif status == AuditStatus.SKIP:
                self._report.skipped += 1
            elif status == AuditStatus.ERROR:
                self._report.errored += 1
        return result

    def _pass(
        self,
        check_id: str,
        score: float,
        threshold: float,
        message: str,
        detail: Dict = None,
        duration_ms: float = 0.0,
    ) -> AuditCheckResult:
        """记录PASS结果"""
        return self._check(
            check_id, AuditStatus.PASS, AuditSeverity.INFO,
            score, threshold, message, detail, duration_ms,
        )

    def _warn(
        self,
        check_id: str,
        score: float,
        threshold: float,
        message: str,
        detail: Dict = None,
        duration_ms: float = 0.0,
    ) -> AuditCheckResult:
        """记录WARN结果"""
        return self._check(
            check_id, AuditStatus.WARN, AuditSeverity.MEDIUM,
            score, threshold, message, detail, duration_ms,
        )

    def _fail(
        self,
        check_id: str,
        score: float,
        threshold: float,
        message: str,
        severity: AuditSeverity = AuditSeverity.HIGH,
        detail: Dict = None,
        duration_ms: float = 0.0,
    ) -> AuditCheckResult:
        """记录FAIL结果"""
        return self._check(
            check_id, AuditStatus.FAIL, severity,
            score, threshold, message, detail, duration_ms,
        )

    def _skip(
        self, check_id: str, message: str, threshold: float = 0.0
    ) -> AuditCheckResult:
        """记录SKIP结果"""
        return self._check(
            check_id, AuditStatus.SKIP, AuditSeverity.INFO,
            0.0, threshold, message,
        )

    def _error(
        self, check_id: str, message: str, threshold: float = 0.0, detail: Dict = None
    ) -> AuditCheckResult:
        """记录ERROR结果"""
        return self._check(
            check_id, AuditStatus.ERROR, AuditSeverity.CRITICAL,
            0.0, threshold, message, detail,
        )

    def run(self) -> AuditDimensionReport:
        """执行审计（子类实现）"""
        raise NotImplementedError

    def get_report(self) -> AuditDimensionReport:
        """获取维度报告"""
        return self._report
