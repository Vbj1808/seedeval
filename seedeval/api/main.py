from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from seedeval.config import configure_logging
from seedeval.db import (
    get_check_results,
    get_conn,
    get_frame_critiques,
    get_run,
    init_db,
    list_runs,
    serialize_check_result_row,
    serialize_frame_critique_row,
    serialize_run_row,
)
from seedeval.pipeline import DEFAULT_MODEL, create_queued_run, execute_run

configure_logging()

app = FastAPI(title="SeedEval API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        return [dict(row) for row in list_runs(conn, limit=50)]


@app.get("/runs/{run_id}")
async def get_run_detail(run_id: str) -> dict:
    with get_conn() as conn:
        init_db(conn)
        run_row = get_run(conn, run_id)
        if run_row is None:
            raise HTTPException(status_code=404, detail="Run not found")

        return {
            **serialize_run_row(run_row),
            "check_results": [
                serialize_check_result_row(row)
                for row in get_check_results(conn, run_id)
            ],
            "frame_critiques": [
                serialize_frame_critique_row(row)
                for row in get_frame_critiques(conn, run_id)
            ],
        }
