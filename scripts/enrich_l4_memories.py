r"""
D26: L4知识归一化+KG三元组融合 v1.0
=====================================
查询L4层所有记录，同义概念合并，三元组提取融合
"""

import os
import sys
import time
import json
import sqlite3
import re
from typing import Optional, Dict, List, Set, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))


class L4Enricher:
    BATCH_SIZE = 10
    API_INTERVAL = 3.0
    SIMILARITY_THRESHOLD = 0.85

    def __init__(self, db_path: Optional[str] = None, llm_bridge=None):
        if db_path is None:
            root = os.environ.get("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.join(root, "data", "icme.db")
        self._db_path = db_path
        self._llm = llm_bridge
        self._stats = {
            "total_candidates": 0,
            "enriched": 0,
            "concepts_merged": 0,
            "triples_extracted": 0,
            "hierarchy_edges": 0,
            "errors": 0,
            "batches": 0,
        }

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _extract_knowledge_fallback(self, content: str) -> List[Dict]:
        triples = []
        patterns = [
            (r'(\w{2,8})是(?:一种|一个|一类)(\w{2,8})', "is_a"),
            (r'(\w{2,8})包含(\w{2,8})', "contains"),
            (r'(\w{2,8})依赖(?:于)?(\w{2,8})', "depends_on"),
            (r'(\w{2,8})影响(\w{2,8})', "affects"),
            (r'(\w{2,8})(?:使用|调用)(\w{2,8})', "uses"),
            (r'(\w{2,8})实现(\w{2,8})', "implements"),
        ]
        for pattern, pred in patterns:
            matches = re.findall(pattern, content[:3000])
            for m in matches[:3]:
                triples.append({"subject": m[0], "predicate": pred, "object": m[1]})
            if len(triples) >= 8:
                break
        return triples

    def _compute_similarity(self, s1: str, s2: str) -> float:
        if s1 == s2:
            return 1.0
        set1 = set(s1)
        set2 = set(s2)
        if not set1 or not set2:
            return 0.0
        intersection = set1 & set2
        union = set1 | set2
        return len(intersection) / len(union)

    def _find_merge_candidates(self, concepts: List[str]) -> List[Tuple[str, str]]:
        merges = []
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                sim = self._compute_similarity(concepts[i], concepts[j])
                if sim >= self.SIMILARITY_THRESHOLD:
                    merges.append((concepts[i], concepts[j]))
        return merges

    def _build_hierarchy(self, triples: List[Dict]) -> List[Dict]:
        hierarchy_edges = []
        for t in triples:
            pred = t.get("predicate", "")
            if pred in ("is_a", "implements", "contains"):
                hierarchy_edges.append({
                    "source": t["subject"],
                    "target": t["object"],
                    "relation": f"hierarchy_{pred}",
                })
        return hierarchy_edges

    def enrich(self, dry_run: bool = False) -> Dict:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, content, tags, metadata FROM memories "
                "WHERE layer = 'semantic' AND archived = 0"
            ).fetchall()

            self._stats["total_candidates"] = len(rows)

            all_concepts = []
            all_triples = []

            for i in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[i:i + self.BATCH_SIZE]
                self._stats["batches"] += 1

                for row in batch:
                    memory_id = row["id"]
                    content = row["content"] or ""
                    try:
                        meta = json.loads(row["metadata"]) if row["metadata"] else {}
                    except Exception:
                        meta = {}

                    try:
                        if self._llm and self._llm.is_ready:
                            triples = self._llm.extract_knowledge(content)
                            if not triples:
                                triples = self._extract_knowledge_fallback(content)
                        else:
                            triples = self._extract_knowledge_fallback(content)

                        all_triples.extend(triples)
                        for t in triples:
                            all_concepts.append(t.get("subject", ""))
                            all_concepts.append(t.get("object", ""))

                        hierarchy = self._build_hierarchy(triples)
                        self._stats["hierarchy_edges"] += len(hierarchy)

                        existing_triples = meta.get("knowledge_triples", [])
                        merged_triples = existing_triples + triples
                        deduped = []
                        seen = set()
                        for t in merged_triples:
                            key = f"{t.get('subject','')}|{t.get('predicate','')}|{t.get('object','')}"
                            if key not in seen:
                                seen.add(key)
                                deduped.append(t)

                        meta["knowledge_triples"] = deduped
                        meta["enriched_by"] = "l4_enricher"
                        meta["enriched_at"] = time.time()

                        self._stats["triples_extracted"] += len(triples)

                        if not dry_run:
                            conn.execute(
                                "UPDATE memories SET metadata = ? WHERE id = ?",
                                (json.dumps(meta, ensure_ascii=False), memory_id),
                            )
                            conn.commit()

                        self._stats["enriched"] += 1

                    except Exception:
                        self._stats["errors"] += 1

                if self._llm and self._llm.is_ready and not dry_run:
                    time.sleep(self.API_INTERVAL)

            unique_concepts = list(set(c for c in all_concepts if c))
            merges = self._find_merge_candidates(unique_concepts)
            self._stats["concepts_merged"] = len(merges)

            if not dry_run and merges:
                kg_conn = self._get_conn()
                try:
                    for c1, c2 in merges:
                        canonical = c1 if len(c1) <= len(c2) else c2
                        alias = c2 if canonical == c1 else c1
                        kg_conn.execute(
                            "INSERT OR IGNORE INTO knowledge_graph "
                            "(entity_name, entity_type, properties, first_seen, last_seen, frequency) "
                            "VALUES (?, 'concept', ?, ?, ?, 1)",
                            (canonical, json.dumps({"aliases": [alias]}, ensure_ascii=False),
                             time.time(), time.time()),
                        )
                        kg_conn.execute(
                            "INSERT OR IGNORE INTO knowledge_edges "
                            "(source, target, relation, weight, timestamp) "
                            "VALUES (?, ?, 'similar_to', ?, ?)",
                            (c1, c2, self.SIMILARITY_THRESHOLD, time.time()),
                        )
                    kg_conn.commit()
                finally:
                    kg_conn.close()

        finally:
            conn.close()

        return dict(self._stats)

    def get_stats(self) -> Dict:
        return dict(self._stats)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D26: L4 Knowledge Normalization + KG Fusion")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    enricher = L4Enricher()
    print("=" * 50)
    print("  D26: L4 Knowledge Normalization + KG Fusion")
    print("=" * 50)
    result = enricher.enrich(dry_run=args.dry_run)
    print(f"  Candidates:     {result['total_candidates']}")
    print(f"  Enriched:       {result['enriched']}")
    print(f"  Concepts merged:{result['concepts_merged']}")
    print(f"  Triples:        {result['triples_extracted']}")
    print(f"  Hierarchy:      {result['hierarchy_edges']}")
    print(f"  Errors:         {result['errors']}")
    print("=" * 50)
