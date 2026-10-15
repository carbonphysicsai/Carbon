"""T07 base selection without ladder activation or historical replay changes."""

import copy
import json
from types import SimpleNamespace

import pytest
import test_miner_launchpad_runner as fixture

from carbon.development_session import construction_level as cl
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction import capability_registry as cr
from scripts.dev.miner_launchpad import levels, operations
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.runner import RunnerAdapter

CHALLENGE = {"id": cr.BATTERY_CHALLENGE, "version": "1.0"}
BASE = cr.contract(cr.BATTERY_CHALLENGE).digest


def request(**changes):
    return {"construction_variant_digest": BASE, **changes}


@pytest.mark.parametrize("agent", ["none", "graphite"])
def test_base_subject_never_resolves_or_compiles_a_composition(agent, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("base selection must not enter the composition path")

    monkeypatch.setattr(cl, "resolve_composition", forbidden)
    monkeypatch.setattr(cl, "RUN", forbidden)
    monkeypatch.setattr(cl, "READ_TARGET", forbidden)
    for hint in ({}, {"construction_level": 0}, {"construction_level": None}):
        assert levels.launch_binding(request(**hint), CHALLENGE, agent, {}) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"construction_level": 1},
        {"construction_level": 4},
        {"construction_level": False},
        {"construction_level": "0"},
        {"arm": "signed"},
        {"construction_variant_digest": "sha256:" + "0" * 64},
        {"construction_variant_digest": None},
        {"construction_variant_digest": {}},
    ],
)
def test_base_selection_refuses_conflicting_or_unregistered_subjects(changes):
    with pytest.raises(Rejected, match="construction_variant_invalid"):
        levels.launch_binding(request(**changes), CHALLENGE, "none", {})


def test_foreign_challenge_cannot_claim_the_battery_base_subject():
    foreign = {"id": cr.BURGERS_CHALLENGE, "version": "1.0"}
    with pytest.raises(Rejected, match="construction_variant_invalid"):
        levels.launch_binding(request(), foreign, "none", {})


def test_base_subject_keeps_widened_fields_under_the_real_base_compiler():
    from carbon.reconstruction.challenge_contracts import validate_for_challenge

    found = levels.launch_binding(request(), CHALLENGE, "none", {})
    strategy = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE["id"],
        "backbone": "mlp",
        "parameters": {"muon_spectral": True},
    }
    unchanged = levels.checked_strategy(found, strategy)
    result = validate_for_challenge(unchanged)
    assert any("muon_spectral" in issue.path for issue in result.errors)


def test_base_replay_refuses_a_changed_current_contract(monkeypatch):
    captured = levels.capture_binding(None, selector=BASE)
    monkeypatch.setattr(cr, "contract", lambda *args: SimpleNamespace(digest="changed"))
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.replay_binding(request(), CHALLENGE, "none", {}, captured)


def test_base_capture_is_prospective_and_cannot_downgrade_or_change_subject():
    captured = levels.capture_binding(None, selector=BASE)
    assert levels.capture_version(captured) == 3
    row = {
        "construction_binding_version": 3,
        "construction_binding_digest": digest(canonical(captured)),
    }
    assert levels.checked_capture(row, captured) == captured
    assert levels.replay_binding(request(), CHALLENGE, "none", {}, captured) is None
    for version in (0, 1, 2, True):
        with pytest.raises(Rejected, match="launch_record_differs"):
            levels.checked_capture(
                {**row, "construction_binding_version": version}, captured
            )
    for change in ({}, {"construction_variant_digest": levels.STANDALONE_GRAPH_V3}):
        with pytest.raises(Rejected, match="launch_record_differs"):
            levels.replay_binding(change, CHALLENGE, "none", {}, captured)
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.replay_binding(request(arm="signed"), CHALLENGE, "none", {}, captured)
    changed = copy.deepcopy(captured)
    changed["binding"] = {"digest": BASE}
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.checked_capture(
            {**row, "construction_binding_digest": digest(canonical(changed))}, changed
        )
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.checked_capture(row, None)


def test_existing_composition_and_graph_records_keep_their_subjects():
    composed = cl.with_target(cl.resolve_composition(CHALLENGE["id"]), None)
    composition = levels.capture_binding(composed)
    assert levels.capture_version(composition) == 1
    assert levels.replay_binding({}, CHALLENGE, "none", None, composition) == composed
    graph = cl.with_target(cl.resolve(CHALLENGE["id"], 4), None)
    selected = levels.capture_binding(graph, selector=levels.STANDALONE_GRAPH_V3)
    assert levels.capture_version(selected) == 2
    assert (
        levels.replay_binding(
            {"construction_variant_digest": levels.STANDALONE_GRAPH_V3},
            CHALLENGE,
            "graphite",
            None,
            selected,
        )
        == graph
    )
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.replay_binding(request(), CHALLENGE, "none", None, composition)


def test_base_writer_persists_subject_and_restart_replay_does_not_dispatch(
    tmp_path, monkeypatch
):
    cfg = fixture.configured(tmp_path)
    host = RunnerAdapter(tmp_path / "launch.sqlite3", principal="alice")
    monkeypatch.setattr(operations, "_registered", lambda *args: fixture.registered())
    monkeypatch.setattr(operations, "_signer_reachable", lambda *args: None)
    dispatches = []
    monkeypatch.setattr(host, "_dispatch_run", lambda *args: dispatches.append(args))
    body = {
        "agent": "none",
        "challenge": CHALLENGE["id"],
        "challenge_version": CHALLENGE["version"],
        "idempotency_key": "base-t07-public-fixture",
        **request(),
    }
    try:
        admitted = SimpleNamespace(profile=cfg, miner=fixture.registered())
        answer = host.launch_admitted(admitted, body)
        with host.db() as db:
            row = dict(
                db.execute(
                    "SELECT * FROM launchpad_campaigns WHERE id=?", (answer["id"],)
                ).fetchone()
            )
        assert row["construction_binding_version"] == 3
        captured = json.loads(row["launch_request"])[levels.CONSTRUCTION_ADMISSION]
        assert captured == levels.capture_binding(None, selector=BASE)
        assert row["construction_binding_digest"] == digest(canonical(captured))
        assert levels.campaign_binding(row, cfg) is None
        restarted = RunnerAdapter(host.database, principal="alice")
        try:
            replay_dispatches = []
            monkeypatch.setattr(
                restarted, "_dispatch_run", lambda *args: replay_dispatches.append(args)
            )
            assert restarted._recorded_launch(row, cfg)[1] is None
            assert restarted.replayed(cfg, body)["id"] == answer["id"]
            assert not replay_dispatches
        finally:
            restarted.close()
        assert len(dispatches) == 1
    finally:
        host.close()
