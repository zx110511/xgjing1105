r"""
天机 (TIANJI) - Data Migration v1.0 SSS
=============================================
《天机·星枢运转》— 数据迁移引擎

Migrates data from:
  1. 素问 (SUWEN) JSON files → 天机 SQLite
  2. 灵枢 (LINGSHU) JSON files → 天机 SQLite
  3. 天机旧版 JSON → 天机 SQLite (upgrade)
  4. Generic JSON import

Migration Strategy:
  Phase 1: Scan source data (count + validate)
  Phase 2: Transform to 天机 schema
  Phase 3: Insert into SQLite (batch)
  Phase 4: Verify (count + sample check)
  Phase 5: Report

Usage:
    python -m tools.migration --source suwen
    python -m tools.migration --source lingshu
    python -m tools.migration --source json --path /path/to/data
    python -m tools.migration --source all
    python -m tools.migration --verify
"""

import sys
import os
import json
import time
import uuid
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TIANJI_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = TIANJI_ROOT
TIANJI_DATA = TIANJI_ROOT / "data" / ".memory"
TIANJI_DB = TIANJI_DATA / "icme.db"

SUWEN_ROOT = PROJECT_ROOT / "素问"
SUWEN_DATA = SUWEN_ROOT / "data"

LINGSHU_ROOT = PROJECT_ROOT / "灵枢"
LINGSHU_DATA = LINGSHU_ROOT / "data"

BACKUP_DIR = TIANJI_ROOT / "backups" / "migration"

from daemon.tianji_logger import get_logger
log = get_logger("migration")


@dataclass
class MigrationStats:
    source: str = ""
    scanned: int = 0
    transformed: int = 0
    inserted: int = 0
    skipped: int = 0
    errors: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    details: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0.0

    def summary(self) -> str:
        return (
            f"Migration [{self.source}]: "
            f"scanned={self.scanned}, transformed={self.transformed}, "
            f"inserted={self.inserted}, skipped={self.skipped}, "
            f"errors={self.errors}, duration={self.duration:.1f}s"
        )


