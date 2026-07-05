# -*- coding: utf-8-sig -*-
"""sqlite_store_search.py — SQLiteMemoryStoreSearchMixin (SSS-PhaseB)

从 sqlite_store.py 拆分的方法组: search
源文件: sqlite_store.py
"""

import json
import logging
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any



from typing import Dict

class SQLiteMemoryStoreSearchMixin:
    """search方法组Mixin"""

    def search(
        self,
        query: str | None = None,
        layers: list[str] | None = None,
        tags: list[str] | None = None,
        priority: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        min_score: float = 0.0,
        use_fts: bool = True,
        include_archived: bool = False,
    ) -> list[dict]:
        conn = self._get_conn()
        conditions = []
        params = []
        use_fts_query = use_fts and query

        if not include_archived:
            conditions.append("m.archived = 0")

        if layers:
            placeholders = ",".join("?" * len(layers))
            conditions.append(f"m.layer IN ({placeholders})")
            params.extend(layers)

        if priority:
            placeholders = ",".join("?" * len(priority))
            conditions.append(f"m.priority IN ({placeholders})")
            params.extend(priority)

        if tags:
            tag_placeholders = ",".join("?" * len(tags))
            conditions.append(f"""
                m.id IN (
                    SELECT memory_id FROM tag_index
                    WHERE tag IN ({tag_placeholders})
                    GROUP BY memory_id
                    HAVING COUNT(DISTINCT tag) = ?
                )
            """)
            params.extend(tags)
            params.append(len(tags))

        if min_score > 0:
            conditions.append("m.value_score >= ?")
            params.append(min_score)

        if query and not use_fts_query:
            conditions.append("(m.content LIKE ? OR m.tags LIKE ?)")
            like_query = f"%{query}%"
            params.extend([like_query, like_query])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        if use_fts_query:
            fts_query = self._escape_fts_query(query)
            sql = f"""
                SELECT m.*, COALESCE(fts_match.rank, 0) as fts_rank
                FROM memories m
                INNER JOIN (
                    SELECT rowid, rank
                    FROM memories_fts
                    WHERE memories_fts MATCH ?
                ) fts_match ON m.rowid = fts_match.rowid
                WHERE {where_clause}
                ORDER BY
                    fts_match.rank,
                    m.value_score DESC,
                    m.created_at DESC
                LIMIT ? OFFSET ?
            """
            final_params = [fts_query] + params + [limit, offset]
        else:
            sql = f"""
                SELECT m.*, 0 as fts_rank
                FROM memories m
                WHERE {where_clause}
                ORDER BY m.value_score DESC, m.created_at DESC
                LIMIT ? OFFSET ?
            """
            final_params = params + [limit, offset]

        try:
            rows = conn.execute(sql, final_params).fetchall()
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                f"[SQLiteStore] search('{query[:50] if query else ''}') 失败: {e}",
                exc_info=True,
            )
            rows = []
        if use_fts_query and len(rows) == 0 and query:
            like_query = f"%{query}%"
            like_sql = f"""
                SELECT m.*, 0 as fts_rank
                FROM memories m
                WHERE (m.content LIKE ? OR m.tags LIKE ?)
                AND {where_clause}
                ORDER BY m.value_score DESC, m.created_at DESC
                LIMIT ? OFFSET ?
            """
            try:
                rows = conn.execute(
                    like_sql, [like_query, like_query] + params + [limit, offset]
                ).fetchall()
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"[SQLiteStore] LIKE回退搜索失败: {e}")
                rows = []
        self._stats["total_reads"] += 1
        self._stats["search_ops"] += 1
        results = [self._row_to_dict(r) for r in rows]
        for r in results:
            self._cache_set(r["id"], r)

        # P0-fix: 禁用store层evo_loop.record_action (同insert原因)
        # if self._evo_loop is not None:
        #     try:
        #         self._evo_loop.record_action(
        #             action="search",
        #             state_before={"total_reads": self._stats["total_reads"] - 1},
        #             state_after={
        #                 "total_reads": self._stats["total_reads"],
        #                 "results_count": len(results),
        #                 "query": query[:100] if query else "",
        #             },
        #         )
        #     except Exception as e:
        #         logger.debug(f"[SQLiteStore] evo_loop.record_action(search) 忽略: {e}")

        return results

    def search_by_tags(
        self, tags: list[str], limit: int = 20, layers: list[str] | None = None
    ) -> list[dict]:
        conn = self._get_conn()
        placeholders = ",".join("?" * len(tags))
        layer_clause = ""
        layer_params = []
        if layers:
            layer_placeholders = ",".join("?" * len(layers))
            layer_clause = f" AND m.layer IN ({layer_placeholders})"
            layer_params = list(layers)
        rows = conn.execute(
            f"""
            SELECT m.* FROM memories m
            INNER JOIN tag_index t ON m.id = t.memory_id
            WHERE t.tag IN ({placeholders}) AND m.archived = 0{layer_clause}
            GROUP BY m.id
            HAVING COUNT(DISTINCT t.tag) = ?
            ORDER BY MAX(m.value_score) DESC
            LIMIT ?
        """,
            tags + layer_params + [len(tags), limit],
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _escape_fts_query(self, query: str) -> str:
        if not query:
            return "*"
        import re
        # FTS5特殊字符: " * ( ) : ^ AND OR NOT NEAR
        # 先清洗查询中的FTS5不安全字符
        safe_query = re.sub(r'["\*\(\)\:^]', ' ', query)
        safe_query = re.sub(r'\b(AND|OR|NOT|NEAR)\b', ' ', safe_query, flags=re.IGNORECASE)
        safe_query = re.sub(r'\s+', ' ', safe_query).strip()
        if not safe_query:
            return "*"

        from core.shared.chinese_tokenizer import tokenize_query_or

        try:
            fts_q = tokenize_query_or(safe_query)
            # 二次清洗: 确保最终FTS查询中不含危险字符
            fts_q = re.sub(r'["\*\(\)\:^]', '', fts_q)
            # 重新构建安全的OR查询
            tokens = [t.strip().strip('"') for t in fts_q.split(' OR ') if t.strip().strip('"')]
            if not tokens:
                return "*"
            if len(tokens) == 1:
                return f'"{tokens[0]}"'
            return " OR ".join(f'"{t}"' for t in tokens)
        except Exception as e:
            logger.debug(
                f"[SQLiteStore] _escape_fts_query tokenizer失败, 回退regex: {e}"
            )
            cleaned = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", safe_query)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if not cleaned:
                return "*"
            parts = cleaned.split()
            return " OR ".join(f'"{p}"' for p in parts)

    @staticmethod
    def _row_to_dict(row) -> dict:
        d = dict(row)
        for field in ["tags", "metadata", "related_ids", "changelog"]:
            if d.get(field) and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = [] if field != "metadata" else {}
        d.pop("archived", None)
        d.pop("content_segmented", None)
        return d
