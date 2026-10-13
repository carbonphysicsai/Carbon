"""OPT-11: offline Phase 4 recovery uses the existing model-call ledger."""

from __future__ import annotations

import json

import pytest
from test_graphite_phase4 import _stand_in_material  # noqa: F401
from test_graphite_phase4_model import _open, _provider, _state

from carbon.agent_campaign.controller import SimulatedCrash
from carbon.agent_campaign.graphite import phase4
from carbon.agent_campaign.graphite.model import ScriptedModel, crash
from carbon.agent_campaign.graphite.provider import OWNER
from carbon.development_session import research_agent
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical
from carbon.development_session.research_ledger import CampaignLedger


def _crashed(tmp_path):
    model = ScriptedModel([crash(), crash()])
    provider = _provider(tmp_path / "attacker", model)
    run_id = _open(provider)
    with pytest.raises(SimulatedCrash):
        provider.run(run_id)
    ledger = CampaignLedger(provider._dir(run_id) / "ledger")
    pending = research_agent.uncertain_calls(ledger, owner=OWNER)
    assert len(pending) == 1
    return provider, model, run_id, ledger, pending[0]["identity"]


def test_crashed_call_reconciles_once_and_original_session_is_resumable(tmp_path):
    provider, model, run_id, ledger, identity = _crashed(tmp_path)
    before = len(model.requests)
    report = phase4.reconcile_session(tmp_path / "attacker", 1)
    assert report["status"] == "RESUMABLE"
    assert report["candidate_charged"] is False
    assert report["settled"][0]["identity"] == identity
    assert report["settled"][0]["charge_basis"] == "full_reservation"
    assert "full reservation" in report["settled"][0]["accounting"]
    assert report["booked_nanodollars"] > 0
    assert research_agent.uncertain_calls(ledger, owner=OWNER) == []
    assert _state(provider, run_id)["state"] == "running"
    assert len(model.requests) == before  # reconciliation sent no model request
    assert phase4.reconcile_session(tmp_path / "attacker", 1) == report
    assert len(model.requests) == before
    assert (
        len(
            [
                op
                for op in ledger.status(owner=OWNER)["operations"]
                if op["reservation"].get("provider_attempts") == 1
            ]
        )
        == 1
    )
    # Continuation uses a new call identity and may itself crash later.
    with pytest.raises(SimulatedCrash):
        provider.run(run_id)
    operations = [
        op
        for op in ledger.status(owner=OWNER)["operations"]
        if op["reservation"].get("provider_attempts") == 1
    ]
    assert len(model.requests) > before
    assert len({op["id"] for op in operations}) == len(operations)
    assert (
        next(op for op in operations if op["id"] == identity)["state"] == "FAILED_INFRA"
    )
    second = phase4.reconcile_session(tmp_path / "attacker", 1)
    assert second["status"] == "RESUMABLE"
    assert len(second["settled"]) == 2
    assert second["booked_nanodollars"] == 2 * report["booked_nanodollars"]
    assert phase4.reconcile_session(tmp_path / "attacker", 1) == second


