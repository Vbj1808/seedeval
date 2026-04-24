from __future__ import annotations

import base64
import contextvars
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from seedeval.config import require_aimlapi_key

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_URL = "https://api.aimlapi.com/v1/chat/completions"
SEED18_MODEL = "bytedance/seed-1-8"
SEED18_ESTIMATED_CALL_COST_USD = 0.015

_active_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "seedeval_active_run_id",
    default=None,
)
_run_costs_usd: dict[str, float] = defaultdict(float)
_run_call_counts: dict[str, int] = defaultdict(int)


def set_active_run_id(run_id: str) -> contextvars.Token[str | None]:
    return _active_run_id.set(run_id)


def reset_active_run_id(token: contextvars.Token[str | None]) -> None:
    _active_run_id.reset(token)


def get_run_seed18_cost(run_id: str) -> float:
    return float(_run_costs_usd.get(run_id, 0.0))


def get_run_seed18_call_count(run_id: str) -> int:
    return int(_run_call_counts.get(run_id, 0))


def reset_run_seed18_cost(run_id: str) -> float:
    cost = float(_run_costs_usd.pop(run_id, 0.0))
    _run_call_counts.pop(run_id, None)
    return cost


def _data_url_for_image(frame_path: str) -> str:
    image_bytes = Path(frame_path).read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _extract_json_payload(content: str) -> dict[str, Any]:
    stripped = content.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    candidate = stripped[start : end + 1] if start != -1 and end != -1 and end > start else stripped
    return json.loads(candidate)


def _fallback_payload(content: str) -> dict[str, Any]:
    return {
        "error": "parse_failed",
        "raw": content,
        "score": 0,
        "flagged": True,
    }


def _postprocess_scores(parsed: dict[str, Any]) -> dict[str, Any]:
    dim_scores = [
        parsed["subject_presence"],
        parsed["setting_match"],
        parsed["action_match"],
        parsed["style_match"],
    ]
    model_overall = parsed.get("overall")
    parsed["model_overall"] = model_overall
    parsed["overall"] = min(dim_scores)
    parsed["flagged"] = parsed["overall"] <= 7 or any(d <= 5 for d in dim_scores)
    return parsed


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential_jitter(initial=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _post_chat_completion(
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(CHAT_COMPLETIONS_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def _judge_once(
    frame_path: str,
    prompt_text: str,
    *,
    stricter_system_prompt: bool = False,
) -> tuple[dict[str, Any], str]:
    system_prompt = (
        "You inspect one video frame and must return only a single JSON object. "
        "Do not include prose, markdown, or code fences before or after the JSON."
        if stricter_system_prompt
        else """SYSTEM: You are a strict, skeptical video-quality judge evaluating AI-generated video frames. Your job is to find failures, not confirm successes. You are paid to catch problems.

CALIBRATION (read carefully - this is binding):
- 10/10 is RESERVED for frames that could be mistaken for professional footage. In practice, almost no AI-generated frame scores 10.
- 8-9 = strong match with minor imperfections you can name specifically
- 5-7 = partial match, clear gaps
- 3-4 = major mismatch, prompt elements missing or wrong
- 0-2 = unrelated or fundamentally broken output

Most AI-generated frames from models like Seedance Lite score between 4 and 6. Lite is a low-tier model - typical outputs have visible artifacts (garbled text on signs, warped faces, impossible physics, blurred motion where sharpness was requested). If you find yourself giving an 8 or higher to a Lite output, re-examine the frame - you are almost certainly missing something. Reserve 10/10 for truly professional-quality frames only.

You must provide SPECIFIC, CONCRETE critiques:
- BAD (reject): "Perfect match", "Great style", "All elements present"
- GOOD: "The taxis are the wrong shade of yellow and lack the checker pattern.", "The crowd appears static and blurred - 'bustling' implies visible motion which is absent.", "The neon signs are unreadable shapes, not recognizable text."

For each dimension, ask yourself: "If this frame appeared in a professional portfolio, would a critic notice issues?" If yes, deduct points and name them.

USER: The user's prompt was: "{prompt}"

This is frame {idx} of 8, sampled at {timestamp_s}s of a 5-second video.

Rate each dimension 0-10 using the calibration above:
- subject_presence: Are the specific subjects named in the prompt actually visible, identifiable, and correct?
- setting_match: Does the environment match the prompt's specific details (not just the general vibe)?
- action_match: Is the action/motion described actually happening? "Bustling" and "eating" and "running" all imply visible motion.
- style_match: Does the visual style match? ("Cinematic", "IMAX", "slow motion" are strong specific claims.)

Then:
- overall: 0-10 integer (weighted average you compute yourself, not a generic "sum it up")
- one_sentence_reason: MUST name at least one specific flaw OR specific strength. Reject generic praise.
- flagged: true if overall <= 7 OR any dimension <= 5

Return JSON with EXACTLY these keys and no others:
{
  "subject_presence": <int>,
  "setting_match": <int>,
  "action_match": <int>,
  "style_match": <int>,
  "overall": <int>,
  "one_sentence_reason": "<specific, concrete, under 25 words>",
  "flagged": <bool>
}"""
    )
    payload = {
        "model": SEED18_MODEL,
        "max_tokens": 2000,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": _data_url_for_image(frame_path)}},
                ],
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {require_aimlapi_key()}",
        "Content-Type": "application/json",
    }
    response = await _post_chat_completion(payload, headers)
    _record_seed18_cost(response)
    message = response["choices"][0]["message"]
    content = message.get("content", "") or ""
    return response, content


def _record_seed18_cost(response: dict[str, Any]) -> None:
    run_id = _active_run_id.get()
    if not run_id:
        return
    _run_costs_usd[run_id] += SEED18_ESTIMATED_CALL_COST_USD
    _run_call_counts[run_id] += 1
    reasoning = response.get("choices", [{}])[0].get("message", {}).get("reasoning_content")
    if reasoning:
        logger.debug("Seed 1.8 returned reasoning_content for run %s", run_id)


async def judge_frame(
    frame_path: str,
    prompt: str,
    prompt_text: str,
) -> dict[str, Any]:
    """Send a frame plus a JSON-only question to Seed 1.8 and parse the response."""
    del prompt

    raw_content = ""
    try:
        _, raw_content = await _judge_once(
            frame_path,
            prompt_text,
            stricter_system_prompt=False,
        )
        return _postprocess_scores(_extract_json_payload(raw_content))
    except json.JSONDecodeError:
        logger.warning("Seed 1.8 returned wrapped JSON for %s; retrying stricter prompt", frame_path)

    try:
        _, raw_content = await _judge_once(
            frame_path,
            prompt_text,
            stricter_system_prompt=True,
        )
        return _postprocess_scores(_extract_json_payload(raw_content))
    except json.JSONDecodeError:
        logger.error("Seed 1.8 parse failed twice for %s", frame_path)
        return _fallback_payload(raw_content)
    except Exception:
        logger.exception("Seed 1.8 judge failed for %s", frame_path)
        raise
