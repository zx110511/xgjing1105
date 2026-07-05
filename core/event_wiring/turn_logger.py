import sqlite3
import uuid
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TurnLogger:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / ".memory" / "turn_log.db"
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE,
                session_id TEXT,
                turn_no INTEGER,
                user_input TEXT,
                agent_response TEXT,
                tool_calls TEXT,
                created_at REAL
            )
        """)
        self._conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts
            USING fts5(user_input, agent_response, content=turns, content_rowid=rowid)
        """)
        self._conn.execute("""
            CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON turns BEGIN
                INSERT INTO turns_fts(rowid, user_input, agent_response)
                VALUES (new.rowid, new.user_input, new.agent_response);
            END
        """)
        self._conn.execute("""
            CREATE TRIGGER IF NOT EXISTS turns_ad AFTER DELETE ON turns BEGIN
                INSERT INTO turns_fts(turns_fts, rowid, user_input, agent_response)
                VALUES ('delete', old.rowid, old.user_input, old.agent_response);
            END
        """)
        self._conn.execute("""
            CREATE TRIGGER IF NOT EXISTS turns_au AFTER UPDATE ON turns BEGIN
                INSERT INTO turns_fts(turns_fts, rowid, user_input, agent_response)
                VALUES ('delete', old.rowid, old.user_input, old.agent_response);
                INSERT INTO turns_fts(rowid, user_input, agent_response)
                VALUES (new.rowid, new.user_input, new.agent_response);
            END
        """)
        self._conn.commit()
        logger.info("TurnLogger 初始化完成 db=%s", db_path)

    def log(self, session_id, turn_no, user_input, agent_response, tool_calls=None):
        self._conn.execute(
            "INSERT INTO turns (id, session_id, turn_no, user_input, agent_response, tool_calls, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, session_id, turn_no,
             user_input, agent_response,
             str(tool_calls) if tool_calls else "[]",
             time.time())
        )
        self._conn.commit()

    def search(self, keyword, limit=10):
        rows = self._conn.execute(
            "SELECT snippet(turns_fts, 1, '<mark>', '</mark>', '...', 40) "
            "FROM turns_fts WHERE turns_fts MATCH ? LIMIT ?",
            (keyword, limit)
        ).fetchall()
        return [r[0] for r in rows]

    def count(self):
        return self._conn.execute("SELECT count(*) FROM turns").fetchone()[0]
