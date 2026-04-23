from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GeneratedVideo(BaseModel):
    video_path: Path
    latency_s: float
    cost_usd: float
    provider_raw_response: dict[str, Any]
    model_used: str


class Run(BaseModel):
    id: str
    created_at: datetime
    prompt: str
    model: str
    video_path: Path | None = None
    status: str
    total_cost_usd: float = 0
    total_latency_s: float = 0
    overall_score: float | None = None
    raw_config: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class Frame(BaseModel):
    id: int | None = None
    run_id: str
    idx: int
    timestamp_s: float
    image_path: Path
    embedding: bytes | None = None

    model_config = ConfigDict(from_attributes=True)


class CheckResult(BaseModel):
    id: int | None = None
    run_id: str
    check_name: str
    score: float | None = None
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FrameCritique(BaseModel):
    id: int | None = None
    frame_id: int
    check_name: str
    score: float | None = None
    flagged: bool | None = None
    reason: str | None = None

    model_config = ConfigDict(from_attributes=True)
