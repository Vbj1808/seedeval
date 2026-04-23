from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from seedeval.config import get_settings
from seedeval.models import Frame, Run


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
  id              TEXT PRIMARY KEY,
  created_at      TEXT NOT NULL,
  prompt          TEXT NOT NULL,
  model           TEXT NOT NULL,
  video_path      TEXT,
  status          TEXT NOT NULL,
  total_cost_usd  REAL DEFAULT 0,
  total_latency_s REAL DEFAULT 0,
  overall_score   REAL,
  raw_config      TEXT
);

CREATE TABLE IF NOT EXISTS frames (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id      TEXT NOT NULL REFERENCES runs(id),
  idx         INTEGER NOT NULL,
  timestamp_s REAL NOT NULL,
  image_path  TEXT NOT NULL,
  embedding   BLOB
);

CREATE TABLE IF NOT EXISTS check_results (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id      TEXT NOT NULL REFERENCES runs(id),
  check_name  TEXT NOT NULL,
  score       REAL,
  passed      INTEGER,
  details     TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS frame_critiques (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  frame_id    INTEGER NOT NULL REFERENCES frames(id),
  check_name  TEXT NOT NULL,
  score       REAL,
  flagged     INTEGER,
  reason      TEXT
);

CREATE INDEX IF NOT EXISTS idx_frames_run ON frames(run_id);
CREATE INDEX IF NOT EXISTS idx_check_run ON check_results(run_id);
CREATE INDEX IF NOT EXISTS idx_critique_frame ON frame_critiques(frame_id);
"""


def get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    owns_conn = conn is None
    active_conn = conn or get_conn()
    try:
        active_conn.executescript(SCHEMA_SQL)
        active_conn.commit()
    finally:
        if owns_conn:
            active_conn.close()


def insert_run(conn: sqlite3.Connection, run: Run) -> None:
    conn.execute(
        """
        INSERT INTO runs (
            id, created_at, prompt, model, video_path, status,
            total_cost_usd, total_latency_s, overall_score, raw_config
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run.id,
            run.created_at.isoformat(),
            run.prompt,
            run.model,
            str(run.video_path) if run.video_path else None,
            run.status,
            run.total_cost_usd,
            run.total_latency_s,
            run.overall_score,
            json.dumps(run.raw_config),
        ),
    )


def insert_frames(conn: sqlite3.Connection, frames: Iterable[Frame]) -> None:
    conn.executemany(
        """
        INSERT INTO frames (run_id, idx, timestamp_s, image_path, embedding)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                frame.run_id,
                frame.idx,
                frame.timestamp_s,
                str(frame.image_path),
                frame.embedding,
            )
            for frame in frames
        ],
    )


def get_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def get_frames(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM frames WHERE run_id = ? ORDER BY idx ASC",
            (run_id,),
        ).fetchall()
    )


def count_runs_created_on(conn: sqlite3.Connection, day_prefix: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM runs WHERE created_at LIKE ?",
        (f"{day_prefix}%",),
    ).fetchone()
    return int(row["count"])
