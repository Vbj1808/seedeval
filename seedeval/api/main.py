from __future__ import annotations

import json
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from seedeval.api.sse import event_stream
from seedeval.config import configure_logging
from seedeval.pipeline import DEFAULT_MODEL, _ensure_run_columns, create_queued_run, execute_run
from seedeval.db import (
    get_check_results,
    get_conn,
    get_frame_critiques,
    get_run,
    init_db,
    list_runs,
    serialize_check_result_row,
    serialize_frame_critique_row,
)
from seedeval.config import get_settings

configure_logging()

app = FastAPI(title="SeedEval API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount(
    "/artifacts",
    StaticFiles(directory=str(Path(get_settings().artifacts_dir))),
    name="artifacts",
)


class CreateRunRequest(BaseModel):
    prompt: str
    model: str = DEFAULT_MODEL


@app.post("/runs")
async def create_run(request: CreateRunRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    run_id = create_queued_run(request.prompt, request.model)
    background_tasks.add_task(execute_run, run_id)
    return {"run_id": run_id, "status": "queued"}


@app.get("/runs")
async def get_runs() -> list[dict]:
    with get_conn() as conn:
        init_db(conn)
        _ensure_run_columns(conn)
        return [dict(row) for row in list_runs(conn, limit=50)]


@app.get("/runs/{run_id}")
async def get_run_detail(run_id: str) -> dict:
    with get_conn() as conn:
        init_db(conn)
        _ensure_run_columns(conn)
        run_row = get_run(conn, run_id)
        if run_row is None:
            raise HTTPException(status_code=404, detail="Run not found")

        return {
            "id": run_row["id"],
            "created_at": run_row["created_at"],
            "prompt": run_row["prompt"],
            "model": run_row["model"],
            "video_path": run_row["video_path"],
            "status": run_row["status"],
            "total_cost_usd": run_row["total_cost_usd"],
            "total_latency_s": run_row["total_latency_s"],
            "overall_score": run_row["overall_score"],
            "verdict": run_row["verdict"],
            "raw_config": json.loads(run_row["raw_config"]) if run_row["raw_config"] else {},
            "check_results": [
                serialize_check_result_row(row)
                for row in get_check_results(conn, run_id)
            ],
            "frame_critiques": [
                serialize_frame_critique_row(row)
                for row in get_frame_critiques(conn, run_id)
            ],
        }


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: str) -> EventSourceResponse:
    return EventSourceResponse(event_stream(run_id))
