from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from ulid import ULID

from seedeval.agents.orchestrator import (
    get_plan_cost,
    plan_run,
    reset_active_run_id,
    set_active_run_id,
    synthesize_verdict,
)
from seedeval.agents.vlm_judge import get_run_seed18_cost
from seedeval.api.sse import clear_run_events, publish_event
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


def _ensure_run_columns(conn) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "verdict" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN verdict TEXT")
        conn.commit()


def create_queued_run(prompt: str, model: str = DEFAULT_MODEL) -> str:
    settings = get_settings()
    created_at = datetime.now(timezone.utc)
    run_id = new_run_id()

    with get_conn(settings.db_path) as conn:
        init_db(conn)
        _ensure_run_columns(conn)
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


def _cost_score(total_cost_usd: float) -> float:
    return max(0.0, 10.0 - (total_cost_usd / 0.05))


async def execute_run(run_id: str) -> None:
    started_at = datetime.now(timezone.utc)
    clear_run_events(run_id)
    with get_conn() as conn:
        init_db(conn)
        _ensure_run_columns(conn)
        run_row = get_run(conn, run_id)
        if run_row is None:
            raise RuntimeError(f"Run {run_id} not found")
        prompt = run_row["prompt"]
        model = run_row["model"]
        raw_config = json.loads(run_row["raw_config"]) if run_row["raw_config"] else {}
        await publish_event(run_id, {"stage": "planning", "message": "Classifying prompt..."})
        token = set_active_run_id(run_id)
        try:
            plan = await plan_run(prompt, model)
        finally:
            reset_active_run_id(token)
        raw_config["plan"] = plan
        update_run_fields(conn, run_id, raw_config=raw_config, status="generating")
        conn.commit()
        await publish_event(run_id, {"stage": "plan_complete", "plan": plan})
        await publish_event(run_id, {"stage": "generating", "message": "Generating video via Seedance..."})

    try:
        provider = AIMLAPISeedanceProvider(run_id=run_id)
        generated = await provider.generate_video(prompt, model, duration_s=5)
        await publish_event(
            run_id,
            {
                "stage": "generation_complete",
                "latency_s": generated.latency_s,
                "cost_usd": generated.cost_usd,
            },
        )

        await publish_event(run_id, {"stage": "extracting_frames", "message": "Extracting 8 frames..."})
        extracted = extract_frames(generated.video_path, run_id, count=FRAME_COUNT)
        await publish_event(run_id, {"stage": "frames_complete", "count": len(extracted)})
        embeddings = compute_clip_embeddings([path for _, _, path in extracted])
        await publish_event(run_id, {"stage": "embedding_complete"})
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
            _ensure_run_columns(conn)
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

            await publish_event(run_id, {"stage": "check_started", "check": "temporal"})
            temporal_result = await TemporalCheck(
                drift_threshold=float(plan.get("temporal_drift_threshold", 0.7))
            ).run(run_id, conn)
            await publish_event(
                run_id,
                {"stage": "check_complete", "check": "temporal", "score": temporal_result.score},
            )
            await publish_event(run_id, {"stage": "check_started", "check": "adherence"})
            adherence_result = await AdherenceCheck(frame_callback=lambda e: publish_event(run_id, e)).run(run_id, conn)
            await publish_event(
                run_id,
                {"stage": "check_complete", "check": "adherence", "score": adherence_result.score},
            )

            flagged_frames = [
                frame
                for frame in adherence_result.details.get("per_frame", [])
                if frame.get("flagged")
            ][:3]
            projected_total_cost_usd = (
                generated.cost_usd
                + get_run_seed18_cost(run_id)
                + get_plan_cost(run_id)
                + 0.001
            )
            pre_cost_overall = _compute_overall_score(
                {
                    "adherence": float(adherence_result.score or 0.0),
                    "temporal": float(temporal_result.score or 0.0),
                    "cost": _cost_score(projected_total_cost_usd),
                }
            )
            verdict_payload = {
                "prompt": prompt,
                "model": model,
                "overall_score": pre_cost_overall,
                "check_results": {
                    "adherence": adherence_result.details,
                    "temporal": temporal_result.details,
                    "cost": {
                        "seedance_cost_usd": generated.cost_usd,
                        "total_latency_s": generated.latency_s,
                    },
                },
                "flagged_frames": flagged_frames,
            }
            await publish_event(run_id, {"stage": "synthesizing", "message": "Writing verdict..."})
            token = set_active_run_id(run_id)
            try:
                verdict = await synthesize_verdict(verdict_payload)
            finally:
                reset_active_run_id(token)
            total_latency_s = (datetime.now(timezone.utc) - started_at).total_seconds()
            update_run_fields(conn, run_id, total_latency_s=total_latency_s, verdict=verdict)
            conn.commit()

            await publish_event(run_id, {"stage": "check_started", "check": "cost"})
            cost_result = await CostCheck().run(run_id, conn)
            await publish_event(
                run_id,
                {"stage": "check_complete", "check": "cost", "score": cost_result.score},
            )
            overall_score = _compute_overall_score(
                {
                    "adherence": float(adherence_result.score or 0.0),
                    "temporal": float(temporal_result.score or 0.0),
                    "cost": float(cost_result.score or 0.0),
                }
            )
            update_run_fields(conn, run_id, overall_score=overall_score, status="done")
            conn.commit()
            await publish_event(
                run_id,
                {"stage": "done", "overall_score": overall_score, "verdict": verdict},
            )
    except Exception:
        logger.exception("Run %s failed", run_id)
        with get_conn() as conn:
            init_db(conn)
            _ensure_run_columns(conn)
            update_run_fields(conn, run_id, status="failed")
            conn.commit()
        await publish_event(run_id, {"stage": "done", "overall_score": None, "verdict": "Run failed."})
        raise


async def run_full_eval(prompt: str, model: str = DEFAULT_MODEL) -> str:
    run_id = create_queued_run(prompt, model)
    await execute_run(run_id)
    return run_id
