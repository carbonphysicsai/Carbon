"""Motor Graphite public-practice scoring: no pod, solver or private material."""

import json
import os
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import pod_phase, pods
from carbon.challenge_validator import scoring as cs
from carbon.challenge_validator.motor_scoring import MotorScoring
from carbon.motor.challenge import (
    CALIBRATION_PATH,
    CHALLENGE,
    PRACTICE_PATH,
    TRAIN_PATH,
)
from carbon.motor.practice import PROGRAM, score_practice
from carbon.motor.research import SCAFFOLD

REPOSITORY = Path(__file__).resolve().parents[2]


def scoring():
    return cs.scoring_for(CHALLENGE.challenge_id)


def test_motor_is_named_and_public_only():
    motor = scoring()
    assert type(motor) is MotorScoring
    assert motor.challenge() == {
        "id": CHALLENGE.challenge_id,
        "version": CHALLENGE.version,
    }
    assert motor.ship_check() == (TRAIN_PATH, PRACTICE_PATH, CALIBRATION_PATH)
    assert motor.served_backends == ("numpy",)
    assert motor.baseline_strategy() is SCAFFOLD
    assert motor.work_seconds() == 600
    with pytest.raises(cs.ScoringUnavailable, match="challenge_scoring_must_be_named"):
        cs.scoring_for()
    with pytest.raises(cs.Unrebuildable) as refused:
        cs.admit(motor, {**SCAFFOLD, "challenge_id": "chip-cold-plate"}, 7, REPOSITORY)
    assert refused.value.code == motor.wrong_challenge_code


def test_motor_host_and_pod_rebuild_same_digest_bound_record():
    motor = scoring()
    contract = motor.recorded_contract()["contract_digest"]
    direct, files, program = motor.built_record(SCAFFOLD, contract, 7, REPOSITORY)
    via_pod, pod_files, pod_program = pod_phase.built_record(
        SCAFFOLD, contract, 7, REPOSITORY, scoring=motor
    )
    assert direct == via_pod
    assert files == pod_files and program == pod_program == PROGRAM
    assert set(cs.REBUILT_FIELDS) <= set(direct)
    assert cs.admit(motor, SCAFFOLD, 7, REPOSITORY) == {
        **direct,
        "record_sequence": motor.recorded_contract()["record_sequence"],
    }
    assert set(files) == {
        "learned-baseline.py",
        "motor-domain.py",
        "motor-recipes.py",
        "train-v1.jsonl",
        "practice-inputs.json",
        "recipe.json",
    }
    assert "outputs" not in json.loads(files["practice-inputs.json"])["cases"][0]


def test_motor_rule_reuses_public_exam_and_descriptive_comparison():
    rule = scoring().frozen_rule(REPOSITORY)
    exact = {record["case_id"]: record["outputs"] for record in rule.practice.records}
    rows, summary = rule.score(exact)
    original_rows, original_summary = score_practice(
        exact, rule.practice, rule.material
    )
    assert rows == [cs.clean(row) for row in original_rows]
    # The rule adds only the coverage count (GRAPHITE-COVERAGE-PARITY-02).
    assert summary == {**cs.clean(original_summary), "n_missing": 0}
    assert len(rows) == 30 and summary["eligible"] is True and summary["score"] == 0.0
    comparison = rule.compare(rows, rows, True)
    assert comparison["outcome"] == "NO_IMPROVEMENT"
    assert comparison["overall"] == {"n": 30, "mean_delta": 0.0}
    assert comparison["important"] == {"n": summary["n_important"], "mean_delta": 0.0}
    assert comparison["promotable"] is False and comparison["ci"] is None
    assert rule.compare(rows, rows, False)["outcome"] == "REGRESSION"


def test_motor_synthetic_fixture_is_challenge_owned_and_nonpromoting():
    motor = scoring()
    contract = motor.recorded_contract()["contract_digest"]
    job = pods.PodJob(
        intent_id="motor-synthetic",
        strategy=SCAFFOLD,
        contract_digest=contract,
        seed=7,
        expected={"files": {}, "program": "sha256:" + "0" * 64},
        minutes=30,
        seconds=600,
    )
    rule = motor.frozen_rule(REPOSITORY)
    scores = []
    for quality in (1.0, 0.4):
        outputs = pods.synthetic_outputs(quality, scoring=motor)(job)
        predictions = json.loads(outputs["predictions.json"])
        _rows, summary = rule.score(predictions)
        assert summary["eligible"] is True
        scores.append(summary["score"])
    assert scores[1] < scores[0]
    assert rule.identity["comparison"]["promotable"] is False


def test_motor_graphite_dry_run_uses_named_adapter(tmp_path, capsys, monkeypatch):
    if os.name != "posix":
        pytest.skip("the Graphite controller requires POSIX fcntl")
    import containment_double

    from carbon.agent_campaign.graphite import phase3

    # The dry run's carrier containment check (synthetic passing double).
    containment_double.install(monkeypatch)
    assert phase3.dry_run(tmp_path, scoring()) == 0
    output = capsys.readouterr().out
    result = json.loads(output[output.index("{\n") :])
    assert result["provider_state"] == "succeeded"
    assert result["delivery"]["clean_rebuild"]["status"] == "REBUILT"
    assert result["dry_run"]["synthetic"] is True
    assert result["dry_run"]["real_pod_path"]["status"] == "OK"