class DataMigrator:
    LAYER_MAP = {
        "sensory": "sensory",
        "working": "working",
        "short_term": "short_term",
        "episodic": "episodic",
        "semantic": "semantic",
        "meta": "meta",
        "L0": "sensory",
        "L1": "working",
        "L2": "short_term",
        "L3": "episodic",
        "L4": "semantic",
        "L5": "meta",
        "0": "sensory",
        "1": "working",
        "2": "short_term",
        "3": "episodic",
        "4": "semantic",
        "5": "meta",
    }

    PRIORITY_MAP = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "critical": "critical",
        "0": "low",
        "1": "medium",
        "2": "high",
        "3": "critical",
    }

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or TIANJI_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), timeout=30)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _close_conn(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _backup_before_migration(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / timestamp
        backup_path.mkdir(parents=True, exist_ok=True)

        if self.db_path.exists():
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()
            except Exception:
                pass
            shutil.copy2(self.db_path, backup_path / "icme.db")
            for ext in ["-shm", "-wal"]:
                src = TIANJI_DATA / f"icme.db{ext}"
                if src.exists():
                    shutil.copy2(src, backup_path / f"icme.db{ext}")

        log.info(f"Pre-migration backup: {backup_path}")
        return backup_path

    def scan_suwen(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"source": "suwen", "files": [], "total_entries": 0}
        if not SUWEN_DATA.exists():
            result["error"] = f"素问数据目录不存在: {SUWEN_DATA}"
            return result

        for json_file in SUWEN_DATA.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                count = 0
                if isinstance(data, list):
                    count = len(data)
                elif isinstance(data, dict):
                    if "memories" in data:
                        count = len(data["memories"])
                    elif "entries" in data:
                        count = len(data["entries"])
                    else:
                        count = 1
                result["files"].append({
                    "path": str(json_file.relative_to(SUWEN_DATA)),
                    "entries": count,
                })
                result["total_entries"] += count
            except Exception as e:
                result["files"].append({
                    "path": str(json_file.relative_to(SUWEN_DATA)),
                    "error": str(e),
                })

        return result

    def scan_lingshu(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"source": "lingshu", "files": [], "total_entries": 0}
        if not LINGSHU_DATA.exists():
            result["error"] = f"灵枢数据目录不存在: {LINGSHU_DATA}"
            return result

        for json_file in LINGSHU_DATA.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                count = 0
                if isinstance(data, list):
                    count = len(data)
                elif isinstance(data, dict):
                    for key in ["memories", "entries", "records", "data"]:
                        if key in data and isinstance(data[key], list):
                            count = len(data[key])
                            break
                    if count == 0:
                        count = 1
                result["files"].append({
                    "path": str(json_file.relative_to(LINGSHU_DATA)),
                    "entries": count,
                })
                result["total_entries"] += count
            except Exception as e:
                result["files"].append({
                    "path": str(json_file.relative_to(LINGSHU_DATA)),
                    "error": str(e),
                })

        return result

    def _transform_entry(self, raw: Dict, source: str) -> Optional[Dict]:
        try:
            content = raw.get("content") or raw.get("text") or raw.get("body") or ""
            if not content:
                return None

            raw_layer = str(raw.get("layer", raw.get("level", "working"))).lower()
            layer = self.LAYER_MAP.get(raw_layer, "working")

            raw_priority = str(raw.get("priority", raw.get("importance", "medium"))).lower()
            priority = self.PRIORITY_MAP.get(raw_priority, "medium")

            tags = raw.get("tags", raw.get("keywords", []))
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            if source:
                tags = list(set(tags + [f"migrated:{source}"]))

            entry_id = raw.get("id") or raw.get("memory_id") or str(uuid.uuid4())

            created_at = raw.get("created_at", raw.get("timestamp", time.time()))
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at).timestamp()
                except Exception:
                    created_at = time.time()

            metadata = raw.get("metadata", raw.get("meta", {}))
            if not isinstance(metadata, dict):
                metadata = {"original": str(metadata)}
            metadata["migration_source"] = source
            metadata["migration_time"] = datetime.now().isoformat()

            return {
                "id": entry_id,
                "content": content,
                "layer": layer,
                "tags": tags,
                "priority": priority,
                "value_score": float(raw.get("value_score", raw.get("score", 0.5))),
                "access_count": int(raw.get("access_count", raw.get("reads", 0))),
                "created_at": float(created_at),
                "last_accessed": float(raw.get("last_accessed", raw.get("last_read", created_at))),
                "metadata": metadata,
                "related_ids": raw.get("related_ids", raw.get("relations", [])),
                "changelog": [{"action": "migrated", "from": source, "at": datetime.now().isoformat()}],
            }
        except Exception as e:
            log.error(f"Transform error: {e}")
            return None

    def _extract_entries_from_data(self, data: Any) -> List[Dict]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ["memories", "entries", "records", "data"]:
                if key in data and isinstance(data[key], list):
                    return [item for item in data[key] if isinstance(item, dict)]
            return [data]
        return []

    def migrate_suwen(self) -> MigrationStats:
        stats = MigrationStats(source="suwen", start_time=time.time())
        log.info("Starting 素问 → 天机 migration...")

        if not SUWEN_DATA.exists():
            stats.details.append(f"素问数据目录不存在: {SUWEN_DATA}")
            stats.end_time = time.time()
            return stats

        self._backup_before_migration()
        conn = self._get_conn()

        for json_file in SUWEN_DATA.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                entries = self._extract_entries_from_data(data)
                stats.scanned += len(entries)

                for raw in entries:
                    transformed = self._transform_entry(raw, "suwen")
                    if transformed is None:
                        stats.skipped += 1
                        continue
                    stats.transformed += 1

                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO memories (
                                id, content, layer, tags, priority, value_score,
                                access_count, created_at, last_accessed, size_bytes,
                                metadata, related_ids, changelog
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            transformed["id"],
                            transformed["content"],
                            transformed["layer"],
                            json.dumps(transformed["tags"], ensure_ascii=False),
                            transformed["priority"],
                            transformed["value_score"],
                            transformed["access_count"],
                            transformed["created_at"],
                            transformed["last_accessed"],
                            len(transformed["content"].encode("utf-8")),
                            json.dumps(transformed["metadata"], ensure_ascii=False),
                            json.dumps(transformed["related_ids"], ensure_ascii=False),
                            json.dumps(transformed["changelog"], ensure_ascii=False),
                        ))
                        stats.inserted += 1
                    except sqlite3.IntegrityError:
                        stats.skipped += 1
                    except Exception as e:
                        stats.errors += 1
                        log.error(f"Insert error for {transformed['id']}: {e}")

                conn.commit()
            except Exception as e:
                stats.errors += 1
                log.error(f"File processing error {json_file}: {e}")

        stats.end_time = time.time()
        self._close_conn()
        log.info(stats.summary())
        return stats

    def migrate_lingshu(self) -> MigrationStats:
        stats = MigrationStats(source="lingshu", start_time=time.time())
        log.info("Starting 灵枢 → 天机 migration...")

        if not LINGSHU_DATA.exists():
            stats.details.append(f"灵枢数据目录不存在: {LINGSHU_DATA}")
            stats.end_time = time.time()
            return stats

        self._backup_before_migration()
        conn = self._get_conn()

        for json_file in LINGSHU_DATA.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                entries = self._extract_entries_from_data(data)
                stats.scanned += len(entries)

                for raw in entries:
                    transformed = self._transform_entry(raw, "lingshu")
                    if transformed is None:
                        stats.skipped += 1
                        continue
                    stats.transformed += 1

                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO memories (
                                id, content, layer, tags, priority, value_score,
                                access_count, created_at, last_accessed, size_bytes,
                                metadata, related_ids, changelog
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            transformed["id"],
                            transformed["content"],
                            transformed["layer"],
                            json.dumps(transformed["tags"], ensure_ascii=False),
                            transformed["priority"],
                            transformed["value_score"],
                            transformed["access_count"],
                            transformed["created_at"],
                            transformed["last_accessed"],
                            len(transformed["content"].encode("utf-8")),
                            json.dumps(transformed["metadata"], ensure_ascii=False),
                            json.dumps(transformed["related_ids"], ensure_ascii=False),
                            json.dumps(transformed["changelog"], ensure_ascii=False),
                        ))
                        stats.inserted += 1
                    except sqlite3.IntegrityError:
                        stats.skipped += 1
                    except Exception as e:
                        stats.errors += 1
                        log.error(f"Insert error for {transformed['id']}: {e}")

                conn.commit()
            except Exception as e:
                stats.errors += 1
                log.error(f"File processing error {json_file}: {e}")

        stats.end_time = time.time()
        self._close_conn()
        log.info(stats.summary())
        return stats

    def migrate_json_dir(self, json_dir: Path, source_name: str = "json_import") -> MigrationStats:
        stats = MigrationStats(source=source_name, start_time=time.time())
        log.info(f"Starting JSON import from {json_dir}...")

        if not json_dir.exists():
            stats.details.append(f"目录不存在: {json_dir}")
            stats.end_time = time.time()
            return stats

        self._backup_before_migration()
        conn = self._get_conn()

        for json_file in json_dir.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                entries = self._extract_entries_from_data(data)
                stats.scanned += len(entries)

                for raw in entries:
                    transformed = self._transform_entry(raw, source_name)
                    if transformed is None:
                        stats.skipped += 1
                        continue
                    stats.transformed += 1

                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO memories (
                                id, content, layer, tags, priority, value_score,
                                access_count, created_at, last_accessed, size_bytes,
                                metadata, related_ids, changelog
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            transformed["id"],
                            transformed["content"],
                            transformed["layer"],
                            json.dumps(transformed["tags"], ensure_ascii=False),
                            transformed["priority"],
                            transformed["value_score"],
                            transformed["access_count"],
                            transformed["created_at"],
                            transformed["last_accessed"],
                            len(transformed["content"].encode("utf-8")),
                            json.dumps(transformed["metadata"], ensure_ascii=False),
                            json.dumps(transformed["related_ids"], ensure_ascii=False),
                            json.dumps(transformed["changelog"], ensure_ascii=False),
                        ))
                        stats.inserted += 1
                    except sqlite3.IntegrityError:
                        stats.skipped += 1
                    except Exception as e:
                        stats.errors += 1

                conn.commit()
            except Exception as e:
                stats.errors += 1
                log.error(f"File error {json_file}: {e}")

        stats.end_time = time.time()
        self._close_conn()
        log.info(stats.summary())
        return stats

    def migrate_all(self) -> List[MigrationStats]:
        results = []
        for migrate_fn in [self.migrate_suwen, self.migrate_lingshu]:
            try:
                stats = migrate_fn()
                results.append(stats)
            except Exception as e:
                log.error(f"Migration failed: {e}")
                results.append(MigrationStats(source="error", errors=1, details=[str(e)]))
        return results

    def verify(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"timestamp": datetime.now().isoformat()}

        if not TIANJI_DB.exists():
            result["error"] = "天机数据库不存在"
            return result

        conn = sqlite3.connect(str(TIANJI_DB), timeout=10)
        try:
            total = conn.execute("SELECT COUNT(*) FROM memories WHERE archived = 0").fetchone()[0]
            result["total_active_memories"] = total

            layer_counts = {}
            for row in conn.execute("SELECT layer, COUNT(*) FROM memories WHERE archived = 0 GROUP BY layer"):
                layer_counts[row[0]] = row[1]
            result["layer_distribution"] = layer_counts

            migrated = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE metadata LIKE '%migrated:%'"
            ).fetchone()[0]
            result["migrated_entries"] = migrated

            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            result["integrity"] = integrity[0] if integrity else "unknown"

            sample = conn.execute(
                "SELECT id, content, layer, tags FROM memories WHERE archived = 0 LIMIT 3"
            ).fetchall()
            result["sample_entries"] = [
                {"id": r[0], "content": r[1][:50], "layer": r[2], "tags": r[3]}
                for r in sample
            ]
        except Exception as e:
            result["error"] = str(e)
        finally:
            conn.close()

        return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="天机数据迁移工具")
    parser.add_argument("--source", choices=["suwen", "lingshu", "all", "json"], default="all")
    parser.add_argument("--path", type=str, help="JSON目录路径 (--source json时使用)")
    parser.add_argument("--verify", action="store_true", help="仅验证当前数据")
    parser.add_argument("--scan", action="store_true", help="仅扫描源数据")
    args = parser.parse_args()

    migrator = DataMigrator()

    if args.verify:
        result = migrator.verify()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.scan:
        if args.source in ("suwen", "all"):
            print("=== 素问数据扫描 ===")
            scan = migrator.scan_suwen()
            print(json.dumps(scan, ensure_ascii=False, indent=2))
        if args.source in ("lingshu", "all"):
            print("=== 灵枢数据扫描 ===")
            scan = migrator.scan_lingshu()
            print(json.dumps(scan, ensure_ascii=False, indent=2))
        return

    if args.source == "suwen":
        stats = migrator.migrate_suwen()
        print(stats.summary())
    elif args.source == "lingshu":
        stats = migrator.migrate_lingshu()
        print(stats.summary())
    elif args.source == "json":
        if not args.path:
            print("Error: --path required for --source json")
            return
        stats = migrator.migrate_json_dir(Path(args.path))
        print(stats.summary())
    elif args.source == "all":
        results = migrator.migrate_all()
        for stats in results:
            print(stats.summary())

    verify_result = migrator.verify()
    print("\n=== 迁移后验证 ===")
    print(json.dumps(verify_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
