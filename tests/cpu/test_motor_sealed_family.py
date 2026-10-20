"""Motor 1.1's sealed exam (Validator, 2026-10-20): a family beside 1.0's
hidden pool, selected by the deployment schema; its batches become a private
bank in Motor's development-bank format, or a typed refusal."""

from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_motor_hidden import Solver
from test_challenge_validator_motor_hidden import (
    write_deployment as write_hidden_deployment,
)

from carbon.challenge_kit import motor_sealed_pack as pack
from carbon.challenge_kit import physical_pack
from carbon.challenge_validator import motor_hidden
from carbon.challenge_validator import motor_sealed as sealed
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.motor_sealed_source import (
    MotorSealedBatchSource,
    motor_sealed_family,
    motor_source_for,
)
from carbon.challenge_validator.motor_source import MotorBatchSource
from carbon.motor import population

MOTOR = "electric-motor-magnetics"


def write_deployment(path, **fields):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_text(json.dumps({"schema": sealed.DEPLOYMENT_SCHEMA, **fields}))
    path.chmod(0o600)
    return path


def test_the_registration_is_1_1_with_motors_own_values():
    family = motor_sealed_family()
    assert (family.challenge_id, family.challenge_version) == (MOTOR, "1.1")
    assert family.kinds == motor_hidden.KINDS
    assert family.batch_cases == motor_hidden.BATCH_CASES == 30
    assert family.image == motor_hidden.SOLVER_IMAGE
    assert family.terminal == motor_hidden.TERMINAL
    assert family.active_batches == 3
    assert family.every_blocks == 648_000
    assert family.document_schema != motor_hidden.DOCUMENT_SCHEMA


def test_the_rule_cites_the_sealed_exam_and_never_restates_scoring():
    rule = sealed.hidden_rule()
    assert rule["exam"] == {
        "pack_version": "motor-normal-construction-development-2",
        "evaluation_version": "motor-dual-sealed-batch-30-v1",
    }
    assert rule["challenge"] == {"id": MOTOR, "version": "1.1"}
    assert physical_pack.PACK_VERSIONS[(MOTOR, "1.1")] == sealed.PACK_VERSION
    text = json.dumps(rule)
    for scoring in ("weight", "threshold", "margin", "reward", "min_torque"):
        assert scoring not in text


def test_the_contract_digest_is_the_served_1_1_kit():
    from carbon.challenge_kit import physical_material
    from carbon.challenge_validator.interface import digest

    kit = physical_material.bundle_material(MOTOR, "1.1")["construction_kit"]
    assert sealed.contract_digest() == digest(kit)


