# -*- coding: utf-8-sig -*-
"""sqlite_store_init.py — SQLiteMemoryStoreInitMixin (SSS-PhaseB)

从 sqlite_store.py 拆分的方法组: init
源文件: sqlite_store.py
"""

import json
import logging
logger = logging.getLogger(__name__)  # SSS-PhaseE: 补充logger定义 (拆分时遗漏)
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any



from typing import Dict

# SSS-PhaseE: 安全导入EvolutionLoop (可选依赖，拆分时遗漏)
try:
    from core.processors.evolution_loop import EvolutionLoop
except Exception:
    EvolutionLoop = None

class SQLiteMemoryStoreInitMixin:
    """init方法组Mixin"""

    def __init__(
        self,
        db_path: Path,
        cache_size: int = 500,
        recorder: Any | None = None,
        learning_engine: Any | None = None,
    ):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._cache: dict[str, dict] = {}
        self._cache_max = cache_size
        self._cache_lock = threading.Lock()
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._stats = {
            "total_writes": 0,
            "total_reads": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "last_vacuum": time.time(),
            "start_time": time.time(),
            "insert_ops": 0,
            "batch_ops": 0,
            "search_ops": 0,
            "update_ops": 0,
            "delete_ops": 0,
            "vacuum_ops": 0,
            "errors": 0,
        }
        self._errors = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="sqlite_store",
                    effectiveness_fn=self._calc_store_effectiveness,
                    learn_fn=self._learn_from_store,
                    evolve_fn=self._evolve_store_config,
                    mutable_config={
                        "cache_size": cache_size,
                        "vacuum_interval_seconds": 3600.0,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception as e:
                logger.warning(f"[SQLiteStore] EvolutionLoop初始化失败: {e}")

        self._init_db()
        self._verify_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False, timeout=10
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-8000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA mmap_size=268435456")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA wal_autocheckpoint=1000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    content_segmented TEXT NOT NULL DEFAULT '',
                    layer TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    value_score REAL NOT NULL DEFAULT 0.5,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    related_ids TEXT NOT NULL DEFAULT '[]',
                    changelog TEXT NOT NULL DEFAULT '[]',
                    archived INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_memories_layer
                    ON memories(layer);
                CREATE INDEX IF NOT EXISTS idx_memories_priority
                    ON memories(priority);
                CREATE INDEX IF NOT EXISTS idx_memories_created
                    ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_value
                    ON memories(value_score DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_archived
                    ON memories(archived);

                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                    USING fts5(content_segmented, tags, metadata, content=memories, content_rowid=rowid);

                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content_segmented, tags, metadata)
                    VALUES (new.rowid, new.content_segmented, new.tags, new.metadata);
                END;

                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content_segmented, tags, metadata)
                    VALUES ('delete', old.rowid, old.content_segmented, old.tags, old.metadata);
                END;

                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content_segmented, tags, metadata)
                    VALUES ('delete', old.rowid, old.content_segmented, old.tags, old.metadata);
                    INSERT INTO memories_fts(rowid, content_segmented, tags, metadata)
                    VALUES (new.rowid, new.content_segmented, new.tags, new.metadata);
                END;

                CREATE TABLE IF NOT EXISTS tag_index (
                    tag TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    PRIMARY KEY (tag, memory_id)
                );

                CREATE INDEX IF NOT EXISTS idx_tag_index_tag
                    ON tag_index(tag);
                CREATE INDEX IF NOT EXISTS idx_tag_index_memory
                    ON tag_index(memory_id);

                CREATE TABLE IF NOT EXISTS knowledge_graph (
                    entity_name TEXT NOT NULL,
                    entity_type TEXT NOT NULL DEFAULT 'concept',
                    properties TEXT NOT NULL DEFAULT '{}',
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    frequency INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (entity_name)
                );

                CREATE TABLE IF NOT EXISTS knowledge_edges (
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (source, target, relation)
                );

                CREATE TABLE IF NOT EXISTS namespace_stats (
                    namespace TEXT PRIMARY KEY,
                    memory_count INTEGER NOT NULL DEFAULT 0,
                    last_updated REAL NOT NULL
                );

                -- [STO-PHASE-1] system_config表 — 统一辅助文件存储
                -- 替代散落的cognition.json/llm_stats_counters.json/.pending_cursor.json等
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '{}',
                    updated_at REAL NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    source_file TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_system_config_updated
                    ON system_config(updated_at);
            """)

            self._migrate_schema(conn)

            conn.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (self.SCHEMA_VERSION, time.time()),
            )
            conn.commit()
            conn.close()
            logger.info(f"[SQLiteStore] _init_db() 完成: {self.db_path}")

            # [STO-PHASE-1] 启动时自动迁移辅助JSON文件 → system_config表
            self._migrate_auxiliary_files()
        except sqlite3.OperationalError as e:
            logger.critical(f"[SQLiteStore] _init_db() 数据库操作失败: {e}")
            raise
        except Exception as e:
            logger.critical(f"[SQLiteStore] _init_db() 未知错误: {e}", exc_info=True)
            raise

    def _migrate_auxiliary_files(self):
        """[STO-PHASE-1] 启动时迁移散落JSON辅助文件 → system_config表

        迁移映射:
          cognition.json           → config_key='cognition_state'
          llm_stats_counters.json  → config_key='llm_stats'
          .pending_cursor.json     → config_key='push_cursor'
          .dashboard/cumulative.json→ config_key='dashboard_cumulative'
          .dashboard/history.json  → config_key='dashboard_history'

        迁移后原文件重命名为.deprecated保留30天兼容期。
        """
        import os
        from pathlib import Path

        data_dir = self.db_path.parent
        migrations = [
            (data_dir / "cognition.json", "cognition_state"),
            (data_dir / "llm_stats_counters.json", "llm_stats"),
            (data_dir / ".pending_cursor.json", "push_cursor"),
            (data_dir / ".dashboard" / "cumulative.json", "dashboard_cumulative"),
            (data_dir / ".dashboard" / "history.json", "dashboard_history"),
        ]

        migrated_count = 0
        for json_path, config_key in migrations:
            # 检查是否已迁移过(通过config表是否有记录)
            existing = self.config_get(config_key)
            if existing is not None:
                continue  # 已迁移过，跳过

            result = self.config_migrate_from_json(json_path, config_key)
            if result["migrated"]:
                # 标记原文件为deprecated(不删除，保留兼容)
                try:
                    dep_path = json_path.with_suffix(".json.deprecated")
                    if not dep_path.exists():
                        import shutil
                        shutil.copy2(json_path, dep_path)
                    logger.info(f"[STO-PHASE-1] 已迁移: {json_path.name} → system_config[{config_key}]")
                except Exception as dep_err:
                    logger.warning(f"[STO-PHASE-1] deprecated标记失败({json_path.name}): {dep_err}")
                migrated_count += 1
            else:
                logger.debug(f"[STO-PHASE-1] 跳过({json_path.name}): {result.get('error', '?')}")

        if migrated_count > 0:
            logger.info(f"[STO-PHASE-1] 辅助文件迁移完成: {migrated_count}个文件迁入system_config表")

        # [STO-PHASE-2] 清理上次异常中断残留的.tmp临时文件
        self._cleanup_temp_files()

    def _cleanup_temp_files(self):
        """[STO-PHASE-2] 启动时清理残留的.json.tmp临时文件

        正常流程: 写入.tmp → rename为.json → .tmp被替换不存在
        异常中断: .tmp残留，说明对应写入未完成，应清理。
        """
        data_path = self.db_path.parent / ".memory"
        cleaned = 0
        if data_path.exists():
            for tmp_file in data_path.rglob("*.json.tmp"):
                try:
                    tmp_file.unlink()
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"[STO-PHASE-2] 清理tmp失败: {tmp_file.name} — {e}")
        if cleaned > 0:
            logger.info(f"[STO-PHASE-2] 清理残留临时文件: {cleaned}个")

    def _verify_db(self) -> dict:
        """v9.1 P0: 验证数据库表结构和完整性

        检查:
        - memories表是否存在且含预期列
        - FTS5虚拟表是否正常
        - 索引是否可用
        - 可选的磁盘空间检查

        返回: {"ok": bool, "tables": dict, "issues": list, "disk_free_mb": float}
        """
        result = {"ok": True, "tables": {}, "issues": [], "disk_free_mb": 0.0}

        # 磁盘空间检查 (跨平台: shutil.disk_usage 兼容 Windows/Unix)
        try:
            disk_usage = shutil.disk_usage(str(self.db_path.parent))
            result["disk_free_mb"] = round(disk_usage.free / (1024 * 1024), 1)
            if result["disk_free_mb"] < 50:
                result["issues"].append(
                    f"磁盘可用空间不足: {result['disk_free_mb']}MB (建议≥50MB)"
                )
                result["ok"] = False
        except Exception as e:
            logger.warning(f"[SQLiteStore] 磁盘空间检查失败: {e}")
            result["issues"].append(f"磁盘空间检查异常: {e}")

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5)

            # 1. 验证memories表
            try:
                table_info = conn.execute("PRAGMA table_info(memories)").fetchall()
                if not table_info:
                    result["ok"] = False
                    result["issues"].append("memories表不存在")
                    logger.critical("[SQLiteStore] memories表不存在!")
                else:
                    columns = {r[1] for r in table_info}
                    expected = {
                        "id",
                        "content",
                        "content_segmented",
                        "layer",
                        "tags",
                        "priority",
                        "value_score",
                        "access_count",
                        "created_at",
                        "last_accessed",
                        "size_bytes",
                        "metadata",
                        "related_ids",
                        "changelog",
                        "archived",
                    }
                    missing = expected - columns
                    if missing:
                        result["ok"] = False
                        result["issues"].append(f"memories表缺少列: {missing}")
                        logger.critical(f"[SQLiteStore] memories表缺少列: {missing}")

                    row_count = conn.execute(
                        "SELECT COUNT(*) FROM memories"
                    ).fetchone()[0]
                    result["tables"]["memories"] = {
                        "columns": len(columns),
                        "rows": row_count,
                        "all_columns_present": len(missing) == 0,
                    }
            except sqlite3.OperationalError as e:
                result["ok"] = False
                result["issues"].append(f"memories表检查失败: {e}")
                logger.critical(f"[SQLiteStore] memories表PRAGMA失败: {e}")

            # 2. 验证FTS5虚拟表
            try:
                fts_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'"
                ).fetchone()
                if fts_check:
                    fts_rows = conn.execute(
                        "SELECT COUNT(*) FROM memories_fts"
                    ).fetchone()[0]
                    result["tables"]["memories_fts"] = {"rows": fts_rows, "ok": True}
                else:
                    result["issues"].append("FTS5虚拟表memories_fts不存在")
                    result["tables"]["memories_fts"] = {"rows": 0, "ok": False}
                    logger.warning("[SQLiteStore] FTS5虚拟表memories_fts缺失")
            except Exception as e:
                result["issues"].append(f"FTS5检查失败: {e}")
                logger.warning(f"[SQLiteStore] FTS5检查异常: {e}")

            # 3. 验证其他关键表
            for tbl in [
                "tag_index",
                "knowledge_graph",
                "knowledge_edges",
                "namespace_stats",
                "schema_version",
            ]:
                try:
                    exists = conn.execute(
                        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'"
                    ).fetchone()
                    cnt = (
                        conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                        if exists
                        else 0
                    )
                    result["tables"][tbl] = {"exists": bool(exists), "rows": cnt}
                    if not exists:
                        result["issues"].append(f"表{tbl}不存在")
                        logger.warning(f"[SQLiteStore] 表{tbl}不存在")
                except Exception as e:
                    result["tables"][tbl] = {
                        "exists": False,
                        "rows": 0,
                        "error": str(e),
                    }
                    logger.warning(f"[SQLiteStore] 表{tbl}检查异常: {e}")

            # 4. 验证WAL模式
            try:
                journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                result["journal_mode"] = journal_mode
                if journal_mode.lower() != "wal":
                    result["issues"].append(f"journal_mode={journal_mode} (期望WAL)")
                    logger.warning(
                        f"[SQLiteStore] journal_mode={journal_mode}, 期望WAL"
                    )
            except Exception as e:
                logger.debug(f"[SQLiteStore] journal_mode检查跳过: {e}")

            conn.close()
        except sqlite3.OperationalError as e:
            result["ok"] = False
            result["issues"].append(f"无法连接数据库: {e}")
            logger.critical(f"[SQLiteStore] _verify_db() 无法连接: {e}")
        except Exception as e:
            result["ok"] = False
            result["issues"].append(f"验证过程异常: {e}")
            logger.critical(f"[SQLiteStore] _verify_db() 异常: {e}", exc_info=True)

        if result["ok"]:
            logger.info(
                f"[SQLiteStore] _verify_db() 通过: {len(result['tables'])}个表验证OK"
            )
        else:
            logger.critical(
                f"[SQLiteStore] _verify_db() 失败: {len(result['issues'])}个问题 - "
                + "; ".join(result["issues"][:5])
            )

        return result

    def get_db_health(self) -> dict:
        """v9.1 P1: 返回存储健康状态 (供/storage_health端点使用)"""
        health = {
            "db_path": str(self.db_path),
            "db_exists": self.db_path.exists(),
            "db_size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2)
            if self.db_path.exists()
            else 0,
            "wal_size_mb": 0,
            "table_stats": {},
            "errors": self._stats.get("errors", 0),
            "total_writes": self._stats.get("total_writes", 0),
            "total_reads": self._stats.get("total_reads", 0),
            "cache_hit_rate": 0,
        }

        # WAL文件大小
        wal_path = Path(str(self.db_path) + "-wal")
        if wal_path.exists():
            health["wal_size_mb"] = round(wal_path.stat().st_size / (1024 * 1024), 2)

        # 缓存命中率
        total = self._stats.get("cache_hits", 0) + self._stats.get("cache_misses", 0)
        if total > 0:
            health["cache_hit_rate"] = round(
                self._stats.get("cache_hits", 0) / total * 100, 1
            )

        # 磁盘空间 (跨平台: shutil.disk_usage 兼容 Windows/Unix)
        try:
            disk_usage = shutil.disk_usage(str(self.db_path.parent))
            health["disk_free_mb"] = round(disk_usage.free / (1024 * 1024), 1)
        except Exception:
            health["disk_free_mb"] = -1

        # 验证表格
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5)
            for tbl in [
                "memories",
                "memories_fts",
                "tag_index",
                "knowledge_graph",
                "knowledge_edges",
                "namespace_stats",
                "schema_version",
            ]:
                try:
                    cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                    health["table_stats"][tbl] = {"rows": cnt, "ok": True}
                except Exception as e:
                    health["table_stats"][tbl] = {
                        "rows": 0,
                        "ok": False,
                        "error": str(e),
                    }
            conn.close()
        except Exception as e:
            health["db_connect_error"] = str(e)

        return health

    def _migrate_schema(self, conn):
        try:
            current = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()[0]
        except Exception:
            current = 1
        if current is None:
            current = 1
        if current < 3:
            self._migrate_v2_to_v3(conn)
        if current < 4:
            self._migrate_v3_to_v4(conn)

    def _migrate_v2_to_v3(self, conn):
        try:
            cols = [
                r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()
            ]
            if "content_segmented" not in cols:
                conn.execute(
                    "ALTER TABLE memories ADD COLUMN content_segmented TEXT NOT NULL DEFAULT ''"
                )
            from core.shared.chinese_tokenizer import tokenize_for_fts

            rows = conn.execute(
                "SELECT rowid, content FROM memories WHERE content_segmented = ''"
            ).fetchall()
            for row in rows:
                segmented = tokenize_for_fts(
                    row["content"] if hasattr(row, "keys") else row[1]
                )
                rid = row["rowid"] if hasattr(row, "keys") else row[0]
                conn.execute(
                    "UPDATE memories SET content_segmented = ? WHERE rowid = ?",
                    (segmented, rid),
                )
            conn.execute("DROP TRIGGER IF EXISTS memories_ai")
            conn.execute("DROP TRIGGER IF EXISTS memories_ad")
            conn.execute("DROP TRIGGER IF EXISTS memories_au")
            conn.execute("DROP TABLE IF EXISTS memories_fts")
            conn.execute("""
                CREATE VIRTUAL TABLE memories_fts
                    USING fts5(content_segmented, tags, metadata, content=memories, content_rowid=rowid)
            """)
            conn.execute("""
                CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content_segmented, tags, metadata)
                    VALUES (new.rowid, new.content_segmented, new.tags, new.metadata);
                END
            """)
            conn.execute("""
                CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content_segmented, tags, metadata)
                    VALUES ('delete', old.rowid, old.content_segmented, old.tags, old.metadata);
                END
            """)
            conn.execute("""
                CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content_segmented, tags, metadata)
                    VALUES ('delete', old.rowid, old.content_segmented, old.tags, old.metadata);
                    INSERT INTO memories_fts(rowid, content_segmented, tags, metadata)
                    VALUES (new.rowid, new.content_segmented, new.tags, new.metadata);
                END
            """)
            conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
            conn.execute(
                "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (3, time.time()),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"[SQLiteStore] migration v2→v3 失败: {e}", exc_info=True)

    def _migrate_v3_to_v4(self, conn):
        try:
            cols = [
                r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()
            ]
            if "content_segmented" not in cols:
                conn.execute(
                    "ALTER TABLE memories ADD COLUMN content_segmented TEXT NOT NULL DEFAULT ''"
                )
            from core.shared.chinese_tokenizer import tokenize_for_fts

            rows = conn.execute(
                "SELECT rowid, content FROM memories WHERE content_segmented = ''"
            ).fetchall()
            for row in rows:
                segmented = tokenize_for_fts(
                    row["content"] if hasattr(row, "keys") else row[1]
                )
                rid = row["rowid"] if hasattr(row, "keys") else row[0]
                conn.execute(
                    "UPDATE memories SET content_segmented = ? WHERE rowid = ?",
                    (segmented, rid),
                )
            conn.execute("DROP TRIGGER IF EXISTS memories_ai")
            conn.execute("DROP TRIGGER IF EXISTS memories_ad")
            conn.execute("DROP TRIGGER IF EXISTS memories_au")
            conn.execute("DROP TABLE IF EXISTS memories_fts")
            conn.execute("""
                CREATE VIRTUAL TABLE memories_fts
                    USING fts5(content_segmented, tags, metadata, content=memories, content_rowid=rowid)
            """)
            conn.execute("""
                CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content_segmented, tags, metadata)
                    VALUES (new.rowid, new.content_segmented, new.tags, new.metadata);
                END
            """)
            conn.execute("""
                CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content_segmented, tags, metadata)
                    VALUES ('delete', old.rowid, old.content_segmented, old.tags, old.metadata);
                END
            """)
            conn.execute("""
                CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content_segmented, tags, metadata)
                    VALUES ('delete', old.rowid, old.content_segmented, old.tags, old.metadata);
                    INSERT INTO memories_fts(rowid, content_segmented, tags, metadata)
                    VALUES (new.rowid, new.content_segmented, new.tags, new.metadata);
                END
            """)
            conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
            conn.execute(
                "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (4, time.time()),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"[SQLiteStore] migration v3→v4 失败: {e}", exc_info=True)

