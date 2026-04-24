from __future__ import annotations

import logging
from datetime import datetime, timezone

from ulid import ULID

from seedeval.checks import AdherenceCheck, CostCheck, TemporalCheck
from seedeval.config import get_settings
from seedeval.db import (
    count_runs_created_on,
    get_conn,
    get_run,
    init_db,
    insert_frames,
    insert_run,
    update_run_fields,
)
from seedeval.models import Frame, Run
from seedeval.providers.aimlapi import AIMLAPISeedanceProvider
from seedeval.storage import compute_clip_embeddings, extract_frames

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "bytedance/seedance-1-0-lite-t2v"
FRAME_COUNT = 8


def new_run_id() -> str:
    return str(ULID())


def create_queued_run(prompt: str, model: str = DEFAULT_MODEL) -> str:
    settings = get_settings()
    created_at = datetime.now(timezone.utc)
    run_id = new_run_id()

    with get_conn(settings.db_path) as conn:
        init_db(conn)
        runs_today = count_runs_created_on(conn, created_at.date().isoformat())
        if runs_today >= settings.max_runs_per_day:
            raise RuntimeError(
                f"SEEDEVAL_MAX_RUNS_PER_DAY={settings.max_runs_per_day} reached for "
                f"{created_at.date().isoformat()}"
            )
        insert_run(
            conn,
            Run(
                id=run_id,
                created_at=created_at,
                prompt=prompt,
                model=model,
                status="queued",
                raw_config={"prompt": prompt, "model": model, "duration_s": 5},
            ),
        )
        conn.commit()
    return run_id


def _compute_overall_score(check_scores: dict[str, float]) -> float:
    weights = {
        "adherence": 0.40,
        "temporal": 0.25,
        "cost": 0.10,
    }
    active_weights = {name: weight for name, weight in weights.items() if name in check_scores}
    total_weight = sum(active_weights.values())
    if total_weight == 0:
        return 0.0
    return sum(check_scores[name] * (weight / total_weight) for name, weight in active_weights.items())


async def execute_run(run_id: str) -> None:
    started_at = datetime.now(timezone.utc)
    with get_conn() as conn:
        init_db(conn)
        run_row = get_run(conn, run_id)
        if run_row is None:
            raise RuntimeError(f"Run {run_id} not found")
        prompt = run_row["prompt"]
        model = run_row["model"]
        update_run_fields(conn, run_id, status="generating")
        conn.commit()

    try:
        provider = AIMLAPISeedanceProvider(run_id=run_id)
        generated = await provider.generate_video(prompt, model, duration_s=5)

        extracted = extract_frames(generated.video_path, run_id, count=FRAME_COUNT)
        embeddings = compute_clip_embeddings([path for _, _, path in extracted])
        frames = [
            Frame(
                run_id=run_id,
                idx=idx,
                timestamp_s=timestamp_s,
                image_path=path,
                embedding=embedding,
            )
            for (idx, timestamp_s, path), embedding in zip(extracted, embeddings, strict=True)
        ]

        with get_conn() as conn:
            init_db(conn)
            update_run_fields(
                conn,
                run_id,
                status="evaluating",
                video_path=generated.video_path,
                total_cost_usd=generated.cost_usd,
                total_latency_s=generated.latency_s,
            )
            insert_frames(conn, frames)
            conn.commit()

            temporal_result = await TemporalCheck().run(run_id, conn)
            adherence_result = await AdherenceCheck().run(run_id, conn)

            total_latency_s = (datetime.now(timezone.utc) - started_at).total_seconds()
            update_run_fields(conn, run_id, total_latency_s=total_latency_s)
            conn.commit()

            cost_result = await CostCheck().run(run_id, conn)
            overall_score = _compute_overall_score(
                {
                    "adherence": float(adherence_result.score or 0.0),
                    "temporal": float(temporal_result.score or 0.0),
                    "cost": float(cost_result.score or 0.0),
                }
            )
            update_run_fields(conn, run_id, overall_score=overall_score, status="done")
            conn.commit()
    except Exception:
        logger.exception("Run %s failed", run_id)
        with get_conn() as conn:
            init_db(conn)
            update_run_fields(conn, run_id, status="failed")
            conn.commit()
        raise


async def run_full_eval(prompt: str, model: str = DEFAULT_MODEL) -> str:
    run_id = create_queued_run(prompt, model)
    await execute_run(run_id)
    return run_id
