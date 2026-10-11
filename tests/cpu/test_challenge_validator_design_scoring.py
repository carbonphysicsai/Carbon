"""Scoring a window's design questions (VALIDATOR-23 slice 3c): report-only.

Battery Q3 questions are filled into a small design bank with the scripted
truth (lattice, refine, settle), then scored as a validator scores them: the
model's lattice predictions, projected, through the neutral design score
(#827) under the Test Lead's registered rule. The q equals `score_tuning`'s
(q3_judge, q3_measures, member_legs) exactly, for a perfect and a flawed
model. The daemon's report and the pooled cross-window evidence follow.

Synthetic roots and scripted solves only: no container, chain, network or
spend. Not a security audit (AGENTS.md §13).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_design_windows import adapter
from test_challenge_validator_tuning_quiz import scripted_solve, solved

from carbon.battery import quiz_stratum as qs
from carbon.battery.value import quiz as bq
from carbon.battery.value import score_tuning
from carbon.battery.worker import WorkerFailure
from carbon.challenge_validator import design_bank as db
from carbon.challenge_validator import design_scoring as ds
from carbon.challenge_validator.battery_q3_bank import BatteryQ3Law
from carbon.challenge_validator.tuning import _records, _refined_records


@pytest.fixture(scope="module")
def bank(tmp_path_factory):
    """A small battery Q3 design bank: its live questions as a validator
    stores them, and the settled truth behind them."""
    tmp = tmp_path_factory.mktemp("design-scoring")
    saved = db.DESIGN_BANKS["battery-q3"]
    db.DESIGN_BANKS["battery-q3"] = {**saved, "size": 4}
    try:
        target = adapter(tmp / "producer-state").target
        law = BatteryQ3Law(target, repository=REPOSITORY)
        filled = db.DesignBank(
            tmp / "bank", law, lambda work, workers: scripted_solve(work, edge=True)
        )
        filled.top_up()
    finally:
        db.DESIGN_BANKS["battery-q3"] = saved
    contract = qs.contract(REPOSITORY)
    settled = {}
    questions = {}
    for row in filled.ledger.tranches(filled.bank):
        work = tmp / "bank" / "work" / row["role"]
        leaves = filled.ledger._leaves(row["role"])
        entries = [inputs["draw"] for _, inputs, _ in leaves]
        settled.update(
            qs.settle(
                _records(work),
                qs.refine_points(contract, entries, _records(work)),
                _refined_records(work),
            )
        )
        for case_id, inputs, reference in leaves:
            if reference["status"] == "OK":
                questions[case_id] = {
                    "task": inputs["task"],
                    "draw": inputs["draw"],
                    "reference": reference,
                }
    assert questions, "the scripted battery leaves at least one live question"
    return {
        "contract": contract,
        "settled": settled,
        "design": {"bank": "design:battery-q3", "questions": questions},
    }


def predictor(flaw=None):
    """A model's lattice predictions: the scripted standard truth, with an
    optional flaw applied to each candidate's outputs."""

    def predict(asked):
        found = {}
        for case_id, inputs in asked.items():
            outputs = solved({**inputs, "case_id": case_id}, edge=True)["outputs"]
            found[case_id] = flaw(inputs, outputs) if flaw else outputs
        return found

    return predict


def optimist(inputs, outputs):
    """Calls the edge column safe: plating margins read 5 mV higher."""
    return {**outputs, "plating_margin_v": outputs["plating_margin_v"] + 0.005}


def native_q(bank, predictions):
    """`score_tuning`'s q for the same questions and predictions."""
    contract = bank["contract"]
    outcomes = []
    for question in bank["design"]["questions"].values():
        scenario = qs.scenario(question["draw"])
        grid = bq.q3_grid(contract, scenario)
        outcomes.append(
            bq.q3_judge(
                contract,
                scenario,
                {job["case_id"]: predictions[job["case_id"]] for job in grid},
                {job["case_id"]: bank["settled"][job["case_id"]] for job in grid},
            )
        )
    regret = bq.q3_measures(outcomes, contract)["regret"]
    return score_tuning.member_legs(
        contract, {}, SimpleNamespace(refs={}, twins={}), [], decision_regret=regret
    )["legs"]["q"]