def document(seed=5):
    cases = population.draw(random.Random(seed), 30)
    cases = cases[0] if type(cases) is tuple else cases
    return {
        "schema": sealed.DOCUMENT_SCHEMA,
        "challenge": {"id": MOTOR, "version": "1.1"},
        "role": "exam",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"m{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }


def test_documents_are_checked_at_1_1():
    good = document()
    assert len(sealed.check_document(good)) == 30
    for bad in (
        dict(good, challenge={"id": MOTOR, "version": "1.0"}),
        dict(good, schema=motor_hidden.DOCUMENT_SCHEMA),
        dict(good, cases=good["cases"][:29]),
        dict(good, kind="final"),
    ):
        with pytest.raises(ValueError):
            sealed.check_document(bad)


def records_for(doc):
    from carbon.motor.domain import ANGLE_STEPS

    out = []
    for case in doc["cases"]:
        j = case["inputs"]["current_density_a_mm2"]
        out.append(
            {
                "case_id": case["case_id"],
                "status": "OK",
                "inputs": case["inputs"],
                "image": sealed.SOLVER_IMAGE,
                # Synthetic, non-production curve.
                "outputs": {
                    "torque_nm": [0.4 * j + 0.01 * k for k in range(ANGLE_STEPS)]
                },
            }
        )
    return out


def test_the_bank_has_motors_development_bank_shape():
    doc = document()
    mine = pack.sealed_bank(doc, records_for(doc))
    theirs = physical_pack.development_bank(MOTOR, "1.1")
    assert set(mine) == set(theirs)
    assert mine["inputs"].dtype == theirs["inputs"].dtype
    assert mine["inputs"].shape[1] == theirs["inputs"].shape[1]
    assert mine["references"].shape == (30, theirs["references"].shape[1])
    assert mine["cohorts"] == ("screening",) * 30
    assert list(mine["case_ids"]) == sorted(mine["case_ids"])
    assert not mine["inputs"].flags.writeable


def test_an_exam_is_the_whole_batch_or_nothing():
    doc = document()
    records = records_for(doc)

    def refusal(recs):
        with pytest.raises(pack.SealedPackRefused) as refused:
            pack.sealed_bank(doc, recs)
        return refused.value.code

    assert refusal(records[:29]) == "motor_sealed_case_unresolved"
    failed = copy.deepcopy(records)
    failed[4] = {k: failed[4][k] for k in ("case_id", "inputs", "image")} | {
        "status": "REFERENCE_INVALID"
    }
    assert refusal(failed) == "motor_sealed_case_unresolved"
    short = copy.deepcopy(records)
    short[1]["outputs"]["torque_nm"] = short[1]["outputs"]["torque_nm"][:59]
    assert refusal(short) == "motor_sealed_record_malformed"
    other_image = copy.deepcopy(records)
    other_image[2]["image"] = "sha256:" + "0" * 64
    assert refusal(other_image) == "motor_sealed_record_malformed"
    assert refusal(records + [records[0]]) == "motor_sealed_records_mismatch"
    with pytest.raises(pack.SealedPackRefused):
        pack.sealed_bank(doc, records, version="1.0")


def test_the_selector_keeps_1_0_and_adds_1_1(tmp_path):
    hidden = write_hidden_deployment(
        tmp_path / "etc-hidden" / "motor.json",
        store=str(tmp_path / "hidden-store"),
        custody=str(tmp_path / "hidden-custody"),
    )
    MotorBatchSource.init(hidden)
    assert type(motor_source_for(hidden, repository=REPOSITORY)) is MotorBatchSource
    path = write_deployment(
        tmp_path / "etc-sealed" / "motor.json",
        store=str(tmp_path / "sealed-store"),
        custody=str(tmp_path / "sealed-custody"),
    )
    MotorSealedBatchSource.init(path)
    chosen = motor_source_for(path, repository=REPOSITORY)
    assert type(chosen) is MotorSealedBatchSource


def test_a_sealed_batch_is_drawn_solved_with_a_retry_sealed_and_packed(tmp_path):
    path = write_deployment(
        tmp_path / "producer-etc" / "motor.json",
        store=str(tmp_path / "producer-store"),
        custody=str(tmp_path / "producer-custody"),
    )
    MotorSealedBatchSource.init(path)
    solver = Solver()
    source = MotorSealedBatchSource(path, repository=REPOSITORY, runner=solver)
    producer = pr.Producer(tmp_path / "producer", [source])
    drawn = producer.draw(MOTOR, "motor-exam-S1", kind="screening")
    jobs = source.jobs(drawn["fingerprint"])
    assert len(jobs) == 30
    solver.fail = {jobs[0]["case_id"]}
    producer.solve(MOTOR, drawn["fingerprint"])
    producer.seal(MOTOR, drawn["fingerprint"])
    assert [len(p) for p in solver.planned] == [30, 1]  # only the retry
    assert source.sealed(drawn["fingerprint"])["cases"] == 30


def test_a_shared_deployment_is_refused(tmp_path):
    path = write_deployment(tmp_path / "etc" / "motor.json", store="s")
    path.chmod(0o644)
    with pytest.raises(sealed.MotorSealedError) as refused:
        sealed.load_deployment(path)
    assert refused.value.code == "motor_sealed_deployment_not_owner_only"
