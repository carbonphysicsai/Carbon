"""#504's Constructor runs staged, like the Attacker (CHALLENGE-PROTOCOL-04,
PROTO4-D11; OWNER-CHALLENGE-STEP4-01, third amendment: revision 1).

The Constructor campaign's profile, and every task's, is the stage profile of
`test_iterate` composed with #504's own Level-0 permission profile. A staged
Constructor is refused for a role outside its stage's ledger row, at a
construction level that differs from the inventory's, and under a changed
ledger. The runner refuses an unstaged provider and a stale permission
profile.

All scripted: no live inference, no pod, no key, no network, no spend.
"""

from __future__ import annotations

import shutil

import pytest
from graphite_phase3_fixtures import (
    ScriptedPods,
    brief,
    controller,
    provider,
    run_id,
    session,
    text,
)

from carbon.agent_campaign import study
from carbon.agent_campaign.graphite import challenge as challenges
from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite import stage as stages
from carbon.agent_campaign.graphite.adapters import battery as battery_adapter
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import ProviderUnavailable, TaskSpec
from carbon.challenge_pipeline.graphite_ledger import LEDGER

BATTERY = "battery-fastcharge-ageing-development-v1"


def _spec(graphite):
    return TaskSpec(
        campaign_id=phase3.CAMPAIGN,
        role=ROLES[RoleName.CONSTRUCTOR].boundary.value,
        workspace_id=phase3.WORKSPACE,
        credential_ref=phase3.CREDENTIAL_REF,
        profile_digest=phase3.campaign_profile(graphite),
        instructions_digest=graphite.register_brief(brief(graphite)),
        max_runtime_s=graphite.grant.max_runtime_s,
    )


def _open(graphite):
    return graphite.start(_spec(graphite), phase3.session_key(1)).provider_run_id


def test_the_campaign_profile_composes_the_stage_with_504s_own():
    document, own = phase3.permission_profile()
    profile = phase3.staged_profile()
    assert profile["runner_profile"] == document
    assert profile["stage"] == "test_iterate"
    assert profile["construction_level"] == document["level"] == 0
    assert profile["challenge"] == BATTERY
    assert document["construction_contract"]["challenge"] == BATTERY
    assert profile["permissions_digest"] == study._digest(study.permission_inventory())
    assert stages.profile_digest(profile) != own
    # The Attacker has no permission profile of its own to compose.
    assert stages.stage_profile("test_iterate", BATTERY)["runner_profile"] is None


def test_a_staged_constructor_session_runs_and_records_its_stage(tmp_path):
    result, graphite, _ = session(tmp_path, [text("done")], ScriptedPods())
    assert result["provider_state"] == "succeeded"
    opened = graphite._opened(run_id())
    assert opened["stage"]["stage"] == "test_iterate"
    assert opened["stage"]["construction_level"] == 0
    composed = stages.profile_digest(phase3.staged_profile())
    assert opened["task"]["profile_digest"] == composed
    assert opened["stage"]["profile_digest"] == composed


def test_a_staged_constructor_outside_its_stage_row_is_refused(tmp_path):
    graphite = provider(
        tmp_path,
        [text("never")],
        ScriptedPods(),
        stage_profile=phase3.staged_profile("prioritize"),
    )
    control = controller(tmp_path, graphite)
    try:
        result = phase3.run_session(control, graphite, brief(graphite), 1)
    finally:
        control.close()
    assert result["provider_state"] is None
    assert graphite.find(phase3.session_key(1)) is None
    assert graphite.model.requests == []
    with pytest.raises(ProviderUnavailable, match="role_not_permitted_at_stage"):
        _open(graphite)


def _level_one(monkeypatch):
    inventory = study.permission_inventory()
    monkeypatch.setattr(
        battery_adapter,
        "permission_inventory",
        lambda: {**inventory, "profile": "level-1"},
    )
    pipeline = challenges.get(BATTERY).construction
    monkeypatch.setattr(
        challenges,
        "pipeline_construction",
        lambda family, records=None: {**pipeline, "level": 1},
    )


def test_a_staged_constructor_at_another_level_is_refused(tmp_path, monkeypatch):
    profile = phase3.staged_profile()
    graphite = provider(tmp_path, [text("done")], ScriptedPods(), stage_profile=profile)
    opened = _open(graphite)
    _level_one(monkeypatch)
    with pytest.raises(ProviderUnavailable, match="construction_level_mismatch"):
        provider(tmp_path / "again", [], ScriptedPods(), stage_profile=profile)
    assert graphite.run(opened) == "failed"
    assert graphite._state(opened)["failure"] == {
        "code": "session_record_mismatch",
        "detail": "construction_level_mismatch",
    }
    # #504's runner constructs at Level 0, so it composes with no other level.
    with pytest.raises(ValueError, match="runner_profile_level_differs"):
        phase3.staged_profile()


def test_a_staged_constructor_under_a_changed_ledger_is_refused(tmp_path, monkeypatch):
    copy = tmp_path / "ledger.json"
    shutil.copyfile(LEDGER, copy)
    document, _ = phase3.permission_profile()
    profile = stages.stage_profile(
        "test_iterate", BATTERY, runner_profile=document, ledger_path=copy
    )
    original = stages.check
    monkeypatch.setattr(
        stages, "check", lambda p, ledger_path=copy: original(p, ledger_path=copy)
    )
    graphite = provider(
        tmp_path, [text("never")], ScriptedPods(), stage_profile=profile
    )
    copy.write_text(copy.read_text().replace('"rank"', '"rank" '))
    with pytest.raises(ProviderUnavailable, match="stage_ledger_changed"):
        _open(graphite)
    assert graphite.find(phase3.session_key(1)) is None


def test_an_unstaged_constructor_cannot_be_started_through_the_runner(tmp_path):
    graphite = provider(tmp_path, [text("never")], ScriptedPods(), stage_profile=None)
    control = controller(tmp_path, graphite)
    try:
        with pytest.raises(ProviderUnavailable, match="stage_profile_required"):
            phase3.run_session(control, graphite, brief(graphite), 1)
        assert phase3.CAMPAIGN not in control.budget()["campaigns"]
    finally:
        control.close()
    assert graphite.find(phase3.session_key(1)) is None
    assert graphite.model.requests == []


def test_a_stale_constructor_permission_profile_is_refused(tmp_path, monkeypatch):
    graphite = provider(tmp_path, [text("never")], ScriptedPods())
    document, own = phase3.permission_profile()
    monkeypatch.setattr(
        phase3, "permission_profile", lambda: ({**document, "widens": ["x"]}, own)
    )
    with pytest.raises(ProviderUnavailable, match="runner_profile_changed"):
        phase3.campaign_profile(graphite)


def test_a_runner_profile_names_its_level_and_its_challenge():
    document, _ = phase3.permission_profile()
    with pytest.raises(ValueError, match="runner_profile_names_no_level"):
        stages.stage_profile("test_iterate", BATTERY, runner_profile={"surface": "x"})
    other = {
        **document,
        "construction_contract": {
            **document["construction_contract"],
            "challenge": "burgers-dynamics-v1",
        },
    }
    with pytest.raises(ValueError, match="runner_profile_for_another_challenge"):
        stages.stage_profile("test_iterate", BATTERY, runner_profile=other)