def test_the_rule_is_registered_by_the_test_lead():
    rule = ds.battery_q3_rule(REPOSITORY)
    assert rule["version"] == ds.RULE_VERSION
    assert ds.RULE_RECORD["registered_by"] == "Test Lead"
    assert ds.RULE_RECORD["registered_on"] == "2026-10-08"


@pytest.mark.parametrize("flaw", [None, optimist], ids=["perfect", "optimist"])
def test_q_equals_score_tuning_exactly(bank, flaw):
    measures = ds.BatteryQ3Measures(REPOSITORY)
    designs = {"f1": bank["design"]}
    predictions = predictor(flaw)(measures.inputs(designs))
    result = measures.measure(designs, predictions)
    window = result["batches"]["f1"]
    assert window["status"] == "OK", window
    assert window["q"] == native_q(bank, predictions)
    assert len(window["per_question"]) == len(bank["design"]["questions"])
    assert result["rule"] == ds.RULE_RECORD


def test_a_missing_prediction_is_the_candidates(bank):
    measures = ds.BatteryQ3Measures(REPOSITORY)
    designs = {"f1": bank["design"]}
    predictions = predictor()(measures.inputs(designs))
    predictions.pop(next(iter(predictions)))
    window = measures.measure(designs, predictions)["batches"]["f1"]
    assert (window["status"], window["eligible"], window["q"]) == (
        "INELIGIBLE",
        False,
        None,
    )


def test_the_daemon_reports_and_retries_infrastructure(bank, tmp_path, monkeypatch):
    target = adapter(tmp_path / "validator", import_only=True).target
    target.store.set_design("f1", "design:battery-q3", bank["design"]["questions"])
    monkeypatch.setattr(
        target.store,
        "score",
        lambda sid: {"record": {"active_batches": ["f1"]}, "pool_version": 1},
    )
    calls = []

    def predictions(sid, inputs, tag, namespace=None):
        calls.append((namespace, tag))
        if len(calls) == 1:
            raise WorkerFailure("infer_unavailable", candidate=False)
        return predictor()(inputs)

    monkeypatch.setattr(target, "_quiz_predictions", predictions)
    assert target.design_report("s1") is None  # no measures given: nothing
    target.design_measures = ds.BatteryQ3Measures(REPOSITORY)
    first = target.design_report("s1")
    assert (first["state"], first["code"]) == ("FAILED_INFRA", "infer_unavailable")
    second = target.design_report("s1")
    assert second["state"] == "MEASURED"
    assert second["batches"]["f1"]["status"] == "OK"
    assert second["rule"] == ds.RULE_RECORD
    assert calls[-1] == (target.DESIGN_PREDICTIONS, "design-v1")
    # A measured report is kept: the next call never predicts again.
    assert target.design_report("s1") == second and len(calls) == 2


def report(sid, fingerprint, losses, status="OK"):
    return {
        "submission_id": sid,
        "state": "MEASURED",
        "batches": {
            fingerprint: {
                "status": status,
                "q": None,
                "per_question": [
                    {"question_id": q, "outcome": "x", "loss": loss}
                    for q, loss in losses.items()
                ],
            }
        },
    }


def test_evidence_pools_windows_and_signs_against_the_reference():
    worse = [
        report("s1", "w1", {f"q{i}": 1.0 for i in range(3)}),
        report("s2", "w2", {f"q{i}": 1.0 for i in range(3, 6)}),
        {"submission_id": "s3", "state": "FAILED_INFRA", "batches": {}},
    ]
    found = ds.evidence(worse, {})
    assert (found["windows"], found["questions"], found["nonzero"]) == (2, 6, 6)
    assert found["p_value"] == pytest.approx(1 / 64)
    assert found["method"] == ds.EVIDENCE_METHOD and found["diagnostic"] is True
    # A miner as good as the reference shows no evidence.
    good = ds.evidence([report("s1", "w1", {"q0": 0.0, "q1": 0.0})], {})
    assert (good["nonzero"], good["p_value"]) == (0, 1.0)
    # The reference's own loss is subtracted per question.
    even = ds.evidence(worse[:1], {"q0": 1.0, "q1": 1.0, "q2": 1.0})
    assert even["nonzero"] == 0


def test_the_good_reference_loses_nothing_on_live_questions(bank):
    losses = ds.BatteryQ3Measures(REPOSITORY).reference_losses({"f1": bank["design"]})
    assert set(losses) == set(bank["design"]["questions"])
    assert all(loss == 0 for loss in losses.values())
