"""S3 Launchpad composition identity and replay; no host, chain or spend.

The child compile and durable launch writer are real. Intake facts,
registration and dispatch are inert public fixtures.
"""

import copy
import json
import shutil
from types import SimpleNamespace

import pytest
import test_miner_launchpad_runner as runner_fixture
from composition_check_fixtures import accepted_fixture_checks
from test_composition_ladder import strategy

from carbon.battery import campaign
from carbon.battery.daemon import development_commitment_digest
from carbon.development_session import construction_level as cl
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import composition_registry as metadata
from carbon.reconstruction import development_composition as dc
from scripts.dev.miner_launchpad import levels, operations
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.runner import RunnerAdapter

BATTERY = cr.BATTERY_CHALLENGE
CHALLENGE = {"id": BATTERY, "version": "1.0"}
URL = "http://127.0.0.1:9/carbon/v1/battery/intake"
CFG = {"intakes": {BATTERY: URL}}


def bound():
    return cl.with_target(cl.resolve_composition(BATTERY), URL)


def facts(found):
    return {
        "served_contracts": [
            {
                "level": None,
                "kind": "composition",
                "variant": found["variant"],
                "digest": found["digest"],
            }
        ]
    }


@pytest.fixture(autouse=True)
def compiled_cache():
    cl._compiled.cache_clear()
    yield
    cl._compiled.cache_clear()


def test_new_launch_uses_composition_without_a_level_or_agent_permission():
    expected = bound()
    for agent in ("none", "graphite", "own"):
        for hint in (None, 0, 1, 4):
            request = {} if hint is None else {"construction_level": hint}
            assert levels.launch_binding(request, CHALLENGE, agent, CFG) == expected
    assert expected["level"] is None and expected["kind"] == "composition"
    assert levels.launch_binding({}, CHALLENGE, "none", CFG, legacy=True) is None


def standalone():
    return cl.with_target(cl.resolve(BATTERY, 4), URL)


def selected_request(**changes):
    return {"construction_variant_digest": levels.STANDALONE_GRAPH_V3, **changes}


def test_explicit_development_subject_binds_registered_standalone_graph():
    found = standalone()
    assert found["digest"] == levels.STANDALONE_GRAPH_V3
    assert found["level"] == 4 and found["scope"] == "DEVELOPMENT"
    for hint in ({}, {"construction_level": 4}):
        assert (
            levels.launch_binding(selected_request(**hint), CHALLENGE, "graphite", CFG)
            == found
        )
    assert (
        levels.launch_binding({"construction_level": 4}, CHALLENGE, "graphite", CFG)
        == bound()
    )


def test_selected_subject_cannot_compile_without_exact_target_service(monkeypatch):
    calls = []
    monkeypatch.setattr(cl, "READ_TARGET", lambda *args: {"served_contracts": []})
    monkeypatch.setattr(cl, "RUN", lambda request: calls.append(request))
    with pytest.raises(cl.LevelRefused, match="level_compile_not_served_by_target"):
        cl.compile_strategy(standalone(), strategy())
    assert calls == []


@pytest.mark.parametrize(
    "launch_request,challenge,agent",
    [
        (
            selected_request(construction_variant_digest="sha256:" + "0" * 64),
            CHALLENGE,
            "graphite",
        ),
        (selected_request(construction_variant_digest=4), CHALLENGE, "graphite"),
        (selected_request(construction_variant_digest=None), CHALLENGE, "graphite"),
        (
            selected_request(),
            {"id": cr.BURGERS_CHALLENGE, "version": "1.0"},
            "graphite",
        ),
        (selected_request(), CHALLENGE, "none"),
        (selected_request(arm="inert_fields"), CHALLENGE, "graphite"),
        (selected_request(construction_level=3), CHALLENGE, "graphite"),
        (selected_request(construction_level=True), CHALLENGE, "graphite"),
    ],
)
def test_explicit_subject_refuses_wrong_scope_before_dispatch(
    launch_request, challenge, agent
):
    with pytest.raises(Rejected, match="construction_variant_invalid"):
        levels.launch_binding(launch_request, challenge, agent, CFG)


