from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from statistics import mean

from seedeval.agents.vlm_judge import judge_frame, reset_active_run_id, set_active_run_id
from seedeval.checks.base import Check
from seedeval.db import (
    delete_check_rows,
    get_frames,
    get_run,
    insert_check_result,
    insert_frame_critiques,
)
from seedeval.models import CheckResult, FrameCritique


def _build_adherence_prompt(prompt: str, idx: int, timestamp_s: float) -> str:
    return f"""Original prompt: "{prompt}"

This is frame {idx + 1} of 8, taken at {timestamp_s:.2f}s.

Rate 0-10 on each dimension:
- subject_presence: Is the subject described in the prompt visible?
- setting_match:   Does the environment match what was described?
- action_match:    Is the action/motion consistent with the prompt?
- style_match:     Does the visual style match the prompt (e.g., "cinematic")?

Also return:
- overall: 0-10 integer
- one_sentence_reason: plain English, under 25 words
- flagged: true/false (true if any dimension <= 4)

Return JSON with EXACTLY these keys and no others:
{{
  "subject_presence": <int>,
  "setting_match": <int>,
  "action_match": <int>,
  "style_match": <int>,
  "overall": <int>,
  "one_sentence_reason": "<str>",
  "flagged": <bool>
}}"""


class AdherenceCheck(Check):
    name = "adherence"

    async def run(self, run_id: str, conn: sqlite3.Connection) -> CheckResult:
        run_row = get_run(conn, run_id)
        if run_row is None:
            raise RuntimeError(f"Run {run_id} not found")
        frame_rows = get_frames(conn, run_id)
        if len(frame_rows) != 8:
            raise RuntimeError(f"Expected 8 frames for run {run_id}, found {len(frame_rows)}")

        delete_check_rows(conn, run_id, self.name)
        conn.commit()

        token = set_active_run_id(run_id)
        try:
            responses = await asyncio.gather(
                *[
                    judge_frame(
                        frame_path=row["image_path"],
                        prompt=run_row["prompt"],
                        prompt_text=_build_adherence_prompt(
                            run_row["prompt"],
                            row["idx"],
                            row["timestamp_s"],
                        ),
                    )
                    for row in frame_rows
                ]
            )
        finally:
            reset_active_run_id(token)

        frame_critiques = []
        overall_scores: list[int] = []
        subject_scores: list[int] = []
        setting_scores: list[int] = []
        action_scores: list[int] = []
        style_scores: list[int] = []
        per_frame: list[dict[str, object]] = []

        for row, response in zip(frame_rows, responses, strict=True):
            overall = int(response.get("overall", response.get("score", 0)) or 0)
            subject = int(response.get("subject_presence", 0) or 0)
            setting = int(response.get("setting_match", 0) or 0)
            action = int(response.get("action_match", 0) or 0)
            style = int(response.get("style_match", 0) or 0)
            flagged = bool(response.get("flagged", True))
            reason = str(response.get("one_sentence_reason", response.get("error", "parse_failed")))

            overall_scores.append(overall)
            subject_scores.append(subject)
            setting_scores.append(setting)
            action_scores.append(action)
            style_scores.append(style)
            frame_critiques.append(
                FrameCritique(
                    frame_id=row["id"],
                    check_name=self.name,
                    score=overall,
                    flagged=flagged,
                    reason=reason,
                )
            )
            per_frame.append(
                {
                    "frame_id": row["id"],
                    "frame_idx": row["idx"],
                    "timestamp_s": row["timestamp_s"],
                    "image_path": row["image_path"],
                    "subject_presence": subject,
                    "setting_match": setting,
                    "action_match": action,
                    "style_match": style,
                    "overall": overall,
                    "flagged": flagged,
                    "one_sentence_reason": reason,
                }
            )

        trimmed_scores = sorted(overall_scores)
        trimmed_mean = mean(trimmed_scores[1:-1]) if len(trimmed_scores) > 2 else mean(trimmed_scores)
        result = CheckResult(
            run_id=run_id,
            check_name=self.name,
            score=float(trimmed_mean),
            passed=float(trimmed_mean) >= 6,
            details={
                "subject_presence": mean(subject_scores),
                "setting_match": mean(setting_scores),
                "action_match": mean(action_scores),
                "style_match": mean(style_scores),
                "per_frame": per_frame,
                "trimmed_mean_source_scores": trimmed_scores[1:-1]
                if len(trimmed_scores) > 2
                else trimmed_scores,
            },
            created_at=datetime.now(timezone.utc),
        )

        insert_frame_critiques(conn, frame_critiques)
        insert_check_result(conn, result)
        conn.commit()
        return result
