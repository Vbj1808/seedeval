from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import numpy as np

from seedeval.checks.base import Check
from seedeval.db import delete_check_rows, get_frames, insert_check_result
from seedeval.models import CheckResult


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class TemporalCheck(Check):
    name = "temporal"

    async def run(self, run_id: str, conn: sqlite3.Connection) -> CheckResult:
        frame_rows = get_frames(conn, run_id)
        if not frame_rows:
            raise RuntimeError(f"No frames found for run {run_id}")

        embeddings = [
            np.frombuffer(row["embedding"], dtype=np.float32)
            for row in frame_rows
            if row["embedding"] is not None
        ]
        if len(embeddings) != len(frame_rows):
            raise RuntimeError(f"Missing embeddings for run {run_id}")

        smoothness = [
            _cosine_similarity(embeddings[idx], embeddings[idx + 1])
            for idx in range(len(embeddings) - 1)
        ]
        drift = [
            _cosine_similarity(embeddings[idx], embeddings[0])
            for idx in range(len(embeddings))
        ]

        smooth_mean = float(np.mean(smoothness)) if smoothness else 0.0
        smooth_std = float(np.std(smoothness)) if smoothness else 0.0
        smooth_threshold = smooth_mean - (2 * smooth_std)

        flagged_smooth_indices = [
            idx for idx, value in enumerate(smoothness) if value < smooth_threshold
        ]
        flagged_drift_indices = [
            idx for idx, value in enumerate(drift) if value < 0.7
        ]

        raw_score = 10 * (1 - ((len(flagged_smooth_indices) + len(flagged_drift_indices)) / 16))
        score = max(0.0, min(10.0, raw_score))

        result = CheckResult(
            run_id=run_id,
            check_name=self.name,
            score=score,
            passed=score >= 7,
            details={
                "smoothness": smoothness,
                "drift": drift,
                "flagged_smooth_indices": flagged_smooth_indices,
                "flagged_drift_indices": flagged_drift_indices,
                "smoothness_mean": smooth_mean,
                "smoothness_stdev": smooth_std,
                "drift_threshold": 0.7,
            },
            created_at=datetime.now(timezone.utc),
        )

        delete_check_rows(conn, run_id, self.name)
        insert_check_result(conn, result)
        conn.commit()
        return result