def test_selected_capture_is_versioned_and_replay_cannot_change_subject():
    found = standalone()
    request = selected_request(construction_level=4)
    captured = levels.capture_binding(found, selector=levels.STANDALONE_GRAPH_V3)
    row = {
        "construction_binding_version": 2,
        "construction_binding_digest": digest(canonical(captured)),
    }
    assert levels.checked_capture(row, captured) == captured
    assert levels.replay_binding(request, CHALLENGE, "graphite", CFG, captured) == found
    for changed in (
        {"construction_level": 4},
        selected_request(construction_level=3),
        selected_request(construction_variant_digest="sha256:" + "0" * 64),
    ):
        with pytest.raises(Rejected, match="launch_record_differs"):
            levels.replay_binding(changed, CHALLENGE, "graphite", CFG, captured)
    wrong_binding = copy.deepcopy(captured)
    wrong_binding["binding"]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.checked_capture(row, wrong_binding)
    old = levels.capture_binding(bound())
    assert levels.replay_binding({}, CHALLENGE, "graphite", CFG, old) == bound()
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.replay_binding(request, CHALLENGE, "graphite", CFG, old)


def test_selected_launch_writer_persists_subject_and_replays_before_dispatch(
    tmp_path, monkeypatch
):
    cfg = runner_fixture.configured(tmp_path)
    cfg.update(CFG)
    host = RunnerAdapter(tmp_path / "launch.sqlite3", principal="alice")
    dispatches = []
    monkeypatch.setattr(host, "_dispatch_run", lambda *args: dispatches.append(args))
    monkeypatch.setattr(
        host,
        "_graphite_choice",
        lambda *args, **kwargs: {
            "mode": "FULL",
            "research_share": 0.1,
            "plan": None,
            "hunt": None,
            "limits": {},
            "curation_digest": "sha256:" + "1" * 64,
        },
    )
    monkeypatch.setattr(
        operations, "_registered", lambda *args: runner_fixture.registered()
    )
    monkeypatch.setattr(operations, "_signer_reachable", lambda *args: None)
    request = {
        "challenge": BATTERY,
        "challenge_version": "1.0",
        "agent": "graphite",
        "idempotency_key": "standalone-graph-v3-fixture",
        **selected_request(),
    }
    try:
        admitted = SimpleNamespace(profile=cfg, miner=runner_fixture.registered())
        answer = host.launch_admitted(admitted, request)
        with host.db() as db:
            row = dict(
                db.execute(
                    "SELECT * FROM launchpad_campaigns WHERE id=?", (answer["id"],)
                ).fetchone()
            )
        captured = json.loads(row["launch_request"])[levels.CONSTRUCTION_ADMISSION]
        assert row["construction_binding_version"] == 2
        assert captured == levels.capture_binding(
            standalone(), selector=levels.STANDALONE_GRAPH_V3
        )
        assert row["construction_binding_digest"] == digest(canonical(captured))
        assert len(dispatches) == 1
        assert levels.campaign_binding(row, cfg) == standalone()
        assert levels.campaign_binding(row) == standalone()
        assert (
            levels.campaign_slot(standalone(), {})["variant"]["digest"]
            == levels.STANDALONE_GRAPH_V3
        )
        assert host.replayed(cfg, request)["id"] == answer["id"]
        with pytest.raises(Rejected, match="research_launch_replay_conflict"):
            host.replayed(
                cfg, {**request, "construction_variant_digest": "sha256:" + "0" * 64}
            )
        _, choice = host._recorded_launch(row, cfg)
        assert choice.construction_level == standalone()
        changed = copy.deepcopy(row)
        recorded = json.loads(changed["launch_request"])
        recorded["construction_variant_digest"] = "sha256:" + "0" * 64
        changed["launch_request"] = canonical(recorded)
        with pytest.raises(Rejected, match="launch_record_differs"):
            host._recorded_launch(changed, cfg)
        assert len(dispatches) == 1
    finally:
        host.close()


def test_fixture_check_compile_returns_all_parts_and_the_actual_derived_summary(
    monkeypatch,
    accepted_fixture_checks,
):
    found = bound()
    monkeypatch.setattr(cl, "READ_TARGET", lambda *args: facts(found))
    value = cl.compile_strategy(found, strategy())
    direct = dc.compile(strategy())
    assert value["development"] == direct.development
    assert value["derived"] == direct.derived
    assert value["variant_digest"] == found["digest"]
    assert len(value["derived"]["changes"]) == 3 and value["derived"]["level"] == 3
    base = levels.checked_strategy(found, strategy())
    assert not {"muon_spectral", "quasi_newton_family", "line_search"} & set(
        base["parameters"]
    )


