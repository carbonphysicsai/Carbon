"""PRACTICE-SAFETY-01 B4: the feasible-choice rate on the practice decision set.

The claims tested:
- the copied candidate grid and tie rule are EV4's;
- the set is pinned: a file that does not match `SHA256SUMS`, a `SHA256SUMS`
  that does not match its pin (even when it matches forged files) and a
  missing file are each refused with a typed reason, and nothing is computed;
  a mutant that skips the file digest check is killed;
- B4 is computed on the committed set and on fixtures: a reference-FEASIBLE
  choice counts, an INFEASIBLE one lowers the rate, an abstention and a
  choice the reference leaves UNRESOLVED are counted beside the rate, never
  in it, and a missing prediction makes B4 null and is counted;
- B4 is allow-listed: only its aggregate counts and rate leave, never a case
  id, condition value or per-condition verdict;
- the worker is asked for the set's inputs only, never a label.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path

import pytest

from carbon import practice_safety_feedback as ps
from carbon.battery import practice as battery_practice
from carbon.battery import practice_safety as bs
from carbon.battery.challenge import CHALLENGE
from carbon.battery.domain import INPUTS

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def battery():
    return battery_practice.PracticeSet.load(REPO)


@pytest.fixture(scope="module")
def decision():
    return bs.load_decision_set(REPO)


def oracle(decision):
    return {c: dict(decision.references[c]["outputs"]) for c in decision.case_ids}


def shifted(decision, plating=0.0, temperature=0.0):
    out = {}
    for case, outputs in oracle(decision).items():
        out[case] = {
            **outputs,
            "plating_margin_v": outputs["plating_margin_v"] + plating,
            "temperature_c": [t + temperature for t in outputs["temperature_c"]],
        }
    return out


def b4(predictions, decision):
    return bs.feasible_choice(predictions, decision)


# --- the copies are EV4's ----------------------------------------------------


def test_the_candidate_grid_and_tie_rule_are_ev4_s():
    from carbon.battery.value import contract as ev

    contract = json.loads((REPO / bs.CONTRACT_SOURCE).read_text())
    assert list(bs.CANDIDATES) == ev.candidates(contract)
    assert len(bs.CANDIDATES) == 35
    assert contract["tie_rule"] == (
        "lowest predicted objective; exact ties broken by lower c1, then lower c2"
    )


# --- the pin -----------------------------------------------------------------


def test_the_committed_set_matches_its_pins_and_shape(decision):
    sums = REPO / bs.DECISION_SET_PATH / "SHA256SUMS"
    assert hashlib.sha256(sums.read_bytes()).hexdigest() == bs.DECISION_SET_SUMS_SHA256
    assert decision.refused is None
    assert len(decision.conditions) == 6 and len(decision.case_ids) == 210
    assert all(r["status"] == "OK" for r in decision.references.values())


def _copy_set(root):
    target = Path(root) / bs.DECISION_SET_PATH
    shutil.copytree(REPO / bs.DECISION_SET_PATH, target)
    return target


def _rewrite_records(target):
    """A valid set file whose one reference is changed."""
    lines = gzip.decompress((target / "records.jsonl.gz").read_bytes()).splitlines()
    first = json.loads(lines[0])
    first["outputs"]["plating_margin_v"] += 1.0
    lines[0] = json.dumps(first).encode()
    (target / "records.jsonl.gz").write_bytes(gzip.compress(b"\n".join(lines) + b"\n"))


def _forge_sums(target):
    """A `SHA256SUMS` that matches the (forged) files beside it."""
    lines = [
        hashlib.sha256((target / name).read_bytes()).hexdigest() + "  " + name
        for name in ("records.jsonl.gz", "conditions.json")
    ]
    (target / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def _tamper_reasons(tmp_path):
    """The load outcome for each tampering: its refusal reason, or LOADED."""
    reasons = []
    for index, tamper in enumerate(("records", "conditions", "forged", "missing")):
        root = tmp_path / str(index)
        target = _copy_set(root)
        if tamper == "records":
            _rewrite_records(target)
        elif tamper == "conditions":
            document = json.loads((target / "conditions.json").read_text())
            document["conditions"][0]["t_amb_c"] += 0.1
            (target / "conditions.json").write_text(json.dumps(document))
        elif tamper == "forged":
            _rewrite_records(target)
            _forge_sums(target)
        else:
            (target / "records.jsonl.gz").unlink()
        try:
            bs.load_decision_set(root)
        except bs.DecisionSetRefused as refusal:
            reasons.append(refusal.reason)
        else:
            reasons.append("LOADED")
    return reasons


def test_a_set_that_does_not_match_its_pins_is_refused_with_a_typed_reason(
    tmp_path,
):
    assert _tamper_reasons(tmp_path) == [
        bs.B4_REFUSED_DIGEST,
        bs.B4_REFUSED_DIGEST,
        bs.B4_REFUSED_SUMS,
        bs.B4_REFUSED_MISSING,
    ]


def test_a_refused_set_stages_nothing_and_computes_nothing(
    battery, tmp_path, monkeypatch
):
    from carbon.battery.value import decision as d

    target = _copy_set(tmp_path)
    _rewrite_records(target)
    refused = bs.decision_set(tmp_path)
    assert refused.refused == bs.B4_REFUSED_DIGEST
    assert refused.cases() == [] and refused.case_ids == []

    def never(*args, **kwargs):
        raise AssertionError("a refused set computed B4")

    monkeypatch.setattr(d, "assess_predicted", never)
    monkeypatch.setattr(d, "assess_reference", never)
    predictions = {r["case_id"]: dict(r["outputs"]) for r in battery.records}
    document = bs.safety(predictions, battery, refused)
    assert document["metrics"]["B4"] == bs.B4_REFUSED_DIGEST
    assert document["metrics"]["B1"]["feedback_only"] is True
    assert document["unmeasured"] == 0


def test_an_untyped_refusal_cannot_be_raised():
    with pytest.raises(TypeError):
        bs.DecisionSetRefused("REFUSED: anything")


def _unpinned_file(root, name, sums):
    """The mutant: a set file read without its digest check."""
    try:
        return (Path(root) / bs.DECISION_SET_PATH / name).read_bytes()
    except OSError:
        raise bs.DecisionSetRefused(bs.B4_REFUSED_MISSING) from None


def test_the_digest_bypass_mutant_is_killed(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "_pinned_set_file", _unpinned_file)
    reasons = _tamper_reasons(tmp_path)
    assert reasons[0] == "LOADED"  # a changed reference would be used
    assert reasons != [
        bs.B4_REFUSED_DIGEST,
        bs.B4_REFUSED_DIGEST,
        bs.B4_REFUSED_SUMS,
        bs.B4_REFUSED_MISSING,
    ]


# --- B4 computed -------------------------------------------------------------

ORACLE_B4 = {
    "feasible_choice": 5,
    "chosen": 5,
    "rate": 1.0,
    "abstained": 1,
    "unresolved": 0,
    "feedback_only": True,
}


def test_b4_on_the_committed_set_with_the_reference_as_the_model(decision):
    assert b4(oracle(decision), decision) == (ORACLE_B4, 0)


def test_b4_lowers_the_rate_for_an_optimist_that_chooses_infeasible_protocols(
    decision,
):
    # Predicted plating margin up 1 V and temperature down 20 degC: every
    # protocol reads feasible, so the fastest is chosen at every condition.
    metric, unmeasured = b4(shifted(decision, plating=1.0, temperature=-20.0), decision)
    assert unmeasured == 0 and metric["abstained"] == 0
    assert metric["chosen"] + metric["unresolved"] == 6
    assert metric["feasible_choice"] < metric["chosen"]
    assert metric["rate"] < ORACLE_B4["rate"]


def test_b4_counts_abstentions_beside_the_rate_never_in_it(decision):
    metric, _ = b4(shifted(decision, plating=-1.0), decision)
    assert metric == {
        "feasible_choice": 0,
        "chosen": 0,
        "rate": None,
        "abstained": 6,
        "unresolved": 0,
        "feedback_only": True,
    }


def test_a_choice_the_reference_leaves_unresolved_is_counted_never_rated(decision):
    # Fixture: the first condition's references put every plating margin
    # inside its band of the limit, so the model's (unchanged) choice there
    # is UNRESOLVED at the reference.
    band = bs.DECISION_RULES["reference"]["uncertainty"]["bands"]["plating_margin_v"]
    first = set(decision.grid[0].values())
    records = []
    for case, record in decision.references.items():
        if case in first:
            record = {
                **record,
                "outputs": {**record["outputs"], "plating_margin_v": band / 4},
            }
        records.append(record)
    fixture = bs.DecisionSet.from_records(decision.conditions, records)
    metric, _ = b4(oracle(decision), fixture)
    assert metric == {**ORACLE_B4, "feasible_choice": 4, "chosen": 4, "unresolved": 1}


@pytest.mark.parametrize("broken", ["missing", None, math.nan])
def test_a_missing_decision_prediction_makes_b4_null_and_is_counted(
    battery, decision, broken
):
    predictions = {
        **{r["case_id"]: dict(r["outputs"]) for r in battery.records},
        **oracle(decision),
    }
    case = decision.case_ids[7]
    if broken == "missing":
        del predictions[case]
    elif broken is None:
        predictions[case] = None
    else:
        predictions[case] = {**predictions[case], "plating_margin_v": broken}
    document = bs.safety(predictions, battery, decision)
    assert document["metrics"]["B4"] is None
    assert document["unmeasured"] == 1
    assert document["metrics"]["B1"]["feedback_only"] is True


def test_an_incomplete_grid_is_refused_as_a_shape(decision):
    records = list(decision.references.values())[1:]
    with pytest.raises(bs.DecisionSetRefused) as refused:
        bs.DecisionSet.from_records(decision.conditions, records)
    assert refused.value.reason == bs.B4_REFUSED_SHAPE


# --- disclosure --------------------------------------------------------------


def _document(b4_metric):
    return ps.document(
        CHALLENGE.challenge_id,
        {"B1": None, "B2": None, "B3": None, "B4": b4_metric},
        unmeasured=0,
        unresolved=0,
        material={"path": "p", "sha256": "s"},
        allowed=bs.ALLOWED,
    )


@pytest.mark.parametrize("metric", [ORACLE_B4, None, *bs.B4_REFUSALS])
def test_the_allow_list_accepts_b4_s_aggregates_null_and_its_refusals(metric):
    assert _document(metric)["metrics"]["B4"] == metric


@pytest.mark.parametrize(
    "metric",
    [
        {**ORACLE_B4, "case_id": "practice-b4-P-T37.6-S0.344-c11-c20.8"},
        {**ORACLE_B4, "condition": "P-T37.6-S0.344"},
        {**ORACLE_B4, "t_amb_c": 37.6},
        {**ORACLE_B4, "per_condition": ["SELECTED_FEASIBLE"]},
        {**ORACLE_B4, "rate": math.nan},
        {**ORACLE_B4, "chosen": 5.0},
        {k: v for k, v in ORACLE_B4.items() if k != "feedback_only"},
        ps.B4_BLOCKED,
        "REFUSED: anything else",
    ],
)
def test_the_allow_list_refuses_anything_else_in_b4(metric):
    with pytest.raises(ps.DisclosureRefused):
        _document(metric)


def test_no_decision_case_id_or_condition_leaves(battery, decision):
    predictions = {
        **{r["case_id"]: dict(r["outputs"]) for r in battery.records},
        **oracle(decision),
    }
    document = bs.safety(predictions, battery, decision)
    assert document["metrics"]["B4"] == ORACLE_B4
    text = json.dumps(document)
    assert not [c for c in decision.case_ids if c in text]
    assert "P-T" not in text and "practice-b4" not in text
    assert set(document["metrics"]["B4"]) == set(ORACLE_B4)


def test_the_worker_is_asked_for_the_set_s_inputs_never_a_label(battery, decision):
    cases = decision.cases()
    assert len(cases) == 210
    assert all(set(c) == {"case_id", "inputs"} for c in cases)
    assert all(set(c["inputs"]) == set(INPUTS) for c in cases)
    document = battery.inputs_document(cases)
    assert document["schema"] == "carbon.battery.practice-inputs.v2"
    assert len(document["cases"]) == 410
    assert battery.inputs_document()["schema"] == "carbon.battery.practice-inputs.v1"
    with pytest.raises(battery_practice.MaterialMismatch):
        battery.inputs_document(cases[:1] + cases[:1])
