"""
Centralized Pipeline Logging & Metrics System
=============================================
Thread-safe, multi-level logging with real-time metrics collection.
Tracks: stage duration, resource usage, test coverage, error rates.
"""

import os
import sys
import json
import time
import threading
import traceback
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40
    FATAL = 50


@dataclass
class LogEntry:
    timestamp: str
    level: LogLevel
    stage: str
    agent: str
    message: str
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageMetrics:
    stage_name: str
    start_time: float
    end_time: float = 0.0
    status: str = "running"
    sub_stages: int = 0
    passed: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)
    resource_usage: Dict[str, float] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def pass_rate(self) -> float:
        total = self.passed + self.failed
        return self.passed / total if total > 0 else 0.0


class PipelineLogger:
    """
    Thread-safe centralized logger with metrics collection.
    Singleton pattern ensures single metrics registry.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: Optional[Path] = None, log_level: LogLevel = LogLevel.INFO):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.log_dir = log_dir or (Path(__file__).resolve().parent.parent / "logs")
        self.log_level = log_level
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.entries: List[LogEntry] = []
        self.stages: Dict[str, StageMetrics] = {}
        self.pipeline_start_time = time.time()
        self._write_lock = threading.Lock()

        self._log_file = self.log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self._json_file = self.log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    def log(self, level: LogLevel, stage: str, agent: str, message: str,
            duration_ms: float = 0.0, metadata: Optional[Dict] = None):
        if level.value < self.log_level.value:
            return

        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            stage=stage,
            agent=agent,
            message=message,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )

        with self._write_lock:
            self.entries.append(entry)

        prefix = {LogLevel.DEBUG: "[DBG]", LogLevel.INFO: "[INF]",
                   LogLevel.WARN: "[WRN]", LogLevel.ERROR: "[ERR]",
                   LogLevel.FATAL: "[FTL]"}.get(level, "---")

        line = f"{entry.timestamp} {prefix} [{stage:>12}][{agent:>16}] {message}"
        if duration_ms > 0:
            line += f" ({duration_ms:.0f}ms)"

        print(line)
        sys.stdout.flush()

        self._append_file(line)

    def stage_start(self, stage_name: str) -> None:
        metrics = StageMetrics(stage_name=stage_name, start_time=time.time())
        with self._write_lock:
            self.stages[stage_name] = metrics
        self.log(LogLevel.INFO, stage_name, "Pipeline", f"Stage [{stage_name}] started")

    def stage_end(self, stage_name: str, status: str = "completed") -> None:
        with self._write_lock:
            if stage_name in self.stages:
                self.stages[stage_name].end_time = time.time()
                self.stages[stage_name].status = status

        duration = self.stages[stage_name].duration_seconds if stage_name in self.stages else 0
        self.log(LogLevel.INFO, stage_name, "Pipeline",
                 f"Stage [{stage_name}] {status} ({duration:.1f}s)")

    def record_test_result(self, stage_name: str, passed: int, failed: int) -> None:
        with self._write_lock:
            if stage_name in self.stages:
                self.stages[stage_name].passed += passed
                self.stages[stage_name].failed += failed

    def record_error(self, stage_name: str, agent: str, error: str) -> None:
        with self._write_lock:
            if stage_name in self.stages:
                self.stages[stage_name].errors.append(error)
        self.log(LogLevel.ERROR, stage_name, agent, error)

    def _append_file(self, line: str) -> None:
        try:
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass

    def generate_report(self) -> Dict[str, Any]:
        total_duration = time.time() - self.pipeline_start_time
        total_tests = sum(s.passed + s.failed for s in self.stages.values())
        total_passed = sum(s.passed for s in self.stages.values())
        total_failed = sum(s.failed for s in self.stages.values())
        error_count = sum(len(s.errors) for s in self.stages.values())

        report = {
            "pipeline_version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "total_duration_seconds": round(total_duration, 2),
            "summary": {
                "stages": len(self.stages),
                "total_tests": total_tests,
                "passed": total_passed,
                "failed": total_failed,
                "pass_rate": round(total_passed / total_tests * 100, 1) if total_tests > 0 else 0,
                "errors": error_count,
                "status": "PASS" if total_failed == 0 and error_count == 0 else "FAIL"
            },
            "stages": {},
            "critical_errors": []
        }

        for name, metrics in self.stages.items():
            report["stages"][name] = {
                "status": metrics.status,
                "duration_seconds": round(metrics.duration_seconds, 2),
                "sub_stages": metrics.sub_stages,
                "tests_passed": metrics.passed,
                "tests_failed": metrics.failed,
                "pass_rate": round(metrics.pass_rate * 100, 1),
                "errors": metrics.errors[-5:]
            }

        for entry in self.entries:
            if entry.level in (LogLevel.ERROR, LogLevel.FATAL):
                report["critical_errors"].append({
                    "stage": entry.stage,
                    "agent": entry.agent,
                    "message": entry.message,
                    "timestamp": entry.timestamp
                })

        report["critical_errors"] = report["critical_errors"][-20:]

        try:
            with open(self._json_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return report

    def print_summary(self) -> None:
        report = self.generate_report()
        s = report["summary"]

        print("\n" + "=" * 80)
        print("  PIPELINE EXECUTION REPORT")
        print("=" * 80)
        print(f"  Duration:  {report['total_duration_seconds']:.1f}s")
        print(f"  Stages:    {s['stages']}")
        print(f"  Tests:     {s['total_tests']} total | {s['passed']} passed | {s['failed']} failed")
        print(f"  Pass Rate: {s['pass_rate']}%")
        print(f"  Errors:    {s['errors']}")
        print(f"  Status:    {s['status']}")
        print("=" * 80)

        for name, stage in report["stages"].items():
            icon = "[OK]" if stage["status"] == "completed" else "[FAIL]"
            print(f"  {icon} {name:<20} {stage['duration_seconds']:>6.1f}s  "
                  f"tests: {stage['tests_passed']}/{stage['tests_passed']+stage['tests_failed']}"
                  f"  rate: {stage['pass_rate']}%")

        if report["critical_errors"]:
            print(f"\n  Critical Errors ({len(report['critical_errors'])}):")
            for err in report["critical_errors"][:5]:
                print(f"  - [{err['stage']}] {err['message'][:100]}")

        print("=" * 80)
        print(f"  Log:  {self._log_file}")
        print(f"  JSON: {self._json_file}")
        print("=" * 80)