def test_receiver_level_label_cannot_allow_or_block_a_composition(monkeypatch):
    found = bound()
    for label in (None, 1, 999, False):
        listed = facts(found)
        listed["served_contracts"][0]["level"] = label
        assert cl.lists(listed, found)
        assert cl.lists_digest(listed, found["digest"])
    calls = []
    monkeypatch.setattr(cl, "RUN", lambda request: calls.append(request))
    for changed in (
        {"served_contracts": []},
        {
            "served_contracts": [
                {**facts(found)["served_contracts"][0], "digest": "sha256:" + "0" * 64}
            ]
        },
    ):
        monkeypatch.setattr(cl, "READ_TARGET", lambda *args, changed=changed: changed)
        with pytest.raises(cl.LevelRefused, match="level_compile_not_served_by_target"):
            cl.compile_strategy(found, strategy())
    assert calls == []


def test_freeze_and_commit_bind_exact_composition_and_original_recipe(
    monkeypatch, accepted_fixture_checks
):
    found = bound()
    monkeypatch.setattr(cl, "READ_TARGET", lambda *args: facts(found))
    compiled, envelope = cl.check_freeze(found, strategy())
    assert envelope is None
    record = cl.candidate_record(
        found, strategy(), "public fixture practice", False, compiled
    )
    assert record["construction_level"]["level"] == 3
    assert record["construction_level"]["summary"] == compiled["derived"]["summary"]
    manifest = {
        "contract_digest": cr.contract_digest(BATTERY),
        "construction_level": found,
    }
    expected = development_commitment_digest(
        BATTERY, found["digest"], compiled["commitment_strategy_hash"], strategy()
    )
    assert campaign.frozen_commitment(record, manifest) == expected
    altered = copy.deepcopy(record)
    altered["strategy"]["parameters"]["muon_spectral"] = False
    assert campaign.frozen_commitment(altered, manifest) != expected
    altered["contract_digest"] = cr.contract_digest(BATTERY)
    with pytest.raises(ValueError):
        campaign.frozen_commitment(altered, manifest)


def test_replay_keeps_historical_pinned_composition_after_default_changes(
    tmp_path, monkeypatch
):
    found = bound()
    captured = levels.capture_binding(found)
    shutil.copytree(metadata.DIRECTORY, tmp_path / "compositions")
    directory = tmp_path / "compositions"
    registry = metadata.registry(directory)
    document = metadata.document(found["digest"], directory)
    document["version"] = "battery-construction-fixture-next"
    registry["versions"][document["version"]] = digest(canonical(document))
    registry["current"][BATTERY] = document["version"]
    (directory / (document["version"] + ".json")).write_bytes(canonical(document))
    (directory / "registry.json").write_bytes(canonical(registry))
    monkeypatch.setattr(metadata, "DIRECTORY", directory)
    monkeypatch.setattr(dc, "DIRECTORY", directory)
    assert cl.resolve_composition(BATTERY)["digest"] != found["digest"]
    assert levels.replay_binding({}, CHALLENGE, "none", CFG, captured) == found
    assert cl.still_registered(found)["digest"] == found["digest"]


@pytest.mark.parametrize(
    "mutation",
    ["missing", "digest", "challenge", "extra", "version", "legacy_with_capture"],
)
def test_new_writer_capture_cannot_disappear_or_change_into_a_legacy_launch(mutation):
    captured = levels.capture_binding(bound())
    row = {
        "construction_binding_version": 1,
        "construction_binding_digest": digest(canonical(captured)),
    }
    changed = copy.deepcopy(captured)
    if mutation == "missing":
        changed = None
    elif mutation == "digest":
        changed["binding"]["digest"] = "sha256:" + "0" * 64
    elif mutation == "challenge":
        changed["binding"]["challenge"] = cr.BURGERS_CHALLENGE
    elif mutation == "extra":
        changed["authority"] = "invented"
    elif mutation == "version":
        row["construction_binding_version"] = True
    else:
        row["construction_binding_version"] = 0
    with pytest.raises(Rejected, match="launch_record_differs"):
        levels.checked_capture(row, changed)


def test_clients_cannot_supply_the_writer_capture_or_receipt_fields():
    request = {
        "challenge": BATTERY,
        "challenge_version": "1.0",
        "agent": "none",
        "idempotency_key": "fixture-launch-key",
    }
    for key in (
        levels.CONSTRUCTION_ADMISSION,
        "construction_binding_version",
        "construction_binding_digest",
    ):
        with pytest.raises(Rejected, match="closed_request_required"):
            operations.perform(SimpleNamespace(), "launch", {**request, key: {}})


