import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

INIT_SQL = """
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    window TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    toothbrush_grade TEXT,
    facewash_grade TEXT,
    toothbrush_seconds INTEGER DEFAULT 0,
    facewash_seconds INTEGER DEFAULT 0,
    rinse_detected INTEGER DEFAULT 0,
    summary_text TEXT,
    evidence_frame_path TEXT,
    evidence_clip_path TEXT,
    status TEXT NOT NULL DEFAULT 'success',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    message TEXT,
    level TEXT NOT NULL DEFAULT 'info',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_results_date ON analysis_results(date);
CREATE INDEX IF NOT EXISTS idx_results_window ON analysis_results(window);
CREATE INDEX IF NOT EXISTS idx_events_created ON system_events(created_at);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(INIT_SQL)
            conn.commit()
        logger.info("Database initialized: %s", self.db_path)

    def insert_result(
        self,
        date: str,
        window: str,
        start_time: str,
        end_time: str,
        status: str = "success",
        toothbrush_grade: Optional[str] = None,
        facewash_grade: Optional[str] = None,
        toothbrush_seconds: int = 0,
        facewash_seconds: int = 0,
        rinse_detected: bool = False,
        summary_text: Optional[str] = None,
        evidence_frame_path: Optional[str] = None,
        evidence_clip_path: Optional[str] = None,
    ) -> int:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_results
                (date, window, start_time, end_time, status,
                 toothbrush_grade, facewash_grade, toothbrush_seconds,
                 facewash_seconds, rinse_detected, summary_text,
                 evidence_frame_path, evidence_clip_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    date, window, start_time, end_time, status,
                    toothbrush_grade, facewash_grade, toothbrush_seconds,
                    facewash_seconds, int(rinse_detected), summary_text,
                    evidence_frame_path, evidence_clip_path, now,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def has_result_for_window(self, date: str, window: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM analysis_results
                WHERE date = ? AND window = ?
                LIMIT 1
                """,
                (date, window),
            ).fetchone()
            return row is not None

    def insert_event(self, event_type: str, message: str, level: str = "info"):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO system_events (event_type, message, level, created_at) VALUES (?, ?, ?, ?)",
                (event_type, message, level, now),
            )
            conn.commit()
