"""
RecoveryAgent - Automatic Error Diagnosis & Self-Healing
=========================================================
Classifies errors, determines fix strategy, attempts auto-recovery,
and escalates to human notification when recovery fails.

Recovery Strategies:
    1. Dependency Missing → Re-run dependency fix
    2. Build Failure → Clean + Retry with exponential backoff
    3. Import Error → Re-install package + re-copy to _internal
    4. Port Conflict → Kill existing process + retry
    5. File Lock → Force kill + retry
    6. Unknown → Escalate with detailed diagnostics
"""

import os
import sys
import time
import re
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field

from agents.pipeline_logger import PipelineLogger, LogLevel
from agents.orchestrator import PipelineState


class ErrorCategory:
    DEPENDENCY_MISSING = "dependency_missing"
    BUILD_FAILURE = "build_failure"
    IMPORT_ERROR = "import_error"
    PORT_CONFLICT = "port_conflict"
    FILE_LOCK = "file_lock"
    ENV_MISSING = "env_missing"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class DiagnosedError:
    category: str
    stage: PipelineState
    message: str
    suggestion: str
    auto_fixable: bool
    fix_function: str = ""
    recoverable: bool = True


class RecoveryAgent:
    """
    Self-healing agent with error classification and automated recovery.
    Implements exponential backoff retry with increasing delay.
    """

    PYTHON_EXE = str(Path(__file__).resolve().parent.parent / "python" / "python.exe")
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 5

    def _resolve_python(self) -> str:
        try:
            from core.shared.config import get_python_executable
            return str(get_python_executable())
        except Exception:
            return self.PYTHON_EXE

    ERROR_PATTERNS = [
        (r"No module named ['\"]?(\S+?)['\"]?", ErrorCategory.DEPENDENCY_MISSING,
         "Missing Python module: {0}. Run dependency fix or pip install."),
        (r"\[MISS\]\s+(\S+)", ErrorCategory.DEPENDENCY_MISSING,
         "Missing dependency: {0}. Copy from source site-packages."),
        (r"\[FAIL\]\s+(\S+?):\s*No module named", ErrorCategory.DEPENDENCY_MISSING,
         "Import failure for {0}. Check _internal path and retry fix."),
        (r"Import failed:\s*(\S+?)\s*-", ErrorCategory.IMPORT_ERROR,
         "Import error for {0}. Path issue, re-run dependency fix."),
        (r"PermissionError|WinError 5", ErrorCategory.FILE_LOCK,
         "File lock/permission error. Kill holding process and retry."),
        (r"Address already in use|port already|EADDRINUSE", ErrorCategory.PORT_CONFLICT,
         "Port conflict. Kill existing process using the port."),
        (r"Build failed|error:.*compilation", ErrorCategory.BUILD_FAILURE,
         "Build compilation error. Check toolchain and retry."),
        (r"ImportError|ModuleNotFoundError", ErrorCategory.IMPORT_ERROR,
         "Import error. Verify package installation and path."),
        (r"Connection refused|HTTPConnectionPool|timeout", ErrorCategory.NETWORK_ERROR,
         "Network connectivity issue. Check network and retry."),
    ]

    def __init__(self, logger: Optional[PipelineLogger] = None):
        self.logger = logger or PipelineLogger()
        self.recovery_history: List[Dict] = []
        self.retry_counts: Dict[PipelineState, int] = {}

    def diagnose(self, state: PipelineState, error_message: str,
                 context: Optional[Dict] = None) -> DiagnosedError:
        """Classify error based on message patterns and stage context."""

        self.logger.log(LogLevel.INFO, "Recovery", "RecoveryAgent",
                        f"Diagnosing error at stage [{state.label}]")

        for pattern, category, suggestion in self.ERROR_PATTERNS:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                detail = match.group(1) if match.groups() else "unknown"
                return DiagnosedError(
                    category=category,
                    stage=state,
                    message=error_message[:200],
                    suggestion=suggestion.format(detail),
                    auto_fixable=category != ErrorCategory.UNKNOWN,
                    fix_function=self._get_fix_function(category),
                )

        return DiagnosedError(
            category=ErrorCategory.UNKNOWN,
            stage=state,
            message=error_message[:200],
            suggestion="Unknown error type. Manual investigation required.",
            auto_fixable=False,
            recoverable=False,
        )

    def _get_fix_function(self, category: str) -> str:
        mapping = {
            ErrorCategory.DEPENDENCY_MISSING: "_fix_dependency",
            ErrorCategory.FILE_LOCK: "_fix_file_lock",
            ErrorCategory.PORT_CONFLICT: "_fix_port_conflict",
            ErrorCategory.BUILD_FAILURE: "_fix_build_failure",
            ErrorCategory.IMPORT_ERROR: "_fix_import_error",
            ErrorCategory.NETWORK_ERROR: "_fix_network",
        }
        return mapping.get(category, "generic")

    def attempt_recovery(self, state: PipelineState,
                         failed_tasks: List) -> bool:
        """
        Attempt automatic recovery based on error diagnosis.
        Returns True if recovery was successful.
        """

        retry_count = self.retry_counts.get(state, 0)

        if retry_count >= self.MAX_RETRIES:
            self.logger.log(LogLevel.FATAL, "Recovery", "RecoveryAgent",
                            f"Max retries ({self.MAX_RETRIES}) exceeded for [{state.label}]. "
                            f"Manual intervention required.")
            self._send_alert(state, f"Max retries exceeded ({retry_count})")
            return False

        self.retry_counts[state] = retry_count + 1
        backoff = self.BASE_BACKOFF_SECONDS * (2 ** retry_count)

        self.logger.log(LogLevel.WARN, "Recovery", "RecoveryAgent",
                        f"Recovery attempt {retry_count + 1}/{self.MAX_RETRIES} "
                        f"for [{state.label}] (backoff: {backoff}s)")

        error_msg = ""
        if failed_tasks:
            last_task = failed_tasks[-1] if hasattr(failed_tasks[-1], 'message') else None
            error_msg = str(last_task) if last_task else str(failed_tasks[-1])

        diagnosis = self.diagnose(state, error_msg)

        self.recovery_history.append({
            "stage": state.label,
            "attempt": retry_count + 1,
            "category": diagnosis.category,
            "diagnosis": diagnosis.suggestion,
            "timestamp": time.time(),
        })

        self.logger.log(LogLevel.INFO, "Recovery", "RecoveryAgent",
                        f"Diagnosis: [{diagnosis.category}] {diagnosis.suggestion}")

        if not diagnosis.auto_fixable or not diagnosis.recoverable:
            self._send_alert(state, diagnosis.suggestion)
            return False

        try:
            fix_method = getattr(self, diagnosis.fix_function, None)
            if fix_method:
                self.logger.log(LogLevel.INFO, "Recovery", "RecoveryAgent",
                                f"Applying fix: {diagnosis.fix_function}...")
                result = fix_method()
                time.sleep(backoff)
                return result
        except Exception as e:
            self.logger.log(LogLevel.ERROR, "Recovery", "RecoveryAgent",
                            f"Fix failed: {e}")

        time.sleep(backoff)
        return True

    def _fix_dependency(self) -> bool:
        self.logger.log(LogLevel.INFO, "Recovery", "RecoveryAgent",
                        "Re-running dependency fix...")

        fix_script = self.PROJECT_ROOT / "auto_fix_all.py"
        if fix_script.exists():
            try:
                result = subprocess.run(
                    [self.PYTHON_EXE, str(fix_script)],
                    capture_output=True, text=True, timeout=300
                )
                return result.returncode == 0
            except Exception:
                return False

        try:
            result = subprocess.run(
                [self.PYTHON_EXE, "-m", "pip", "install", "typing_extensions",
                 "python-dotenv", "websockets", "aiofiles"],
                capture_output=True, text=True, timeout=120
            )
            return result.returncode == 0
        except Exception:
            return False

    def _fix_file_lock(self) -> bool:
        """Kill processes holding files."""
        self.logger.log(LogLevel.INFO, "Recovery", "RecoveryAgent",
                        "Attempting to resolve file locks...")

        processes = ["AI_Memory_System_Backend.exe", "python.exe"]

        for proc in processes:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc],
                    capture_output=True,
                    timeout=10
                )
            except Exception:
                pass

        time.sleep(3)
        return True

    def _fix_port_conflict(self) -> bool:
        """Resolve port conflicts."""
        self.logger.log(LogLevel.INFO, "Recovery", "RecoveryAgent",
                        "Resolving port conflicts...")

        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=10
            )

            for line in result.stdout.split('\n'):
                if ':8771' in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid],
                            capture_output=True
                        )

            time.sleep(2)
            return True
        except Exception:
            return False

    def _fix_build_failure(self) -> bool:
        """Clean and retry build."""
        self.logger.log(LogLevel.INFO, "Recovery", "RecoveryAgent",
                        "Cleaning build artifacts...")

        build_dirs = [
            self.PROJECT_ROOT / "output" / "build_pyinstaller",
            self.PROJECT_ROOT / "output" / "AI_Memory_System_v4.0_Windows",
        ]

        for d in build_dirs:
            import shutil
            try:
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

        time.sleep(2)
        return True

    def _fix_import_error(self) -> bool:
        """Fix import errors by reinstalling and re-copying."""
        return self._fix_dependency()

    def _fix_network(self) -> bool:
        """Wait and retry for network issues."""
        self.logger.log(LogLevel.INFO, "Recovery", "RecoveryAgent",
                        "Waiting for network recovery...")
        time.sleep(10)
        return True

    def _send_alert(self, state: PipelineState, reason: str) -> None:
        """Send alert notification when auto-recovery fails."""
        alert_dir = self.PROJECT_ROOT / "alerts"
        alert_dir.mkdir(exist_ok=True)

        alert_file = alert_dir / f"alert_{int(time.time())}.txt"
        content = (
            f"=== AI Memory System - Pipeline Alert ===\n"
            f"Time:     {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Stage:    {state.label}\n"
            f"Reason:   {reason}\n"
            f"History:  {len(self.recovery_history)} recovery attempts\n"
            f"Action:   Manual intervention required\n"
            f"===========================================\n"
        )
        alert_file.write_text(content)

        self.logger.log(LogLevel.FATAL, "Recovery", "RecoveryAgent",
                        f"ALERT SENT: {alert_file}")
        self.logger.log(LogLevel.FATAL, "Recovery", "RecoveryAgent",
                        f"Reason: {reason}")

    def get_recovery_stats(self) -> Dict[str, Any]:
        return {
            "total_attempts": len(self.recovery_history),
            "attempts_by_stage": {
                stage.label: count for stage, count in self.retry_counts.items()
            },
            "history": self.recovery_history[-10:],
        }
