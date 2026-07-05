r"""
ChangeTracker - 天机变更追踪器 v1.0
====================================
AI工具调用→ChangeAtom自动生成。

D04: AI工具调用→ChangeAtom生成
"""

import time
import json
import hashlib
import threading
from typing import Any, Optional, List, Dict
from pathlib import Path

from ..memory.asset_atom import AssetRegistry, ChangeAtom, AssetAtom, Provenance


class ChangeTracker:
    def __init__(self, registry: AssetRegistry):
        self._registry = registry
        self._lock = threading.Lock()
        self._pending: List[ChangeAtom] = []
        self._stats = {
            "total_tracked": 0,
            "creates": 0,
            "updates": 0,
            "deletes": 0,
            "renames": 0,
        }

    def track_create(
        self,
        path: str,
        content: str,
        memory_id: str = "",
        session_id: str = "",
        trigger_source: str = "ai_action",
    ) -> ChangeAtom:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        atom = AssetAtom(
            memory_id=memory_id,
            layer="working",
            content_type="file",
            content_hash=content_hash,
            provenance=Provenance(
                created_by="ai",
                created_at=time.time(),
                reason=f"File created: {path}",
                session_id=session_id,
            ),
        )
        asset_id = self._registry.register(atom)

        change = ChangeAtom(
            change_type="create",
            target_asset_id=asset_id,
            target_path=path,
            after_snapshot=content_hash,
            diff_summary=f"File created: {path} ({len(content)} bytes)",
            trigger_source=trigger_source,
            session_id=session_id,
            undo_possible=True,
        )
        self._registry.log_change(change)

        with self._lock:
            self._stats["creates"] += 1
            self._stats["total_tracked"] += 1

        return change

    def track_update(
        self,
        path: str,
        before: str,
        after: str,
        memory_id: str = "",
        session_id: str = "",
        trigger_source: str = "ai_action",
    ) -> ChangeAtom:
        before_hash = hashlib.sha256(before.encode("utf-8")).hexdigest()
        after_hash = hashlib.sha256(after.encode("utf-8")).hexdigest()

        if before_hash == after_hash:
            return ChangeAtom(
                change_type="update",
                target_asset_id="",
                target_path=path,
                before_snapshot=before_hash,
                after_snapshot=after_hash,
                diff_summary="No content change detected",
                trigger_source=trigger_source,
                session_id=session_id,
            )

        existing = self._registry.get_by_memory_id(memory_id) if memory_id else []
        if existing:
            latest = self._registry.get_latest_version(memory_id)
            if latest:
                old_asset_id = latest.asset_id
                old_status = latest.status if isinstance(latest.status, str) else latest.status.value
                if old_status == "active":
                    self._registry.transition(old_asset_id, "superseded", session_id)

                new_atom = AssetAtom(
                    memory_id=memory_id,
                    layer=latest.layer,
                    content_type=latest.content_type,
                    content_hash=after_hash,
                    version=latest.version + 1,
                    parent_version_id=old_asset_id,
                    provenance=Provenance(
                        created_by="ai",
                        created_at=time.time(),
                        reason=f"File updated: {path}",
                        session_id=session_id,
                    ),
                    references=latest.references[:],
                    referenced_by=latest.referenced_by[:],
                )
                new_asset_id = self._registry.register(new_atom)
                target_asset_id = new_asset_id
            else:
                target_asset_id = ""
        else:
            atom = AssetAtom(
                memory_id=memory_id,
                content_hash=after_hash,
                content_type="file",
                provenance=Provenance(
                    created_by="ai",
                    created_at=time.time(),
                    reason=f"File updated: {path}",
                    session_id=session_id,
                ),
            )
            target_asset_id = self._registry.register(atom)

        diff_lines_before = before.split("\n")
        diff_lines_after = after.split("\n")
        added = max(0, len(diff_lines_after) - len(diff_lines_before))
        removed = max(0, len(diff_lines_before) - len(diff_lines_after))

        change = ChangeAtom(
            change_type="update",
            target_asset_id=target_asset_id,
            target_path=path,
            before_snapshot=before_hash,
            after_snapshot=after_hash,
            diff_summary=f"File updated: {path} (+{added}/-{removed} lines)",
            impact_scope=[],
            trigger_source=trigger_source,
            session_id=session_id,
            undo_possible=True,
        )
        self._registry.log_change(change)

        with self._lock:
            self._stats["updates"] += 1
            self._stats["total_tracked"] += 1

        return change

    def track_delete(
        self,
        path: str,
        last_content: str = "",
        memory_id: str = "",
        session_id: str = "",
        trigger_source: str = "ai_action",
    ) -> ChangeAtom:
        content_hash = ""
        if last_content:
            content_hash = hashlib.sha256(last_content.encode("utf-8")).hexdigest()

        target_asset_id = ""
        if memory_id:
            latest = self._registry.get_latest_version(memory_id)
            if latest:
                target_asset_id = latest.asset_id
                self._registry.transition(target_asset_id, "deleted", session_id)

        change = ChangeAtom(
            change_type="delete",
            target_asset_id=target_asset_id,
            target_path=path,
            before_snapshot=content_hash,
            diff_summary=f"File deleted: {path}",
            trigger_source=trigger_source,
            session_id=session_id,
            undo_possible=bool(last_content),
        )
        self._registry.log_change(change)

        with self._lock:
            self._stats["deletes"] += 1
            self._stats["total_tracked"] += 1

        return change

    def track_rename(
        self,
        old_path: str,
        new_path: str,
        content: str = "",
        memory_id: str = "",
        session_id: str = "",
        trigger_source: str = "ai_action",
    ) -> ChangeAtom:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else ""

        target_asset_id = ""
        if memory_id:
            latest = self._registry.get_latest_version(memory_id)
            if latest:
                target_asset_id = latest.asset_id

        change = ChangeAtom(
            change_type="rename",
            target_asset_id=target_asset_id,
            target_path=new_path,
            before_snapshot=old_path,
            after_snapshot=new_path,
            diff_summary=f"File renamed: {old_path} → {new_path}",
            trigger_source=trigger_source,
            session_id=session_id,
            undo_possible=True,
        )
        self._registry.log_change(change)

        with self._lock:
            self._stats["renames"] += 1
            self._stats["total_tracked"] += 1

        return change

    def get_stats(self) -> Dict:
        return dict(self._stats)
