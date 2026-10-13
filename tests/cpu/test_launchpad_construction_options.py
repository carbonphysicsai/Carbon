"""The page and agent see registered public choices, never guessed opening."""

from types import SimpleNamespace

import pytest

from carbon.battery.unified_contract import contract
from carbon.development_session.unified_construction import (
    UnifiedContract,
    classify,
    digest,
)
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from scripts.dev.miner_launchpad import construction_options as options
from scripts.dev.miner_launchpad import operations, runner
from scripts.dev.miner_launchpad.controller import Rejected


def test_all_registered_changes_are_visible_and_unknown_ceiling_keeps_them_closed():
    registered = contract()
    shown = options.build(registered)
    assert shown["ceiling"] is None and not shown["qualification"]
    assert shown["types"][0]["type"] == "parameters"
    assert shown["types"][0]["availability"] == "available"
    assert {row["type"] for row in shown["types"][1:]} == {
        row["type"] for row in registered.facts()["types"]
    }
    assert all(
        row["availability"] == "coming_soon" and row["reason"]
        for row in shown["types"][1:]
    )
    assert shown["unified_digest"] == registered.digest
    assert shown["launch_mode"] == "content_derived"


def test_raw_contract_and_unregistered_serving_claims_never_create_availability():
    registered = contract()
    with pytest.raises(ValueError):
        options.build(registered.document)
    shown = options.build(
        registered, [{**registered.facts(), "unified_digest": "sha256:" + "0" * 64}]
    )
    assert shown["submission_path_available"] is False
    # Owner ceiling/opening still dominates even a matching serving claim.
    assert all(row["availability"] == "coming_soon" for row in shown["types"][1:])


def test_receiver_mismatch_is_not_treated_as_a_served_contract():
    cfg = {
        "intake_targets": {
            BATTERY_CHALLENGE: [
                {
                    "intake_url": "https://fixture.example.test",
                    "receiver_hotkey": "5" + "A" * 47,
                }
            ]
        }
    }
    public = {**contract().facts(), "receiver": "another receiver"}
    shown = options.for_profile(cfg, lambda url: public)[BATTERY_CHALLENGE]
    assert shown["submission_path_available"] is False
    assert not shown["qualification"]


def test_options_operation_exposes_the_same_document_the_page_reads(monkeypatch):
    cfg = {"paths": {}, "runtime": {}}
    host = runner.RunnerAdapter.__new__(runner.RunnerAdapter)
    # Find the executable implementation's method without initializing a host.
    monkeypatch.setattr(host, "configured", lambda: cfg)
    monkeypatch.setattr(host, "read_intake_facts", lambda url: {})
    monkeypatch.setattr(host, "_model_providers", lambda cfg: [])
    monkeypatch.setattr(runner, "graphite_options", lambda cfg: {})
    shown = host.options_admitted(SimpleNamespace(), {})
    assert shown["construction_options"] == options.for_profile(cfg, lambda url: {})
    assert "Coming soon" in str(shown["construction_options"])


def test_new_launch_schema_refuses_manual_level_selection():
    with pytest.raises(Rejected) as refused:
        operations._closed(
            operations.OPERATIONS["launch"],
            {"profile": "p", "agent": "none", "construction_level": 2},
        )
    assert refused.value.code == "closed_request_required"


def test_pre_sign_preview_uses_the_same_classifier_and_stops_changed_construction(
    monkeypatch,
):
    strategy = {
        "schema_version": "1.0",
        "challenge_id": BATTERY_CHALLENGE,
        "backbone": "mlp",
        "parameters": {
            "steps": 48,
            "width": 16,
            "depth": 1,
            "muon_spectral": True,
            "optimizer_family": "muon",
        },
    }
    answer = classify(strategy, contract())
    assert answer["refusal"] is not None
    host = runner.RunnerAdapter.__new__(runner.RunnerAdapter)
    with pytest.raises(Rejected) as refused:
        host._design_refusal(strategy)
    assert refused.value.code == answer["refusal"]


def test_registered_ceiling_opening_checks_and_serving_all_constrain_the_display():
    # Synthetic preview data remains structurally DEVELOPMENT_SHADOW_ONLY;
    # it never reaches an intake, deployment, signer or scoring authority.
    doc = contract().document
    doc["ceiling"] = 2
    for row in doc["types"]:
        row["within_ceiling"] = row["label"] <= 2
        row["open"], row["owner_acceptance"] = (
            "EXTERNAL",
            "OWNER-TEST-ONLY-NOT-AN-ACCEPTANCE",
        )
        for arm in row["arms"]:
            arm["external_allowed"] = True
        for check in row["checks"]:
            check["status"] = "PASS"
        row["registration_digest"] = digest(
            {k: row[k] for k in ("type", "label", "fields", "arms")}
        )
    registered = UnifiedContract(doc)
    without_route = options.build(registered)
    assert all(
        row["availability"] == "coming_soon" for row in without_route["types"][1:]
    )
    serving = options.build(registered, [registered.facts()])
    assert [row["availability"] for row in serving["types"][1:]] == [
        "available",
        "available",
        "coming_soon",
        "coming_soon",
    ]
    assert not serving["qualification"]


def test_missing_contract_is_explicit_and_never_a_successful_empty_catalog(monkeypatch):
    from carbon.battery import unified_contract

    def missing():
        raise OSError("fixture private path must not be disclosed")

    monkeypatch.setattr(unified_contract, "contract", missing)
    shown = options.for_profile({})[BATTERY_CHALLENGE]
    assert shown["status"] == "PUBLIC_CONTRACT_UNAVAILABLE"
    assert shown["types"] == [] and shown["ceiling"] is None
    assert "private path" not in str(shown)
