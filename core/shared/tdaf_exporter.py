r"""
TDAF Exporter - 天机数字资产导出器 v1.0
=========================================
D17: 全量导出器 (按层分批+流式写入)
D18: 增量导出器 (since_timestamp增量)
"""

import time
import json
import sqlite3
from typing import Optional, List, Dict, Callable
from pathlib import Path

from .tdaf_schema import (
    TDAFDocument, TDAFManifest, TDAFValidator,
    validate_tdaf, create_empty_tdaf,
)


class TDAFExporter:
    BATCH_SIZE = 1000

    def __init__(self, db_path: str, registry=None):
        self._db_path = db_path
        self._registry = registry
        self._last_export_timestamp = 0.0

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def export_full(self, output_path: str, include_content: bool = False) -> Dict:
        start = time.time()
        doc = create_empty_tdaf(export_type="full")

        manifest = TDAFManifest()
        all_assets = []
        total_size = 0

        conn = self._get_conn()
        try:
            conn_assets = sqlite3.connect(self._db_path)
            conn_assets.row_factory = sqlite3.Row
            try:
                offset = 0
                while True:
                    rows = conn_assets.execute(
                        "SELECT * FROM asset_registry ORDER BY asset_id LIMIT ? OFFSET ?",
                        (self.BATCH_SIZE, offset),
                    ).fetchall()

                    if not rows:
                        break

                    for row in rows:
                        asset_dict = self._row_to_tdaf_asset(row, include_content)
                        all_assets.append(asset_dict)

                        layer = row["layer"]
                        ct = row["content_type"]
                        status = row["status"]
                        manifest.by_layer[layer] = manifest.by_layer.get(layer, 0) + 1
                        manifest.by_content_type[ct] = manifest.by_content_type.get(ct, 0) + 1
                        manifest.by_status[status] = manifest.by_status.get(status, 0) + 1

                    offset += self.BATCH_SIZE
            finally:
                conn_assets.close()

            kg = self._export_kg(conn)
            doc.knowledge_graph = kg

            changes = self._export_changes(conn)
            doc.change_log = changes

        finally:
            conn.close()

        manifest.total_assets = len(all_assets)
        manifest.total_size_bytes = total_size
        doc.manifest = manifest
        doc.assets = all_assets
        doc.export_timestamp = time.time()

        valid, errors = validate_tdaf(doc.to_dict())

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(doc.to_json())

        self._last_export_timestamp = doc.export_timestamp

        return {
            "success": True,
            "output_path": output_path,
            "total_assets": manifest.total_assets,
            "by_layer": manifest.by_layer,
            "validation_passed": valid,
            "validation_errors": errors,
            "duration_ms": (time.time() - start) * 1000,
        }

    def export_incremental(self, output_path: str, since_timestamp: float = 0.0,
                           include_content: bool = False) -> Dict:
        start = time.time()

        if since_timestamp == 0.0:
            since_timestamp = self._last_export_timestamp

        doc = create_empty_tdaf(export_type="incremental", since_timestamp=since_timestamp)
        manifest = TDAFManifest()
        all_assets = []

        conn = self._get_conn()
        try:
            conn_assets = sqlite3.connect(self._db_path)
            conn_assets.row_factory = sqlite3.Row
            try:
                rows = conn_assets.execute(
                    "SELECT * FROM asset_registry WHERE updated_at > ? ORDER BY asset_id",
                    (since_timestamp,),
                ).fetchall()

                for row in rows:
                    asset_dict = self._row_to_tdaf_asset(row, include_content)
                    all_assets.append(asset_dict)

                    layer = row["layer"]
                    ct = row["content_type"]
                    status = row["status"]
                    manifest.by_layer[layer] = manifest.by_layer.get(layer, 0) + 1
                    manifest.by_content_type[ct] = manifest.by_content_type.get(ct, 0) + 1
                    manifest.by_status[status] = manifest.by_status.get(status, 0) + 1
            finally:
                conn_assets.close()

            changes = self._export_changes(conn, since_timestamp=since_timestamp)
            doc.change_log = changes

        finally:
            conn.close()

        manifest.total_assets = len(all_assets)
        doc.manifest = manifest
        doc.assets = all_assets
        doc.export_timestamp = time.time()

        valid, errors = validate_tdaf(doc.to_dict())

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(doc.to_json())

        self._last_export_timestamp = doc.export_timestamp

        return {
            "success": True,
            "output_path": output_path,
            "since_timestamp": since_timestamp,
            "total_assets": manifest.total_assets,
            "by_layer": manifest.by_layer,
            "validation_passed": valid,
            "validation_errors": errors,
            "duration_ms": (time.time() - start) * 1000,
        }

    def _row_to_tdaf_asset(self, row, include_content: bool) -> dict:
        asset = {
            "asset_id": row["asset_id"],
            "memory_id": row["memory_id"],
            "layer": row["layer"],
            "content_type": row["content_type"],
            "content_hash": row["content_hash"],
            "version": row["version"],
            "parent_version_id": row["parent_version_id"],
            "provenance": json.loads(row["provenance"]) if row["provenance"] else {},
            "tags": [],
            "triples": [],
            "references": json.loads(row["references_ids"]) if row["references_ids"] else [],
            "referenced_by": json.loads(row["referenced_by_ids"]) if row["referenced_by_ids"] else [],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

        if include_content:
            try:
                mem_conn = sqlite3.connect(self._db_path)
                mem_conn.row_factory = sqlite3.Row
                try:
                    mem_row = mem_conn.execute(
                        "SELECT content, tags FROM memories WHERE id = ?",
                        (row["memory_id"],),
                    ).fetchone()
                    if mem_row:
                        asset["content"] = mem_row["content"] or ""
                        asset["tags"] = json.loads(mem_row["tags"]) if mem_row["tags"] else []
                finally:
                    mem_conn.close()
            except Exception:
                pass

        return asset

    def _export_kg(self, conn) -> dict:
        nodes = []
        edges = []
        try:
            kg_rows = conn.execute("SELECT * FROM knowledge_graph LIMIT 10000").fetchall()
            for row in kg_rows:
                if row["subject"] and row["predicate"] and row["object"]:
                    nodes.append({"id": row["subject"], "label": row["subject"], "type": "entity"})
                    nodes.append({"id": row["object"], "label": row["object"], "type": "entity"})
                    edges.append({
                        "source": row["subject"],
                        "target": row["object"],
                        "predicate": row["predicate"],
                        "weight": 1.0,
                    })
        except Exception:
            pass

        seen = {}
        unique_nodes = []
        for n in nodes:
            if n["id"] not in seen:
                seen[n["id"]] = True
                unique_nodes.append(n)

        return {"nodes": unique_nodes, "edges": edges}

    def _export_changes(self, conn, since_timestamp: float = 0.0) -> list:
        changes = []
        try:
            if since_timestamp > 0:
                rows = conn.execute(
                    "SELECT * FROM change_log WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 10000",
                    (since_timestamp,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM change_log ORDER BY timestamp DESC LIMIT 10000",
                ).fetchall()

            for row in rows:
                changes.append({
                    "change_id": row["change_id"],
                    "change_type": row["change_type"],
                    "target_asset_id": row["target_asset_id"],
                    "diff_summary": row["diff_summary"],
                    "timestamp": row["timestamp"],
                    "trigger_source": row["trigger_source"],
                })
        except Exception:
            pass

        return changes
