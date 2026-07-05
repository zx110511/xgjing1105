# -*- coding: utf-8-sig -*-
"""tianji_daemon_IntegrityChecker — 从 tianji_daemon.py 拆分 (SSS-PhaseB)

源文件: tianji_daemon.py
"""

import os
import sys



from typing import Optional

class IntegrityChecker:
    def __init__(self):
        self.last_check = 0.0

    def check(self) -> dict:
        now = time.time()
        if now - self.last_check < INTEGRITY_CHECK_INTERVAL:
            return {"skipped": True}

        db_path = DATA_DIR / "icme.db"
        results: dict = {"timestamp": now, "checks": {}}

        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path), timeout=5)
                integrity = conn.execute("PRAGMA integrity_check").fetchone()
                results["checks"]["integrity"] = (
                    integrity[0] if integrity else "unknown"
                )

                page_count = conn.execute("PRAGMA page_count").fetchone()
                free_pages = conn.execute("PRAGMA freelist_count").fetchone()
                if page_count and free_pages:
                    total = page_count[0]
                    free = free_pages[0]
                    fragmentation = free / total if total > 0 else 0
                    results["checks"]["fragmentation"] = round(fragmentation, 4)
                    if fragmentation > 0.3:
                        conn.execute("VACUUM")
                        results["checks"]["auto_vacuum"] = True

                wal_size = 0
                wal_path = DATA_DIR / "icme.db-wal"
                if wal_path.exists():
                    wal_size = wal_path.stat().st_size
                results["checks"]["wal_size_mb"] = round(wal_size / (1024 * 1024), 2)

                if wal_size > 50 * 1024 * 1024:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    results["checks"]["wal_checkpoint"] = True

                conn.close()
            except Exception as e:
                results["checks"]["error"] = str(e)
        else:
            results["checks"]["db_exists"] = False

        self.last_check = now
        return results


__all__ = ["IntegrityChecker"]
