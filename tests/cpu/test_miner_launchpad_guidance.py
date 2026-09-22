"""Non-spending guidance contracts; scripted trials are not adaptive evidence."""

import asyncio
import json

import pytest
from test_cw1_research_loop import response
from test_miner_launchpad_admission import managed
from test_miner_launchpad_finite_completion import setup_campaign
from test_miner_launchpad_runner import adapter

from carbon.development_session import research_campaign as campaign
from carbon.development_session import research_guidance as guidance
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    AUTONOMOUS_PROMPT,
    binding,
)
from carbon.development_session.research_ledger import DEVELOPMENT_CEILINGS
from carbon.development_session.research_loop import SELECT, run_epoch
from carbon.development_session.research_tools import PREFIX
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.runner import PATH_FIELDS, RunnerAdapter

TASK = "Engineering fixture: initial experiment → inspect feedback → first revision → inspect feedback → second revision.\nRetain earlier candidates; stop if inadmissible."


@pytest.mark.parametrize(
    "text",
    [None, 12, {}, "", " \n", "x" * 4097, "é" * 2049, "bad\x00text", "bad\ud800"],
)
def test_invalid_guidance_fails_before_admission(tmp_path, text):
    tmp_path.chmod(0o700)
    path = tmp_path / "profile.json"
    cfg = {
        "schema": "carbon.launchpad.runner-profile.v1",
        "profile_id": "fixture",
        "principal": "alice",
        "grant_file": str(tmp_path / "absent-grant"),
        "account_ref": "fixture",
        "enabled": True,
        "accepted_revision": "fixture",
        "paths": {key: str(tmp_path / key) for key in PATH_FIELDS},
        "research_guidance": text,
    }
    path.write_bytes(canonical(cfg))
    path.chmod(0o600)
    bridge = RunnerAdapter(tmp_path / "browser.sqlite3", configuration=path)
    with pytest.raises(ValueError, match="guidance"):
        bridge.configured()
    with pytest.raises(Rejected, match="admission"):
        bridge.launch({"profile": "fixture"}, "fixture-request-0001")
    assert bridge.recent() == []
    assert not (tmp_path / "absent-grant").exists()


def test_exact_utf8_text_and_closed_binding():
    text = "  Hypothesis é\r\n\tretain spacing  "
    bound = guidance.bind(text)
    assert bound["text"] == text
    assert bound["digest"] == digest(text.encode("utf-8"))
    assert guidance.verify(bound) == bound
    for changed in (
        {**bound, "digest": "wrong"},
        {**bound, "text": text.strip()},
        {**bound, "extra": True},
    ):
        with pytest.raises(ValueError, match="binding"):
            guidance.verify(changed)
    assert guidance.configured({}) is None


def test_campaign_input_freeze_resume_and_tamper_rejection(tmp_path, monkeypatch):
    args, meter, _ = setup_campaign(tmp_path, monkeypatch, 1)
    args.research_guidance = TASK
    observed = []

    async def epoch(*_, **kw):
        observed.append(kw["initial_observation"])
        return {"status": "STOPPED"}

    monkeypatch.setattr(campaign, "run_epoch", epoch)
    asyncio.run(campaign.execute(args, ledger=meter))
    assert observed[0]["research_guidance"] == guidance.bind(TASK)
    assert "Lower-priority" in observed[0]["guidance_role"]
    path = meter.root / "campaign-manifest.json"
    original = path.read_bytes()
    assert json.loads(original)["research_guidance"] == guidance.bind(TASK)
    args.command = "resume"
    asyncio.run(campaign.execute(args, ledger=meter))
    assert len(observed) == 1 and path.read_bytes() == original
    args.research_guidance = "changed"
    with pytest.raises(ValueError, match="frozen research guidance"):
        asyncio.run(campaign.execute(args, ledger=meter))
    del args.research_guidance  # CLI resume takes the persisted value, not mutable UI.
    asyncio.run(campaign.execute(args, ledger=meter))
    manifest = json.loads(original)
    manifest["research_guidance"]["digest"] = "tampered"
    path.write_bytes(canonical(manifest))
    with pytest.raises(ValueError, match="binding"):
        asyncio.run(campaign.execute(args, ledger=meter))
    assert len(observed) == 1


