from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from seedeval.config import get_settings
from seedeval.models import CheckResult, Frame, FrameCritique, Run


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


def update_run_fields(conn: sqlite3.Connection, run_id: str, **fields: Any) -> None:
    if not fields:
        return

    assignments: list[str] = []
    values: list[Any] = []
    for column, value in fields.items():
        assignments.append(f"{column} = ?")
        if isinstance(value, Path):
            values.append(str(value))
        elif isinstance(value, dict):
            values.append(json.dumps(value))
        else:
            values.append(value)
    values.append(run_id)

    conn.execute(
        f"UPDATE runs SET {', '.join(assignments)} WHERE id = ?",
        values,
    )


def get_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def list_runs(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT id, prompt, model, status, overall_score, total_cost_usd, created_at
            FROM runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    )


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


def delete_check_rows(conn: sqlite3.Connection, run_id: str, check_name: str) -> None:
    conn.execute(
        "DELETE FROM check_results WHERE run_id = ? AND check_name = ?",
        (run_id, check_name),
    )
    conn.execute(
        """
        DELETE FROM frame_critiques
        WHERE check_name = ?
          AND frame_id IN (SELECT id FROM frames WHERE run_id = ?)
        """,
        (check_name, run_id),
    )


def insert_check_result(conn: sqlite3.Connection, result: CheckResult) -> int:
    cursor = conn.execute(
        """
        INSERT INTO check_results (run_id, check_name, score, passed, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            result.run_id,
            result.check_name,
            result.score,
            None if result.passed is None else int(result.passed),
            json.dumps(result.details),
            result.created_at.isoformat(),
        ),
    )
    return int(cursor.lastrowid)


def insert_frame_critiques(conn: sqlite3.Connection, critiques: Iterable[FrameCritique]) -> None:
    conn.executemany(
        """
        INSERT INTO frame_critiques (frame_id, check_name, score, flagged, reason)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                critique.frame_id,
                critique.check_name,
                critique.score,
                None if critique.flagged is None else int(critique.flagged),
                critique.reason,
            )
            for critique in critiques
        ],
    )


def get_check_results(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT *
            FROM check_results
            WHERE run_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (run_id,),
        ).fetchall()
    )


def get_frame_critiques(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT fc.id, fc.frame_id, fc.check_name, fc.score, fc.flagged, fc.reason,
                   f.idx AS frame_idx, f.timestamp_s, f.image_path
            FROM frame_critiques fc
            JOIN frames f ON f.id = fc.frame_id
            WHERE f.run_id = ?
            ORDER BY f.idx ASC, fc.id ASC
            """,
            (run_id,),
        ).fetchall()
    )


def serialize_run_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "prompt": row["prompt"],
        "model": row["model"],
        "video_path": row["video_path"],
        "status": row["status"],
        "total_cost_usd": row["total_cost_usd"],
        "total_latency_s": row["total_latency_s"],
        "overall_score": row["overall_score"],
        "raw_config": json.loads(row["raw_config"]) if row["raw_config"] else {},
    }


def serialize_check_result_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "check_name": row["check_name"],
        "score": row["score"],
        "passed": None if row["passed"] is None else bool(row["passed"]),
        "details": json.loads(row["details"]),
        "created_at": row["created_at"],
    }


def serialize_frame_critique_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "frame_id": row["frame_id"],
        "check_name": row["check_name"],
        "score": row["score"],
        "flagged": None if row["flagged"] is None else bool(row["flagged"]),
        "reason": row["reason"],
        "frame_idx": row["frame_idx"],
        "timestamp_s": row["timestamp_s"],
        "image_path": row["image_path"],
    }