def test_real_launch_writer_versions_capture_and_replay_before_dispatch(
    tmp_path, monkeypatch
):
    cfg = runner_fixture.configured(tmp_path)
    cfg.update(CFG)
    host = RunnerAdapter(tmp_path / "launch.sqlite3", principal="alice")
    dispatches = []
    monkeypatch.setattr(host, "_dispatch_run", lambda *args: dispatches.append(args))
    monkeypatch.setattr(
        operations, "_registered", lambda *args: runner_fixture.registered()
    )
    monkeypatch.setattr(operations, "_signer_reachable", lambda *args: None)
    request = {
        "challenge": BATTERY,
        "challenge_version": "1.0",
        "agent": "none",
        "idempotency_key": "composition-launch-fixture",
    }
    try:
        admitted = SimpleNamespace(profile=cfg, miner=runner_fixture.registered())
        answer = host.launch_admitted(admitted, request)
        with host.db() as db:
            row = dict(
                db.execute(
                    "SELECT * FROM launchpad_campaigns WHERE id=?", (answer["id"],)
                ).fetchone()
            )
        assert row["construction_binding_version"] == 1
        captured = json.loads(row["launch_request"])[levels.CONSTRUCTION_ADMISSION]
        assert captured["binding"] == bound()
        assert row["construction_binding_digest"] == digest(canonical(captured))
        _, choice = host._recorded_launch(row, cfg)
        assert choice.construction_level == bound() and len(dispatches) == 1
        missing = copy.deepcopy(row)
        recorded = json.loads(missing["launch_request"])
        del recorded[levels.CONSTRUCTION_ADMISSION]
        missing["launch_request"] = canonical(recorded)
        with pytest.raises(Rejected, match="launch_record_differs"):
            host._recorded_launch(missing, cfg)
        assert len(dispatches) == 1
        # A genuine pre-S3 record has the migration's version-0/default-null
        # identity, not a version-1 record with its capture removed.
        historical = {
            **missing,
            "construction_binding_version": 0,
            "construction_binding_digest": None,
        }
        _, legacy_choice = host._recorded_launch(historical, cfg)
        assert legacy_choice is None or legacy_choice.construction_level is None
    finally:
        host.close()


def test_composition_smoke_pass_freezes_only_that_original_combined_recipe(
    tmp_path, monkeypatch, accepted_fixture_checks
):
    import test_launchpad_smoke_practice as smoke_fixture

    from carbon.development_session import research_campaign as rc

    found = bound()
    monkeypatch.setattr(cl, "READ_TARGET", lambda *args: facts(found))
    requested = strategy()
    requested["parameters"]["steps"] = 20000
    ledger, manifest = smoke_fixture.ledger_at(tmp_path, found)
    practice = smoke_fixture.FixturePractice(ledger, level=found)
    assert rc.freeze_refusal(ledger.root, requested) == "practice_result_required"
    _, result = smoke_fixture.execute(
        ledger, practice, requested, "composition-smoke", smoke_mode=True
    )
    assert result["recipe"] == requested
    assert result["status"] == "PASSED"
    assert not {"score", "metrics", "diagnostics"} & set(result)
    assert practice.sent[0]["parameters"]["steps"] < requested["parameters"]["steps"]
    assert practice.sent[0]["parameters"]["muon_spectral"] is True
    assert rc.freeze_refusal(ledger.root, requested) is None
    changed = copy.deepcopy(requested)
    changed["parameters"]["muon_spectral"] = False
    assert rc.freeze_refusal(ledger.root, changed) == "practice_result_required"
    answer = smoke_fixture.freeze(ledger, manifest, requested, monkeypatch)
    assert answer["selection"]["contract_digest"] == found["digest"]
    assert answer["selection"]["construction_level"]["level"] == 3


def test_pre_sign_graph_transport_depends_on_the_frozen_graph_field(
    accepted_fixture_checks,
):
    found = bound()
    manifest = {"challenge": CHALLENGE, "construction_level": found}
    read = lambda url: facts(found)
    record = {
        "strategy": strategy(),
        "contract_digest": found["digest"],
        "construction_level": found,
    }
    levels.require_served(CFG, manifest, read, record=record)
    graph_record = copy.deepcopy(record)
    graph_record["strategy"]["parameters"]["composition_graphs"] = "sha256:" + "1" * 64
    with pytest.raises(Rejected, match="level4_envelope_transport_unavailable"):
        levels.require_served(CFG, manifest, read, record=graph_record)
    with pytest.raises(Rejected, match="freeze_a_candidate_first"):
        levels.require_served(CFG, manifest, read)


__all__ = ["accepted_fixture_checks"]
