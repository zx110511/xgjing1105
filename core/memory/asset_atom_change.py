# -*- coding: utf-8-sig -*-
"""资产原子 — 变更原子

从 asset_atom.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-asset-002] 延迟类型注解求值,避免前向引用NameError

import hashlib
import json
import sqlite3
import threading
import time
import zlib
from dataclasses import asdict, dataclass, field
from difflib import unified_diff
from enum import Enum

class ChangeAtom:
    change_id: str = ""
    change_type: str = ""
    target_asset_id: str = ""
    target_path: str = ""
    before_snapshot: str = ""
    after_snapshot: str = ""
    diff_summary: str = ""
    impact_scope: list[str] = field(default_factory=list)
    trigger_source: str = ""
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""
    undo_possible: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ChangeAtom":
        return cls(
            change_id=d.get("change_id", ""),
            change_type=d.get("change_type", ""),
            target_asset_id=d.get("target_asset_id", ""),
            target_path=d.get("target_path", ""),
            before_snapshot=d.get("before_snapshot", ""),
            after_snapshot=d.get("after_snapshot", ""),
            diff_summary=d.get("diff_summary", ""),
            impact_scope=d.get("impact_scope", [])
            if isinstance(d.get("impact_scope"), list)
            else json.loads(d.get("impact_scope", "[]")),
            trigger_source=d.get("trigger_source", ""),
            timestamp=d.get("timestamp", 0.0),
            session_id=d.get("session_id", ""),
            undo_possible=d.get("undo_possible", False),
        )


# ============================================================
#  策略D 混合存储: AssetSnapshot + DiffEngine + SnapshotManager
# ============================================================

CHECKPOINT_INTERVAL = 10  # 每10个版本创建一个全量快照
COMPRESS_THRESHOLD = 4096  # 超过4KB自动zlib压缩


@dataclass
class AssetSnapshot:
    """资产快照 — 存储全量或增量内容"""

    snapshot_id: str = ""
    asset_id: str = ""
    memory_id: str = ""
    snapshot_type: str = "DIFF"  # FULL / DIFF
    base_snapshot_id: str = ""  # DIFF的基准快照
    content: str = ""  # 全量内容(FULL)或diff内容(DIFF)
    size: int = 0
    compressed: bool = False  # 是否zlib压缩
    checkpoint: bool = False  # 是否检查点
    version: int = 1
    tcl_canonical_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "asset_id": self.asset_id,
            "memory_id": self.memory_id,
            "snapshot_type": self.snapshot_type,
            "base_snapshot_id": self.base_snapshot_id,
            "content": self.content,
            "size": self.size,
            "compressed": self.compressed,
            "checkpoint": self.checkpoint,
            "version": self.version,
            "tcl_canonical_ids": self.tcl_canonical_ids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AssetSnapshot":
        return cls(
            snapshot_id=d.get("snapshot_id", ""),
            asset_id=d.get("asset_id", ""),
            memory_id=d.get("memory_id", ""),
            snapshot_type=d.get("snapshot_type", "DIFF"),
            base_snapshot_id=d.get("base_snapshot_id", ""),
            content=d.get("content", ""),
            size=d.get("size", 0),
            compressed=d.get("compressed", False),
            checkpoint=d.get("checkpoint", False),
            version=d.get("version", 1),
            tcl_canonical_ids=d.get("tcl_canonical_ids", []),
            created_at=d.get("created_at", 0.0),
        )




__all__ = ["ChangeAtom", "AssetSnapshot"]
