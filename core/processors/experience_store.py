# -*- coding: utf-8-sig -*-
"""经验自动沉淀 - 存储层

基于SQLite的操作轨迹与经验条目存储。

架构位置: D4悟道域 - 进化处理器
版本: v1.0.0 (Phase 1 MVP)
"""

from __future__ import annotations

import json
import sqlite3
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .experience_models import (
    OperationTrace,
    ExperienceEntry,
    CollectionStats,
    ExperienceDomain,
    PatternType,
    ExperienceGrade,
)

logger = logging.getLogger(__name__)


class ExperienceStore:
    """经验存储 - SQLite实现

    Phase 1 MVP:
    - 操作轨迹CRUD
    - 经验条目CRUD
    - 基础查询与统计
    - 本地存储，与记忆系统解耦
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / ".memory" / "experience.db"
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_tables()
        logger.info("ExperienceStore 初始化完成 db=%s", db_path)

    def _init_tables(self) -> None:
        """初始化数据库表结构"""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS operation_traces (
                trace_id TEXT PRIMARY KEY,
                session_id TEXT,
                agent_id TEXT,
                task_type TEXT,
                tool_name TEXT,
                tool_params TEXT,
                result_summary TEXT,
                success INTEGER,
                duration_ms REAL,
                error_type TEXT,
                error_message TEXT,
                context_tags TEXT,
                timestamp REAL,
                parent_trace_id TEXT,
                content_hash TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_traces_tool ON operation_traces(tool_name);
            CREATE INDEX IF NOT EXISTS idx_traces_agent ON operation_traces(agent_id);
            CREATE INDEX IF NOT EXISTS idx_traces_session ON operation_traces(session_id);
            CREATE INDEX IF NOT EXISTS idx_traces_success ON operation_traces(success);
            CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON operation_traces(timestamp);
            CREATE INDEX IF NOT EXISTS idx_traces_hash ON operation_traces(content_hash);

            CREATE TABLE IF NOT EXISTS experience_entries (
                experience_id TEXT PRIMARY KEY,
                version TEXT,
                domain TEXT,
                pattern_type TEXT,
                grade TEXT,
                trigger_context TEXT,
                solution TEXT,
                outcome TEXT,
                metadata TEXT,
                source_trace_ids TEXT,
                created_at REAL,
                updated_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_exp_domain ON experience_entries(domain);
            CREATE INDEX IF NOT EXISTS idx_exp_pattern ON experience_entries(pattern_type);
            CREATE INDEX IF NOT EXISTS idx_exp_grade ON experience_entries(grade);
            CREATE INDEX IF NOT EXISTS idx_exp_created ON experience_entries(created_at);

            CREATE VIRTUAL TABLE IF NOT EXISTS traces_fts USING fts5(
                tool_name, result_summary, error_message, context_tags,
                content=operation_traces, content_rowid=rowid,
                tokenize='trigram'
            );

            CREATE TRIGGER IF NOT EXISTS traces_ai AFTER INSERT ON operation_traces BEGIN
                INSERT INTO traces_fts(rowid, tool_name, result_summary, error_message, context_tags)
                VALUES (new.rowid, new.tool_name, new.result_summary, new.error_message, new.context_tags);
            END;

            CREATE TRIGGER IF NOT EXISTS traces_ad AFTER DELETE ON operation_traces BEGIN
                INSERT INTO traces_fts(traces_fts, rowid, tool_name, result_summary, error_message, context_tags)
                VALUES ('delete', old.rowid, old.tool_name, old.result_summary, old.error_message, old.context_tags);
            END;

            CREATE TRIGGER IF NOT EXISTS traces_au AFTER UPDATE ON operation_traces BEGIN
                INSERT INTO traces_fts(traces_fts, rowid, tool_name, result_summary, error_message, context_tags)
                VALUES ('delete', old.rowid, old.tool_name, old.result_summary, old.error_message, old.context_tags);
                INSERT INTO traces_fts(rowid, tool_name, result_summary, error_message, context_tags)
                VALUES (new.rowid, new.tool_name, new.result_summary, new.error_message, new.context_tags);
            END;
        """)
        self._conn.commit()

    # ── 操作轨迹 ──

    def add_trace(self, trace: OperationTrace) -> str:
        """添加操作轨迹"""
        content_hash = trace.content_hash()
        self._conn.execute(
            """INSERT OR REPLACE INTO operation_traces
               (trace_id, session_id, agent_id, task_type, tool_name, tool_params,
                result_summary, success, duration_ms, error_type, error_message,
                context_tags, timestamp, parent_trace_id, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trace.trace_id,
                trace.session_id,
                trace.agent_id,
                trace.task_type,
                trace.tool_name,
                json.dumps(trace.tool_params, ensure_ascii=False),
                trace.result_summary,
                1 if trace.success else 0,
                trace.duration_ms,
                trace.error_type,
                trace.error_message,
                json.dumps(trace.context_tags, ensure_ascii=False),
                trace.timestamp,
                trace.parent_trace_id,
                content_hash,
            ),
        )
        self._conn.commit()
        logger.debug("添加操作轨迹: %s (tool=%s, success=%s)", trace.trace_id, trace.tool_name, trace.success)
        return trace.trace_id

    def get_trace(self, trace_id: str) -> Optional[OperationTrace]:
        """根据ID获取操作轨迹"""
        row = self._conn.execute(
            "SELECT * FROM operation_traces WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_trace(row)

    def list_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        tool_name: Optional[str] = None,
        agent_id: Optional[str] = None,
        success: Optional[bool] = None,
        domain: Optional[str] = None,
    ) -> List[OperationTrace]:
        """列出操作轨迹，支持多条件筛选"""
        query = "SELECT * FROM operation_traces WHERE 1=1"
        params: List[Any] = []

        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if success is not None:
            query += " AND success = ?"
            params.append(1 if success else 0)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_trace(r) for r in rows]

    def search_traces(self, keyword: str, limit: int = 20) -> List[OperationTrace]:
        """全文搜索操作轨迹

        中文优先使用LIKE（FTS5对中文支持有限），英文尝试FTS5
        """
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in keyword)

        if not has_chinese:
            try:
                search_term = f'"{keyword}"'
                rows = self._conn.execute(
                    """SELECT t.* FROM operation_traces t
                       JOIN traces_fts f ON t.rowid = f.rowid
                       WHERE traces_fts MATCH ?
                       ORDER BY rank LIMIT ?""",
                    (search_term, limit),
                ).fetchall()
                if rows:
                    return [self._row_to_trace(r) for r in rows]
            except sqlite3.OperationalError:
                pass

        rows = self._conn.execute(
            """SELECT * FROM operation_traces
               WHERE tool_name LIKE ? OR result_summary LIKE ?
                  OR error_message LIKE ? OR context_tags LIKE ?
               ORDER BY timestamp DESC LIMIT ?""",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit),
        ).fetchall()
        return [self._row_to_trace(r) for r in rows]

    def count_traces(
        self,
        tool_name: Optional[str] = None,
        agent_id: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> int:
        """统计操作轨迹数量"""
        query = "SELECT COUNT(*) FROM operation_traces WHERE 1=1"
        params: List[Any] = []

        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if success is not None:
            query += " AND success = ?"
            params.append(1 if success else 0)

        return self._conn.execute(query, params).fetchone()[0]

    def _row_to_trace(self, row: sqlite3.Row) -> OperationTrace:
        """将数据库行转为OperationTrace对象"""
        d = dict(row)
        return OperationTrace(
            trace_id=d["trace_id"],
            session_id=d["session_id"] or "",
            agent_id=d["agent_id"] or "",
            task_type=d["task_type"] or "",
            tool_name=d["tool_name"] or "",
            tool_params=json.loads(d["tool_params"]) if d["tool_params"] else {},
            result_summary=d["result_summary"] or "",
            success=bool(d["success"]),
            duration_ms=d["duration_ms"] or 0.0,
            error_type=d["error_type"] or "",
            error_message=d["error_message"] or "",
            context_tags=json.loads(d["context_tags"]) if d["context_tags"] else [],
            timestamp=d["timestamp"] or 0.0,
            parent_trace_id=d["parent_trace_id"] or "",
        )

    # ── 经验条目 ──

    def add_experience(self, experience: ExperienceEntry) -> str:
        """添加经验条目"""
        self._conn.execute(
            """INSERT OR REPLACE INTO experience_entries
               (experience_id, version, domain, pattern_type, grade,
                trigger_context, solution, outcome, metadata,
                source_trace_ids, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experience.experience_id,
                experience.version,
                experience.domain.value if isinstance(experience.domain, ExperienceDomain) else experience.domain,
                experience.pattern_type.value if isinstance(experience.pattern_type, PatternType) else experience.pattern_type,
                experience.grade.value if isinstance(experience.grade, ExperienceGrade) else experience.grade,
                json.dumps(experience.trigger_context, ensure_ascii=False),
                json.dumps(experience.solution, ensure_ascii=False),
                json.dumps(experience.outcome, ensure_ascii=False),
                json.dumps(experience.metadata, ensure_ascii=False),
                json.dumps(experience.source_trace_ids, ensure_ascii=False),
                experience.created_at,
                experience.updated_at,
            ),
        )
        self._conn.commit()
        logger.debug("添加经验条目: %s (domain=%s)", experience.experience_id, experience.domain)
        return experience.experience_id

    def get_experience(self, experience_id: str) -> Optional[ExperienceEntry]:
        """获取经验条目"""
        row = self._conn.execute(
            "SELECT * FROM experience_entries WHERE experience_id = ?",
            (experience_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_experience(row)

    def list_experiences(
        self,
        limit: int = 50,
        offset: int = 0,
        domain: Optional[str] = None,
        pattern_type: Optional[str] = None,
        grade: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> List[ExperienceEntry]:
        """列出经验条目"""
        query = "SELECT * FROM experience_entries WHERE 1=1"
        params: List[Any] = []

        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)
        if grade:
            query += " AND grade = ?"
            params.append(grade)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def count_experiences(self, domain: Optional[str] = None, grade: Optional[str] = None) -> int:
        """统计经验条目数量"""
        query = "SELECT COUNT(*) FROM experience_entries WHERE 1=1"
        params: List[Any] = []

        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if grade:
            query += " AND grade = ?"
            params.append(grade)

        return self._conn.execute(query, params).fetchone()[0]

    def _row_to_experience(self, row: sqlite3.Row) -> ExperienceEntry:
        """将数据库行转为ExperienceEntry对象"""
        d = dict(row)
        return ExperienceEntry(
            experience_id=d["experience_id"],
            version=d["version"],
            domain=ExperienceDomain(d["domain"]) if d["domain"] else ExperienceDomain.OTHER,
            pattern_type=PatternType(d["pattern_type"]) if d["pattern_type"] else PatternType.TRACE,
            grade=ExperienceGrade(d["grade"]) if d["grade"] else ExperienceGrade.D,
            trigger_context=json.loads(d["trigger_context"]) if d["trigger_context"] else {},
            solution=json.loads(d["solution"]) if d["solution"] else {},
            outcome=json.loads(d["outcome"]) if d["outcome"] else {},
            metadata=json.loads(d["metadata"]) if d["metadata"] else {},
            source_trace_ids=json.loads(d["source_trace_ids"]) if d["source_trace_ids"] else [],
            created_at=d["created_at"] or 0.0,
            updated_at=d["updated_at"] or 0.0,
        )

    # ── 统计信息 ──

    def get_stats(self) -> CollectionStats:
        """获取采集统计信息"""
        total = self.count_traces()
        success = self.count_traces(success=True)
        failure = self.count_traces(success=False)

        by_domain: Dict[str, int] = {}
        by_tool: Dict[str, int] = {}
        by_agent: Dict[str, int] = {}
        avg_duration = 0.0

        if total > 0:
            tool_rows = self._conn.execute(
                "SELECT tool_name, COUNT(*) as cnt FROM operation_traces GROUP BY tool_name ORDER BY cnt DESC LIMIT 20"
            ).fetchall()
            for r in tool_rows:
                if r[0]:
                    by_tool[r[0]] = r[1]

            agent_rows = self._conn.execute(
                "SELECT agent_id, COUNT(*) as cnt FROM operation_traces WHERE agent_id != '' GROUP BY agent_id ORDER BY cnt DESC LIMIT 20"
            ).fetchall()
            for r in agent_rows:
                if r[0]:
                    by_agent[r[0]] = r[1]

            avg_row = self._conn.execute(
                "SELECT AVG(duration_ms) FROM operation_traces WHERE duration_ms > 0"
            ).fetchone()
            avg_duration = avg_row[0] or 0.0

            domain_rows = self._conn.execute(
                "SELECT tool_name FROM operation_traces"
            ).fetchall()
            for r in domain_rows:
                domain = ExperienceEntry._infer_domain(r[0] or "").value
                by_domain[domain] = by_domain.get(domain, 0) + 1

        last_time_row = self._conn.execute(
            "SELECT MAX(timestamp) FROM operation_traces"
        ).fetchone()

        return CollectionStats(
            total_traces=total,
            success_count=success,
            failure_count=failure,
            total_experiences=self.count_experiences(),
            by_domain=by_domain,
            by_tool=by_tool,
            by_agent=by_agent,
            avg_duration_ms=avg_duration,
            last_collection_time=last_time_row[0] or 0.0,
        )

    # ── 清理与维护 ──

    def clean_old_traces(self, days: int = 90) -> int:
        """清理指定天数前的旧轨迹"""
        cutoff = time.time() - days * 86400
        cursor = self._conn.execute(
            "DELETE FROM operation_traces WHERE timestamp < ?",
            (cutoff,),
        )
        self._conn.commit()
        count = cursor.rowcount
        logger.info("清理旧轨迹: %d 条 (>%d天)", count, days)
        return count

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            logger.info("ExperienceStore 已关闭")


# 模块级默认实例
_default_store: Optional[ExperienceStore] = None


def get_experience_store() -> ExperienceStore:
    """获取默认经验存储实例（单例）"""
    global _default_store
    if _default_store is None:
        _default_store = ExperienceStore()
    return _default_store


__all__ = [
    "ExperienceStore",
    "get_experience_store",
]