def test_retained_provider_charge_is_booked_and_over_cap_is_refused(tmp_path):
    _provider, _model, _run_id, ledger, identity = _crashed(tmp_path)
    response = research_agent._call_directory(ledger, OWNER, identity) / "response.json"
    response.write_text(json.dumps({"x_engy": {"charged_micro": 100}}))
    report = phase4.reconcile_session(tmp_path / "attacker", 1)
    assert report["booked_nanodollars"] == 100_000
    assert report["settled"][0]["charge_basis"] == "provider_reported_charge"
    assert "provider response" in report["settled"][0]["accounting"]

    mismatch = tmp_path / "different-model"
    _provider, _model, _run_id, _ledger, identity = _crashed(mismatch)
    call_dir = research_agent._call_directory(_ledger, OWNER, identity)
    (call_dir / "response.json").write_text(
        json.dumps({"model": "different-model", "x_engy": {"charged_micro": 100}})
    )
    (call_dir / "uncertain.json").write_text(
        json.dumps(
            {"schema": research_agent.UNCERTAIN_CALL, "reason": "model_mismatch"}
        )
    )
    reported = phase4.reconcile_session(mismatch / "attacker", 1)
    assert "provider-reported charge" in reported["settled"][0]["caveat"]

    other = tmp_path / "over-cap"
    _provider, _model, _run_id, ledger, identity = _crashed(other)
    response = research_agent._call_directory(ledger, OWNER, identity) / "response.json"
    reservation = ledger.status(owner=OWNER)["operations"][0]["reservation"]
    response.write_text(
        json.dumps({"x_engy": {"charged_micro": reservation["provider_nanodollars"]}})
    )
    refused = phase4.reconcile_session(other / "attacker", 1)
    assert refused["status"] == "UNRESOLVED"
    assert refused["refused"][0]["code"] == "charge_exceeds_reservation"
    assert research_agent.uncertain_calls(ledger, owner=OWNER)
    assert not (
        other / "attacker" / "graphite" / "runs" / _run_id / "reconciliation.json"
    ).exists()
    malformed = tmp_path / "malformed"
    _provider, _model, _run_id, ledger, identity = _crashed(malformed)
    response = research_agent._call_directory(ledger, OWNER, identity) / "response.json"
    response.write_text(json.dumps({"x_engy": {"charged_micro": -1}}))
    refused = phase4.reconcile_session(malformed / "attacker", 1)
    assert refused["refused"][0]["code"] == "provider_charge_invalid"
    assert research_agent.uncertain_calls(ledger, owner=OWNER)


def test_terminal_crash_keeps_original_export_and_appends_typed_infra_close(tmp_path):
    provider, _model, run_id, ledger, identity = _crashed(tmp_path)
    provider._finish(run_id, "failed", {"code": "reconciliation_required"}, None)
    export = (provider._dir(run_id) / "graphite-session.json").read_bytes()
    # Simulate a crash after ledger booking but before the operator receipt.
    settled = research_agent.settle_uncertain_calls(
        ledger, owner=OWNER, charge_from_response=True
    )
    assert settled["settled"][0]["identity"] == identity
    report = phase4.reconcile_session(tmp_path / "attacker", 1)
    assert report["status"] == "FAILED_INFRA_CLOSED"
    assert report["candidate_charged"] is False
    assert report["settled"][0]["identity"] == identity
    assert (provider._dir(run_id) / "graphite-session.json").read_bytes() == export
    assert phase4.reconcile_session(tmp_path / "attacker", 1) == report
    assert research_agent.uncertain_calls(ledger, owner=OWNER) == []


def test_crash_after_settlement_file_but_before_booking_reuses_same_record(tmp_path):
    _provider, _model, _run_id, ledger, identity = _crashed(tmp_path)
    fingerprint, settlement = research_agent._settlement(
        ledger, OWNER, identity, charge_from_response=True
    )
    assert fingerprint is not None
    record = research_agent._call_directory(ledger, OWNER, identity) / "settlement.json"
    write_once(record, canonical(settlement))
    assert ledger.status(owner=OWNER)["operations"][0]["state"] == "RESERVED"
    report = phase4.reconcile_session(tmp_path / "attacker", 1)
    assert report["status"] == "RESUMABLE"
    assert record.read_bytes() == canonical(settlement)
    assert report["booked_nanodollars"] == settlement["booked"]["provider_nanodollars"]
    assert phase4.reconcile_session(tmp_path / "attacker", 1) == report


