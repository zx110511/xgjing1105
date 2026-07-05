r"""
D24: L2标签+价值评分补全 v1.0
================================
查询L2层tags为空或value_score=0.5的记录
调用LLM auto_tag + assess_value 补全
"""

import os
import sys
import time
import json
import sqlite3
from typing import Optional, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))


class L2Enricher:
    BATCH_SIZE = 50
    API_INTERVAL = 1.0

    def __init__(self, db_path: Optional[str] = None, llm_bridge=None):
        if db_path is None:
            root = os.environ.get("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.join(root, "data", "icme.db")
        self._db_path = db_path
        self._llm = llm_bridge
        self._stats = {
            "total_candidates": 0,
            "enriched": 0,
            "skipped": 0,
            "errors": 0,
            "batches": 0,
            "tags_added": 0,
            "values_updated": 0,
        }

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _auto_tag_fallback(self, content: str) -> List[str]:
        tags = []
        keywords = {
            "python": "编程", "代码": "开发", "bug": "调试", "错误": "调试",
            "设计": "架构", "优化": "性能", "测试": "质量", "安全": "安全",
            "数据库": "存储", "API": "接口", "配置": "运维", "部署": "运维",
            "对话": "交互", "记忆": "知识管理", "天机": "系统", "规则": "治理",
        }
        content_lower = content[:500].lower()
        for kw, tag in keywords.items():
            if kw in content_lower and tag not in tags:
                tags.append(tag)
            if len(tags) >= 5:
                break
        if not tags:
            tags = ["未分类"]
        return tags

    def _assess_value_fallback(self, content: str, tags: List[str]) -> float:
        score = 0.5
        if len(content) > 500:
            score += 0.1
        if len(content) > 2000:
            score += 0.1
        if any(t in ("架构", "安全", "系统") for t in tags):
            score += 0.15
        if any(t in ("调试", "运维") for t in tags):
            score += 0.05
        return min(score, 1.0)

    def enrich(self, dry_run: bool = False) -> Dict:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, content, tags, value_score, metadata FROM memories "
                "WHERE layer = 'short_term' AND archived = 0 "
                "AND (tags = '[]' OR value_score = 0.5)"
            ).fetchall()

            self._stats["total_candidates"] = len(rows)

            for i in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[i:i + self.BATCH_SIZE]
                self._stats["batches"] += 1

                for row in batch:
                    memory_id = row["id"]
                    content = row["content"] or ""
                    try:
                        existing_tags = json.loads(row["tags"]) if row["tags"] else []
                    except Exception:
                        existing_tags = []

                    try:
                        if self._llm and self._llm.is_ready:
                            new_tags = self._llm.auto_tag(content)
                            if not new_tags:
                                new_tags = self._auto_tag_fallback(content)
                            value_score = self._llm.assess_value(content)
                            if value_score == 0.5:
                                value_score = self._assess_value_fallback(content, new_tags)
                        else:
                            new_tags = self._auto_tag_fallback(content)
                            value_score = self._assess_value_fallback(content, new_tags)

                        merged_tags = list(set(existing_tags + new_tags))
                        self._stats["tags_added"] += len(new_tags)

                        if value_score != row["value_score"]:
                            self._stats["values_updated"] += 1

                        if not dry_run:
                            try:
                                meta = json.loads(row["metadata"]) if row["metadata"] else {}
                            except Exception:
                                meta = {}
                            meta["llm_value_score"] = value_score
                            meta["enriched_by"] = "l2_enricher"
                            meta["enriched_at"] = time.time()

                            conn.execute(
                                "UPDATE memories SET tags = ?, value_score = ?, metadata = ? WHERE id = ?",
                                (json.dumps(merged_tags, ensure_ascii=False), value_score,
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
    parser = argparse.ArgumentParser(description="D24: L2 Tag+Value Enrichment")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    enricher = L2Enricher()
    print("=" * 50)
    print("  D24: L2 Tag + Value Score Enrichment")
    print("=" * 50)
    result = enricher.enrich(dry_run=args.dry_run)
    print(f"  Candidates:  {result['total_candidates']}")
    print(f"  Enriched:    {result['enriched']}")
    print(f"  Tags added:  {result['tags_added']}")
    print(f"  Values upd:  {result['values_updated']}")
    print(f"  Errors:      {result['errors']}")
    print("=" * 50)
