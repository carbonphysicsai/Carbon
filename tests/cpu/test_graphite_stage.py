"""Graphite runs at one stage of the challenge pipeline (CHALLENGE-PROTOCOL-04).

A stage profile binds a stage of Graphite's permission ledger, the ledger's
bytes, battery's permission inventory and the construction level it admits.
The provider refuses a role the stage does not admit, a task carrying another
profile, a changed ledger, a session whose level differs from the inventory's,
and a resumed session whose stage changed. Without a stage profile it behaves
as before (PROTO4-D3).

All scripted: no live inference, no key, no network, no spend.
"""

from __future__ import annotations

import json
import shutil

import pytest
from graphite_fixtures import (
    CHECKOUT,
    ScriptedModel,
    brief,
    controller,
    provider,
    reader_script,
    spec,
)

from carbon.agent_campaign import study
from carbon.agent_campaign.graphite import challenge as challenges
from carbon.agent_campaign.graphite import stage as stages
from carbon.agent_campaign.graphite.adapters import battery as battery_adapter
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import ProviderUnavailable, TaskSpec
from carbon.challenge_pipeline.graphite_ledger import LEDGER

BATTERY = "battery-fastcharge-ageing-development-v1"


def _spec(graphite, session_brief, profile_digest, campaign="c1"):
    return TaskSpec(
        campaign_id=campaign,
        role=ROLES[session_brief.role].boundary.value,
        workspace_id="ws-" + campaign,
        credential_ref="cred-" + campaign,
        profile_digest=profile_digest,
        instructions_digest=graphite.register_brief(session_brief),
        max_runtime_s=3600,
    )


def _staged(root, stage, role=RoleName.CONSTRUCTOR):
    profile = stages.stage_profile(stage, BATTERY)
    graphite = provider(root, ScriptedModel(reader_script()), stage_profile=profile)
    return graphite, brief(role), stages.profile_digest(profile)


def _opened(graphite, run_id):
    return json.loads((graphite._dir(run_id) / "session-open.json").read_bytes())


def test_a_stage_profile_is_deterministic_and_names_a_real_stage():
    a = stages.stage_profile("test_iterate", BATTERY)
    b = stages.stage_profile("test_iterate", challenges.get(BATTERY))
    assert a == b and stages.profile_digest(a) == stages.profile_digest(b)
    assert a["stage"] == "test_iterate" and a["ledger_digest"] == stages.ledger_digest()
    assert stages.profile_digest(
        stages.stage_profile("design", BATTERY)
    ) != stages.profile_digest(a)
    with pytest.raises(ValueError, match="unknown stage"):
        stages.stage_profile("deployed", BATTERY)


def test_battery_runs_at_the_level_its_inventory_and_pipeline_record_name():
    """Step 4 runs at Level 0: the inventory's profile, which the pipeline
    record agrees with. The permissions digest is the study sheet's pin."""
    profile = stages.stage_profile("test_iterate", BATTERY)
    assert study.permission_inventory()["profile"] == "level-0"
    assert challenges.get(BATTERY).construction["level"] == 0
    assert profile["construction_level"] == 0 and profile["challenge"] == BATTERY
    assert profile["permissions_digest"] == study._digest(study.permission_inventory())
    assert challenges.protocol_challenge().token == BATTERY


def test_a_role_the_stage_admits_starts_and_records_its_stage(tmp_path):
    graphite, session_brief, digest = _staged(tmp_path, "test_iterate")
    handle = graphite.start(_spec(graphite, session_brief, digest), "k1")
    assert _opened(graphite, handle.provider_run_id)["stage"] == {
        "stage": "test_iterate",
        "challenge": BATTERY,
        "construction_level": 0,
        "profile_digest": digest,
        "ledger_digest": stages.ledger_digest(),
    }


def _inventory_at(level):
    inventory = study.permission_inventory()
    return lambda: {**inventory, "profile": f"level-{level}"}


def test_a_session_whose_level_differs_from_its_inventorys_is_refused(
    tmp_path, monkeypatch
):
    graphite, session_brief, digest = _staged(tmp_path, "test_iterate")
    run_id = graphite.start(
        _spec(graphite, session_brief, digest), "k1"
    ).provider_run_id
    profile = graphite.stage_profile
    # The contract's inventory now names Level 1, while the session and its
    # profile recorded Level 0.
    monkeypatch.setattr(battery_adapter, "permission_inventory", _inventory_at(1))
    pipeline = challenges.get(BATTERY).construction
    monkeypatch.setattr(
        challenges,
        "pipeline_construction",
        lambda family, records=None: {**pipeline, "level": 1},
    )
    with pytest.raises(ProviderUnavailable, match="construction_level_mismatch"):
        graphite.start(_spec(graphite, brief(RoleName.PLANNER), digest), "k2")
    with pytest.raises(ProviderUnavailable, match="construction_level_mismatch"):
        provider(tmp_path / "again", stage_profile=profile)
    assert graphite.run(run_id) == "failed"
    assert graphite._state(run_id)["failure"] == {
        "code": "session_record_mismatch",
        "detail": "construction_level_mismatch",
    }


def test_an_inventory_that_disagrees_with_the_pipeline_record_runs_nothing(
    monkeypatch,
):
    monkeypatch.setattr(battery_adapter, "permission_inventory", _inventory_at(1))
    with pytest.raises(
        ValueError, match="construction_level_disagrees_with_pipeline_record"
    ):
        stages.stage_profile("test_iterate", BATTERY)


