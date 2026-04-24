from __future__ import annotations

import contextvars
import json
import logging
from collections import defaultdict
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from seedeval.agents.vlm_judge import _extract_json_payload
from seedeval.config import require_aimlapi_key

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_URL = "https://api.aimlapi.com/v1/chat/completions"
SEED18_MODEL = "bytedance/seed-1-8"
SEED18_ESTIMATED_CALL_COST_USD = 0.001

PLAN_SYSTEM_PROMPT = """You are SeedEval's orchestrator. Given a video generation prompt, classify it and decide how to evaluate the output. You return ONLY valid JSON matching the schema. No prose outside JSON.

PROMPT CLASSES:
- landscape: wide shots, scenery, environments with minimal subject focus
- portrait: one or few people/creatures, often stationary
- action: explicit motion, sports, chases, dancing, "bustling", "running"
- abstract: artistic, non-literal, style-heavy

DRIFT THRESHOLD TUNING:
- portrait: 0.80 (faces should stay stable)
- action: 0.60 (motion is expected)
- landscape: 0.70
- abstract: 0.55 (experimental content drifts naturally)

Schema:
{
  "prompt_class": "landscape" | "portrait" | "action" | "abstract",
  "checks_to_run": ["adherence", "temporal", "cost"],
  "frame_sample_count": 8,
  "temporal_drift_threshold": <float 0.5-0.85>,
  "rationale": "<1-2 sentences>"
}"""

VERDICT_SYSTEM_PROMPT = """You are SeedEval's verdict synthesizer. You summarize a completed video eval run for a developer reading their dashboard. Be direct. Be specific. Quote the concrete flaws found. 2-4 sentences total. No headers, no bullets, no markdown.

STRUCTURE:
1. Open with the overall verdict (pass/fail and why).
2. Name the STRONGEST finding - usually a flagged-frame critique with specific details.
3. If relevant, mention cost/latency context.

TONE: professional code review, not marketing. Developers will read this and act on it."""

_active_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "seedeval_orchestrator_run_id",
    default=None,
)
_plan_costs_usd: dict[str, float] = defaultdict(float)
_verdict_costs_usd: dict[str, float] = defaultdict(float)


def set_active_run_id(run_id: str) -> contextvars.Token[str | None]:
    return _active_run_id.set(run_id)


def reset_active_run_id(token: contextvars.Token[str | None]) -> None:
    _active_run_id.reset(token)


def _record_cost(kind: str) -> None:
    run_id = _active_run_id.get()
    if not run_id:
        return
    if kind == "plan":
        _plan_costs_usd[run_id] += SEED18_ESTIMATED_CALL_COST_USD
    elif kind == "verdict":
        _verdict_costs_usd[run_id] += SEED18_ESTIMATED_CALL_COST_USD


def get_plan_cost(run_id: str) -> float:
    return float(_plan_costs_usd.get(run_id, 0.0))


def get_verdict_cost(run_id: str) -> float:
    return float(_verdict_costs_usd.get(run_id, 0.0))


def reset_run_costs(run_id: str) -> tuple[float, float]:
    plan_cost = float(_plan_costs_usd.pop(run_id, 0.0))
    verdict_cost = float(_verdict_costs_usd.pop(run_id, 0.0))
    return plan_cost, verdict_cost


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential_jitter(initial=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _post_chat_completion(messages: list[dict[str, Any]]) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {require_aimlapi_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": SEED18_MODEL,
        "max_tokens": 2000,
        "messages": messages,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(CHAT_COMPLETIONS_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def plan_run(prompt: str, model: str) -> dict[str, Any]:
    response = await _post_chat_completion(
        [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f'Prompt: "{prompt}"\nModel: {model}\n\nReturn your plan as JSON.',
            },
        ]
    )
    _record_cost("plan")
    content = response["choices"][0]["message"].get("content", "") or ""
    parsed = _extract_json_payload(content)
    return {
        "prompt_class": parsed["prompt_class"],
        "checks_to_run": parsed["checks_to_run"],
        "frame_sample_count": int(parsed["frame_sample_count"]),
        "temporal_drift_threshold": float(parsed["temporal_drift_threshold"]),
        "rationale": str(parsed["rationale"]),
    }


async def synthesize_verdict(run_data: dict[str, Any]) -> str:
    response = await _post_chat_completion(
        [
            {"role": "system", "content": VERDICT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(run_data, indent=2)},
        ]
    )
    _record_cost("verdict")
    return (response["choices"][0]["message"].get("content", "") or "").strip()
