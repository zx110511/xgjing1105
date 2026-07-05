"""测试FTS5查询生成"""

import io
import sys

sys.path.insert(0, r"d:\元初系统\天机v9.1")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from core.shared.chinese_tokenizer import tokenize_for_fts, tokenize_query_or

print("=" * 60)
print("测试1: jieba分词")
print("=" * 60)
test_queries = [
    "跨会话审计",
    "跨会话审计补录",
    "系统级策略沉淀",
    "10day-backfill",
    "cross session audit",
    "fb6e53897f9ace36",
]
for q in test_queries:
    tokens = tokenize_for_fts(q)
    fts_or = tokenize_query_or(q)
    print(f"  原文: {q}")
    print(f"  分词(for_fts): {tokens}")
    print(f"  FTS查询(OR): {fts_or}")
    print()

print("=" * 60)
print("测试2: 模拟_escape_fts_query")
print("=" * 60)
import re


def escape_fts_query(query):
    if not query:
        return "*"
    safe_query = re.sub(r'["\*\(\)\:^]', " ", query)
    safe_query = re.sub(r"\b(AND|OR|NOT|NEAR)\b", " ", safe_query, flags=re.IGNORECASE)
    safe_query = re.sub(r"\s+", " ", safe_query).strip()
    if not safe_query:
        return "*"
    try:
        fts_q = tokenize_query_or(safe_query)
        fts_q = re.sub(r'["\*\(\)\:^]', "", fts_q)
        tokens = [
            t.strip().strip('"') for t in fts_q.split(" OR ") if t.strip().strip('"')
        ]
        if not tokens:
            return "*"
        if len(tokens) == 1:
            return f'"{tokens[0]}"'
        return " OR ".join(f'"{t}"' for t in tokens)
    except Exception as e:
        return f"ERROR: {e}"


for q in test_queries:
    escaped = escape_fts_query(q)
    print(f"  Q='{q}' -> escaped='{escaped}'")

print()
print("=" * 60)
print("测试3: 实际FTS5查询")
print("=" * 60)
import sqlite3

db = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db)
for q in test_queries:
    escaped = escape_fts_query(q)
    try:
        rows = conn.execute(
            "SELECT m.id, m.layer FROM memories m "
            "INNER JOIN memories_fts f ON m.rowid = f.rowid "
            "WHERE memories_fts MATCH ? "
            "ORDER BY f.rank LIMIT 2",
            (escaped,),
        ).fetchall()
        print(f"  Q='{q}' escaped='{escaped}' -> {len(rows)}条")
        for r in rows:
            print(f"    - {r[0]} ({r[1]})")
    except Exception as e:
        print(f"  Q='{q}' -> 错误: {e}")

conn.close()
