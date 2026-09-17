"""Deterministic SDK/Responses mocks test control flow, never agent evidence."""

import asyncio
import json

from test_cw1_research_ledger import ledger

from carbon.development_session.agent import MODEL
from carbon.development_session.research_loop import SELECT, run_epoch


def response(output):
    return {
        "model": MODEL,
        "status": "completed",
        "output": output,
        "usage": {
            "input_tokens": 10,
            "output_tokens": 20,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def test_agent_can_stop_without_forced_trials_and_replay_is_free(tmp_path):
    meter = ledger(tmp_path)
    calls = []

    def transport(request):
        calls.append(request)
        return response(
            [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "No feasible useful action in this synthetic control.",
                        }
                    ],
                }
            ]
        )

    args = {
        "owner": "alice",
        "epoch": 1,
        "sdk": None,
        "credential_file": None,
        "initial_observation": {"fixture": True},
        "transport": transport,
    }
    first = asyncio.run(run_epoch(meter, **args))
    assert first["status"] == "STOPPED"
    assert asyncio.run(run_epoch(meter, **args)) == first
    assert len(calls) == 1
    assert meter.status(owner="alice")["used"]["research_trials"] == 0


def test_selection_is_compiled_recipe_not_a_final_result(tmp_path):
    meter = ledger(tmp_path)
    strategy = {
        "schema_version": "1.0",
        "challenge_id": "burgers-dynamics-v1",
        "backbone": "fno",
        "parameters": {"steps": 512, "enforce_mean": True},
    }

    def transport(request):
        return response(
            [
                {
                    "type": "function_call",
                    "name": SELECT,
                    "call_id": "fixture-call-1",
                    "arguments": json.dumps(
                        {
                            "strategy_json": json.dumps(strategy),
                            "reason": "synthetic control-flow test, no quality claim",
                            "used_feedback": False,
                        }
                    ),
                }
            ]
        )

    result = asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=None,
            credential_file=None,
            initial_observation={"fixture": True},
            transport=transport,
        )
    )
    assert result["status"] == "SELECTED"
    assert result["strategy"] == strategy
    assert not result["final_evidence"]
    assert meter.status(owner="alice")["used"]["final_replicas"] == 0