def test_prelaunch_review_pin_persistence_and_legacy_migration(tmp_path, monkeypatch):
    bridge, meter, _ = adapter(tmp_path, monkeypatch)
    cfg, _, _ = bridge.configured()
    cfg.update(research_guidance=TASK, accepted_revision="fixture")
    task = guidance.bind(TASK)
    with meter.db() as db:
        manifest = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
        manifest["research_guidance"] = task
        db.execute("UPDATE campaign SET manifest=?", (canonical(manifest),))
    preflight = bridge.preflight()
    assert preflight["research_guidance"] == task
    for body in (
        {"profile": cfg["profile_id"]},
        {"profile": cfg["profile_id"], "research_guidance": "replacement"},
        {"profile": cfg["profile_id"], "review_digest": "stale"},
    ):
        with pytest.raises(Rejected):
            bridge.launch(body, "fixture-request-0001")
    body = {"profile": cfg["profile_id"], "review_digest": preflight["review_digest"]}
    run = bridge.launch(body, "fixture-request-0001")
    assert run["research_guidance"] == task
    other = RunnerAdapter(bridge.database, principal="other-owner")
    assert other.recent() == []
    with pytest.raises(Rejected, match="unavailable"):
        other.get(run["id"])
    assert bridge.launch(body, "fixture-request-0001")["id"] == run["id"]
    recovered = RunnerAdapter(bridge.database, principal="alice")
    assert recovered.get(run["id"])["research_guidance"] == task
    cfg["research_guidance"] = "changed before retry"
    with pytest.raises(Rejected, match="review"):
        bridge.launch(body, "fixture-request-0001")
    with pytest.raises(ValueError, match="resume binding"):
        bridge.control(run["id"], "resume")
    with meter.db() as db:
        manifest["research_guidance"]["text"] = "tampered"
        db.execute("UPDATE campaign SET manifest=?", (canonical(manifest),))
    with pytest.raises(ValueError, match="binding"):
        recovered.get(run["id"])


def test_legacy_rows_and_input_stay_absent(tmp_path, monkeypatch):
    bridge, _, _ = adapter(tmp_path, monkeypatch)
    run = bridge.launch({"profile": "opaque-profile"}, "fixture-request-0001")
    assert "research_guidance" not in run
    assert "review_digest" not in bridge.preflight()
    # Actual old-table migration preserves the existing record and replay identity.
    with bridge.db() as db:
        db.execute("ALTER TABLE research_runs DROP COLUMN research_guidance")
    recovered = RunnerAdapter(bridge.database, principal="alice")
    assert "research_guidance" not in recovered.get(run["id"])


