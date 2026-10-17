"""Prospective direct-recipe launch identity; no worker or chain action."""

import copy
import json
from types import SimpleNamespace

import pytest

from carbon.development_session.profile import canonical, digest
from scripts.dev.miner_launchpad import levels, operations
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.runner import RunnerAdapter

CHALLENGE = {"id": "battery-fastcharge-ageing-development-v1", "version": "1.0"}


def _capture():
    return levels.capture_direct_campaign(CHALLENGE)


def test_new_launch_schema_has_no_level_arm_or_variant_selector():
    launch = operations.OPERATIONS["launch"]
    retired = {"construction_level", "arm", "construction_variant_digest"}
    assert not retired & (launch.required | launch.optional)
    assert launch.replay_optional == retired


def test_old_selector_can_only_replay_an_existing_launch():
    class Host:
        def __init__(self, result):
            self.result = result

        def configured(self):
            return {"profile_id": "test"}

        def replayed(self, profile, request, operation):
            assert operation == "launch"
            return self.result

    request = {"agent": "none", "idempotency_key": "old", "construction_level": 0}
    assert operations.perform(Host({"campaign": "prior"}), "launch", request) == {
        "campaign": "prior"
    }
    with pytest.raises(Rejected, match="construction_selector_retired"):
        operations.perform(Host(None), "launch", request)


def test_v4_practice_never_falls_through_to_legacy_base(monkeypatch):
    monkeypatch.setattr(levels, "campaign_is_direct", lambda row, cfg: True)
    direct = []
    host = SimpleNamespace(
        _require_current_revision=lambda admitted: None,
        _direct_recipe=lambda admitted, strategy: direct.append(strategy),
        _design_refusal=lambda strategy: pytest.fail("legacy design admission ran"),
    )
    admitted = SimpleNamespace(campaign={}, profile={})
    strategy = {"schema": "direct-recipe"}
    RunnerAdapter._practice_gates(host, admitted, strategy)
    assert direct == [strategy]


def test_direct_task_refused_before_queue_on_legacy_provider():
    from test_battery_direct_practice import _recipe

    from carbon.development_session.research_tasks import PublicDevelopmentResearchTasks
    from carbon.research.errors import ResearchServiceErrorCode
    from carbon.research.lifecycle import ResearchTaskProviderError
    from carbon.research.model import DirectPracticeTaskSpecV1

    provider = object.__new__(PublicDevelopmentResearchTasks)
    provider._executor = SimpleNamespace(
        executor=SimpleNamespace(practice=SimpleNamespace(construction_mode=None))
    )
    request = SimpleNamespace(
        task_spec=DirectPracticeTaskSpecV1(
            "carbon.direct-practice.v1", _recipe("sha256:" + "a" * 64)
        )
    )
    with pytest.raises(ResearchTaskProviderError) as refused:
        provider._resolve_start(request)
    assert refused.value.code is ResearchServiceErrorCode.REQUEST_TYPE_INVALID


def test_direct_capture_is_versioned_and_bound_to_its_exact_bytes():
    captured = _capture()
    row = {
        "construction_binding_version": 4,
        "construction_binding_digest": digest(canonical(captured)),
    }
    assert levels.checked_capture(row, captured) == captured
    changed = copy.deepcopy(captured)
    changed["challenge"]["version"] = "2.0"
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.checked_capture(row, changed)


def test_direct_replay_refuses_legacy_selector_or_challenge_drift(monkeypatch):
    captured = _capture()
    monkeypatch.setattr(
        levels, "_cl", lambda: pytest.fail("direct replay imported legacy levels")
    )
    assert levels.replay_binding({}, CHALLENGE, "none", {}, captured) is None
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.replay_binding({"arm": "inert_fields"}, CHALLENGE, "none", {}, captured)
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.replay_binding({}, {**CHALLENGE, "version": "2.0"}, "none", {}, captured)


def test_prepared_manifest_must_match_direct_mode_and_challenge(tmp_path, monkeypatch):
    captured = _capture()
    row = {
        "root": str(tmp_path),
        "construction_binding_version": 4,
        "construction_binding_digest": digest(canonical(captured)),
        "launch_request": json.dumps(
            {
                "challenge": CHALLENGE["id"],
                "challenge_version": CHALLENGE["version"],
                "agent": "none",
                levels.CONSTRUCTION_ADMISSION: captured,
            }
        ),
    }
    manifest = tmp_path / "campaign-manifest.json"
    manifest.write_text(
        json.dumps({"construction_mode": "direct", "challenge": CHALLENGE}),
        encoding="utf-8",
    )
    assert levels.campaign_is_direct(row, {}) is True
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.campaign_is_direct({**row, "launch_request": None}, {})
    monkeypatch.setattr(
        levels, "_cl", lambda: pytest.fail("direct campaign imported legacy levels")
    )
    assert levels.campaign_binding(row, {}) is None
    manifest.write_text(
        json.dumps(
            {
                "construction_mode": "direct",
                "challenge": {**CHALLENGE, "version": "2.0"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.campaign_is_direct(row, {})
