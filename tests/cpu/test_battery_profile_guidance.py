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
from carbon.development_session.research_ledger import CampaignLedger
from scripts.dev.miner_launchpad.projection import project

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
@pytest.mark.parametrize("agent", ["graphite", "autonomous"])
def test_actual_agent_request_and_own_projection_bind_private_task(
    host, monkeypatch, guided, agent
):
    kwargs = {"research_guidance": TASK} if guided else {}
    args = host.args("run", agent=agent, graphite={"mode": "BUILD"}, **kwargs)
    # Real-shaped accepted implementation metadata for the actual own view;
    # image/host verification remains the existing external-boundary fixture.
    implementation = {"revision": "fixture-commit"}
    args.product.runtime["implementation"] = implementation
    monkeypatch.setattr(
        research_campaign, "accepted_implementation", lambda _: implementation
    )
    prepared = asyncio.run(
        battery.prepare_battery(args, ledger=CampaignLedger(host.root), campaign=None)
    )
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
    run = driver.run if agent == "graphite" else research_campaign.run_agent
    assert asyncio.run(run(prepared, transport=transport)) is None
    assert len(transport.requests) == (2 if agent == "graphite" else 1)
    constructor = (
        [
            r
            for r in transport.requests
            if r["instructions"].startswith(edition.CONSTRUCTOR_PROMPT)
        ]
        if agent == "graphite"
        else transport.requests
    )
    assert len(constructor) == 1
    request = constructor[0]
    assert TASK not in request["instructions"]
    first = request["input"][0]
    assert first["role"] == "user"
    observation = json.loads(first["content"])
    if agent == "graphite":
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

    row = {
        "id": "fixture-run",
        "campaign": prepared.manifest["campaign_id"],
        "profile": "fixture-profile",
        "state": "COMPLETED",
        "principal": prepared.manifest["principal"],
        "research_guidance": json.dumps(guidance.bind(TASK)) if guided else None,
    }
    own = project(row, host.root)
    if guided:
        assert own["research_guidance"] == guidance.bind(TASK)
        assert (
            own["effective_research_inputs"][0]["digest"]
            == plan["effective_input_digest"]
        )
        assert prepared.manifest["agent_policy"] == plan["agent_policy"]
        path = host.root / "epoch-1" / "plan.json"
        original = path.read_bytes()
        for field, value in (
            ("agent_policy", {**plan["agent_policy"], "version": "wrong"}),
            ("prompt", plan["prompt"] + "changed"),
            ("effective_input_digest", "wrong"),
        ):
            path.write_bytes(canonical({**plan, field: value}))
            with pytest.raises(
                ValueError, match="frozen effective research input differs"
            ):
                project(row, host.root)
        for field, value in (
            ("research_guidance", guidance.bind("different task")),
            (
                "research_context",
                {**observation["research_context"], "campaign_id": "other"},
            ),
        ):
            changed = {**observation, field: value}
            altered = {
                **plan,
                "initial_observation": changed,
                "effective_input_digest": guidance.effective_digest(
                    plan["agent_policy"], changed
                ),
            }
            path.write_bytes(canonical(altered))
            with pytest.raises(
                ValueError, match="frozen effective research input differs"
            ):
                project(row, host.root)
        path.write_bytes(original)
        assert (
            project(row, host.root)["effective_research_inputs"]
            == own["effective_research_inputs"]
        )
    else:
        assert "research_guidance" not in own and "effective_research_inputs" not in own


@pytest.mark.parametrize("agent", ["autonomous", "graphite"])
def test_guided_policy_freezes_from_campaign_authority_and_tamper_fails_early(
    host, monkeypatch, agent
):
    prepared = host.prepare("run", agent=agent, research_guidance=TASK)
    assert prepared.manifest["agent_policy"] == battery.research_task_policy(
        prepared.manifest
    )
    path = host.root / "campaign-manifest.json"
    frozen = json.loads(path.read_bytes())
    frozen["agent_policy"]["prompt_digest"] = "wrong"
    path.write_bytes(canonical(frozen))

    def forbidden(*_):
        pytest.fail("external preparation must not start for altered task policy")

    monkeypatch.setattr(research_campaign, "accepted_implementation", forbidden)
    with pytest.raises(ValueError, match="guided campaign policy differs"):
        host.prepare("resume", agent=agent)
