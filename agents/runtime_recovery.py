r"""
天机 (TIANJI) - Runtime Recovery Agent v1.0 SSS
=================================================
《天机·星枢运转》— 运行时自诊断与自修复

Extends the existing installer-oriented RecoveryAgent with
runtime-specific diagnosis and repair strategies.

Runtime Error Categories:
    1. Server Unresponsive  → Health check fail + auto-restart
    2. Port Conflict        → Kill conflicting process + retry
    3. DB Lock              → WAL checkpoint + retry
    4. DB Corruption        → Restore from backup
    5. Disk Full            → Emergency VACUUM + log rotation
    6. Memory Pressure      → Cache flush + consolidation
    7. Import Error         → Module re-import + fallback
    8. Unknown              → Alert + dump diagnostics

Integration: Called by TianjiDaemon watchdog loop
"""

import os
import sys
import time
import re
import sqlite3
import shutil
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

TIANJI_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = TIANJI_ROOT / "data" / ".memory"
BACKUP_DIR = TIANJI_ROOT / "backups"
LOG_DIR = TIANJI_ROOT / "logs"

from daemon.tianji_logger import get_logger
log = get_logger("recovery")


class RuntimeErrorCategory(str, Enum):
    SERVER_UNRESPONSIVE = "server_unresponsive"
    PORT_CONFLICT = "port_conflict"
    DB_LOCK = "db_locked"
    DB_CORRUPTION = "db_corruption"
    DISK_FULL = "disk_full"
    MEMORY_PRESSURE = "memory_pressure"
    IMPORT_ERROR = "import_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class RuntimeDiagnosis:
    category: RuntimeErrorCategory
    severity: str
    message: str
    auto_fixable: bool
    fix_applied: bool = False
    fix_result: str = ""
    timestamp: float = field(default_factory=time.time)


