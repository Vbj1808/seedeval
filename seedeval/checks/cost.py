from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from seedeval.agents.orchestrator import reset_run_costs
from seedeval.agents.vlm_judge import get_run_seed18_call_count, reset_run_seed18_cost
from seedeval.checks.base import Check
from seedeval.db import delete_check_rows, get_run, insert_check_result, update_run_fields
from seedeval.models import CheckResult


class CostCheck(Check):
    name = "cost"

    async def run(self, run_id: str, conn: sqlite3.Connection) -> CheckResult:
        run_row = get_run(conn, run_id)
        if run_row is None:
            raise RuntimeError(f"Run {run_id} not found")

        base_cost = float(run_row["total_cost_usd"] or 0.0)
        latency_s = float(run_row["total_latency_s"] or 0.0)
        seed18_call_count = get_run_seed18_call_count(run_id)
        seed18_cost = reset_run_seed18_cost(run_id)
        plan_seed18_cost_usd, verdict_seed18_cost_usd = reset_run_costs(run_id)
        total_cost = base_cost + seed18_cost + plan_seed18_cost_usd + verdict_seed18_cost_usd
        score = max(0.0, 10.0 - (total_cost / 0.05))

        result = CheckResult(
            run_id=run_id,
            check_name=self.name,
            score=score,
            passed=True,
            details={
                "seedance_cost_usd": base_cost,
                "seed18_cost_usd": seed18_cost,
                "seed18_call_count": seed18_call_count,
                "plan_seed18_cost_usd": plan_seed18_cost_usd,
                "verdict_seed18_cost_usd": verdict_seed18_cost_usd,
                "total_cost_usd": total_cost,
                "total_latency_s": latency_s,
                "zero_score_cost_usd": 0.50,
            },
            created_at=datetime.now(timezone.utc),
        )

        update_run_fields(conn, run_id, total_cost_usd=total_cost)
        delete_check_rows(conn, run_id, self.name)
        insert_check_result(conn, result)
        conn.commit()
        return result
