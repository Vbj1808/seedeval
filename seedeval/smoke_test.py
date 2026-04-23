from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import open_clip
import torch
from PIL import Image
from ulid import ULID

from seedeval.config import configure_logging, get_settings
from seedeval.db import (
    count_runs_created_on,
    get_conn,
    get_frames,
    get_run,
    init_db,
    insert_frames,
    insert_run,
)
from seedeval.models import Frame, Run
from seedeval.providers.aimlapi import AIMLAPISeedanceProvider
from seedeval.storage import extract_frames, get_video_duration_s

logger = logging.getLogger(__name__)

PROMPT = "A red panda eating bamboo in a snowy forest, cinematic lighting, slow motion"
MODEL = "bytedance/seedance-1-0-lite-t2v"
FRAME_COUNT = 8


def _new_run_id() -> str:
    return str(ULID())


def _compute_clip_embeddings(frame_paths: list[Path]) -> list[bytes]:
    logger.info("Loading CLIP ViT-B/32 on CPU")
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32",
        pretrained="openai",
        device="cpu",
    )
    model.eval()

    embeddings: list[bytes] = []
    with torch.no_grad():
        for idx, path in enumerate(frame_paths):
            logger.info("Embedding frame %s/%s", idx + 1, len(frame_paths))
            image = preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
            embedding = model.encode_image(image)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            vector = embedding.squeeze(0).cpu().numpy().astype("float32")
            embeddings.append(vector.tobytes())
    return embeddings


async def main() -> None:
    configure_logging()
    settings = get_settings()
    run_id = _new_run_id()
    created_at = datetime.now(timezone.utc)

    with get_conn(settings.db_path) as conn:
        init_db(conn)
        runs_today = count_runs_created_on(conn, created_at.date().isoformat())
    if runs_today >= settings.max_runs_per_day:
        raise RuntimeError(
            f"SEEDEVAL_MAX_RUNS_PER_DAY={settings.max_runs_per_day} reached for "
            f"{created_at.date().isoformat()}"
        )

    provider = AIMLAPISeedanceProvider(run_id=run_id)
    generated = await provider.generate_video(PROMPT, MODEL, duration_s=5)

    extracted = extract_frames(generated.video_path, run_id, count=FRAME_COUNT)
    frame_paths = [path for _, _, path in extracted]
    embeddings = _compute_clip_embeddings(frame_paths)

    run = Run(
        id=run_id,
        created_at=created_at,
        prompt=PROMPT,
        model=generated.model_used,
        video_path=generated.video_path,
        status="done",
        total_cost_usd=generated.cost_usd,
        total_latency_s=generated.latency_s,
        raw_config={"prompt": PROMPT, "model": MODEL, "duration_s": 5},
    )
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

    with get_conn(settings.db_path) as conn:
        init_db(conn)
        insert_run(conn, run)
        insert_frames(conn, frames)
        conn.commit()
        db_run = get_run(conn, run_id)
        db_frames = get_frames(conn, run_id)

    if db_run is None:
        raise RuntimeError(f"Run {run_id} was not written to the database")

    video_size_mb = generated.video_path.stat().st_size / (1024 * 1024)
    duration_s = get_video_duration_s(generated.video_path)
    embedding_dim = len(embeddings[0]) // 4 if embeddings else 0

    print()
    print("=== SeedEval Smoke Test ===")
    print(f"Run ID: {run_id}")
    print(f"Model: {generated.model_used}")
    print(f"Video: {generated.video_path} ({duration_s:.1f}s, {video_size_mb:.1f} MB)")
    print(f"Latency: {generated.latency_s:.1f}s")
    print(f"Cost: ${generated.cost_usd:.2f}")
    print(f"Frames: {len(extracted)} extracted, {len(embeddings)} embedded (dim={embedding_dim})")
    print(f"DB: wrote 1 run + {len(db_frames)} frames to {settings.db_path}")
    print("=== OK ===")


if __name__ == "__main__":
    asyncio.run(main())
