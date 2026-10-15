"""Private owner guidance reaches the real Battery Constructor input.

DEVELOPMENT fixtures: host images, signer and provider are external-boundary
stand-ins. Preparation, manifest/ledger, Graphite driver and research loop are
real. No Julia, model, solver or evaluator runs; no physical/security claim.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest
import test_battery_graphite_plan as preparation_fixtures
from test_graphite_miner_driver import REAL_STOP, SDK, RoleTransport

from carbon.agent_campaign.graphite.miner import driver, edition
from carbon.battery import campaign as battery
from carbon.development_session import research_campaign
from carbon.development_session import research_guidance as guidance
from carbon.development_session.profile import canonical

# Register the existing fixture without copying its external-boundary setup.
host = preparation_fixtures.host

TASK = "  Try a public Julia calculation.\r\n\tRetain its actual result.  "


def test_battery_freezes_exact_task_and_resumes_from_immutable_binding(host):
    prepared = host.prepare("run", graphite={"mode": "BUILD"}, research_guidance=TASK)
    path = host.root / "campaign-manifest.json"
    original = path.read_bytes()
    frozen = json.loads(original)
    assert prepared.task == frozen["research_guidance"] == guidance.bind(TASK)
    assert prepared.task["text"] == TASK
    again = host.prepare("resume")
    assert again.task == prepared.task and path.read_bytes() == original
    assert host.prepare("resume", research_guidance=TASK).task == prepared.task
    for changed in ("changed task", None):
        with pytest.raises(ValueError, match="frozen research guidance differs"):
            host.prepare("resume", research_guidance=changed)
    assert path.read_bytes() == original


def test_old_unguided_battery_cannot_gain_a_task_on_resume(host):
    prepared = host.prepare("run", graphite={"mode": "BUILD"})
    path = host.root / "campaign-manifest.json"
    original = path.read_bytes()
    assert "research_guidance" not in prepared.manifest and prepared.task is None
    assert host.prepare("resume").task is None
    with pytest.raises(ValueError, match="frozen research guidance differs"):
        host.prepare("resume", research_guidance=TASK)
    assert path.read_bytes() == original


@pytest.mark.parametrize("bad", ["", "   ", 42, "x" * 4097, "bad\x00text", "\ud800"])
def test_invalid_task_is_refused_before_external_preparation(host, monkeypatch, bad):
    def forbidden(*_):
        pytest.fail("external preparation must not start for invalid task input")

    monkeypatch.setattr(research_campaign, "accepted_implementation", forbidden)
    with pytest.raises(ValueError, match="guidance"):
        host.prepare("run", research_guidance=bad)
    assert not (host.root / "campaign-manifest.json").exists()


@pytest.mark.parametrize("field,value", [("digest", "wrong"), ("extra", True)])
def test_frozen_task_tamper_fails_before_external_resume(
    host, monkeypatch, field, value
):
    host.prepare("run", research_guidance=TASK)
    path = host.root / "campaign-manifest.json"
    frozen = json.loads(path.read_bytes())
    frozen["research_guidance"][field] = value
    path.write_bytes(canonical(frozen))

    def forbidden(*_):
        pytest.fail("external preparation must not start for altered task binding")

    monkeypatch.setattr(research_campaign, "accepted_implementation", forbidden)
    with pytest.raises(ValueError, match="guidance binding differs"):
        host.prepare("resume")


@pytest.mark.parametrize("guided", [False, True])
def test_actual_constructor_request_contains_private_task_as_user_input(host, guided):
    kwargs = {"research_guidance": TASK} if guided else {}
    prepared = host.prepare("run", graphite={"mode": "BUILD"}, **kwargs)
    # Real Battery observation on the real driver; only external services are
    # stand-ins. In particular run_epoch is NOT replaced by a wrapper spy.
    prepared.campaign = SimpleNamespace(observation=battery.agent_observation)
    prepared.task = None  # Observation must use the persisted manifest binding.
    prepared.composition.executor = SimpleNamespace(
        gpu=None,
        julia_image=None,
        practice=SimpleNamespace(backends=("jax", "pytorch"), gpu_image=None),
    )
    prepared.sdk = SDK(prepared.ledger, prepared.owner)
    transport = RoleTransport(planner=[REAL_STOP], constructor=[REAL_STOP])
    assert asyncio.run(driver.run(prepared, transport=transport)) is None
    assert len(transport.requests) == 2
    constructor = [
        r
        for r in transport.requests
        if r["instructions"].startswith(edition.CONSTRUCTOR_PROMPT)
    ]
    assert len(constructor) == 1
    request = constructor[0]
    assert request["instructions"].startswith(edition.CONSTRUCTOR_PROMPT)
    assert TASK not in request["instructions"]
    first = request["input"][0]
    assert first["role"] == "user"
    observation = json.loads(first["content"])
    assert observation["graphite"]["role"] == "constructor"
    assert observation["run_plan"]["evaluator_access"] is False
    assert observation["challenge"]["id"] == prepared.challenge.challenge_id
    assert observation["prior_permitted_evaluation_feedback"] is None
    assert "hidden" not in observation and "score" not in observation
    assert request["tools"] and "research_guidance" not in {
        t["name"] for t in request["tools"]
    }
    plan = json.loads((host.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["initial_observation"] == observation
    assert plan["miner_guidance"] == prepared.manifest["provider"]["miner_guidance"]
    if guided:
        assert observation["research_guidance"] == guidance.bind(TASK)
        assert observation["research_context"] == guidance.context(prepared.manifest)
        assert "Lower-priority" in observation["guidance_role"]
        assert plan["effective_input_digest"] == guidance.effective_digest(
            plan["agent_policy"], observation
        )
        changed = {**observation, "research_guidance": guidance.bind("changed")}
        assert (
            guidance.effective_digest(plan["agent_policy"], changed)
            != plan["effective_input_digest"]
        )
    else:
        assert "research_guidance" not in observation
        assert (
            "research_context" not in observation and "guidance_role" not in observation
        )
        assert "effective_input_digest" not in plan
    assert prepared.sdk.dispatched == []
