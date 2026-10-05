"""Cooling's Graphite public-practice scoring adapter.

The tests use only registered public TRAIN/PRACTICE material. They execute no
pod, solver, private reference, model-provider call or spend.
"""

import json
import os
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import pod_phase, pods
from carbon.challenge_validator import scoring as cs
from carbon.challenge_validator.cooling_scoring import CoolingScoring
from carbon.cold_plate.challenge import (
    CALIBRATION_PATH,
    CHALLENGE,
    PRACTICE_PATH,
    TRAIN_PATH,
)
from carbon.cold_plate.research import SCAFFOLD

REPOSITORY = Path(__file__).resolve().parents[2]


def scoring():
    return cs.scoring_for(CHALLENGE.challenge_id)


def test_cooling_reuses_only_the_registered_public_practice_surface():
    cooling = scoring()
    assert type(cooling) is CoolingScoring
    assert cooling.challenge() == {
        "id": CHALLENGE.challenge_id,
        "version": CHALLENGE.version,
    }
    assert cooling.ship_check() == (TRAIN_PATH, PRACTICE_PATH, CALIBRATION_PATH)
    assert cooling.served_backends == ("numpy",)
    assert cooling.baseline_strategy() is SCAFFOLD
    assert cooling.work_seconds() == 600


def test_two_registered_scorings_have_no_unnamed_default():
    assert cs.registered() == sorted(
        ["battery-fastcharge-ageing-development-v1", CHALLENGE.challenge_id]
    )
    with pytest.raises(cs.ScoringUnavailable) as refused:
        cs.scoring_for(None)
    assert refused.value.code == "challenge_scoring_must_be_named"


def test_cooling_build_is_identical_on_the_host_and_pod_routes():
    cooling = scoring()
    contract = cooling.recorded_contract()["contract_digest"]
    direct, files, program = cooling.built_record(SCAFFOLD, contract, 7, REPOSITORY)
    via_pod, pod_files, pod_program = pod_phase.built_record(
        SCAFFOLD, contract, 7, REPOSITORY
    )
    assert direct == via_pod
    assert files == pod_files and program == pod_program
    assert set(cs.REBUILT_FIELDS) <= set(direct)
    admitted = cs.admit(cooling, SCAFFOLD, 7, REPOSITORY)
    assert admitted == {**direct, "record_sequence": admitted["record_sequence"]}


def test_cooling_rule_scores_existing_public_references_without_new_claims():
    rule = scoring().frozen_rule(REPOSITORY)
    exact = {record["case_id"]: record["outputs"] for record in rule.practice.records}
    rows, summary = rule.score(exact)
    assert len(rows) == 100
    assert summary["eligible"] is True
    assert summary["score"] == 0.0
    comparison = rule.compare(rows, rows, True)
    assert comparison == {
        "outcome": "NO_IMPROVEMENT",
        "reason": "equal mean error on the shared public cases; no approved promotion rule",
        "interpretation": "DESCRIPTIVE_PAIRED_MEAN_DIFFERENCE",
        "promotable": False,
        "n": 100,
        "mean_delta": 0.0,
        "ci": None,
        "overall": {"n": 100, "mean_delta": 0.0},
        "important": {"n": summary["n_important"], "mean_delta": 0.0},
    }
    assert rule.identity["comparison"]["confidence_interval"] is None
    assert rule.identity["comparison"]["promotable"] is False


def test_cooling_descriptive_comparison_preserves_ineligibility():
    rule = scoring().frozen_rule(REPOSITORY)
    exact = {record["case_id"]: record["outputs"] for record in rule.practice.records}
    rows, _summary = rule.score(exact)
    result = rule.compare(rows, rows, False)
    assert result["outcome"] == "REGRESSION"
    assert result["promotable"] is False and result["ci"] is None


def test_synthetic_pod_fixture_is_challenge_owned_and_lower_is_better():
    cooling = scoring()
    contract = cooling.recorded_contract()["contract_digest"]
    job = pods.PodJob(
        intent_id="cooling-synthetic",
        strategy=SCAFFOLD,
        contract_digest=contract,
        seed=7,
        expected={"files": {}, "program": "sha256:" + "0" * 64},
        minutes=30,
        seconds=600,
    )
    rule = cooling.frozen_rule(REPOSITORY)
    scores = []
    for quality in (1.0, 0.4):
        files = pods.synthetic_outputs(quality, scoring=cooling)(job)
        predictions = json.loads(files["predictions.json"])
        _rows, summary = rule.score(predictions)
        assert summary["eligible"] is True
        scores.append(summary["score"])
    assert scores[1] < scores[0]


def test_cooling_graphite_dry_run_uses_the_named_adapter(tmp_path, capsys):
    if os.name != "posix":
        pytest.skip("the Graphite controller requires POSIX fcntl")
    from carbon.agent_campaign.graphite import phase3

    assert phase3.dry_run(tmp_path, scoring()) == 0
    output = capsys.readouterr().out
    result = json.loads(output[output.index("{\n") :])
    assert result["provider_state"] == "succeeded"
    assert result["delivery"]["clean_rebuild"]["status"] == "REBUILT"
    assert result["dry_run"]["synthetic"] is True
    assert result["dry_run"]["real_pod_path"]["status"] == "OK"
    assert len(result["findings"]) == 1
