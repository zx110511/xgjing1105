r"""
D25: L3摘要+知识三元组+标签补全 v1.0
======================================
查询L3层无llm_summary的记录
调用LLM summarize + extract_knowledge + auto_tag 补全
"""

import os
import sys
import time
import json
import sqlite3
import re
from typing import Optional, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))


class L3Enricher:
    BATCH_SIZE = 20
    API_INTERVAL = 2.0

    def __init__(self, db_path: Optional[str] = None, llm_bridge=None):
        if db_path is None:
            root = os.environ.get("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.join(root, "data", "icme.db")
        self._db_path = db_path
        self._llm = llm_bridge
        self._stats = {
            "total_candidates": 0,
            "enriched": 0,
            "summaries_added": 0,
            "triples_added": 0,
            "tags_added": 0,
            "errors": 0,
            "batches": 0,
        }

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _summarize_fallback(self, content: str) -> str:
        sentences = re.split(r'[。！？\n]', content)
        key_sentences = [s.strip() for s in sentences if len(s.strip()) > 10][:3]
        if key_sentences:
            return "。".join(key_sentences) + "。"
        return content[:500]

    def _extract_knowledge_fallback(self, content: str) -> List[Dict]:
        triples = []
        patterns = [
            (r'(\w+)是(\w+)', "是"),
            (r'(\w+)包含(\w+)', "包含"),
            (r'(\w+)依赖(\w+)', "依赖"),
            (r'(\w+)影响(\w+)', "影响"),
        ]
        for pattern, pred in patterns:
            matches = re.findall(pattern, content[:2000])
            for m in matches[:3]:
                triples.append({"subject": m[0], "predicate": pred, "object": m[1]})
            if len(triples) >= 5:
                break
        return triples

    def _auto_tag_fallback(self, content: str) -> List[str]:
        tags = []
        categories = {
            "bug": "缺陷修复", "error": "异常处理", "fix": "修复",
            "feature": "功能开发", "design": "设计决策", "deploy": "部署事件",
            "conversation": "对话记录", "learning": "学习经验", "refactor": "重构",
        }
        content_lower = content[:500].lower()
        for kw, tag in categories.items():
            if kw in content_lower and tag not in tags:
                tags.append(tag)
            if len(tags) >= 5:
                break
        if not tags:
            tags = ["事件记录"]
        return tags

    def enrich(self, dry_run: bool = False) -> Dict:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, content, tags, metadata FROM memories "
                "WHERE layer = 'episodic' AND archived = 0"
            ).fetchall()

            candidates = []
            for row in rows:
                try:
                    meta = json.loads(row["metadata"]) if row["metadata"] else {}
                except Exception:
                    meta = {}
                if not meta.get("llm_summary"):
                    candidates.append(row)

            self._stats["total_candidates"] = len(candidates)

            for i in range(0, len(candidates), self.BATCH_SIZE):
                batch = candidates[i:i + self.BATCH_SIZE]
                self._stats["batches"] += 1

                for row in batch:
                    memory_id = row["id"]
                    content = row["content"] or ""
                    try:
                        meta = json.loads(row["metadata"]) if row["metadata"] else {}
                    except Exception:
                        meta = {}
                    try:
                        existing_tags = json.loads(row["tags"]) if row["tags"] else []
                    except Exception:
                        existing_tags = []

                    try:
                        if self._llm and self._llm.is_ready:
                            summary = self._llm.summarize(content, max_length=500)
                            if not summary:
                                summary = self._summarize_fallback(content)
                            triples = self._llm.extract_knowledge(content)
                            if not triples:
                                triples = self._extract_knowledge_fallback(content)
                            new_tags = self._llm.auto_tag(content)
                            if not new_tags:
                                new_tags = self._auto_tag_fallback(content)
                        else:
                            summary = self._summarize_fallback(content)
                            triples = self._extract_knowledge_fallback(content)
                            new_tags = self._auto_tag_fallback(content)

                        meta["llm_summary"] = summary
                        meta["knowledge_triples"] = triples
                        meta["enriched_by"] = "l3_enricher"
                        meta["enriched_at"] = time.time()

                        merged_tags = list(set(existing_tags + new_tags))

                        self._stats["summaries_added"] += 1
                        self._stats["triples_added"] += len(triples)
                        self._stats["tags_added"] += len(new_tags)

                        if not dry_run:
                            conn.execute(
                                "UPDATE memories SET tags = ?, metadata = ? WHERE id = ?",
                                (json.dumps(merged_tags, ensure_ascii=False),
                                 json.dumps(meta, ensure_ascii=False), memory_id),
                            )
                            conn.commit()

                        self._stats["enriched"] += 1

                    except Exception:
                        self._stats["errors"] += 1

                if self._llm and self._llm.is_ready and not dry_run:
                    time.sleep(self.API_INTERVAL)

        finally:
            conn.close()

        return dict(self._stats)

    def get_stats(self) -> Dict:
        return dict(self._stats)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D25: L3 Summary+Triples+Tags Enrichment")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    enricher = L3Enricher()
    print("=" * 50)
    print("  D25: L3 Summary + Knowledge + Tags Enrichment")
    print("=" * 50)
    result = enricher.enrich(dry_run=args.dry_run)
    print(f"  Candidates:    {result['total_candidates']}")
    print(f"  Enriched:      {result['enriched']}")
    print(f"  Summaries:     {result['summaries_added']}")
    print(f"  Triples:       {result['triples_added']}")
    print(f"  Tags added:    {result['tags_added']}")
    print(f"  Errors:        {result['errors']}")
    print("=" * 50)
