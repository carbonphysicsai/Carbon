"""Cooling's Graphite public-practice scoring adapter.

The tests use only registered public TRAIN/PRACTICE material. They execute no
pod, solver, private reference, model-provider call or spend.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import pod_phase, pods
from carbon.challenge_validator import cooling_scoring
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


def test_registered_scorings_have_no_unnamed_default():
    assert cs.registered() == sorted(
        [
            "battery-fastcharge-ageing-development-v1",
            CHALLENGE.challenge_id,
            "electric-motor-magnetics",
        ]
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


def test_cooling_rule_scores_existing_public_references_with_testing_only_comparison():
    rule = scoring().frozen_rule(REPOSITORY)
    exact = {record["case_id"]: record["outputs"] for record in rule.practice.records}
    rows, summary = rule.score(exact)
    assert len(rows) == 100
    assert summary["eligible"] is True
    assert summary["score"] == 0.0
    comparison = rule.compare(rows, rows, True)
    assert comparison["outcome"] == "NO_IMPROVEMENT"
    assert comparison["promotable"] is False
    assert comparison["n"] == 100
    assert comparison["n_important"] == summary["n_important"] == 30
    assert comparison["mean_delta"] == 0.0
    assert comparison["ci"] == [0.0, 0.0]
    assert comparison["interpretation"].endswith("PUBLIC_PRACTICE_TESTING_ONLY")
    assert comparison["reference_available"] is True
    assert comparison["evidence_complete"] is True
    assert rule.identity["rule"] == "cold-plate-public-practice-v2"
    policy = rule.identity["comparison"]
    assert policy["margin_rel"] == 0.13157222884271824
    assert (
        policy["n_min"],
        policy["n_boot"],
        policy["alpha"],
        policy["important_min"],
    ) == (30, 4000, 0.05, 10)
    assert policy["fresh_confirmation"] is False
    assert rule.identity["coverage"] == cs.COVERAGE_RULE


def _test_rows(rule, ordinary=1.0, important=1.0):
    from carbon.cold_plate.exam import important as is_important

    return [
        {
            "case_id": ref["case_id"],
            "state": "SCORABLE",
            "important": is_important(ref),
            "error": important if is_important(ref) else ordinary,
            "components": {
                name: important if is_important(ref) else ordinary
                for name in ("peak", "profile", "pressure")
            },
            "gates": {},
        }
        for ref in rule.practice.records
    ]


def test_cooling_testing_comparison_improves_only_on_complete_paired_evidence():
    rule = scoring().frozen_rule(REPOSITORY)
    baseline = _test_rows(rule)
    improved = _test_rows(rule, 0.5, 0.5)
    result = rule.compare(baseline, improved, True)
    assert result == rule.compare(baseline, improved, True)
    assert result["outcome"] == "IMPROVEMENT"
    assert result["promotable"] is True
    assert result["n"] == 100 and result["n_important"] == 30
    assert result["mean_delta"] == pytest.approx(-0.5)
    assert result["ci"][1] < 0
    assert result["reference_available"] is True and result["evidence_complete"] is True


def test_cooling_important_region_regression_blocks_testing_promotion():
    rule = scoring().frozen_rule(REPOSITORY)
    result = rule.compare(_test_rows(rule), _test_rows(rule, 0.1, 1.5), True)
    assert result["overall"] == "better"
    assert result["important"] == "worse"
    assert result["outcome"] == "TRADE_OFF"
    assert result["regional_block"] is True and result["promotable"] is False


def test_cooling_component_tradeoff_is_not_a_testing_improvement():
    rule = scoring().frozen_rule(REPOSITORY)
    baseline = _test_rows(rule)
    candidate = _test_rows(rule)
    for row in candidate:
        row["components"] = {"peak": 0.5, "profile": 1.5, "pressure": 1.0}
    result = rule.compare(baseline, candidate, True)
    assert result["overall"] == "equivalent"
    assert result["components"]["peak"] == "better"
    assert result["components"]["profile"] == "worse"
    assert result["outcome"] == "TRADE_OFF" and result["promotable"] is False


def test_cooling_missing_prediction_is_candidate_gate_failure():
    rule = scoring().frozen_rule(REPOSITORY)
    exact = {record["case_id"]: record["outputs"] for record in rule.practice.records}
    exact.pop(rule.practice.case_ids[0])
    rows, summary = rule.score(exact)
    assert summary["n_missing"] == 1
    assert summary["n_gate_failed"] == 1
    assert summary["eligible"] is False
    assert rows[0]["state"] == "GATE_FAILED"


def test_cooling_comparison_preserves_violation_with_unavailable_case():
    rule = scoring().frozen_rule(REPOSITORY)
    baseline = _test_rows(rule)
    candidate = _test_rows(rule, 0.5, 0.5)
    candidate[0] = {"case_id": candidate[0]["case_id"], "state": "GATE_FAILED"}
    candidate[1] = {"case_id": candidate[1]["case_id"], "state": "FAILED_INFRA"}
    result = rule.compare(baseline, candidate, False)
    assert result["outcome"] == "REGRESSION"
    assert result["known_gate_failure"] is True
    assert result["reference_available"] is True
    assert result["evidence_complete"] is False
    assert result["promotable"] is False
    assert result["mean_delta"] is None and result["ci"] is None


@pytest.mark.parametrize("damage", ["missing", "duplicate", "infra", "reference"])
def test_cooling_comparison_refuses_incomplete_or_unavailable_evidence(damage):
    rule = scoring().frozen_rule(REPOSITORY)
    baseline = _test_rows(rule)
    candidate = _test_rows(rule, 0.5, 0.5)
    if damage == "missing":
        candidate.pop()
    elif damage == "duplicate":
        candidate[-1] = dict(candidate[0])
    elif damage == "infra":
        candidate[0] = {"case_id": candidate[0]["case_id"], "state": "FAILED_INFRA"}
    else:
        baseline[0] = {"case_id": baseline[0]["case_id"], "state": "REFERENCE_INVALID"}
    result = rule.compare(baseline, candidate, True)
    assert result["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert result["promotable"] is False and result["evidence_complete"] is False
    assert result["reference_available"] is (damage != "reference")
    assert result["mean_delta"] is None and result["ci"] is None


def test_cooling_margin_record_is_digest_pinned(monkeypatch):
    path = REPOSITORY / cooling_scoring.MARGIN_RECORD
    body = path.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(body).hexdigest() == cooling_scoring.MARGIN_SHA256
    monkeypatch.setattr(cooling_scoring, "MARGIN_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="digest mismatch"):
        scoring().frozen_rule(REPOSITORY)


def test_cooling_testing_comparison_preserves_ineligibility():
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
