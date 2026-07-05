# -*- coding: utf-8-sig -*-
"""tianji_daemon_AutoBackup — 从 tianji_daemon.py 拆分 (SSS-PhaseB)

源文件: tianji_daemon.py
"""

import os
import sys



from pathlib import Path

class AutoBackup:
    def __init__(self):
        self.last_backup = 0.0
        self.last_full_backup = 0.0

    def incremental(self):
        now = time.time()
        if now - self.last_backup < BACKUP_INTERVAL:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = BACKUP_DIR / "incremental" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        db_path = DATA_DIR / "icme.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()
            except Exception as e:
                log.warning(f"WAL checkpoint before backup: {e}")

            shutil.copy2(db_path, backup_dir / "icme.db")
            for ext in ["-shm", "-wal"]:
                src = DATA_DIR / f"icme.db{ext}"
                if src.exists():
                    shutil.copy2(src, backup_dir / f"icme.db{ext}")

            log.info(f"Incremental backup: {backup_dir}")

        self.last_backup = now

    def full(self):
        now = time.time()
        if now - self.last_full_backup < FULL_BACKUP_INTERVAL:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        full_dir = BACKUP_DIR / "full" / timestamp
        full_dir.mkdir(parents=True, exist_ok=True)

        db_path = DATA_DIR / "icme.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()
            except Exception as e:
                log.warning(f"WAL checkpoint before full backup: {e}")

            vacuum_path = full_dir / "icme_vacuum.db"
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute(f"VACUUM INTO '{vacuum_path}'")
                conn.close()
                log.info(f"Full VACUUM backup: {vacuum_path}")
            except Exception as e:
                log.warning(f"VACUUM failed, falling back to copy: {e}")
                shutil.copy2(db_path, full_dir / "icme.db")

        self.last_full_backup = now

    def cleanup_old(self, max_incremental: int = 28, max_full: int = 7):
        for backup_type, max_count in [
            ("incremental", max_incremental),
            ("full", max_full),
        ]:
            type_dir = BACKUP_DIR / backup_type
            if not type_dir.exists():
                continue
            dirs = sorted(
                [d for d in type_dir.iterdir() if d.is_dir()],
                key=lambda d: d.name,
            )
            if len(dirs) > max_count:
                for old_dir in dirs[:-max_count]:
                    try:
                        shutil.rmtree(old_dir)
                        log.info(f"Cleaned old {backup_type} backup: {old_dir.name}")
                    except Exception as e:
                        log.warning(f"Cleanup failed for {old_dir}: {e}")


__all__ = ["AutoBackup"]
