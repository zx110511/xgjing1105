r"""
D23: 历史AssetAtom批量注册器 v1.0
===================================
扫描icme.db所有记忆条目，为每条补注册AssetAtom
支持: 断点续传 / 批量写入 / 进度追踪
"""

import os
import sys
import time
import json
import hashlib
import sqlite3
from typing import Optional, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))

from core.memory.asset_atom import AssetAtom, AssetRegistry, Provenance, ContentType


class HistoricalAssetRegistrar:
    BATCH_SIZE = 1000
    CHECKPOINT_FILE = "register_historical_checkpoint.json"

    def __init__(self, db_path: Optional[str] = None, asset_db_path: Optional[str] = None):
        if db_path is None:
            root = os.environ.get("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.join(root, "data", "icme.db")
        if asset_db_path is None:
            root = os.environ.get("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))
            asset_db_path = os.path.join(root, "data", "asset_registry.db")

        self._db_path = db_path
        self._registry = AssetRegistry(asset_db_path)
        self._checkpoint_path = os.path.join(os.path.dirname(db_path), self.CHECKPOINT_FILE)
        self._stats = {
            "total_scanned": 0,
            "registered": 0,
            "skipped": 0,
            "errors": 0,
            "batches": 0,
        }

    def _get_memories_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_checkpoint(self) -> Dict:
        if os.path.exists(self._checkpoint_path):
            try:
                with open(self._checkpoint_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_offset": 0, "registered_ids": []}

    def _save_checkpoint(self, offset: int, registered_ids: List[str]):
        data = {
            "last_offset": offset,
            "registered_ids": registered_ids[-1000:],
            "timestamp": time.time(),
        }
        try:
            with open(self._checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _clear_checkpoint(self):
        if os.path.exists(self._checkpoint_path):
            os.remove(self._checkpoint_path)

    def _compute_content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _classify_content_type(self, content: str, layer: str, metadata: str) -> str:
        try:
            meta = json.loads(metadata) if metadata else {}
        except Exception:
            meta = {}

        if meta.get("llm_summary"):
            return ContentType.SUMMARY.value
        if meta.get("knowledge_triples"):
            return ContentType.KNOWLEDGE.value
        if meta.get("rule_type") or layer == "meta":
            return ContentType.RULE.value
        if meta.get("decision") or meta.get("decision_type"):
            return ContentType.DECISION.value
        if "conversation" in content[:200].lower() or "user:" in content[:200].lower():
            return ContentType.CONVERSATION.value
        if layer == "episodic":
            return ContentType.CONVERSATION.value
        return ContentType.KNOWLEDGE.value

    def register_all(self, dry_run: bool = False) -> Dict:
        checkpoint = self._load_checkpoint()
        start_offset = checkpoint.get("last_offset", 0)
        registered_ids = checkpoint.get("registered_ids", [])

        conn = self._get_memories_conn()
        try:
            total_count = conn.execute("SELECT COUNT(*) FROM memories WHERE archived = 0").fetchone()[0]
            self._stats["total_scanned"] = total_count

            already_registered = set()
            asset_conn = self._registry._get_conn()
            try:
                rows = asset_conn.execute("SELECT memory_id FROM asset_registry").fetchall()
                already_registered = {r[0] for r in rows}
            finally:
                asset_conn.close()

            offset = start_offset
            while True:
                rows = conn.execute(
                    "SELECT id, content, layer, tags, priority, value_score, "
                    "created_at, metadata FROM memories WHERE archived = 0 "
                    "ORDER BY created_at LIMIT ? OFFSET ?",
                    (self.BATCH_SIZE, offset),
                ).fetchall()

                if not rows:
                    break

                batch_registered = 0
                for row in rows:
                    memory_id = row["id"]
                    if memory_id in already_registered:
                        self._stats["skipped"] += 1
                        continue

                    try:
                        content = row["content"] or ""
                        layer = row["layer"] or "working"
                        content_hash = self._compute_content_hash(content)
                        content_type = self._classify_content_type(
                            content, layer, row["metadata"]
                        )

                        atom = AssetAtom(
                            memory_id=memory_id,
                            layer=layer,
                            content_type=content_type,
                            content_hash=content_hash,
                            version=1,
                            parent_version_id="",
                            provenance=Provenance(
                                created_by="historical_registrar",
                                created_at=row["created_at"] or time.time(),
                                reason="icme_db_migration",
                            ),
                        )

                        if not dry_run:
                            asset_id = self._registry.register(atom)
                            already_registered.add(memory_id)
                            registered_ids.append(memory_id)
                        batch_registered += 1
                        self._stats["registered"] += 1

                    except Exception as e:
                        self._stats["errors"] += 1

                self._stats["batches"] += 1
                offset += self.BATCH_SIZE

                if not dry_run:
                    self._save_checkpoint(offset, registered_ids)

            if not dry_run:
                self._clear_checkpoint()

        finally:
            conn.close()

        return dict(self._stats)

    def get_stats(self) -> Dict:
        return dict(self._stats)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D23: Historical AssetAtom Registration")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--db", default=None, help="Path to icme.db")
    args = parser.parse_args()

    registrar = HistoricalAssetRegistrar(db_path=args.db)
    print("=" * 50)
    print("  D23: Historical AssetAtom Registration")
    print("=" * 50)

    result = registrar.register_all(dry_run=args.dry_run)
    print(f"\n  Total scanned: {result['total_scanned']}")
    print(f"  Registered:    {result['registered']}")
    print(f"  Skipped:       {result['skipped']}")
    print(f"  Errors:        {result['errors']}")
    print(f"  Batches:       {result['batches']}")
    print("=" * 50)
