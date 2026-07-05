# -*- coding: utf-8-sig -*-
"""资产原子 — 数据模型

从 asset_atom.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-asset-004] 延迟类型注解求值,避免前向引用NameError

import hashlib
import json
import sqlite3
import threading
import time
import zlib
from dataclasses import asdict, dataclass, field
from difflib import unified_diff
from enum import Enum


from typing import Optional

class AssetStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETED = "deleted"
    ARCHIVED = "archived"


class ContentType(str, Enum):
    CONVERSATION = "conversation"
    FILE = "file"
    DECISION = "decision"
    KNOWLEDGE = "knowledge"
    RULE = "rule"
    DIRECTORY_INDEX = "directory_index"
    UNKNOWN = "unknown"


VALID_TRANSITIONS = {
    AssetStatus.ACTIVE: [AssetStatus.SUPERSEDED, AssetStatus.DELETED],
    AssetStatus.SUPERSEDED: [
        AssetStatus.ACTIVE,
        AssetStatus.DELETED,
        AssetStatus.ARCHIVED,
    ],
    AssetStatus.DELETED: [AssetStatus.ARCHIVED],
    AssetStatus.ARCHIVED: [],
}


@dataclass
class Provenance:
    created_by: str = ""
    created_at: float = 0.0
    reason: str = ""
    session_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Provenance":
        return cls(
            created_by=d.get("created_by", ""),
            created_at=d.get("created_at", 0.0),
            reason=d.get("reason", ""),
            session_id=d.get("session_id", ""),
        )


@dataclass
class AssetAtom:
    asset_id: str = ""
    memory_id: str = ""
    layer: str = "working"
    content_type: str = ContentType.UNKNOWN
    content_hash: str = ""
    version: int = 1
    parent_version_id: str = ""
    provenance: Provenance = field(default_factory=Provenance)
    references: list[str] = field(default_factory=list)
    referenced_by: list[str] = field(default_factory=list)
    status: str = AssetStatus.ACTIVE
    exported_to: list[str] = field(default_factory=list)
    last_verified: float = 0.0
    tdaf_compatible: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "memory_id": self.memory_id,
            "layer": self.layer,
            "content_type": self.content_type
            if isinstance(self.content_type, str)
            else self.content_type.value,
            "content_hash": self.content_hash,
            "version": self.version,
            "parent_version_id": self.parent_version_id,
            "provenance": self.provenance.to_dict(),
            "references": self.references,
            "referenced_by": self.referenced_by,
            "status": self.status
            if isinstance(self.status, str)
            else self.status.value,
            "exported_to": self.exported_to,
            "last_verified": self.last_verified,
            "tdaf_compatible": self.tdaf_compatible,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AssetAtom":
        prov = d.get("provenance", {})
        if isinstance(prov, str):
            try:
                prov = json.loads(prov)
            except Exception:
                prov = {}
        return cls(
            asset_id=d.get("asset_id", ""),
            memory_id=d.get("memory_id", ""),
            layer=d.get("layer", "working"),
            content_type=d.get("content_type", ContentType.UNKNOWN),
            content_hash=d.get("content_hash", ""),
            version=d.get("version", 1),
            parent_version_id=d.get("parent_version_id", ""),
            provenance=Provenance.from_dict(prov)
            if isinstance(prov, dict)
            else Provenance(),
            references=d.get("references", [])
            if isinstance(d.get("references"), list)
            else json.loads(d.get("references", "[]")),
            referenced_by=d.get("referenced_by", [])
            if isinstance(d.get("referenced_by"), list)
            else json.loads(d.get("referenced_by", "[]")),
            status=d.get("status", AssetStatus.ACTIVE),
            exported_to=d.get("exported_to", [])
            if isinstance(d.get("exported_to"), list)
            else json.loads(d.get("exported_to", "[]")),
            last_verified=d.get("last_verified", 0.0),
            tdaf_compatible=d.get("tdaf_compatible", True),
            created_at=d.get("created_at", 0.0),
            updated_at=d.get("updated_at", 0.0),
        )




__all__ = ["AssetStatus", "ContentType", "Provenance", "AssetAtom"]
