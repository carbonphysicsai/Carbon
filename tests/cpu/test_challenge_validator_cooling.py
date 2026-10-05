"""Cooling's Interface-v1 adapter on pinned public DEVELOPMENT evidence.

No test launches OpenFOAM, a pod or a network request. References are copies
of the committed public PRACTICE artifact, and evaluation rebuilds the existing
deterministic Level-0 KRR model on CPU.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from carbon.challenge_validator.cooling import (
    EVIDENCE,
    PUBLIC_BATCH_KIND,
    CoolingAdapter,
    CoolingAdapterError,
)
from carbon.challenge_validator.dispatch import Adapters, Operator, Validator
from carbon.challenge_validator.interface import (
    COOLING_CONFIRMATION_ROLE,
    ReservedRole,
    Submission,
)
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.cold_plate.openfoam import IMAGE
from carbon.reconstruction import capability_registry as registry

REPOSITORY = Path(__file__).resolve().parents[2]
TOKEN = registry.COLD_PLATE_CHALLENGE
CONTRACT = registry.contract(TOKEN)


def strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": TOKEN,
        "backbone": "kernel_ridge",
        "parameters": parameters,
    }


def submission(value=None, *, hotkey="hk-cooling"):
    return Submission(
        hotkey=hotkey,
        receipt={"sequence": 7, "digest": "d" * 64, "block": 42},
        challenge_id=TOKEN,
        challenge_version=CONTRACT.version,
        strategy_json=json.dumps(strategy() if value is None else value),
        contract_digest=CONTRACT.digest,
    )


@pytest.fixture
def adapter(tmp_path):
    return CoolingAdapter(tmp_path / "cooling", repository=REPOSITORY)


@pytest.fixture
def ledger(tmp_path):
    root = tmp_path / "ledger"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return AttemptLedger(root / "attempts.sqlite3")


def prepare(adapter, role="cooling-public-practice-v1"):
    fingerprint = adapter.prepare_batch(role, kind=PUBLIC_BATCH_KIND)
    assert adapter.ingest_references(fingerprint, list(adapter.material.practice))
    assert adapter.open_pool() == fingerprint
    return fingerprint


def test_adapter_is_registered_to_the_exact_contract_and_pins_its_rule(adapter):
    registered = Adapters([adapter])
    assert registered.digests() == [CONTRACT.digest]
    identities = adapter.identities()
    assert identities["contract_digest"] == CONTRACT.digest
    assert identities["evidence"] == EVIDENCE
    assert identities["reference_solver_image"] == IMAGE
    assert identities["public_material"] == {
        "train_sha256": "sha256:122e001e7ff9f6faefe4e1c558e936089cdc38b6b6dbe8728278812c9d8a6582",
        "practice_sha256": "sha256:a541d43e4a8b59f9704aa642e1c19f1c6725f59d5d60f804d5c20660e50111be",
        "calibration_sha256": "sha256:52236abadb40913e638a8ff5c5d0ff76728b52d27a76b4d6ecadf590852e1aa6",
    }
    assert all(adapter.pinned()[name].startswith("sha256:") for name in adapter.pinned())
    assert adapter.disclosure_budget() is None


def test_public_batch_is_explicit_durable_and_complete_only_after_exact_ingestion(
    adapter,
):
    fingerprint = adapter.prepare_batch(
        "cooling-public-practice-v1", kind=PUBLIC_BATCH_KIND
    )
    assert adapter.prepare_batch(
        "cooling-public-practice-v1", kind=PUBLIC_BATCH_KIND
    ) == fingerprint
    jobs = adapter.reference_jobs(fingerprint)
    assert len(jobs) == 100
    assert all(set(job) == {"case_id", "inputs", "reference", "solver_image"} for job in jobs)
    assert all(job["solver_image"] == IMAGE for job in jobs)
    assert not any("outputs" in job for job in jobs)
    with pytest.raises(CoolingAdapterError) as incomplete:
        adapter.open_pool()
    assert incomplete.value.code == "cooling_public_references_incomplete"
    assert not adapter.ingest_references(
        fingerprint, list(adapter.material.practice[:40])
    )
    assert len(adapter.reference_jobs(fingerprint)) == 60

    restarted = CoolingAdapter(adapter.store.root, repository=REPOSITORY)
    assert len(restarted.reference_jobs(fingerprint)) == 60
    assert restarted.ingest_references(
        fingerprint, list(restarted.material.practice[40:])
    )
    assert restarted.open_pool() == fingerprint
    assert restarted.status() == {
        "schema": "carbon.cold-plate.validator-store.v1",
        "evidence": EVIDENCE,
        "batches": 1,
        "references": 100,
        "pool_open": True,
        "submissions": 0,
        "scored": 0,
    }
    with pytest.raises(CoolingAdapterError) as second:
        restarted.prepare_batch("another-public-role", kind=PUBLIC_BATCH_KIND)
    assert second.value.code == "cooling_public_batch_already_prepared"


@pytest.mark.parametrize("change", ["inputs", "outputs", "checks", "image", "extra"])
def test_reference_ingestion_refuses_any_change_to_the_pinned_record(adapter, change):
    fingerprint = adapter.prepare_batch("public", kind=PUBLIC_BATCH_KIND)
    record = copy.deepcopy(adapter.material.practice[0])
    if change == "inputs":
        record["inputs"]["heat_load_w"] += 1
    elif change == "outputs":
        record["outputs"]["peak_c"] += 1
    elif change == "checks":
        record["checks"]["energy_balance_rel"] = 0
    elif change == "image":
        record["image"] = "opencfd/openfoam-default@sha256:" + "0" * 64
    else:
        record["plausible_but_unregistered"] = True
    with pytest.raises(CoolingAdapterError) as refused:
        adapter.ingest_references(fingerprint, [record])
    assert refused.value.code == "cooling_reference_record_mismatch"
    assert len(adapter.reference_jobs(fingerprint)) == 100


def test_validation_is_unavailable_until_the_operator_opens_the_pool(adapter, ledger):
    validator = Validator(Adapters([adapter]), ledger)
    result = validator.evaluate(submission())
    assert (result["kind"], result["code"]) == (
        "UNAVAILABLE",
        "cooling_public_practice_pool_not_open",
    )
    assert result["outcome"] is None
    assert ledger.attempts()[0]["kind"] == "UNAVAILABLE"


def test_valid_submission_scores_and_operator_record_replays_after_restart(
    adapter, ledger
):
    fingerprint = prepare(adapter)
    adapters = Adapters([adapter])
    validator = Validator(adapters, ledger)
    result = validator.evaluate(
        submission(strategy(length="length_8", ridge="ridge_1e_6"))
    )
    assert result["kind"] == "OUTCOME" and result["code"] is None
    outcome = result["outcome"]
    assert outcome["state"] == "SCORED" and outcome["evidence"] == EVIDENCE
    assert (outcome["qualification"], outcome["reward"]) == (False, False)
    assert outcome["n_cases"] == outcome["n_scored"] == 100
    assert set(outcome) == {
        "schema",
        "submission_id",
        "challenge",
        "state",
        "evidence",
        "qualification",
        "reward",
        "score",
        "eligible",
        "n_cases",
        "n_scored",
        "n_gate_failed",
    }
    assert not ({"cases", "predictions", "references", "recipe"} & set(outcome))

    operator = Operator(adapters, ledger)
    score = operator.score_record(CONTRACT.digest, outcome["submission_id"])
    record = score["record"]
    assert record["pool_fingerprint"] == fingerprint
    assert record["aggregate"]["score"] == outcome["score"]
    assert len(record["cases"]) == len(record["predictions"]) == 100
    assert record["rule_digest"] == result["pinned"]["rule_digest"]
    assert score["audience"] == "OPERATOR_ONLY"

    restarted = CoolingAdapter(adapter.store.root, repository=REPOSITORY)
    read = Validator(Adapters([restarted]), ledger).outcome(
        CONTRACT.digest, outcome["submission_id"], "hk-cooling"
    )
    assert read["outcome"] == outcome
    hidden = Validator(Adapters([restarted]), ledger).outcome(
        CONTRACT.digest, outcome["submission_id"], "hk-other"
    )
    assert (hidden["kind"], hidden["code"]) == ("REFUSED", "unknown_submission")


def test_invalid_recipe_is_an_outcome_and_never_gets_a_score_record(adapter, ledger):
    prepare(adapter)
    adapters = Adapters([adapter])
    result = Validator(adapters, ledger).evaluate(
        submission(strategy(length="length_3"))
    )
    outcome = result["outcome"]
    assert (result["kind"], outcome["state"]) == (
        "OUTCOME",
        "INVALID_CONSTRUCTION",
    )
    assert outcome["failure"]["code"] == "recipe_rejected"
    assert outcome["failure"]["issues"]
    with pytest.raises(LookupError, match="not_scored"):
        Operator(adapters, ledger).score_record(
            CONTRACT.digest, outcome["submission_id"]
        )


def test_confirmation_role_is_reserved_without_creating_a_batch(adapter):
    assert COOLING_CONFIRMATION_ROLE == "cooling-graphite-confirmation-v1"
    with pytest.raises(ReservedRole) as refused:
        adapter.prepare_batch(COOLING_CONFIRMATION_ROLE, kind=PUBLIC_BATCH_KIND)
    assert refused.value.code == "seed_role_reserved"
    assert adapter.status()["batches"] == 0


def test_store_refuses_non_owner_only_custody(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises(CoolingAdapterError) as refused:
        CoolingAdapter(shared, repository=REPOSITORY)
    assert refused.value.code == "cooling_store_directory_not_owner_only"


def test_adapter_source_has_no_counted_or_confirmation_evidence_loader():
    source = (REPOSITORY / "carbon" / "challenge_validator" / "cooling.py").read_text()
    assert "customer_decision" not in source
    assert "decision_study" not in source
    assert "counted-cfd" not in source.lower()
