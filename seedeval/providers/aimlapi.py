from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from seedeval.config import require_aimlapi_key
from seedeval.models import GeneratedVideo
from seedeval.providers.base import SeedanceProvider
from seedeval.storage import video_path

logger = logging.getLogger(__name__)


BASE_URL = "https://api.aimlapi.com/v2"
DEFAULT_TIMEOUT_S = 30
POLL_INTERVAL_S = 5
MAX_GENERATION_WAIT_S = 300

COST_PER_5S_USD = {
    "bytedance/seedance-1-0-lite-t2v": 0.12,
}


class AIMLAPISeedanceProvider(SeedanceProvider):
    def __init__(self, run_id: str, api_key: str | None = None) -> None:
        self.run_id = run_id
        self.api_key = api_key or require_aimlapi_key()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate_video(
        self,
        prompt: str,
        model: str,
        duration_s: int = 5,
    ) -> GeneratedVideo:
        start = time.perf_counter()
        async with httpx.AsyncClient(base_url=BASE_URL, headers=self.headers) as client:
            job_id = await self._submit_generation(client, prompt, model)
            completed = await self._poll_until_complete(client, job_id)
            url = completed["video"]["url"]
            destination = video_path(self.run_id)
            await self._download_video(client, url, destination)

        latency_s = time.perf_counter() - start
        return GeneratedVideo(
            video_path=destination,
            latency_s=latency_s,
            cost_usd=self._estimate_cost(model, duration_s),
            provider_raw_response=completed,
            model_used=model,
        )

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _submit_generation(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        model: str,
    ) -> str:
        logger.info("Submitting Seedance generation job")
        response = await client.post(
            "/generate/video/bytedance/generation",
            json={"model": model, "prompt": prompt},
            timeout=DEFAULT_TIMEOUT_S,
        )
        response.raise_for_status()
        job_id = response.json()["id"]
        logger.info("Seedance job submitted: %s", job_id)
        return job_id

    async def _poll_until_complete(
        self,
        client: httpx.AsyncClient,
        job_id: str,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        while True:
            data = await self._poll_once(client, job_id)
            status = data.get("status")
            elapsed = time.perf_counter() - start
            logger.info("Seedance job status=%s elapsed=%.1fs", status, elapsed)

            if status == "completed":
                if "video" not in data or "url" not in data["video"]:
                    raise RuntimeError(f"Completed generation did not include video URL: {data}")
                return data
            if status == "failed":
                raise RuntimeError(f"Seedance generation failed: {data}")
            if elapsed > MAX_GENERATION_WAIT_S:
                raise TimeoutError("Seedance generation timed out after 5 minutes")

            await self._sleep(POLL_INTERVAL_S)

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _poll_once(self, client: httpx.AsyncClient, job_id: str) -> dict[str, Any]:
        response = await client.get(
            "/video/generations",
            params={"generation_id": job_id},
            timeout=DEFAULT_TIMEOUT_S,
        )
        response.raise_for_status()
        return response.json()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _download_video(
        self,
        client: httpx.AsyncClient,
        url: str,
        destination: Path,
    ) -> None:
        logger.info("Downloading Seedance mp4 to %s", destination)
        response = await client.get(url, timeout=60)
        response.raise_for_status()
        destination.write_bytes(response.content)

    async def _sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    def _estimate_cost(self, model: str, duration_s: int) -> float:
        base = COST_PER_5S_USD.get(model, 0.0)
        return base * max(duration_s, 1) / 5
