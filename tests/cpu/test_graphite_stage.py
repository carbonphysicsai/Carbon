"""Graphite runs at one stage of the challenge pipeline (CHALLENGE-PROTOCOL-04).

A stage profile binds a stage of Graphite's permission ledger, the ledger's
bytes and battery's permission inventory. The provider refuses a role the
stage does not admit, a task carrying another profile, a changed ledger, and
a resumed session whose stage changed. Without a stage profile it behaves as
before (PROTO4-D3).

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

from carbon.agent_campaign.graphite import stage as stages
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import ProviderUnavailable, TaskSpec
from carbon.challenge_pipeline.graphite_ledger import LEDGER


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
    profile = stages.stage_profile(stage)
    graphite = provider(root, ScriptedModel(reader_script()), stage_profile=profile)
    return graphite, brief(role), stages.profile_digest(profile)


def _opened(graphite, run_id):
    return json.loads((graphite._dir(run_id) / "session-open.json").read_bytes())


def test_a_stage_profile_is_deterministic_and_names_a_real_stage():
    a, b = stages.stage_profile("test_iterate"), stages.stage_profile("test_iterate")
    assert a == b and stages.profile_digest(a) == stages.profile_digest(b)
    assert a["stage"] == "test_iterate" and a["ledger_digest"] == stages.ledger_digest()
    assert stages.profile_digest(
        stages.stage_profile("design")
    ) != stages.profile_digest(a)
    with pytest.raises(ValueError, match="unknown stage"):
        stages.stage_profile("deployed")


def test_a_role_the_stage_admits_starts_and_records_its_stage(tmp_path):
    graphite, session_brief, digest = _staged(tmp_path, "test_iterate")
    handle = graphite.start(_spec(graphite, session_brief, digest), "k1")
    assert _opened(graphite, handle.provider_run_id)["stage"] == {
        "stage": "test_iterate",
        "profile_digest": digest,
        "ledger_digest": stages.ledger_digest(),
    }


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
    other = stages.profile_digest(stages.stage_profile("design"))
    with pytest.raises(ProviderUnavailable, match="stage_profile_mismatch"):
        graphite.start(_spec(graphite, session_brief, other), "k1")


def test_a_changed_or_malformed_ledger_profile_is_refused(tmp_path):
    profile = stages.stage_profile("test_iterate")
    for bad, code in (
        (dict(profile, ledger_digest="sha256:" + "0" * 64), "stage_ledger_changed"),
        (dict(profile, stage="nowhere"), "stage_unknown"),
        (
            {k: v for k, v in profile.items() if k != "challenge"},
            "stage_profile_malformed",
        ),
    ):
        with pytest.raises(ProviderUnavailable, match=code):
            provider(tmp_path / code, stage_profile=bad)


def test_a_ledger_changed_after_construction_refuses_the_next_start(
    tmp_path, monkeypatch
):
    copy = tmp_path / "ledger.json"
    shutil.copyfile(LEDGER, copy)
    profile = stages.stage_profile("test_iterate", ledger_path=copy)
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
        stage_profile=stages.stage_profile("design"),
    )
    assert moved.run(run_id) == "failed"
    assert moved._state(run_id)["failure"] == {
        "code": "session_record_mismatch",
        "detail": "stage_changed",
    }


def test_an_unstaged_session_cannot_be_resumed_under_a_stage(tmp_path):
    graphite = provider(tmp_path)
    run_id = graphite.start(spec(graphite), "k1").provider_run_id
    staged = provider(tmp_path, stage_profile=stages.stage_profile("test_iterate"))
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
