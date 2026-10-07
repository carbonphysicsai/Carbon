"""The bank core (VALIDATOR-23; OWNER-BANK-ARCHITECTURE-01) on a synthetic
source: tranches, Merkle proofs, window draws, exposure, retirement, top-up
and diagnostics. There is no solver, chain or network."""

from __future__ import annotations

import hashlib
import json
import random

import pytest

from carbon.challenge_validator import bank_proof
from carbon.challenge_validator.bank import BankLedger, BankRefused, BankSource


class Synthetic(BankSource):
    challenge_id = "synthetic-bank"

    def draw_tranche(self, bank, role, count):
        rng = random.Random(hashlib.sha256(role.encode()).digest())
        return [
            {"case_id": f"{role}-{i:03d}", "inputs": {"x": rng.random()}}
            for i in range(count)
        ]

    def terminal(self):
        return ("OK", "REFERENCE_SOLVER_FAILED")

    def stratum(self, bank, inputs):
        return "lo" if inputs["x"] < 0.5 else "hi"

    def cell(self, bank, inputs):
        return int(inputs["x"] * 10)


def solve(ledger, tranche, failed=()):
    """Every job gets a terminal record; `failed` ids fail."""
    records = [
        {
            "case_id": job["case_id"],
            "inputs": job["inputs"],
            "status": "REFERENCE_SOLVER_FAILED" if job["case_id"] in failed else "OK",
            "y": job["inputs"]["x"] ** 2,
        }
        for job in ledger.jobs(tranche)
    ]
    assert ledger.ingest(tranche, records) == 0
    return ledger.seal(tranche)


@pytest.fixture
def ledger(tmp_path):
    return BankLedger(tmp_path / "bank", Synthetic())


def fill(ledger, bank, count, failed=()):
    drawn = ledger.draw_tranche(bank, count)
    return solve(ledger, drawn["tranche"], failed)


def test_a_sealed_tranche_proves_each_case_and_nothing_else(ledger):
    commitment = fill(ledger, "pool", 7)
    assert commitment["root"].startswith("sha256:")
    drawn = ledger.draw_window("pool", 1, {"all": 7}, retire_at=5)
    window = ledger.window_cases("pool", 1)
    assert window["tranches"] == [commitment]
    for case_id in drawn:
        case = window["cases"][case_id]
        assert bank_proof.verify(
            case_id,
            case["inputs"],
            case["reference"],
            case["proof"],
            commitment["root"],
        )
        changed = dict(case["reference"], y=case["reference"]["y"] + 1e-9)
        assert not bank_proof.verify(
            case_id, case["inputs"], changed, case["proof"], commitment["root"]
        )
        assert not bank_proof.verify(
            case_id + "x",
            case["inputs"],
            case["reference"],
            case["proof"],
            commitment["root"],
        )
    # Sealing again is idempotent.
    assert ledger.seal(commitment["tranche"]) == commitment


def test_a_tranche_is_journaled_before_any_use(ledger):
    drawn = ledger.draw_tranche("pool", 4)
    [entry] = ledger.entries()
    assert entry["event"] == "tranche_drawn"
    assert entry["fingerprint"] == drawn["fingerprint"] and entry["cases"] == 4
    with pytest.raises(BankRefused) as refused:
        ledger.seal(drawn["tranche"])
    assert refused.value.code == "bank_tranche_unsolved"
    with pytest.raises(BankRefused) as refused:
        ledger.draw_window("pool", 1, {"all": 1}, retire_at=5)
    assert refused.value.code == "bank_short:pool"


def test_window_draws_are_seeded_stored_and_disjoint(tmp_path, ledger):
    fill(ledger, "pool", 40)
    first = ledger.draw_window("pool", 1, {"all": 10}, retire_at=5)
    assert ledger.draw_window("pool", 1, {"all": 10}, retire_at=5) == first
    second = ledger.draw_window("pool", 2, {"all": 10}, active_slots=(1,), retire_at=5)
    assert not set(first) & set(second)
    third = ledger.draw_window("pool", 3, {"all": 10}, active_slots=(1, 2), retire_at=5)
    assert not (set(first) | set(second)) & set(third)
    # Another ledger with another key draws differently from the same bank.
    other = BankLedger(tmp_path / "other", Synthetic())
    fill(other, "pool", 40)
    assert other.draw_window("pool", 1, {"all": 10}, retire_at=5) != first


