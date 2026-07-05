# -*- coding: utf-8-sig -*-
"""sqlite_store_crud.py — SQLiteMemoryStoreCrudMixin (SSS-PhaseB)

从 sqlite_store.py 拆分的方法组: crud
源文件: sqlite_store.py
"""

import json
import logging
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any



from typing import Dict

class SQLiteMemoryStoreCrudMixin:
    """crud方法组Mixin"""

    def insert(self, entry: dict) -> bool:
        with self._write_lock:
            conn = self._get_conn()
            try:
                from core.shared.chinese_tokenizer import tokenize_for_fts

                segmented = tokenize_for_fts(entry["content"])
                conn.execute(
                    """
                    INSERT INTO memories (
                        id, content, content_segmented, layer, tags, priority, value_score,
                        access_count, created_at, last_accessed, size_bytes,
                        metadata, related_ids, changelog
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        entry["id"],
                        entry["content"],
                        segmented,
                        entry["layer"],
                        json.dumps(entry.get("tags", [])),
                        entry.get("priority", "medium"),
                        entry.get("value_score", 0.5),
                        entry.get("access_count", 0),
                        entry.get("created_at", time.time()),
                        entry.get("last_accessed", time.time()),
                        len(entry["content"].encode("utf-8")),
                        json.dumps(entry.get("metadata", {})),
                        json.dumps(entry.get("related_ids", [])),
                        json.dumps(entry.get("changelog", [])),
                    ),
                )
                self._update_tag_index(conn, entry["id"], entry.get("tags", []))
                conn.commit()
                self._stats["total_writes"] += 1
                self._stats["insert_ops"] += 1
                self._cache_set(entry["id"], entry)

                # P0-fix: 禁用store层evo_loop.record_action — hybrid_engine层已有evo_loop
                # store层调用evo_loop会触发_persist_action_to_icme递归HTTP调用，导致7秒超时
                # if self._evo_loop is not None:
                #     try:
                #         self._evo_loop.record_action(
                #             action="insert",
                #             state_before={
                #                 "total_writes": self._stats["total_writes"] - 1
                #             },
                #             state_after={
                #                 "total_writes": self._stats["total_writes"],
                #                 "layer": entry.get("layer", ""),
                #             },
                #         )
                #     except Exception as e:
                #         logger.debug(
                #             f"[SQLiteStore] evo_loop.record_action(insert) 忽略: {e}"
                #         )

                return True
            except sqlite3.IntegrityError:
                return False
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(
                    f"[SQLiteStore] insert({entry.get('id', '?')}) 失败: {e}",
                    exc_info=True,
                )
                return False

    def insert_batch(self, entries: list[dict]) -> int:
        with self._write_lock:
            conn = self._get_conn()
            count = 0
            try:
                conn.execute("BEGIN IMMEDIATE")
                from core.shared.chinese_tokenizer import tokenize_for_fts

                for entry in entries:
                    segmented = tokenize_for_fts(entry["content"])
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO memories (
                            id, content, content_segmented, layer, tags, priority, value_score,
                            access_count, created_at, last_accessed, size_bytes,
                            metadata, related_ids, changelog
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            entry["id"],
                            entry["content"],
                            segmented,
                            entry["layer"],
                            json.dumps(entry.get("tags", [])),
                            entry.get("priority", "medium"),
                            entry.get("value_score", 0.5),
                            entry.get("access_count", 0),
                            entry.get("created_at", time.time()),
                            entry.get("last_accessed", time.time()),
                            len(entry["content"].encode("utf-8")),
                            json.dumps(entry.get("metadata", {})),
                            json.dumps(entry.get("related_ids", [])),
                            json.dumps(entry.get("changelog", [])),
                        ),
                    )
                    self._update_tag_index(conn, entry["id"], entry.get("tags", []))
                    self._cache_set(entry["id"], entry)
                    count += 1
                conn.commit()
                self._stats["total_writes"] += count
                self._stats["batch_ops"] += 1

                # P0-fix: 禁用store层evo_loop.record_action (同insert原因)
                # if self._evo_loop is not None:
                #     try:
                #         self._evo_loop.record_action(
                #             action="insert_batch",
                #             state_before={
                #                 "total_writes": self._stats["total_writes"] - count
                #             },
                #             state_after={
                #                 "total_writes": self._stats["total_writes"],
                #                 "batch_count": count,
                #             },
                #         )
                #     except Exception as e:
                #         logger.debug(
                #             f"[SQLiteStore] evo_loop.record_action(batch) 忽略: {e}"
                #         )

            except Exception as e:
                conn.rollback()
                self._stats["errors"] += 1
                logger.error(f"[SQLiteStore] insert_batch 失败: {e}", exc_info=True)
            return count

    def get(self, entry_id: str) -> dict | None:
        cached = self._cache_get(entry_id)
        if cached:
            return cached

        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ? AND archived = 0", (entry_id,)
        ).fetchone()

        if row:
            self._stats["total_reads"] += 1
            entry = self._row_to_dict(row)
            self._cache_set(entry_id, entry)
            return entry
        return None

    def update(self, entry_id: str, updates: dict) -> bool:
        with self._write_lock:
            conn = self._get_conn()
            try:
                updates["last_accessed"] = time.time()
                access_count = updates.pop("access_count", None)
                if access_count is not None:
                    conn.execute(
                        "UPDATE memories SET access_count = ?, last_accessed = ? WHERE id = ?",
                        (access_count, updates["last_accessed"], entry_id),
                    )
                if "content" in updates:
                    from core.shared.chinese_tokenizer import tokenize_for_fts

                    updates["content_segmented"] = tokenize_for_fts(updates["content"])
                json_fields = {"tags", "metadata", "related_ids", "changelog"}
                if updates:
                    safe_updates = {}
                    for k, v in updates.items():
                        if k in json_fields and not isinstance(v, str):
                            safe_updates[k] = json.dumps(v, ensure_ascii=False)
                        else:
                            safe_updates[k] = v
                    set_clause = ", ".join(f"{k} = ?" for k in safe_updates)
                    values = list(safe_updates.values()) + [entry_id]
                    allowed_columns = {
                        "content",
                        "content_segmented",
                        "layer",
                        "tags",
                        "priority",
                        "last_accessed",
                        "access_count",
                        "value_score",
                        "size_bytes",
                        "metadata",
                    }
                    if not all(k in allowed_columns for k in safe_updates):
                        raise ValueError(
                            f"Invalid column in update: {set(safe_updates.keys()) - allowed_columns}"
                        )
                    conn.execute(
                        f"UPDATE memories SET {set_clause} WHERE id = ?", values
                    )
                conn.commit()
                self._cache_pop(entry_id)
                self._stats["update_ops"] += 1
                return True
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(
                    f"[SQLiteStore] update({entry_id}) 失败: {e}", exc_info=True
                )
                return False

    def delete(self, entry_id: str) -> bool:
        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE memories SET archived = 1, last_accessed = ? WHERE id = ?",
                    (time.time(), entry_id),
                )
                conn.execute("DELETE FROM tag_index WHERE memory_id = ?", (entry_id,))
                conn.commit()
                self._cache_pop(entry_id)
                self._stats["total_writes"] += 1
                self._stats["delete_ops"] += 1
                return True
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(
                    f"[SQLiteStore] delete({entry_id}) 失败: {e}", exc_info=True
                )
                return False

    # ====================================================================
    # [STO-PHASE-1] system_config CRUD — 统一辅助文件存储
    # ====================================================================

    def config_get(self, key: str) -> dict | None:
        """读取system_config单条记录"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT value, updated_at, version, source_file FROM system_config WHERE key = ?",
                (key,),
            ).fetchone()
            if row:
                return {
                    "key": key,
                    "value": json.loads(row[0]),
                    "updated_at": row[1],
                    "version": row[2],
                    "source_file": row[3],
                }
            return None
        except Exception:
            return None

    def config_set(self, key: str, value: dict | str, source_file: str = "") -> bool:
        """写入/更新system_config记录"""
        with self._write_lock:
            conn = self._get_conn()
            try:
                now = time.time()
                json_val = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
                conn.execute("""
                    INSERT INTO system_config (key, value, updated_at, version, source_file)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at,
                        version = version + 1,
                        source_file = excluded.source_file
                """, (key, json_val, now, source_file))
                conn.commit()
                self._stats["total_writes"] += 1
                return True
            except Exception as e:
                logger.error(f"[SQLiteStore] config_set({key}) 失败: {e}")
                return False

    def config_get_all(self) -> list[dict]:
        """获取全部system_config记录(运维视图)"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT key, value, updated_at, version, source_file FROM system_config ORDER BY updated_at DESC"
            ).fetchall()
            results = []
            for r in rows:
                try:
                    parsed = json.loads(r[1])
                except (json.JSONDecodeError, ValueError):
                    # 非JSON格式(如Python dict字符串)，原样返回
                    parsed = r[1]
                results.append({
                    "key": r[0],
                    "value": parsed,
                    "updated_at": r[2],
                    "version": r[3],
                    "source_file": r[4],
                })
            return results
        except Exception:
            return []

    def config_delete(self, key: str) -> bool:
        """删除system_config记录"""
        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM system_config WHERE key = ?", (key,))
                conn.commit()
                return True
            except Exception:
                return False

    def config_migrate_from_json(self, json_path: Path, config_key: str) -> dict:
        """从JSON文件迁移数据到system_config表
        Returns: {"migrated": bool, "record": dict, "error": str|None}
        """
        result = {"migrated": False, "record": None, "error": None}
        if not json_path.exists():
            result["error"] = f"源文件不存在: {json_path}"
            return result
        try:
            raw = json_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, (dict, list, str, int, float, bool)):
                ok = self.config_set(config_key, data, source_file=str(json_path))
                if ok:
                    record = self.config_get(config_key)
                    result["migrated"] = True
                    result["record"] = record
                else:
                    result["error"] = "config_set写入失败"
            else:
                result["error"] = f"不支持的JSON类型: {type(data)}"
        except Exception as e:
            result["error"] = str(e)
        return result

