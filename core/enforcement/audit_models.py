# -*- coding: utf-8 -*-
"""
审计引擎数据模型
[SSS-PhaseB] 从audit_engine.py拆分

包含:
- AuditSeverity: 审计严重程度枚举
- AuditStatus: 审计状态枚举
- AuditCheckResult: 单项检查结果
- AuditDimensionReport: 维度报告
- AuditContext: 审计上下文配置
- AuditResult: 最终审计结果
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List



from typing import Optional

class AuditSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AuditStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass
class AuditCheckResult:
    check_id: str
    dimension: str
    status: AuditStatus
    severity: AuditSeverity
    score: float
    threshold: float
    message: str
    detail: Dict = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class AuditDimensionReport:
    dimension: str
    total_checks: int = 0
    passed: int = 0
    warned: int = 0
    failed: int = 0
    skipped: int = 0
    errored: int = 0
    score: float = 0.0
    max_score: float = 0.0
    checks: List[AuditCheckResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total_checks * 100) if self.total_checks > 0 else 0.0

    @property
    def score_rate(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0.0


@dataclass
class AuditContext:
    root_dir: str = ""
    db_path: str = ""
    asset_db_path: str = ""
    tmpdir: str = ""
    round_num: int = 1
    timeout_seconds: float = 300.0
    parallel_workers: int = 4
    thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "functionality_pass_rate": 100.0,
            "functionality_score": 95.0,
            "stability_pass_rate": 95.0,
            "stability_score": 90.0,
            "performance_pass_rate": 90.0,
            "performance_score": 85.0,
            "security_pass_rate": 100.0,
            "security_score": 95.0,
            "data_accuracy_pass_rate": 95.0,
            "data_accuracy_score": 90.0,
        }
    )


@dataclass
class AuditResult:
    status: AuditStatus = AuditStatus.PASS
    overall_score: float = 100.0
    dimensions: Dict[str, AuditDimensionReport] = field(default_factory=dict)
    critical_issues: List[AuditCheckResult] = field(default_factory=list)
    high_issues: List[AuditCheckResult] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: float = 0.0
    summary: str = ""
    # [FIX-AUDIT] 补充engine使用的字段
    round_num: int = 1
    start_time: float = 0.0
    end_time: float = 0.0
    total_checks: int = 0
    total_passed: int = 0
    total_failed: int = 0
    overall_max_score: float = 0.0
    _overall_pass: bool = False

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.start_time == 0.0:
            self.start_time = self.timestamp
        # 默认根据total_failed推断
        self._overall_pass = (self.total_failed == 0 and self.total_checks > 0)

    @property
    def overall_pass_rate(self) -> float:
        return (self.total_passed / self.total_checks * 100.0) if self.total_checks > 0 else 0.0

    @property
    def overall_pass(self) -> bool:
        return self._overall_pass

    @overall_pass.setter
    def overall_pass(self, value: bool):
        self._overall_pass = value

    @property
    def has_critical(self) -> bool:
        return any(i.severity == AuditSeverity.CRITICAL for i in self.critical_issues)

    @property
    def issue_count(self) -> int:
        return len(self.critical_issues) + len(self.high_issues)

    def add_issue(self, result: AuditCheckResult):
        if result.severity in (AuditSeverity.CRITICAL,):
            self.critical_issues.append(result)
        elif result.severity in (AuditSeverity.HIGH,):
            self.high_issues.append(result)
