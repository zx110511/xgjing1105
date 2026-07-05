# -*- coding: utf-8-sig -*-
"""资产原子 — 快照+差异引擎

从 asset_atom.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-asset-003] 延迟类型注解求值,避免前向引用NameError

import hashlib
import json
import sqlite3
import threading
import time
import zlib
from dataclasses import asdict, dataclass, field
from difflib import unified_diff
from enum import Enum

class DiffEngine:
    """统一Diff引擎 — 生成和应用unified diff"""

    @staticmethod
    def generate(
        old_text: str, new_text: str, old_label: str = "v{n-1}", new_label: str = "v{n}"
    ) -> str:
        """生成unified diff格式的差异"""
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff_lines = list(
            unified_diff(
                old_lines,
                new_lines,
                fromfile=old_label,
                tofile=new_label,
                lineterm="",
            )
        )
        return "".join(diff_lines)

    @staticmethod
    def apply(base_text: str, diff_text: str, reverse: bool = False) -> str:
        """
        将diff应用到基础文本，生成新版本
        reverse=True: 反向应用diff（回滚）
        """
        if not diff_text.strip():
            return base_text

        base_lines = base_text.splitlines(keepends=True)
        result_lines: list[str] = []
        diff_lines = diff_text.splitlines(keepends=True)

        i = 0  # base指针
        j = 0  # diff指针

        # 跳过diff头部（---, +++, @@）
        while j < len(diff_lines) and diff_lines[j].startswith(("---", "+++")):
            j += 1

        while j < len(diff_lines):
            line = diff_lines[j]

            if line.startswith("@@"):
                # 解析hunk header: @@ -old_start,old_count +new_start,new_count @@
                parts = line.split()
                old_info = parts[1].lstrip("-")
                new_info = parts[2].lstrip("+")
                old_start = int(old_info.split(",")[0]) - 1  # 0-indexed
                new_start = int(new_info.split(",")[0]) - 1

                if not reverse:
                    # 正向: 跳过base中old_start之前的行
                    while i < old_start and i < len(base_lines):
                        result_lines.append(base_lines[i])
                        i += 1
                else:
                    # 反向: 跳过base中new_start之前的行
                    while i < new_start and i < len(base_lines):
                        result_lines.append(base_lines[i])
                        i += 1

                j += 1
            elif line.startswith(" ") or (
                not line.startswith(("+", "-")) and line.strip() == ""
            ):
                # 上下文行
                if not reverse:
                    if i < len(base_lines):
                        result_lines.append(base_lines[i])
                        i += 1
                else:
                    if i < len(base_lines):
                        result_lines.append(base_lines[i])
                        i += 1
                j += 1
            elif line.startswith("+"):
                if not reverse:
                    # 正向: 添加新行
                    result_lines.append(line[1:])
                else:
                    # 反向: 跳过(删除)base中对应行
                    if i < len(base_lines):
                        i += 1
                j += 1
            elif line.startswith("-"):
                if not reverse:
                    # 正向: 跳过base中被删行
                    if i < len(base_lines):
                        i += 1
                else:
                    # 反向: 添加被删行(恢复)
                    result_lines.append(line[1:])
                j += 1
            else:
                j += 1

        # 追加base剩余行
        while i < len(base_lines):
            result_lines.append(base_lines[i])
            i += 1

        return "".join(result_lines)

    @staticmethod
    def compute_diff_summary(diff_text: str, max_len: int = 100) -> str:
        """生成diff摘要"""
        added = 0
        removed = 0
        for line in diff_text.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
        summary = f"+{added}/-{removed} lines"
        if len(summary) > max_len:
            summary = summary[:max_len]
        return summary


class AssetSnapshotManager:
    """资产快照管理器 — 策略D混合存储核心"""

    SNAPSHOT_DDL = """
        CREATE TABLE IF NOT EXISTS asset_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            memory_id TEXT NOT NULL DEFAULT '',
            snapshot_type TEXT NOT NULL DEFAULT 'DIFF',
            base_snapshot_id TEXT DEFAULT '',
            content BLOB,
            size INTEGER NOT NULL DEFAULT 0,
            compressed INTEGER NOT NULL DEFAULT 0,
            checkpoint INTEGER NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 1,
            tcl_canonical_ids TEXT NOT NULL DEFAULT '[]',
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_snap_asset
            ON asset_snapshots(asset_id);
        CREATE INDEX IF NOT EXISTS idx_snap_memory
            ON asset_snapshots(memory_id);
        CREATE INDEX IF NOT EXISTS idx_snap_checkpoint
            ON asset_snapshots(checkpoint);
        CREATE INDEX IF NOT EXISTS idx_snap_version
            ON asset_snapshots(asset_id, version);
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._diff_engine = DiffEngine()
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
            conn.executescript(self.SNAPSHOT_DDL)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _generate_snapshot_id(asset_id: str, version: int) -> str:
        return f"snap_{asset_id.replace(':', '_')}_v{version:03d}"

    def _compress(self, content: str) -> bytes:
        """zlib压缩内容"""
        return zlib.compress(content.encode("utf-8"))

    def _decompress(self, data: bytes) -> str:
        """zlib解压内容"""
        return zlib.decompress(data).decode("utf-8")

    def store_snapshot(
        self, atom: "AssetAtom", content: str, tcl_ids: list[str] | None = None
    ) -> str:
        """
        存储内容快照 — 自动决定FULL/DIFF策略

        规则:
        - version=1 → FULL (首版全量快照)
        - version % CHECKPOINT_INTERVAL == 0 → FULL (检查点)
        - 否则 → DIFF (增量)
        """
        with self._lock:
            version = atom.version
            is_checkpoint = version > 1 and version % CHECKPOINT_INTERVAL == 0
            is_first = version == 1

            if is_first or is_checkpoint:
                return self._store_full(
                    atom, content, is_checkpoint, tcl_ids=tcl_ids or []
                )
            else:
                return self._store_diff(atom, content, tcl_ids=tcl_ids or [])

    def _store_full(
        self,
        atom: "AssetAtom",
        content: str,
        checkpoint: bool = False,
        tcl_ids: list[str] | None = None,
    ) -> str:
        """存储全量快照"""
        snapshot_id = self._generate_snapshot_id(atom.asset_id, atom.version)
        size = len(content.encode("utf-8"))
        compressed = size > COMPRESS_THRESHOLD

        conn = self._get_conn()
        try:
            blob: bytes
            if compressed:
                blob = self._compress(content)
            else:
                blob = content.encode("utf-8")

            conn.execute(
                """INSERT OR REPLACE INTO asset_snapshots
                   (snapshot_id, asset_id, memory_id, snapshot_type,
                    base_snapshot_id, content, size, compressed, checkpoint,
                    version, tcl_canonical_ids, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snapshot_id,
                    atom.asset_id,
                    atom.memory_id,
                    "FULL",
                    "",  # 全量快照无base
                    blob,
                    size,
                    1 if compressed else 0,
                    1 if checkpoint else 0,
                    atom.version,
                    json.dumps(tcl_ids or [], ensure_ascii=False),
                    time.time(),
                ),
            )
            conn.commit()
            return snapshot_id
        finally:
            conn.close()

    def _store_diff(
        self, atom: "AssetAtom", content: str, tcl_ids: list[str] | None = None
    ) -> str:
        """存储增量diff快照"""
        # 获取上一版本的内容
        prev_content = self._get_content_by_version(atom.memory_id, atom.version - 1)
        if not prev_content:
            # 无法获取上一版本内容 → 降级为全量快照
            return self._store_full(
                atom, content, checkpoint=False, tcl_ids=tcl_ids or []
            )

        diff_text = self._diff_engine.generate(
            prev_content,
            content,
            old_label=f"v{atom.version - 1}",
            new_label=f"v{atom.version}",
        )

        if not diff_text.strip():
            # 内容无变化 → 存储空diff
            diff_text = "# No changes detected"

        snapshot_id = self._generate_snapshot_id(atom.asset_id, atom.version)
        size = len(diff_text.encode("utf-8"))
        compressed = size > COMPRESS_THRESHOLD

        # 查找上一版本的snapshot_id作为base
        base_snapshot_id = self._get_snapshot_id(atom.memory_id, atom.version - 1)

        conn = self._get_conn()
        try:
            blob: bytes
            if compressed:
                blob = self._compress(diff_text)
            else:
                blob = diff_text.encode("utf-8")

            conn.execute(
                """INSERT OR REPLACE INTO asset_snapshots
                   (snapshot_id, asset_id, memory_id, snapshot_type,
                    base_snapshot_id, content, size, compressed, checkpoint,
                    version, tcl_canonical_ids, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snapshot_id,
                    atom.asset_id,
                    atom.memory_id,
                    "DIFF",
                    base_snapshot_id or "",
                    blob,
                    size,
                    1 if compressed else 0,
                    0,
                    atom.version,
                    json.dumps(tcl_ids or [], ensure_ascii=False),
                    time.time(),
                ),
            )
            conn.commit()
            return snapshot_id
        finally:
            conn.close()

    def get_content_at_version(self, memory_id: str, version: int) -> str | None:
        """
        获取指定版本的完整内容 — 通过快照链重建

        算法:
        1. 查找该版本的快照
        2. 如果是FULL → 直接返回内容
        3. 如果是DIFF → 递归重建base版本内容，再apply diff
        """
        return self._get_content_by_version(memory_id, version)

    def _get_content_by_version(self, memory_id: str, version: int) -> str | None:
        """内部: 通过快照链逐级重建内容"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT * FROM asset_snapshots
                   WHERE memory_id = ? AND version = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (memory_id, version),
            ).fetchone()

            if not row:
                return None

            snapshot_type = row["snapshot_type"]
            blob = row["content"]
            compressed = bool(row["compressed"])

            if compressed:
                content = self._decompress(blob)
            else:
                content = blob.decode("utf-8") if isinstance(blob, bytes) else blob

            if snapshot_type == "FULL":
                return content

            # DIFF类型: 需要递归查找base
            base_version = version - 1
            if base_version < 1:
                return None

            base_content = self._get_content_by_version(memory_id, base_version)
            if base_content is None:
                return None

            # 正向应用diff
            return self._diff_engine.apply(base_content, content, reverse=False)
        finally:
            conn.close()

    def _get_snapshot_id(self, memory_id: str, version: int) -> str | None:
        """获取指定版本的snapshot_id"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT snapshot_id FROM asset_snapshots WHERE memory_id = ? AND version = ?",
                (memory_id, version),
            ).fetchone()
            return row["snapshot_id"] if row else None
        finally:
            conn.close()

    def get_version_chain(self, memory_id: str, max_versions: int = 50) -> list[dict]:
        """获取版本的完整快照链信息"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT snapshot_id, asset_id, snapshot_type, base_snapshot_id,
                          size, compressed, checkpoint, version, created_at
                   FROM asset_snapshots
                   WHERE memory_id = ?
                   ORDER BY version DESC LIMIT ?""",
                (memory_id, max_versions),
            ).fetchall()

            chain = []
            for row in rows:
                chain.append(
                    {
                        "snapshot_id": row["snapshot_id"],
                        "asset_id": row["asset_id"],
                        "snapshot_type": row["snapshot_type"],
                        "base_snapshot_id": row["base_snapshot_id"],
                        "size": row["size"],
                        "compressed": bool(row["compressed"]),
                        "checkpoint": bool(row["checkpoint"]),
                        "version": row["version"],
                        "created_at": row["created_at"],
                    }
                )
            return chain
        finally:
            conn.close()

    def get_snapshot_stats(self, memory_id: str) -> dict:
        """获取快照存储统计"""
        conn = self._get_conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*), SUM(size) FROM asset_snapshots WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
            full_count = conn.execute(
                "SELECT COUNT(*) FROM asset_snapshots WHERE memory_id = ? AND snapshot_type='FULL'",
                (memory_id,),
            ).fetchone()[0]
            diff_count = conn.execute(
                "SELECT COUNT(*) FROM asset_snapshots WHERE memory_id = ? AND snapshot_type='DIFF'",
                (memory_id,),
            ).fetchone()[0]
            checkpoints = conn.execute(
                "SELECT COUNT(*) FROM asset_snapshots WHERE memory_id = ? AND checkpoint=1",
                (memory_id,),
            ).fetchone()[0]
            return {
                "memory_id": memory_id,
                "total_snapshots": total[0] or 0,
                "total_size_bytes": total[1] or 0,
                "full_snapshots": full_count or 0,
                "diff_snapshots": diff_count or 0,
                "checkpoints": checkpoints or 0,
                "checkpoint_interval": CHECKPOINT_INTERVAL,
            }
        finally:
            conn.close()

    def get_global_stats(self) -> dict:
        """获取全局快照统计"""
        conn = self._get_conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*), SUM(size) FROM asset_snapshots"
            ).fetchone()
            by_type = {}
            for row in conn.execute(
                "SELECT snapshot_type, COUNT(*) as cnt, SUM(size) as sz FROM asset_snapshots GROUP BY snapshot_type"
            ):
                by_type[row["snapshot_type"]] = {
                    "count": row["cnt"],
                    "size_bytes": row["sz"] or 0,
                }
            memory_count = conn.execute(
                "SELECT COUNT(DISTINCT memory_id) FROM asset_snapshots"
            ).fetchone()[0]
            return {
                "total_snapshots": total[0] or 0,
                "total_size_bytes": total[1] or 0,
                "by_type": by_type,
                "unique_memories": memory_count or 0,
                "checkpoint_interval": CHECKPOINT_INTERVAL,
            }
        finally:
            conn.close()

    def update_tcl_ids(self, snapshot_id: str, canonical_ids: list[str]) -> bool:
        """更新快照的TCL canonical_ids"""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE asset_snapshots SET tcl_canonical_ids = ? WHERE snapshot_id = ?",
                (json.dumps(canonical_ids, ensure_ascii=False), snapshot_id),
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def get_tcl_ids(self, snapshot_id: str) -> list[str]:
        """获取快照的TCL canonical_ids"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT tcl_canonical_ids FROM asset_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            if row:
                return json.loads(row["tcl_canonical_ids"])
            return []
        finally:
            conn.close()

    def find_nearest_checkpoint(self, memory_id: str, version: int) -> dict | None:
        """
        查找最近的checkpoint（快照链加速回滚）

        优先查找 ≤version 的最近FULL checkpoint
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT snapshot_id, asset_id, version, snapshot_type
                   FROM asset_snapshots
                   WHERE memory_id = ? AND checkpoint = 1 AND version <= ?
                   ORDER BY version DESC LIMIT 1""",
                (memory_id, version),
            ).fetchone()
            if row:
                return dict(row)
            # 无checkpoint → 找最早的FULL快照
            row = conn.execute(
                """SELECT snapshot_id, asset_id, version, snapshot_type
                   FROM asset_snapshots
                   WHERE memory_id = ? AND snapshot_type = 'FULL' AND version <= ?
                   ORDER BY version DESC LIMIT 1""",
                (memory_id, version),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


__all__ = ["DiffEngine", "AssetSnapshotManager"]