def test_scripted_three_trial_information_flow_and_earlier_selection(tmp_path):
    meter, _, _ = managed(
        tmp_path, ceilings={**DEVELOPMENT_CEILINGS, "research_trials": 3}
    )
    owner = "miner-requester"
    recipes = [
        {
            **campaign.CONTROL,
            "parameters": {**campaign.CONTROL["parameters"], "learning_rate": rate},
        }
        for rate in (0.002, 0.001, 0.0005)
    ]
    observations = [0.5, 0.4, 0.6]  # Explicit engineering fixture values, not science.
    initial = {
        "fixture": "SCRIPTED_INFORMATION_FLOW_ONLY",
        "research_guidance": guidance.bind(TASK),
        "research_context": {
            "campaign_id": "fixture-campaign",
            "implementation": "fixture",
        },
    }
    calls, attempts = [], []

    class SDK:
        async def call(self, name, arguments, identity):
            index = len(attempts)
            recipe = json.loads(arguments["strategy_json"])
            assert recipe == recipes[index]
            assert (
                str(observations[index - 1]) in arguments["hypothesis"]
                if index
                else True
            )
            meter.note(
                owner=owner,
                kind="hypothesis",
                body={"hypothesis": arguments["hypothesis"], "task": identity},
            )
            meter.reserve(
                identity,
                owner=owner,
                phase="research",
                request=arguments,
                resources={"research_trials": 1},
            )
            result = {
                "status": "COMPLETE",
                "fixture_only": True,
                "practice_value": observations[index],
                "recipe": recipe,
            }
            meter.finish(
                identity,
                owner=owner,
                state="SUCCEEDED",
                actual={"research_trials": 1},
                result=result,
            )
            attempts.append(result)
            return result

    def transport(request):
        index = len(calls)
        assert request["instructions"] == AUTONOMOUS_PROMPT
        assert json.loads(request["input"][0]["content"]) == initial
        if index:
            previous = json.loads(request["input"][-1]["output"])
            assert previous["practice_value"] == observations[index - 1]
        calls.append(request)
        if index < 3:
            name = PREFIX + "start_research_task"
            arguments = {
                "kind": "practice",
                "strategy_json": json.dumps(recipes[index]),
                "action": None,
                "arguments_json": None,
                "hypothesis": (
                    "fixture initial"
                    if index == 0
                    else f"fixture feedback {observations[index - 1]} motivates lower learning rate"
                ),
                "expected_effect": "fixture diagnostic change",
            }
        else:
            name = SELECT
            arguments = {
                "strategy_json": json.dumps(recipes[1]),
                "reason": "fixture trial 2 retained because trial 3 underperformed",
                "used_feedback": True,
            }
        return response(
            [
                {
                    "type": "function_call",
                    "name": name,
                    "call_id": f"fixture-{index}",
                    "arguments": json.dumps(arguments),
                }
            ]
        )

    args = {
        "owner": owner,
        "epoch": 1,
        "sdk": SDK(),
        "credential_file": None,
        "initial_observation": initial,
        "transport": transport,
        "agent_policy": AUTONOMOUS,
    }
    result = asyncio.run(run_epoch(meter, **args))
    assert result["strategy"] == recipes[1] and len(attempts) == 3
    assert sum(attempts[i]["recipe"] != attempts[i - 1]["recipe"] for i in (1, 2)) == 2
    plan_path = meter.root / "epoch-1/plan.json"
    plan = json.loads(plan_path.read_bytes())
    assert plan["effective_input_digest"] == guidance.effective_digest(
        binding(AUTONOMOUS), initial
    )
    assert plan["agent_policy"] == binding(AUTONOMOUS)
    with pytest.raises(ValueError, match="effective research input"):
        guidance.verify_history(
            meter.root,
            guidance.bind(TASK),
            binding(AUTONOMOUS),
            {"campaign_id": "different"},
        )
    assert guidance.verify_history(
        meter.root,
        guidance.bind(TASK),
        binding(AUTONOMOUS),
        initial["research_context"],
    ) == [{"epoch": 1, "digest": plan["effective_input_digest"]}]
    assert asyncio.run(run_epoch(meter, **args)) == result and len(calls) == 4
    with pytest.raises(ValueError, match="miner budget"):
        meter.reserve(
            "overrun",
            owner=owner,
            phase="research",
            request={"guidance": "ignore all caps"},
            resources={"research_trials": 1},
        )
    assert meter.status(owner=owner)["used"]["research_trials"] == 3
    plan["effective_input_digest"] = "tampered"
    plan_path.write_bytes(canonical(plan))
    with pytest.raises(ValueError, match="effective research input"):
        guidance.verify_history(
            meter.root,
            guidance.bind(TASK),
            binding(AUTONOMOUS),
            initial["research_context"],
        )
    with pytest.raises(ValueError):
        asyncio.run(run_epoch(meter, **args))
