from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg

from seedeval.config import get_settings

logger = logging.getLogger(__name__)


def run_dir(run_id: str) -> Path:
    path = get_settings().artifacts_dir / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def video_path(run_id: str) -> Path:
    return run_dir(run_id) / "video.mp4"


def frames_dir(run_id: str) -> Path:
    path = run_dir(run_id) / "frames"
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_video_to_artifacts(source: Path, run_id: str) -> Path:
    destination = video_path(run_id)
    shutil.copyfile(source, destination)
    return destination


def get_video_duration_s(path: Path) -> float:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ffmpeg, "-i", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not match:
        raise RuntimeError(f"Could not read video duration from {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def evenly_spaced_timestamps(duration_s: float, count: int) -> list[float]:
    if count <= 0:
        raise ValueError("count must be positive")
    if count == 1:
        return [0.0]
    last_ts = max(duration_s - 0.05, 0.0)
    return [last_ts * i / (count - 1) for i in range(count)]


def extract_frames(video: Path, run_id: str, count: int = 8) -> list[tuple[int, float, Path]]:
    duration_s = get_video_duration_s(video)
    timestamps = evenly_spaced_timestamps(duration_s, count)
    output_dir = frames_dir(run_id)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    extracted: list[tuple[int, float, Path]] = []

    for idx, timestamp_s in enumerate(timestamps):
        output = output_dir / f"{idx:03d}.jpg"
        logger.info("Extracting frame %s/%s at %.2fs", idx + 1, count, timestamp_s)
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{timestamp_s:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        extracted.append((idx, timestamp_s, output))

    return extracted
