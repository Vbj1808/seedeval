from __future__ import annotations

import asyncio
import sqlite3

import seedeval.agents.vlm_judge as vlm_judge
from seedeval.checks.cost import CostCheck
from seedeval.checks.temporal import TemporalCheck

FIXTURE_RUN_ID = "01KPXHW421VH1NGAYZ8PC580YA"


def test_temporal_check_with_fixture():
    """Temporal check must produce a score 0-10 for the Day 1 fixture run."""
    conn = sqlite3.connect("seedeval.db")
    conn.row_factory = sqlite3.Row
    result = asyncio.run(TemporalCheck().run(FIXTURE_RUN_ID, conn))
    assert result.check_name == "temporal"
    assert result.score is not None
    assert 0 <= result.score <= 10


def test_cost_check_with_fixture():
    """Cost check must read from existing run and return a score."""
    conn = sqlite3.connect("seedeval.db")
    conn.row_factory = sqlite3.Row
    result = asyncio.run(CostCheck().run(FIXTURE_RUN_ID, conn))
    assert result.check_name == "cost"
    assert result.score is not None
    assert 0 <= result.score <= 10


def test_adherence_parses_json_with_prose_wrapping():
    """If Seed 1.8 wraps JSON in prose, our parser must still extract it."""
    raw = 'Here is the JSON you asked for: {"overall": 7, "flagged": false} Thanks.'
    parsed = vlm_judge._extract_json_payload(raw)
    assert parsed["overall"] == 7
    assert parsed["flagged"] is False