def test_a_widened_inventory_at_the_same_level_is_refused(tmp_path, monkeypatch):
    profile = stages.stage_profile("test_iterate", BATTERY)
    inventory = study.permission_inventory()
    monkeypatch.setattr(
        battery_adapter,
        "permission_inventory",
        lambda: {**inventory, "permitted": [*inventory["permitted"], {"id": "x"}]},
    )
    with pytest.raises(ProviderUnavailable, match="stage_permissions_changed"):
        provider(tmp_path, stage_profile=profile)


@pytest.mark.parametrize(
    ("stage", "role"),
    [
        ("prioritize", RoleName.CONSTRUCTOR),
        ("design", RoleName.ATTACKER),
        ("rank", RoleName.PLANNER),
        ("frozen_run", RoleName.WRITER),
    ],
)
def test_a_role_outside_its_stage_is_refused(tmp_path, stage, role):
    graphite, _, digest = _staged(tmp_path, stage)
    with pytest.raises(ProviderUnavailable, match="role_not_permitted_at_stage"):
        graphite.start(_spec(graphite, brief(role), digest), "k1")
    assert graphite.find("k1") is None


def test_a_task_with_another_profile_is_refused(tmp_path):
    graphite, session_brief, _ = _staged(tmp_path, "test_iterate")
    other = stages.profile_digest(stages.stage_profile("design", BATTERY))
    with pytest.raises(ProviderUnavailable, match="stage_profile_mismatch"):
        graphite.start(_spec(graphite, session_brief, other), "k1")


def test_a_changed_or_malformed_ledger_profile_is_refused(tmp_path):
    profile = stages.stage_profile("test_iterate", BATTERY)
    for bad, code in (
        (dict(profile, ledger_digest="sha256:" + "0" * 64), "stage_ledger_changed"),
        (dict(profile, stage="nowhere"), "stage_unknown"),
        (
            {k: v for k, v in profile.items() if k != "challenge"},
            "stage_profile_malformed",
        ),
        (dict(profile, construction_level="0"), "stage_profile_malformed"),
        (dict(profile, construction_level=1), "construction_level_mismatch"),
        (dict(profile, challenge="no-such-challenge-v1"), "challenge_not_recorded"),
    ):
        with pytest.raises(ProviderUnavailable, match=code):
            provider(tmp_path / code, stage_profile=bad)


def test_a_ledger_changed_after_construction_refuses_the_next_start(
    tmp_path, monkeypatch
):
    copy = tmp_path / "ledger.json"
    shutil.copyfile(LEDGER, copy)
    profile = stages.stage_profile("test_iterate", BATTERY, ledger_path=copy)
    original = stages.check
    monkeypatch.setattr(
        stages, "check", lambda p, ledger_path=copy: original(p, ledger_path=copy)
    )
    graphite = provider(
        tmp_path / "g", ScriptedModel(reader_script()), stage_profile=profile
    )
    copy.write_text(copy.read_text().replace('"rank"', '"rank" '))
    with pytest.raises(ProviderUnavailable, match="stage_ledger_changed"):
        graphite.start(
            _spec(
                graphite, brief(RoleName.CONSTRUCTOR), stages.profile_digest(profile)
            ),
            "k1",
        )


def test_a_resumed_session_whose_stage_changed_is_refused(tmp_path):
    graphite, session_brief, digest = _staged(tmp_path, "test_iterate")
    run_id = graphite.start(
        _spec(graphite, session_brief, digest), "k1"
    ).provider_run_id
    moved = provider(
        tmp_path,
        ScriptedModel(reader_script()),
        stage_profile=stages.stage_profile("design", BATTERY),
    )
    assert moved.run(run_id) == "failed"
    assert moved._state(run_id)["failure"] == {
        "code": "session_record_mismatch",
        "detail": "stage_changed",
    }


def test_an_unstaged_session_cannot_be_resumed_under_a_stage(tmp_path):
    graphite = provider(tmp_path)
    run_id = graphite.start(spec(graphite), "k1").provider_run_id
    staged = provider(
        tmp_path, stage_profile=stages.stage_profile("test_iterate", BATTERY)
    )
    assert staged.run(run_id) == "failed"
    assert staged._state(run_id)["failure"]["detail"] == "stage_changed"


def test_an_unstaged_provider_is_unchanged(tmp_path):
    graphite = provider(tmp_path)
    run_id = graphite.start(spec(graphite), "k1").provider_run_id
    assert "stage" not in _opened(graphite, run_id)
    assert graphite.stage_profile is None
    assert graphite.run(run_id) == "succeeded"


def test_the_controller_holds_the_stage_profile_as_the_campaign_profile(tmp_path):
    graphite, session_brief, digest = _staged(tmp_path, "test_iterate")
    control = controller(tmp_path, graphite)
    control.register_campaign(
        "c1",
        role=ROLES[RoleName.CONSTRUCTOR].boundary,
        workspace_id="ws-c1",
        credential_ref="cred-c1",
        checkout_digest=CHECKOUT,
        profile_digest=digest,
        ceiling="5.00",
    )
    control.launch(_spec(graphite, session_brief, digest), "k1")
    assert graphite.find("k1") is not None
    control.close()