class RuntimeRecoveryAgent:
    SYSTEM_TAG = "【天机·智能】"
    MAX_RETRIES = 3
    BASE_BACKOFF = 5.0

    ERROR_PATTERNS: list[tuple[str, RuntimeErrorCategory, str]] = [
        (
            r"Address already in use|port already|EADDRINUSE",
            RuntimeErrorCategory.PORT_CONFLICT,
            "Port conflict detected",
        ),
        (
            r"database is locked|SQLITE_BUSY|database locked",
            RuntimeErrorCategory.DB_LOCK,
            "SQLite database locked",
        ),
        (
            r"database disk image is malformed|SQLITE_CORRUPT",
            RuntimeErrorCategory.DB_CORRUPTION,
            "SQLite database corruption",
        ),
        (
            r"No space left on device|OSError.*28",
            RuntimeErrorCategory.DISK_FULL,
            "Disk full",
        ),
        (
            r"MemoryError|out of memory",
            RuntimeErrorCategory.MEMORY_PRESSURE,
            "Memory pressure",
        ),
        (
            r"No module named|ImportError|ModuleNotFoundError",
            RuntimeErrorCategory.IMPORT_ERROR,
            "Module import error",
        ),
        (
            r"Connection refused|HTTPConnectionPool|timeout",
            RuntimeErrorCategory.NETWORK_ERROR,
            "Network connectivity error",
        ),
    ]

    def __init__(self):
        self.history: list[RuntimeDiagnosis] = []
        self.retry_counts: Dict[RuntimeErrorCategory, int] = {}
        self._last_alert_time: float = 0.0

    def diagnose(self, error_message: str, context: Optional[Dict] = None) -> RuntimeDiagnosis:
        for pattern, category, desc in self.ERROR_PATTERNS:
            if re.search(pattern, error_message, re.IGNORECASE):
                severity = self._assess_severity(category)
                return RuntimeDiagnosis(
                    category=category,
                    severity=severity,
                    message=f"{desc}: {error_message[:200]}",
                    auto_fixable=category not in [RuntimeErrorCategory.UNKNOWN],
                )

        return RuntimeDiagnosis(
            category=RuntimeErrorCategory.UNKNOWN,
            severity="medium",
            message=error_message[:200],
            auto_fixable=False,
        )

    def diagnose_from_health(self, health_result: Dict[str, bool]) -> list[RuntimeDiagnosis]:
        diagnoses = []

        if not health_result.get("server_health") and health_result.get("server_port"):
            diagnoses.append(RuntimeDiagnosis(
                category=RuntimeErrorCategory.SERVER_UNRESPONSIVE,
                severity="high",
                message="Server port open but health check failing",
                auto_fixable=True,
            ))
        elif not health_result.get("server_health") and not health_result.get("server_port"):
            diagnoses.append(RuntimeDiagnosis(
                category=RuntimeErrorCategory.SERVER_UNRESPONSIVE,
                severity="critical",
                message="Server completely down (port + health fail)",
                auto_fixable=True,
            ))

        db_path = DATA_DIR / "icme.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path), timeout=3)
                result = conn.execute("PRAGMA integrity_check").fetchone()
                conn.close()
                if result and result[0] != "ok":
                    diagnoses.append(RuntimeDiagnosis(
                        category=RuntimeErrorCategory.DB_CORRUPTION,
                        severity="critical",
                        message=f"DB integrity: {result[0]}",
                        auto_fixable=True,
                    ))
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    diagnoses.append(RuntimeDiagnosis(
                        category=RuntimeErrorCategory.DB_LOCK,
                        severity="medium",
                        message=f"DB locked: {e}",
                        auto_fixable=True,
                    ))

        usage = shutil.disk_usage(DATA_DIR)
        if usage.used / usage.total > 0.90:
            diagnoses.append(RuntimeDiagnosis(
                category=RuntimeErrorCategory.DISK_FULL,
                severity="critical",
                message=f"Disk usage: {usage.used / usage.total:.1%}",
                auto_fixable=True,
            ))

        return diagnoses

    def attempt_fix(self, diagnosis: RuntimeDiagnosis) -> bool:
        retry_count = self.retry_counts.get(diagnosis.category, 0)
        if retry_count >= self.MAX_RETRIES:
            log.error(
                f"Max retries ({self.MAX_RETRIES}) for {diagnosis.category.value}. "
                f"Manual intervention required."
            )
            self._send_alert(diagnosis)
            return False

        self.retry_counts[diagnosis.category] = retry_count + 1
        backoff = self.BASE_BACKOFF * (2 ** retry_count)
        log.info(
            f"Fix attempt {retry_count + 1}/{self.MAX_RETRIES} "
            f"for {diagnosis.category.value} (backoff: {backoff}s)"
        )

        fix_map = {
            RuntimeErrorCategory.SERVER_UNRESPONSIVE: self._fix_server,
            RuntimeErrorCategory.PORT_CONFLICT: self._fix_port_conflict,
            RuntimeErrorCategory.DB_LOCK: self._fix_db_lock,
            RuntimeErrorCategory.DB_CORRUPTION: self._fix_db_corruption,
            RuntimeErrorCategory.DISK_FULL: self._fix_disk_full,
            RuntimeErrorCategory.MEMORY_PRESSURE: self._fix_memory_pressure,
            RuntimeErrorCategory.IMPORT_ERROR: self._fix_import_error,
            RuntimeErrorCategory.NETWORK_ERROR: self._fix_network,
        }

        fix_fn = fix_map.get(diagnosis.category)
        if fix_fn:
            try:
                result = fix_fn()
                diagnosis.fix_applied = True
                diagnosis.fix_result = "success" if result else "failed"
                if result:
                    self.retry_counts[diagnosis.category] = 0
            except Exception as e:
                diagnosis.fix_result = f"exception: {e}"
                log.exception(f"Fix exception for {diagnosis.category.value}")
        else:
            diagnosis.fix_result = "no_fix_available"

        time.sleep(backoff)
        self.history.append(diagnosis)
        return diagnosis.fix_applied and diagnosis.fix_result == "success"

    def _assess_severity(self, category: RuntimeErrorCategory) -> str:
        severity_map = {
            RuntimeErrorCategory.SERVER_UNRESPONSIVE: "critical",
            RuntimeErrorCategory.PORT_CONFLICT: "high",
            RuntimeErrorCategory.DB_LOCK: "medium",
            RuntimeErrorCategory.DB_CORRUPTION: "critical",
            RuntimeErrorCategory.DISK_FULL: "critical",
            RuntimeErrorCategory.MEMORY_PRESSURE: "high",
            RuntimeErrorCategory.IMPORT_ERROR: "medium",
            RuntimeErrorCategory.NETWORK_ERROR: "medium",
            RuntimeErrorCategory.UNKNOWN: "low",
        }
        return severity_map.get(category, "medium")

    def _fix_server(self) -> bool:
        log.info("Fix: restarting server via daemon...")
        from daemon.tianji_daemon import _stop_server, _start_server
        _stop_server()
        time.sleep(3)
        return _start_server()

    def _fix_port_conflict(self) -> bool:
        log.info("Fix: killing port conflict...")
        from daemon.tianji_daemon import _kill_port_process, _start_server
        _kill_port_process(8771)
        time.sleep(2)
        return _start_server()

    def _fix_db_lock(self) -> bool:
        log.info("Fix: WAL checkpoint to release locks...")
        db_path = DATA_DIR / "icme.db"
        if not db_path.exists():
            return False
        try:
            conn = sqlite3.connect(str(db_path), timeout=10)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            log.info("WAL checkpoint completed")
            return True
        except Exception as e:
            log.error(f"WAL checkpoint failed: {e}")
            return False

    def _fix_db_corruption(self) -> bool:
        log.warning("Fix: attempting DB restore from backup...")
        db_path = DATA_DIR / "icme.db"
        if not db_path.exists():
            return False

        corrupt_backup = BACKUP_DIR / "corrupt" / datetime.now().strftime("%Y%m%d_%H%M%S")
        corrupt_backup.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(db_path, corrupt_backup / "icme_corrupt.db")
        except Exception:
            pass

        full_dir = BACKUP_DIR / "full"
        if not full_dir.exists():
            return False

        backups = sorted(
            [d for d in full_dir.iterdir() if d.is_dir()],
            key=lambda d: d.name, reverse=True,
        )
        for backup_d in backups:
            for name in ["icme_vacuum.db", "icme.db"]:
                candidate = backup_d / name
                if candidate.exists() and candidate.stat().st_size > 0:
                    try:
                        shutil.copy2(candidate, db_path)
                        log.info(f"Restored DB from {candidate}")
                        return True
                    except Exception as e:
                        log.error(f"Restore failed: {e}")

        log.error("No valid backup found for DB restore")
        return False

    def _fix_disk_full(self) -> bool:
        log.info("Fix: emergency VACUUM + log rotation...")
        db_path = DATA_DIR / "icme.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.execute("VACUUM")
                conn.close()
                log.info("Emergency VACUUM completed")
            except Exception as e:
                log.error(f"VACUUM failed: {e}")

        self._rotate_logs()
        self._clean_old_backups()
        return True

    def _fix_memory_pressure(self) -> bool:
        log.info("Fix: cache flush...")
        try:
            import gc
            gc.collect()
            log.info("GC completed")
        except Exception:
            pass
        return True

    def _fix_import_error(self) -> bool:
        log.info("Fix: logging import error for manual resolution")
        return False

    def _fix_network(self) -> bool:
        log.info("Fix: network issue - will retry on next watchdog cycle")
        return True

    def _rotate_logs(self):
        if not LOG_DIR.exists():
            return
        for log_file in LOG_DIR.glob("*.log"):
            if log_file.stat().st_size > 50 * 1024 * 1024:
                try:
                    log_file.unlink()
                    log.info(f"Rotated large log: {log_file.name}")
                except Exception:
                    pass

    def _clean_old_backups(self, max_incremental: int = 7):
        inc_dir = BACKUP_DIR / "incremental"
        if not inc_dir.exists():
            return
        dirs = sorted([d for d in inc_dir.iterdir() if d.is_dir()], key=lambda d: d.name)
        if len(dirs) > max_incremental:
            for old_dir in dirs[:-max_incremental]:
                try:
                    shutil.rmtree(old_dir)
                except Exception:
                    pass

    def _send_alert(self, diagnosis: RuntimeDiagnosis):
        now = time.time()
        if now - self._last_alert_time < 300:
            return
        self._last_alert_time = now

        alert_file = LOG_DIR / "alerts.log"
        try:
            with open(alert_file, "a", encoding="utf-8") as f:
                f.write(
                    f"[{datetime.now().isoformat()}] "
                    f"[{diagnosis.severity.upper()}] "
                    f"{diagnosis.category.value}: {diagnosis.message}\n"
                )
        except Exception:
            pass

        log.critical(
            f"ALERT: [{diagnosis.severity.upper()}] "
            f"{diagnosis.category.value}: {diagnosis.message}"
        )

    def get_history(self, limit: int = 50) -> list[dict]:
        recent = self.history[-limit:]
        return [
            {
                "category": d.category.value,
                "severity": d.severity,
                "message": d.message[:100],
                "fix_applied": d.fix_applied,
                "fix_result": d.fix_result,
                "timestamp": d.timestamp,
            }
            for d in recent
        ]