def test_legacy_full_reservation_journal_survives_opt_in_reconciliation(tmp_path):
    _provider, _model, _run_id, ledger, identity = _crashed(tmp_path)
    response = research_agent._call_directory(ledger, OWNER, identity) / "response.json"
    response.write_text(json.dumps({"x_engy": {"charged_micro": 100}}))
    fingerprint, legacy = research_agent._settlement(ledger, OWNER, identity)
    assert fingerprint is not None and "charge_basis" not in legacy
    journal = (
        research_agent._call_directory(ledger, OWNER, identity) / "settlement.json"
    )
    write_once(journal, canonical(legacy))
    assert ledger.status(owner=OWNER)["operations"][0]["state"] == "RESERVED"
    report = phase4.reconcile_session(tmp_path / "attacker", 1)
    assert report["status"] == "RESUMABLE"
    assert journal.read_bytes() == canonical(legacy)
    assert report["settled"][0]["charge_basis"] == "full_reservation"
    assert report["booked_nanodollars"] == legacy["booked"]["provider_nanodollars"]
    assert report["booked_nanodollars"] > 100_000
    assert phase4.reconcile_session(tmp_path / "attacker", 1) == report


@pytest.mark.parametrize(
    "corrupt", [b"{", canonical({"schema": research_agent.PROVIDER_SETTLEMENT})]
)
def test_corrupt_or_incompatible_settlement_journal_stays_unresolved(tmp_path, corrupt):
    _provider, _model, _run_id, ledger, identity = _crashed(tmp_path)
    journal = (
        research_agent._call_directory(ledger, OWNER, identity) / "settlement.json"
    )
    journal.write_bytes(corrupt)
    report = phase4.reconcile_session(tmp_path / "attacker", 1)
    assert report["status"] == "UNRESOLVED"
    assert report["refused"][0]["code"] == "settlement_journal_invalid"
    assert research_agent.uncertain_calls(ledger, owner=OWNER)
    assert journal.read_bytes() == corrupt


def test_reconcile_command_names_one_session_and_refuses_unknown(tmp_path, capsys):
    with pytest.raises(phase4.RunnerRefused):
        phase4.reconcile_session(tmp_path / "attacker", 1)
    assert json.loads(capsys.readouterr().out)["reason_code"] == "unknown_session"
    _crashed(tmp_path)
    assert phase4.main(["reconcile", "--root", str(tmp_path), "--session", "1"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["status"] == "RESUMABLE"


def test_reconcile_refuses_live_session_and_no_work(tmp_path, capsys):
    from carbon.agent_campaign.graphite import heartbeat

    provider = _provider(tmp_path / "attacker", ScriptedModel([]))
    run_id = _open(provider)
    ledger = CampaignLedger(provider._dir(run_id) / "ledger")
    assert ledger.status(owner=OWNER)["operations"] == []
    with pytest.raises(phase4.RunnerRefused):
        phase4.reconcile_session(tmp_path / "attacker", 1)
    assert json.loads(capsys.readouterr().out)["reason_code"] == (
        "no_model_call_to_reconcile"
    )
    heartbeat.write(provider._dir(run_id), run_id)
    with pytest.raises(phase4.RunnerRefused):
        phase4.reconcile_session(tmp_path / "attacker", 1)
    assert json.loads(capsys.readouterr().out)["reason_code"] == "session_still_active"


def test_reconcile_refuses_corrupt_session_and_receipt(tmp_path, capsys):
    provider, _model, run_id, _ledger, _identity = _crashed(tmp_path)
    capsys.readouterr()
    state_file = provider._dir(run_id) / "state.json"
    state = state_file.read_bytes()
    state_file.write_bytes(b"{")
    with pytest.raises(phase4.RunnerRefused):
        phase4.reconcile_session(tmp_path / "attacker", 1)
    assert (
        json.loads(capsys.readouterr().out)["reason_code"] == "session_record_invalid"
    )
    state_file.write_bytes(state)
    provider._finish(run_id, "failed", {"code": "reconciliation_required"}, None)
    report = phase4.reconcile_session(tmp_path / "attacker", 1)
    assert report["status"] == "FAILED_INFRA_CLOSED"
    receipt = provider._dir(run_id) / "reconciliation.json"
    receipt.write_bytes(b"{}")
    with pytest.raises(phase4.RunnerRefused):
        phase4.reconcile_session(tmp_path / "attacker", 1)
    assert json.loads(capsys.readouterr().out)["reason_code"] == (
        "reconciliation_receipt_invalid"
    )
