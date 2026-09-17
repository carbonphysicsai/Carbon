"""Synthetic control-flow tests, never campaign inference or quality evidence."""

import asyncio
import json

import pytest
from test_cw1_research_ledger import ledger
from test_cw1_research_loop import response

from carbon.development_session.profile import canonical
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    LEGACY,
    STOP,
    binding,
    stop_result,
)
from carbon.development_session.research_loop import run_epoch
from carbon.development_session.research_tools import PREFIX


def text_reply():
    return response(
        [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "Please approve a practice run."}
                ],
            }
        ]
    )


def tool(name, args):
    return response(
        [
            {
                "type": "function_call",
                "name": name,
                "call_id": "test-call",
                "arguments": json.dumps(args),
            }
        ]
    )


def run(meter, transport, sdk=None, **extra):
    return asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=sdk,
            credential_file=None,
            initial_observation={"fixture": True},
            agent_policy=AUTONOMOUS,
            transport=transport,
            **extra,
        )
    )


def stop():
    return tool(
        STOP,
        {
            "reason": "no_feasible_action",
            "evidence": "Synthetic unsupported operation; no real result.",
            "used_feedback": False,
        },
    )


def test_free_text_receives_one_metered_correction_then_can_act_and_stop(tmp_path):
    meter = ledger(tmp_path)
    requests, actions = [], []
    replies = [text_reply(), tool(PREFIX + "get_challenge_info", {}), stop()]

    class SDK:
        async def call(self, name, args, identity):
            actions.append((name, identity))
            return {"status": "TEST_ONLY", "public": "synthetic"}

    def transport(req):
        requests.append(req)
        return replies[len(requests) - 1]

    result = run(meter, transport, SDK())
    assert result["reason"] == "agent reported no_feasible_action"
    assert len(actions) == 1
    assert "already authorized" in requests[1]["input"][2]["content"]
    assert result["accounting"]["used"]["provider_attempts"] == 3
    assert result["accounting"]["used"]["provider_nanodollars"] > 0
    assert result["accounting"]["used"]["research_trials"] == 0
    assert (tmp_path / "epoch-1/epoch-1-provider-000-continuation.json").exists()
    assert (
        run(meter, lambda _: pytest.fail("duplicate model dispatch"), SDK()) == result
    )
    assert len(actions) == 1


def test_repeated_permission_requests_stop_without_infinite_supervision(tmp_path):
    result = run(ledger(tmp_path), lambda _: text_reply())
    assert result["reason"] == "unstructured agent stop after one clarification"
    assert result["accounting"]["used"]["provider_attempts"] == 2
    assert result["accounting"]["used"]["final_replicas"] == 0


def test_explicit_stop_can_precede_any_trial_without_correction(tmp_path):
    result = run(ledger(tmp_path), lambda _: stop())
    assert result["accounting"]["used"]["provider_attempts"] == 1
    assert not list((tmp_path / "epoch-1").glob("*-continuation.json"))
    assert result["evidence_basis"] == "AGENT_REPORTED_NOT_INDEPENDENTLY_VERIFIED"
    assert not result["final_evidence"]


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"reason": "owner_approval", "evidence": "request", "used_feedback": False},
        {"reason": "plateau", "evidence": " ", "used_feedback": False},
        {"reason": "plateau", "evidence": "test", "used_feedback": 1},
        {"reason": "plateau", "evidence": "x" * 4097, "used_feedback": False},
        {
            "reason": "plateau",
            "evidence": "test",
            "used_feedback": False,
            "grant": True,
        },
    ],
)
def test_stop_does_not_grant_authority_or_accept_malformed_evidence(args):
    assert stop_result(args)["status"] == "REJECTED_BEFORE_DISPATCH"


def test_frozen_legacy_plan_cannot_be_resumed_with_new_policy(tmp_path):
    meter = ledger(tmp_path)
    first = asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=None,
            credential_file=None,
            initial_observation={"fixture": True},
            transport=lambda _: text_reply(),
        )
    )
    assert first["accounting"]["used"]["provider_attempts"] == 1
    with pytest.raises(ValueError):
        run(meter, lambda _: pytest.fail("policy must fail before dispatch"))
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 1
    assert "agent_policy" not in json.loads(
        (tmp_path / "epoch-1/plan.json").read_bytes()
    )


def test_unknown_policy_and_changed_plan_fail_before_provider(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        binding("unregistered")
    meter = ledger(tmp_path)
    run(meter, lambda _: stop())
    path = tmp_path / "epoch-1/plan.json"
    value = json.loads(path.read_bytes())
    value["agent_policy"] = binding(LEGACY)
    path.write_bytes(canonical(value))
    with pytest.raises(ValueError):
        run(meter, lambda _: pytest.fail("changed plan dispatch"))


def test_clarification_cannot_bypass_context_budget(tmp_path, monkeypatch):
    from carbon.development_session import research_loop

    monkeypatch.setattr(research_loop, "MAX_INPUT_TOKENS", 4096)
    result = run(ledger(tmp_path), lambda _: pytest.fail("over-budget dispatch"))
    assert "context admission" in result["reason"]
    assert result["accounting"]["used"]["provider_attempts"] == 0
