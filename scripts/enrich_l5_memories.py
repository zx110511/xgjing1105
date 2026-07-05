r"""
D27: L5策略精炼+规则树重组 v1.0
=================================
查询L5层所有记录，规则提取+关系分类+策略精炼+冲突检测
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


class L5Enricher:
    BATCH_SIZE = 5
    API_INTERVAL = 5.0

    def __init__(self, db_path: Optional[str] = None, llm_bridge=None):
        if db_path is None:
            root = os.environ.get("AI_MEMORY_ROOT", os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.join(root, "data", "icme.db")
        self._db_path = db_path
        self._llm = llm_bridge
        self._stats = {
            "total_candidates": 0,
            "enriched": 0,
            "rules_extracted": 0,
            "conflicts_detected": 0,
            "strategies_refined": 0,
            "errors": 0,
            "batches": 0,
        }
        self._rule_tree: Dict[str, List[Dict]] = {}

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _extract_rules_fallback(self, content: str) -> List[Dict]:
        rules = []
        patterns = [
            (r'(?:必须|禁止|不允许|应当|需要|务必)(.{5,50})', "mandatory"),
            (r'(?:建议|推荐|最好|应该)(.{5,50})', "recommended"),
            (r'(?:不能|不可以|切勿|绝不能)(.{5,50})', "prohibited"),
            (r'(?:如果|当|若)(.{5,30})(?:则|那么|就)(.{5,30})', "conditional"),
        ]
        for pattern, rule_type in patterns:
            matches = re.findall(pattern, content[:3000])
            for m in matches[:3]:
                if isinstance(m, tuple):
                    rule_text = f"IF {m[0]} THEN {m[1]}"
                else:
                    rule_text = m
                rules.append({
                    "rule_type": rule_type,
                    "rule_text": rule_text,
                    "version": 1,
                    "effective_from": time.time(),
                })
            if len(rules) >= 5:
                break
        return rules

    def _classify_rule_relations(self, rules: List[Dict]) -> List[Dict]:
        relations = []
        for i, r1 in enumerate(rules):
            for j, r2 in enumerate(rules):
                if i >= j:
                    continue
                t1 = r1.get("rule_type", "")
                t2 = r2.get("rule_type", "")
                if t1 == "prohibited" and t2 == "mandatory":
                    relations.append({
                        "rule_a": r1.get("rule_text", "")[:50],
                        "rule_b": r2.get("rule_text", "")[:50],
                        "relation": "potential_conflict",
                    })
                elif t1 == t2:
                    relations.append({
                        "rule_a": r1.get("rule_text", "")[:50],
                        "rule_b": r2.get("rule_text", "")[:50],
                        "relation": "same_category",
                    })
        return relations

    def _detect_conflicts(self, rules: List[Dict]) -> List[Dict]:
        conflicts = []
        prohibited = [r for r in rules if r.get("rule_type") == "prohibited"]
        mandatory = [r for r in rules if r.get("rule_type") == "mandatory"]

        for p in prohibited:
            for m in mandatory:
                p_text = p.get("rule_text", "")
                m_text = m.get("rule_text", "")
                overlap = len(set(p_text) & set(m_text)) / max(len(set(p_text) | set(m_text)), 1)
                if overlap > 0.3:
                    conflicts.append({
                        "prohibited_rule": p_text[:80],
                        "mandatory_rule": m_text[:80],
                        "overlap_score": round(overlap, 2),
                        "resolution": "requires_manual_review",
                    })
        return conflicts

    def _summarize_fallback(self, content: str) -> str:
        sentences = re.split(r'[。！？\n]', content)
        key = [s.strip() for s in sentences if len(s.strip()) > 15][:2]
        return "。".join(key) + "。" if key else content[:300]

    def enrich(self, dry_run: bool = False) -> Dict:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, content, tags, metadata FROM memories "
                "WHERE layer = 'meta' AND archived = 0"
            ).fetchall()

            self._stats["total_candidates"] = len(rows)

            all_rules = []

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
                            rules = self._llm.extract_knowledge(content)
                            if not rules:
                                rules = self._extract_rules_fallback(content)
                            summary = self._llm.summarize(content, max_length=200)
                            if not summary:
                                summary = self._summarize_fallback(content)
                        else:
                            rules = self._extract_rules_fallback(content)
                            summary = self._summarize_fallback(content)

                        if isinstance(rules, list) and rules and isinstance(rules[0], dict):
                            if "rule_type" not in rules[0]:
                                rules = self._extract_rules_fallback(content)

                        all_rules.extend(rules)

                        rule_relations = self._classify_rule_relations(rules)
                        conflicts = self._detect_conflicts(rules)
                        self._stats["conflicts_detected"] += len(conflicts)

                        meta["extracted_rules"] = rules
                        meta["rule_relations"] = rule_relations
                        meta["detected_conflicts"] = conflicts
                        meta["refined_summary"] = summary
                        meta["strategy_version"] = meta.get("strategy_version", 0) + 1
                        meta["enriched_by"] = "l5_enricher"
                        meta["enriched_at"] = time.time()

                        self._stats["rules_extracted"] += len(rules)
                        self._stats["strategies_refined"] += 1

                        for rule in rules:
                            rule_type = rule.get("rule_type", "unknown")
                            if rule_type not in self._rule_tree:
                                self._rule_tree[rule_type] = []
                            self._rule_tree[rule_type].append({
                                "memory_id": memory_id,
                                "rule": rule,
                            })

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

        finally:
            conn.close()

        return dict(self._stats)

    def get_rule_tree(self) -> Dict:
        return dict(self._rule_tree)

    def get_stats(self) -> Dict:
        return dict(self._stats)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D27: L5 Strategy Refinement + Rule Tree")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    enricher = L5Enricher()
    print("=" * 50)
    print("  D27: L5 Strategy Refinement + Rule Tree")
    print("=" * 50)
    result = enricher.enrich(dry_run=args.dry_run)
    print(f"  Candidates:     {result['total_candidates']}")
    print(f"  Enriched:       {result['enriched']}")
    print(f"  Rules:          {result['rules_extracted']}")
    print(f"  Conflicts:      {result['conflicts_detected']}")
    print(f"  Refined:        {result['strategies_refined']}")
    print(f"  Errors:         {result['errors']}")
    rule_tree = enricher.get_rule_tree()
    for rt, entries in rule_tree.items():
        print(f"  Rule tree [{rt}]: {len(entries)} entries")
    print("=" * 50)