def test_stratum_quotas_are_drawn_within_their_strata(ledger):
    fill(ledger, "q3", 60)
    drawn = ledger.draw_window("q3", 1, {"lo": 4, "hi": 4}, retire_at=5)
    window = ledger.window_cases("q3", 1)["cases"]
    strata = [("lo" if window[c]["inputs"]["x"] < 0.5 else "hi") for c in drawn]
    assert strata.count("lo") == 4 and strata.count("hi") == 4


def test_exposure_retires_at_e_and_the_deficit_tops_up(ledger):
    fill(ledger, "pool", 10)
    for slot in range(1, 6):
        ledger.draw_window("pool", slot, {"all": 10}, retire_at=5)
    status = ledger.status()["pool"]
    assert status["live"] == 0 and status["retired"] == 10
    assert ledger.released() == {"pool": 10}
    with pytest.raises(BankRefused):
        ledger.draw_window("pool", 6, {"all": 10}, retire_at=5)
    assert ledger.deficit("pool", 10) == 10
    drawn = ledger.draw_tranche("pool", ledger.deficit("pool", 10))
    assert ledger.deficit("pool", 10) == 0  # pending counts
    solve(ledger, drawn["tranche"])
    assert len(ledger.draw_window("pool", 7, {"all": 10}, retire_at=5)) == 10
    assert ledger.status()["pool"]["exposures"] == {"1": 10}


def test_a_failed_reference_is_counted_never_drawn(ledger):
    drawn = ledger.draw_tranche("pool", 6)
    failed = {ledger.jobs(drawn["tranche"])[0]["case_id"]}
    solve(ledger, drawn["tranche"], failed)
    assert ledger.status()["pool"]["live"] == 5
    assert ledger.status()["pool"]["reference_failed"] == 1
    assert not failed & set(ledger.draw_window("pool", 1, {"all": 5}, retire_at=5))
    [sealed] = [e for e in ledger.entries() if e["event"] == "tranche_sealed"]
    assert (sealed["live"], sealed["reference_failed"]) == (5, 1)


def test_references_are_checked_on_ingest(ledger):
    drawn = ledger.draw_tranche("pool", 2)
    job = ledger.jobs(drawn["tranche"])[0]
    for record, code in (
        ({"case_id": "elsewhere", "status": "OK"}, "bank_reference_not_in_tranche"),
        (
            {"case_id": job["case_id"], "inputs": {"x": 2.0}, "status": "OK"},
            "bank_reference_inputs_mismatch",
        ),
    ):
        with pytest.raises(BankRefused) as refused:
            ledger.ingest(drawn["tranche"], [record])
        assert refused.value.code == code
    # An infrastructure failure is skipped, then retried.
    assert (
        ledger.ingest(
            drawn["tranche"], [{"case_id": job["case_id"], "status": "FAILED_INFRA"}]
        )
        == 2
    )


def test_coverage_and_status_are_public_counts(ledger):
    fill(ledger, "pool", 30)
    cells = {"lo": {c: 1.0 for c in range(5)}, "hi": {c: 1.0 for c in range(5, 10)}}
    report = ledger.coverage("pool", cells)
    assert set(report) == {"lo", "hi"} and all(0 < v <= 1 for v in report.values())
    ledger.draw_window("pool", 1, {"all": 10}, retire_at=5)
    text = json.dumps([ledger.status(), ledger.entries(), report])
    hidden = ledger.window_cases("pool", 1)["cases"]
    assert not any(case_id in text for case_id in hidden)
    assert not any(repr(case["inputs"]["x"]) in text for case in hidden.values())
    assert "<redacted>" in repr(ledger)


def test_the_ledger_is_owner_only(tmp_path):
    ledger = BankLedger(tmp_path / "bank", Synthetic())
    for name in ("bank.key", "bank.sqlite3", "bank-journal.jsonl"):
        assert (ledger.directory / name).stat().st_mode & 0o077 == 0
    (tmp_path / "open").mkdir(mode=0o755)
    (tmp_path / "open").chmod(0o755)
    with pytest.raises(BankRefused) as refused:
        BankLedger(tmp_path / "open", Synthetic())
    assert refused.value.code == "bank_dir_not_owner_only"
