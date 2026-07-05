# -*- coding: utf-8-sig -*-
"""tianji_daemon_AutoRepair — 从 tianji_daemon.py 拆分 (SSS-PhaseB)

源文件: tianji_daemon.py
"""

import os
import sys
from pathlib import Path
from typing import Optional


from pathlib import Path

class AutoRepair:
    REPAIR_STRATEGIES = {
        "server_down": "restart_server",
        "port_conflict": "kill_port_restart",
        "db_locked": "checkpoint_retry",
        "db_corrupt": "restore_from_backup",
        "disk_full": "emergency_vacuum",
        "memory_leak": "restart_server",
        "import_error": "log_and_skip",
        "unknown": "log_and_alert",
    }

    def diagnose_and_repair(self, watchdog_result: dict[str, bool]) -> dict[str, str]:
        repairs = {}

        if not watchdog_result.get("server_health") and not watchdog_result.get(
            "server_port"
        ):
            repairs["server_down"] = self._restart_server()
        elif not watchdog_result.get("server_health") and watchdog_result.get(
            "server_port"
        ):
            repairs["server_hung"] = self._kill_and_restart()

        db_path = DATA_DIR / "icme.db"
        if db_path.exists():
            integrity = self._check_db_integrity(db_path)
            if integrity != "ok":
                repairs["db_integrity"] = self._repair_db(db_path, integrity)

        disk_usage = self._check_disk_usage(DATA_DIR)
        if disk_usage > 0.90:
            repairs["disk_full"] = self._emergency_vacuum(db_path)

        return repairs

    def _restart_server(self) -> str:
        log.info("Repair: restarting server...")
        _stop_server()
        time.sleep(2)
        success = _start_server()
        return "success" if success else "failed"

    def _kill_and_restart(self) -> str:
        log.info("Repair: killing hung server and restarting...")
        _kill_port_process(TIANJI_SERVICE["port"])
        time.sleep(3)
        success = _start_server()
        return "success" if success else "failed"

    def _check_db_integrity(self, db_path: Path) -> str:
        try:
            conn = sqlite3.connect(str(db_path), timeout=5)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            return result[0] if result else "unknown"
        except Exception as e:
            log.error(f"DB integrity check error: {e}")
            return f"error: {e}"

    def _repair_db(self, db_path: Path, issue: str) -> str:
        log.warning(f"DB integrity issue: {issue}, attempting repair...")

        if not db_path.exists():
            return "db_not_found"

        corrupt_backup = (
            BACKUP_DIR / "corrupt" / datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        corrupt_backup.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(db_path, corrupt_backup / "icme_corrupt.db")
        except Exception:
            pass

        latest_full = self._find_latest_backup()
        if latest_full:
            try:
                shutil.copy2(latest_full, db_path)
                log.info(f"Restored DB from backup: {latest_full}")
                return "restored_from_backup"
            except Exception as e:
                log.error(f"Restore failed: {e}")

        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute(".recover")
            conn.close()
            return "recovery_attempted"
        except Exception:
            return "manual_intervention_required"

    def _find_latest_backup(self) -> Optional[Path]:
        full_dir = BACKUP_DIR / "full"
        if not full_dir.exists():
            return None
        dirs = sorted(
            [d for d in full_dir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True,
        )
        for d in dirs:
            for name in ["icme_vacuum.db", "icme.db"]:
                candidate = d / name
                if candidate.exists() and candidate.stat().st_size > 0:
                    return candidate
        return None

    def _check_disk_usage(self, path: Path) -> float:
        try:
            usage = shutil.disk_usage(path)
            return usage.used / usage.total
        except Exception:
            return 0.0

    def _emergency_vacuum(self, db_path: Path) -> str:
        if not db_path.exists():
            return "no_db"
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
            conn.close()
            log.info("Emergency VACUUM completed")
            return "vacuum_completed"
        except Exception as e:
            log.error(f"Emergency VACUUM failed: {e}")
            return f"vacuum_failed: {e}"


__all__ = ["AutoRepair"]
