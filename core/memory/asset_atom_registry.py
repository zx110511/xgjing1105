# -*- coding: utf-8-sig -*-
"""资产原子 — 资产注册表

从 asset_atom.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-asset-001] 延迟类型注解求值,避免前向引用NameError

import hashlib
import json
import sqlite3
import threading
import time
import zlib
from dataclasses import asdict, dataclass, field
from difflib import unified_diff
from enum import Enum

class AssetRegistry:
    ASSET_REGISTRY_DDL = """
        CREATE TABLE IF NOT EXISTS asset_registry (
            asset_id TEXT PRIMARY KEY,
            memory_id TEXT NOT NULL,
            layer TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'unknown',
            content_hash TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            parent_version_id TEXT NOT NULL DEFAULT '',
            provenance TEXT NOT NULL DEFAULT '{}',
            references_ids TEXT NOT NULL DEFAULT '[]',
            referenced_by_ids TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'active',
            exported_to TEXT NOT NULL DEFAULT '[]',
            last_verified REAL NOT NULL DEFAULT 0.0,
            tdaf_compatible INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_asset_memory_id
            ON asset_registry(memory_id);
        CREATE INDEX IF NOT EXISTS idx_asset_content_hash
            ON asset_registry(content_hash);
        CREATE INDEX IF NOT EXISTS idx_asset_status
            ON asset_registry(status);
        CREATE INDEX IF NOT EXISTS idx_asset_layer
            ON asset_registry(layer);
    """

    CHANGE_LOG_DDL = """
        CREATE TABLE IF NOT EXISTS change_log (
            change_id TEXT PRIMARY KEY,
            change_type TEXT NOT NULL,
            target_asset_id TEXT NOT NULL,
            target_path TEXT NOT NULL DEFAULT '',
            before_snapshot TEXT NOT NULL DEFAULT '',
            after_snapshot TEXT NOT NULL DEFAULT '',
            diff_summary TEXT NOT NULL DEFAULT '',
            impact_scope TEXT NOT NULL DEFAULT '[]',
            trigger_source TEXT NOT NULL DEFAULT '',
            timestamp REAL NOT NULL,
            session_id TEXT NOT NULL DEFAULT '',
            undo_possible INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_change_target
            ON change_log(target_asset_id);
        CREATE INDEX IF NOT EXISTS idx_change_type
            ON change_log(change_type);
        CREATE INDEX IF NOT EXISTS idx_change_timestamp
            ON change_log(timestamp);
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._snapshot_mgr: AssetSnapshotManager | None = None
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        conn = self._get_conn()
        try:
            conn.executescript(self.ASSET_REGISTRY_DDL)
            conn.executescript(self.CHANGE_LOG_DDL)
            conn.commit()
        finally:
            conn.close()

    def set_snapshot_manager(self, mgr: "AssetSnapshotManager") -> None:
        """注入快照管理器（策略D混合存储）"""
        self._snapshot_mgr = mgr

    @staticmethod
    def generate_asset_id(layer: str, content_hash: str, seq: int = 0) -> str:
        hash_prefix = content_hash[:8] if len(content_hash) >= 8 else content_hash
        return f"{layer}:{hash_prefix}:{seq:04d}"

    @staticmethod
    def compute_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def register(
        self, atom: AssetAtom, content: str = "", tcl_ids: list[str] | None = None
    ) -> str:
        """注册资产原子，可选存储内容快照（策略D混合存储）+ TCL canonical_ids"""
        with self._lock:
            conn = self._get_conn()
            try:
                if not atom.asset_id:
                    existing = conn.execute(
                        "SELECT MAX(version) FROM asset_registry WHERE memory_id = ?",
                        (atom.memory_id,),
                    ).fetchone()[0]
                    seq = (existing or 0) + 1
                    atom.asset_id = self.generate_asset_id(
                        atom.layer, atom.content_hash, seq
                    )
                    atom.version = seq
                    if seq > 1:
                        # 查找上一版本的asset_id作为parent
                        prev = conn.execute(
                            "SELECT asset_id FROM asset_registry WHERE memory_id = ? AND version = ?",
                            (atom.memory_id, seq - 1),
                        ).fetchone()
                        if prev:
                            atom.parent_version_id = prev["asset_id"]
                            # 将旧版本标记为superseded
                            conn.execute(
                                "UPDATE asset_registry SET status='superseded' WHERE asset_id=?",
                                (prev["asset_id"],),
                            )

                if not atom.created_at:
                    atom.created_at = time.time()
                atom.updated_at = time.time()

                conn.execute(
                    """INSERT OR REPLACE INTO asset_registry
                       (asset_id, memory_id, layer, content_type, content_hash, version,
                        parent_version_id, provenance, references_ids, referenced_by_ids,
                        status, exported_to, last_verified, tdaf_compatible,
                        created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        atom.asset_id,
                        atom.memory_id,
                        atom.layer,
                        atom.content_type
                        if isinstance(atom.content_type, str)
                        else atom.content_type.value,
                        atom.content_hash,
                        atom.version,
                        atom.parent_version_id,
                        json.dumps(atom.provenance.to_dict(), ensure_ascii=False),
                        json.dumps(atom.references, ensure_ascii=False),
                        json.dumps(atom.referenced_by, ensure_ascii=False),
                        atom.status
                        if isinstance(atom.status, str)
                        else atom.status.value,
                        json.dumps(atom.exported_to, ensure_ascii=False),
                        atom.last_verified,
                        1 if atom.tdaf_compatible else 0,
                        atom.created_at,
                        atom.updated_at,
                    ),
                )
                conn.commit()

                # 策略D: 存储内容快照
                if content and self._snapshot_mgr:
                    try:
                        self._snapshot_mgr.store_snapshot(
                            atom, content, tcl_ids=tcl_ids or []
                        )
                    except Exception:
                        pass  # 快照存储失败不影响主流程

                return atom.asset_id
            finally:
                conn.close()

    def get(self, asset_id: str) -> AssetAtom | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM asset_registry WHERE asset_id = ?", (asset_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_atom(row)
        finally:
            conn.close()

    def get_by_memory_id(self, memory_id: str) -> list[AssetAtom]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM asset_registry WHERE memory_id = ? ORDER BY version DESC",
                (memory_id,),
            ).fetchall()
            return [self._row_to_atom(r) for r in rows]
        finally:
            conn.close()

    def update(self, atom: AssetAtom) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                atom.updated_at = time.time()
                conn.execute(
                    """UPDATE asset_registry SET
                       layer=?, content_type=?, content_hash=?, version=?,
                       parent_version_id=?, provenance=?, references_ids=?,
                       referenced_by_ids=?, status=?, exported_to=?,
                       last_verified=?, tdaf_compatible=?, updated_at=?
                       WHERE asset_id=?""",
                    (
                        atom.layer,
                        atom.content_type
                        if isinstance(atom.content_type, str)
                        else atom.content_type.value,
                        atom.content_hash,
                        atom.version,
                        atom.parent_version_id,
                        json.dumps(atom.provenance.to_dict(), ensure_ascii=False),
                        json.dumps(atom.references, ensure_ascii=False),
                        json.dumps(atom.referenced_by, ensure_ascii=False),
                        atom.status
                        if isinstance(atom.status, str)
                        else atom.status.value,
                        json.dumps(atom.exported_to, ensure_ascii=False),
                        atom.last_verified,
                        1 if atom.tdaf_compatible else 0,
                        atom.updated_at,
                        atom.asset_id,
                    ),
                )
                conn.commit()
                return conn.total_changes > 0
            finally:
                conn.close()

    def transition(
        self, asset_id: str, new_status: str, session_id: str = ""
    ) -> tuple[bool, str]:
        atom = self.get(asset_id)
        if not atom:
            return False, f"Asset {asset_id} not found"

        current = atom.status if isinstance(atom.status, str) else atom.status.value
        try:
            current_enum = AssetStatus(current)
        except ValueError:
            return False, f"Invalid current status: {current}"

        try:
            new_enum = AssetStatus(new_status)
        except ValueError:
            return False, f"Invalid new status: {new_status}"

        allowed = VALID_TRANSITIONS.get(current_enum, [])
        if new_enum not in allowed:
            return (
                False,
                f"Transition {current}→{new_status} not allowed. Allowed: {[s.value for s in allowed]}",
            )

        old_status = current
        atom.status = new_enum
        atom.updated_at = time.time()
        self.update(atom)

        self.log_change(
            ChangeAtom(
                change_type="status_transition",
                target_asset_id=asset_id,
                diff_summary=f"Status: {old_status}→{new_status}",
                trigger_source="state_machine",
                session_id=session_id,
            )
        )

        return True, f"Transition {old_status}→{new_status} successful"

    def get_version_chain(self, asset_id: str) -> list[AssetAtom]:
        chain = []
        current = self.get(asset_id)
        while current:
            chain.append(current)
            if not current.parent_version_id:
                break
            current = self.get(current.parent_version_id)
        return chain

    def get_latest_version(self, memory_id: str) -> AssetAtom | None:
        atoms = self.get_by_memory_id(memory_id)
        active = [a for a in atoms if a.status == AssetStatus.ACTIVE]
        if active:
            return max(active, key=lambda a: a.version)
        if atoms:
            return max(atoms, key=lambda a: a.version)
        return None

    def add_reference(self, from_id: str, to_id: str) -> bool:
        from_atom = self.get(from_id)
        to_atom = self.get(to_id)
        if not from_atom or not to_atom:
            return False

        if to_id not in from_atom.references:
            from_atom.references.append(to_id)
        if from_id not in to_atom.referenced_by:
            to_atom.referenced_by.append(from_id)

        self.update(from_atom)
        self.update(to_atom)
        return True

    def remove_reference(self, from_id: str, to_id: str) -> bool:
        from_atom = self.get(from_id)
        to_atom = self.get(to_id)
        if not from_atom or not to_atom:
            return False

        if to_id in from_atom.references:
            from_atom.references.remove(to_id)
        if from_id in to_atom.referenced_by:
            to_atom.referenced_by.remove(from_id)

        self.update(from_atom)
        self.update(to_atom)
        return True

    def get_dependents(self, asset_id: str) -> list[AssetAtom]:
        atom = self.get(asset_id)
        if not atom:
            return []
        result = []
        for ref_id in atom.referenced_by:
            ref_atom = self.get(ref_id)
            if ref_atom:
                result.append(ref_atom)
        return result

    def get_dependencies(self, asset_id: str) -> list[AssetAtom]:
        atom = self.get(asset_id)
        if not atom:
            return []
        result = []
        for ref_id in atom.references:
            ref_atom = self.get(ref_id)
            if ref_atom:
                result.append(ref_atom)
        return result

    def log_change(self, change: "ChangeAtom") -> str:
        with self._lock:
            conn = self._get_conn()
            try:
                if not change.change_id:
                    change.change_id = hashlib.sha256(
                        f"{change.target_asset_id}:{change.change_type}:{time.time()}".encode()
                    ).hexdigest()[:16]
                if not change.timestamp:
                    change.timestamp = time.time()
                conn.execute(
                    """INSERT OR REPLACE INTO change_log
                       (change_id, change_type, target_asset_id, target_path,
                        before_snapshot, after_snapshot, diff_summary,
                        impact_scope, trigger_source, timestamp,
                        session_id, undo_possible)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        change.change_id,
                        change.change_type,
                        change.target_asset_id,
                        change.target_path,
                        change.before_snapshot,
                        change.after_snapshot,
                        change.diff_summary,
                        json.dumps(change.impact_scope, ensure_ascii=False),
                        change.trigger_source,
                        change.timestamp,
                        change.session_id,
                        1 if change.undo_possible else 0,
                    ),
                )
                conn.commit()
                return change.change_id
            finally:
                conn.close()

    def get_changes(self, asset_id: str, limit: int = 50) -> list["ChangeAtom"]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM change_log WHERE target_asset_id = ? ORDER BY timestamp DESC LIMIT ?",
                (asset_id, limit),
            ).fetchall()
            return [self._row_to_change(r) for r in rows]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM asset_registry").fetchone()[0]
            by_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as cnt FROM asset_registry GROUP BY status"
            ):
                by_status[row["status"]] = row["cnt"]
            by_layer = {}
            for row in conn.execute(
                "SELECT layer, COUNT(*) as cnt FROM asset_registry GROUP BY layer"
            ):
                by_layer[row["layer"]] = row["cnt"]
            changes = conn.execute("SELECT COUNT(*) FROM change_log").fetchone()[0]
            return {
                "total_assets": total,
                "by_status": by_status,
                "by_layer": by_layer,
                "total_changes": changes,
            }
        finally:
            conn.close()

    def _row_to_atom(self, row) -> AssetAtom:
        d = dict(row)
        d["references"] = json.loads(d.pop("references_ids", "[]"))
        d["referenced_by"] = json.loads(d.pop("referenced_by_ids", "[]"))
        d["tdaf_compatible"] = bool(d.pop("tdaf_compatible", 1))
        return AssetAtom.from_dict(d)

    @staticmethod
    def _row_to_change(row) -> "ChangeAtom":
        d = dict(row)
        d["impact_scope"] = json.loads(d.get("impact_scope", "[]"))
        d["undo_possible"] = bool(d.get("undo_possible", 0))
        return ChangeAtom.from_dict(d)


__all__ = ["AssetRegistry"]
