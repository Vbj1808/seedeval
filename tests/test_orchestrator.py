from __future__ import annotations

import json

import pytest

from seedeval.agents import orchestrator


@pytest.mark.asyncio
async def test_plan_run_classifies_portrait_prompt(monkeypatch):
    async def fake_post(messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "prompt_class": "portrait",
                                "checks_to_run": ["adherence", "temporal", "cost"],
                                "frame_sample_count": 8,
                                "temporal_drift_threshold": 0.80,
                                "rationale": "Single subject, so identity stability matters most.",
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(orchestrator, "_post_chat_completion", fake_post)
    plan = await orchestrator.plan_run("A portrait of a fox in a studio", "bytedance/seedance-1-0-lite-t2v")
    assert plan["prompt_class"] == "portrait"
    assert plan["temporal_drift_threshold"] == 0.80


@pytest.mark.asyncio
async def test_plan_run_handles_malformed_json(monkeypatch):
    async def fake_post(messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            'Here is the JSON: {"prompt_class":"action","checks_to_run":["adherence","temporal","cost"],'
                            '"frame_sample_count":8,"temporal_drift_threshold":0.6,"rationale":"Bustling scene."} Done.'
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(orchestrator, "_post_chat_completion", fake_post)
    plan = await orchestrator.plan_run("A bustling street market", "bytedance/seedance-1-0-lite-t2v")
    assert plan["prompt_class"] == "action"
    assert plan["temporal_drift_threshold"] == 0.6


@pytest.mark.asyncio
async def test_synthesize_verdict_produces_nonempty_string(monkeypatch):
    async def fake_post(messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": "This run failed adherence because the neon signage is unreadable, although temporal consistency stayed strong. Cost stayed reasonable."
                    }
                }
            ]
        }

    monkeypatch.setattr(orchestrator, "_post_chat_completion", fake_post)
    verdict = await orchestrator.synthesize_verdict({"overall_score": 6.2})
    assert isinstance(verdict, str)
    assert verdict.strip() != ""
