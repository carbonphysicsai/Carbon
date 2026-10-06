"""Motor Interface-v1 adapter on pinned public DEVELOPMENT evidence only."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest
from carbon.challenge_validator.candidate_fault import load_policy
from carbon.challenge_validator.dispatch import Adapters, Operator, Validator
from carbon.challenge_validator.interface import (
    MOTOR_CONFIRMATION_ROLE,
    ReservedRole,
    Submission,
)
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.challenge_validator.motor import (
    EVIDENCE,
    PUBLIC_BATCH_KIND,
    MotorAdapter,
    MotorAdapterError,
    rule_document,
)
from carbon.challenge_validator.scoring import COVERAGE_RULE
from carbon.motor import exam
from carbon.motor.research import SCAFFOLD
from carbon.reconstruction import capability_registry as registry

REPOSITORY = Path(__file__).resolve().parents[2]
TOKEN = registry.MOTOR_CHALLENGE
CONTRACT = registry.contract(TOKEN)


def submission(value=None, *, hotkey="hk-motor", contract_digest=None):
    return Submission(
        hotkey=hotkey,
        receipt={"sequence": 7, "digest": "d" * 64, "block": 42},
        challenge_id=TOKEN,
        challenge_version=CONTRACT.version,
        strategy_json=json.dumps(SCAFFOLD if value is None else value),
        contract_digest=CONTRACT.digest if contract_digest is None else contract_digest,
    )


@pytest.fixture
def adapter(tmp_path):
    return MotorAdapter(tmp_path / "motor", repository=REPOSITORY)


@pytest.fixture
def ledger(tmp_path):
    root = tmp_path / "ledger"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return AttemptLedger(root / "attempts.sqlite3")


def prepare(adapter):
    fingerprint = adapter.prepare_batch(
        "motor-public-practice-v1", kind=PUBLIC_BATCH_KIND
    )
    assert adapter.ingest_references(fingerprint, list(adapter.material.practice))
    assert adapter.open_pool() == fingerprint
    return fingerprint


def test_contract_and_rule_are_pinned_to_existing_public_motor_material(adapter):
    assert Adapters([adapter]).digests() == [CONTRACT.digest]
    identities = adapter.identities()
    assert identities["contract_digest"] == CONTRACT.digest
    assert identities["evidence"] == EVIDENCE
    assert identities["public_material"] == {
        "train_sha256": "sha256:d027f71133f2fdc0c74d2b62bdfc2fbeff445062f638dd2888f4f54c17389d4e",
        "practice_sha256": "sha256:0466627106bdcf8495b96a93ea89e5d5270ad845171d6770bac2b2d9922dd247",
        "calibration_sha256": "sha256:443006e780b00f92e0f7539ab12224e9f229f21c98df770964301aef57a3da88",
    }
    assert all(value.startswith("sha256:") for value in adapter.pinned().values())
    assert rule_document(adapter.material)["coverage"] == COVERAGE_RULE
    assert adapter.disclosure_budget() is None


def test_motor_candidate_fault_policy_is_registered_and_pinned(adapter):
    policy = load_policy(TOKEN)
    assert policy.version == "motor-candidate-fault-v1"
    assert policy.digest == adapter.candidate_fault_policy.digest
    assert adapter.identities()["candidate_fault_policy_digest"] == policy.digest
    assert policy.retry["validator_performs"] is False
    assert policy.refund["validator_performs"] is False


def test_public_batch_requires_exact_complete_ingestion_and_survives_restart(adapter):
    fingerprint = adapter.prepare_batch(
        "motor-public-practice-v1", kind=PUBLIC_BATCH_KIND
    )
    assert (
        adapter.prepare_batch("motor-public-practice-v1", kind=PUBLIC_BATCH_KIND)
        == fingerprint
    )
    jobs = adapter.reference_jobs(fingerprint)
    assert len(jobs) == 30
    assert all(
        set(job) == {"case_id", "inputs", "reference", "practice_sha256"}
        for job in jobs
    )
    assert not any("outputs" in job for job in jobs)
    with pytest.raises(MotorAdapterError, match="motor_public_references_incomplete"):
        adapter.open_pool()
    assert not adapter.ingest_references(
        fingerprint, list(adapter.material.practice[:11])
    )
    restarted = MotorAdapter(adapter.store.root, repository=REPOSITORY)
    assert len(restarted.reference_jobs(fingerprint)) == 19
    assert restarted.ingest_references(
        fingerprint, list(restarted.material.practice[11:])
    )
    assert restarted.open_pool() == fingerprint
    assert restarted.status()["references"] == 30
    with pytest.raises(MotorAdapterError, match="motor_public_batch_already_prepared"):
        restarted.prepare_batch("another-role", kind=PUBLIC_BATCH_KIND)


@pytest.mark.parametrize("change", ["inputs", "outputs", "checks", "image", "extra"])
def test_reference_ingestion_rejects_any_altered_pinned_record(adapter, change):
    fingerprint = adapter.prepare_batch("public", kind=PUBLIC_BATCH_KIND)
    record = copy.deepcopy(adapter.material.practice[0])
    if change == "inputs":
        record["inputs"]["magnet_mm"] += 0.01
    elif change == "outputs":
        record["outputs"]["torque_nm"][0] += 0.01
    elif change == "checks":
        record["checks"]["periodicity_rel"] = 0
    elif change == "image":
        record["image"] = "unregistered-image"
    else:
        record["extra"] = True
    with pytest.raises(MotorAdapterError, match="motor_reference_record_mismatch"):
        adapter.ingest_references(fingerprint, [record])
    assert len(adapter.reference_jobs(fingerprint)) == 30


def test_duplicate_or_foreign_reference_is_atomic_refusal(adapter):
    fingerprint = adapter.prepare_batch("public", kind=PUBLIC_BATCH_KIND)
    record = copy.deepcopy(adapter.material.practice[0])
    with pytest.raises(MotorAdapterError, match="motor_reference_case_duplicate"):
        adapter.ingest_references(fingerprint, [record, record])
    assert len(adapter.reference_jobs(fingerprint)) == 30
    record["case_id"] = "foreign-0000"
    with pytest.raises(MotorAdapterError, match="motor_reference_case_not_in_batch"):
        adapter.ingest_references(fingerprint, [record])
    assert len(adapter.reference_jobs(fingerprint)) == 30


def test_unavailable_until_pool_open_then_exact_exam_and_owner_only_record(
    adapter, ledger
):
    adapters = Adapters([adapter])
    validator = Validator(adapters, ledger)
    result = validator.evaluate(submission())
    assert (result["kind"], result["code"]) == (
        "UNAVAILABLE",
        "motor_public_practice_pool_not_open",
    )
    fingerprint = prepare(adapter)
    result = validator.evaluate(submission())
    assert result["kind"] == "OUTCOME"
    outcome = result["outcome"]
    assert outcome["state"] == "SCORED" and outcome["evidence"] == EVIDENCE
    assert (outcome["qualification"], outcome["reward"]) == (False, False)
    assert outcome["n_cases"] == 30
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
    record = Operator(adapters, ledger).score_record(
        CONTRACT.digest, outcome["submission_id"]
    )["record"]
    assert record["pool_fingerprint"] == fingerprint
    assert record["aggregate"]["score"] == outcome["score"]
    assert len(record["cases"]) == len(record["predictions"]) == 30
    scales = exam.scales_from_train(adapter.material.train)
    replay = [
        exam.score_case(record["predictions"][ref["case_id"]], ref, scales)
        for ref in adapter.material.practice
    ]
    assert record["cases"] == replay
    assert {**exam.aggregate(replay), "n_missing": 0} == record["aggregate"]
    restarted = MotorAdapter(adapter.store.root, repository=REPOSITORY)
    assert (
        Validator(Adapters([restarted]), ledger).outcome(
            CONTRACT.digest, outcome["submission_id"], "hk-motor"
        )["outcome"]
        == outcome
    )
    assert (
        Validator(Adapters([restarted]), ledger).outcome(
            CONTRACT.digest, outcome["submission_id"], "hk-other"
        )["code"]
        == "unknown_submission"
    )


def test_invalid_or_wrong_contract_never_scores(adapter, ledger):
    prepare(adapter)
    adapters = Adapters([adapter])
    bad = copy.deepcopy(SCAFFOLD)
    bad["parameters"]["length"] = "length_3"
    result = Validator(adapters, ledger).evaluate(submission(bad))
    assert result["outcome"]["state"] == "INVALID_CONSTRUCTION"
    assert result["outcome"]["failure"]["code"] == "recipe_rejected"
    with pytest.raises(LookupError, match="not_scored"):
        Operator(adapters, ledger).score_record(
            CONTRACT.digest, result["outcome"]["submission_id"]
        )
    assert (
        Validator(adapters, ledger).evaluate(
            submission(contract_digest="sha256:" + "0" * 64)
        )["code"]
        == "contract_not_served"
    )
    wrong_challenge = copy.deepcopy(SCAFFOLD)
    wrong_challenge["challenge_id"] = "chip-cold-plate"
    assert (
        Validator(adapters, ledger).evaluate(submission(wrong_challenge))["code"]
        == "challenge_mismatch"
    )


@pytest.mark.parametrize(
    "fault", ["rebuild_exception", "predict_exception", "non_finite_score"]
)
def test_candidate_faults_are_registered_non_scientific_infra(
    adapter, ledger, monkeypatch, fault
):
    from carbon.challenge_validator import motor

    prepare(adapter)
    if fault == "rebuild_exception":
        monkeypatch.setattr(
            motor,
            "rebuild",
            lambda *_: (_ for _ in ()).throw(RuntimeError("private path")),
        )
    elif fault == "predict_exception":
        monkeypatch.setattr(
            motor,
            "rebuild",
            lambda *_: type(
                "Broken",
                (),
                {
                    "predict": lambda self, _inputs: (_ for _ in ()).throw(
                        RuntimeError("private path")
                    )
                },
            )(),
        )
    else:
        original = motor.exam.aggregate
        monkeypatch.setattr(
            motor.exam, "aggregate", lambda rows: {**original(rows), "score": math.nan}
        )
    result = Validator(Adapters([adapter]), ledger).evaluate(submission())
    assert (result["kind"], result["code"], result["outcome"]) == (
        "FAILED_INFRA",
        "adapter_failure",
        None,
    )
    assert result["candidate_fault_policy"] == adapter.candidate_fault_policy.record(
        fault
    )
    assert result["candidate_fault_policy"]["retry"]["validator_performs"] is False
    assert "private path" not in json.dumps(result)


def test_missing_prediction_is_charged_as_schema_gate(adapter, ledger, monkeypatch):
    from carbon.challenge_validator import motor

    prepare(adapter)
    original = motor.rebuild
    missing_inputs = json.dumps(adapter.material.practice[0]["inputs"], sort_keys=True)

    class Nulling:
        def __init__(self, model):
            self.model = model

        def predict(self, inputs):
            if json.dumps(inputs, sort_keys=True) == missing_inputs:
                return None
            return self.model.predict(inputs)

    monkeypatch.setattr(
        motor, "rebuild", lambda recipe, material: Nulling(original(recipe, material))
    )
    adapters = Adapters([adapter])
    result = Validator(adapters, ledger).evaluate(submission())
    outcome = result["outcome"]
    assert result["kind"] == "OUTCOME" and outcome["state"] == "SCORED"
    assert outcome["eligible"] is False
    assert (outcome["n_cases"], outcome["n_scored"], outcome["n_gate_failed"]) == (
        30,
        29,
        1,
    )
    record = Operator(adapters, ledger).score_record(
        CONTRACT.digest, outcome["submission_id"]
    )["record"]
    assert record["aggregate"]["n_missing"] == 1
    assert record["aggregate"]["n_failed_infra"] == 0
    assert record["aggregate"]["gate_failures"] == {"schema_finite": 1}


def test_private_role_and_non_owner_only_store_fail_closed(adapter, tmp_path):
    assert MOTOR_CONFIRMATION_ROLE == "motor-graphite-confirmation-v1"
    with pytest.raises(ReservedRole, match="seed_role_reserved"):
        adapter.prepare_batch(MOTOR_CONFIRMATION_ROLE, kind=PUBLIC_BATCH_KIND)
    assert adapter.status()["batches"] == 0
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises(MotorAdapterError, match="motor_store_directory_not_owner_only"):
        MotorAdapter(shared, repository=REPOSITORY)


def test_adapter_has_no_private_or_counted_reference_loader():
    source = (REPOSITORY / "carbon/challenge_validator/motor.py").read_text()
    assert "customer_decision" not in source
    assert "decision_study" not in source
    assert "reference_campaign" not in source
