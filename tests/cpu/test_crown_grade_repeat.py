"""A crown change needs a second, bit-identical grade (OWNER-CROWN-GRADE-REPEAT-01).

Synthetic pairs shaped like `PoolStore.private_evaluation_pair` output; no model,
solver or reference runs. The store is a recording stub: the question is only
whether `consider_private` moves the crown.
"""

from copy import deepcopy

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator.interface import digest

PACK = digest("score pack")
KEY = digest("evaluation context")
NOISE = {"value": 0.1, "measurement_digest": digest("rebuild noise record")}


def body(model, status=bp.SCORED, total=1.0):
    return {
        "submission_id": model,
        "evidence": {
            "schema": bp.PAIRED_BINDING,
            "challenge": "electric-motor-magnetics",
            "score_compatibility": {"score_pack_digest": PACK},
            "entry_id": digest(["entry", model]),
            "model_p": {"score_status": status, "total_score": total},
        },
    }


def pair(candidate, incumbent):
    return {
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "evaluation_key": KEY,
        "expected_incumbent": None if incumbent is None else incumbent["submission_id"],
        "candidate": candidate,
        "incumbent": incumbent,
    }


def comparator(noise=NOISE):
    return {
        "schema": bp.COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": "electric-motor-magnetics",
        "score_pack_digest": PACK,
        "rebuild_noise": noise,
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": [digest("baseline run")],
        "baseline_total": 0.5,
    }


class Store:
    def __init__(self, fixed, marks=None):
        self.fixed = fixed
        self.moves = []
        self.marks = dict(marks or {})

    def record_baseline(self, *args):
        pass

    def incumbent(self):
        return None

    def private_evaluation_pair(self, *args, **kwargs):
        return self.fixed

    def repeat_verified(self, submission_id, key):
        return self.marks.get((submission_id, key))

    def record_repeat_verified(self, submission_id, key, fingerprint):
        self.marks[(submission_id, key)] = fingerprint

    def set_incumbent(self, model_id, reason, *, expected):
        self.moves.append(("set", model_id, expected))

    def vacate_incumbent(self, expected, reason):
        self.moves.append(("vacate", expected))


def consider(fixed, repeat, marks=None, store=None, noise=NOISE):
    store = store or Store(fixed, marks)
    # The constructor wants a real PoolStore; the stub keeps the question to the gate.
    promotion = bp.BankPromotion.__new__(bp.BankPromotion)
    promotion.store = store
    promotion.registered_source_receipt_sha256 = digest("pin")
    outcome = promotion.consider_private(
        fixed["candidate"]["submission_id"], KEY, comparator(noise), repeat=repeat
    )
    return outcome, store.moves


def same_again(fixed):
    rows = {fixed["candidate"]["submission_id"]: fixed["candidate"]}
    if fixed["incumbent"]:
        rows[fixed["incumbent"]["submission_id"]] = fixed["incumbent"]
    # A second grade has its own entry id and the same graded result.
    return lambda model: _fresh_entry(rows[model])


def _fresh_entry(row):
    copy = deepcopy(row)
    copy["evidence"]["entry_id"] = digest(["second grade", row["submission_id"]])
    return copy


CASES = {
    "first_crown": pair(body("c", total=0.95), None),
    "takeover": pair(body("c", total=0.95), body("k", total=0.5)),
    "dethrone": pair(
        body("c", bp.SCORED, 0.95), body("k", "MANDATORY_GATE_FAILED", 0.0)
    ),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_identical_second_grade_lets_the_crown_change(name):
    fixed = CASES[name]
    outcome, moves = consider(fixed, same_again(fixed))
    assert outcome["outcome"] in (bp.FIRST_INCUMBENT, bp.CHALLENGER)
    assert moves == [("set", "c", fixed["expected_incumbent"])]


def test_dethrone_without_a_successor_vacates_after_an_identical_repeat():
    fixed = pair(body("c", "FAILED_INFRA"), body("k", "MANDATORY_GATE_FAILED", 0.0))
    # Candidate unscored and incumbent failed its gate: dethroned, nobody takes it.
    outcome, moves = consider(fixed, same_again(fixed))
    assert outcome["outcome"] == bp.DETHRONED
    assert moves == [("vacate", "k")]


def moved(row, by):
    """``row`` with its total moved ``by`` (down when that would leave 0..1 upward)."""
    total = row["evidence"]["model_p"]["total_score"]
    row["evidence"]["model_p"]["total_score"] = (
        total - by if total >= by else total + by
    )
    return row


@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("who", ["candidate", "incumbent"])
def test_a_repeat_beyond_the_registered_tolerance_is_failed_infra_and_moves_nothing(
    name, who
):
    fixed = CASES[name]
    if fixed[who] is None:
        pytest.skip("this case has no such state")
    target = fixed[who]["submission_id"]
    again = same_again(fixed)

    def beyond(model):
        row = again(model)
        return moved(row, 0.2) if model == target else row  # NOISE is 0.1

    outcome, moves = consider(fixed, beyond)
    assert outcome["outcome"] == bp.FAILED_INFRA
    assert outcome["reason"] == bp.REPEAT_MISMATCH
    assert outcome["alert"]["schema"] == bp.ALERT_SCHEMA
    assert outcome["alert"]["states"] == [target]
    assert outcome["alert"]["action"] == "recheck_validator_host"
    # The alert names ids only: no grade value of either run.
    assert "total_score" not in repr(outcome["alert"])
    assert moves == []


@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("by", [2**-53, 0.03, 0.1])
def test_a_repeat_within_the_registered_tolerance_lets_the_crown_change(name, by):
    fixed = CASES[name]
    again = same_again(fixed)

    def near(model):
        return moved(again(model), by)

    outcome, moves = consider(fixed, near)
    assert outcome["outcome"] in (bp.FIRST_INCUMBENT, bp.CHALLENGER)
    assert moves == [("set", "c", fixed["expected_incumbent"])]


def test_a_changed_verdict_is_failed_infra_whatever_the_size_of_the_change():
    # The device flips a gate verdict: the totals can agree and the grade still does not.
    fixed = CASES["takeover"]
    again = same_again(fixed)

    def flipped(model):
        row = again(model)
        if model == "c":
            row["evidence"]["model_p"]["score_status"] = "MANDATORY_GATE_FAILED"
        return row

    outcome, moves = consider(fixed, flipped)
    assert outcome["outcome"] == bp.FAILED_INFRA and moves == []


def test_only_score_level_values_have_a_tolerance_everything_else_is_exact():
    first = body("c", total=0.95)
    first["evidence"]["model_p"].update(
        physics_benefit=0.9, design_benefit=0.8, gate_outcomes={"g": "pass", "x": 1.5}
    )
    second = deepcopy(first)
    second["evidence"]["model_p"].update(physics_benefit=0.93, design_benefit=0.76)
    assert bp.repeat_agrees(first, second, 0.1)
    second["evidence"]["model_p"]["gate_outcomes"]["x"] = 1.5 + 2**-52
    assert not bp.repeat_agrees(first, second, 0.1)
    third = deepcopy(first)
    third["evidence"]["score_compatibility"] = {"score_pack_digest": digest("other")}
    assert not bp.repeat_agrees(first, third, 0.1)
    fourth = deepcopy(first)
    fourth["evidence"]["model_p"]["extra"] = 1
    assert not bp.repeat_agrees(first, fourth, 0.1)


@pytest.mark.parametrize("name", sorted(CASES))
def test_no_registered_tolerance_is_unavailable_and_runs_no_repeat(name):
    fixed = CASES[name]

    def never(model):
        raise AssertionError("no tolerance, no repeat")

    store = Store(fixed)
    outcome, moves = consider(fixed, never, store=store, noise=None)
    # A crown change needs the tolerance; the comparison itself may already be UNAVAILABLE without noise.
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert moves == [] and store.marks == {}


def test_the_dethrone_without_a_successor_also_needs_the_tolerance():
    fixed = pair(body("c", "FAILED_INFRA"), body("k", "MANDATORY_GATE_FAILED", 0.0))
    outcome, moves = consider(fixed, same_again(fixed), noise=None)
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert outcome["reason"] == bp.REPEAT_TOLERANCE_UNREGISTERED
    assert moves == []


def test_negative_zero_agrees_within_the_tolerance():
    fixed = pair(body("c", "FAILED_INFRA"), body("k", "MANDATORY_GATE_FAILED", 0.0))

    def negated(model):
        row = same_again(fixed)(model)
        if model == "k":
            row["evidence"]["model_p"]["total_score"] = -0.0
        return row

    outcome, moves = consider(fixed, negated)
    assert outcome["outcome"] == bp.DETHRONED and moves == [("vacate", "k")]


def test_no_repeat_means_no_crown_change():
    fixed = CASES["takeover"]
    outcome, moves = consider(fixed, None)
    assert (outcome["outcome"], outcome["reason"]) == (
        bp.UNAVAILABLE,
        bp.REPEAT_UNAVAILABLE,
    )
    assert moves == []


@pytest.mark.parametrize("fault", [RuntimeError("daemon"), KeyError("k"), ValueError()])
def test_a_repeat_that_cannot_run_is_unavailable_never_a_win(fault):
    def broken(model):
        raise fault

    outcome, moves = consider(CASES["takeover"], broken)
    assert outcome["reason"] == bp.REPEAT_UNAVAILABLE and moves == []


def test_a_repeat_returning_a_malformed_row_is_unavailable():
    outcome, moves = consider(CASES["first_crown"], lambda model: {"evidence": None})
    assert outcome["reason"] == bp.REPEAT_UNAVAILABLE and moves == []


def test_unchanged_outcomes_never_ask_for_a_repeat():
    # Within the margin: the incumbent keeps the crown, so no second grade runs.
    fixed = pair(body("c", total=0.55), body("k", total=0.5))

    def never(model):
        raise AssertionError("no crown change, no repeat")

    outcome, moves = consider(fixed, never)
    assert outcome["outcome"] == bp.INCUMBENT_KEEPS and moves == []


def test_the_repeat_reads_the_grade_not_the_identity():
    fixed = CASES["first_crown"]
    assert bp.grade_fingerprint(fixed["candidate"]) == bp.grade_fingerprint(
        _fresh_entry(fixed["candidate"])
    )
    other = deepcopy(fixed["candidate"])
    other["evidence"]["score_compatibility"] = {"score_pack_digest": digest("other")}
    assert bp.grade_fingerprint(other) != bp.grade_fingerprint(fixed["candidate"])


def test_a_marked_incumbent_is_not_regraded_only_the_contender_is():
    fixed = CASES["takeover"]
    asked = []
    again = same_again(fixed)

    def repeat(model):
        asked.append(model)
        return again(model)

    marks = {("k", KEY): bp.grade_fingerprint(fixed["incumbent"])}
    outcome, moves = consider(fixed, repeat, marks)
    assert outcome["outcome"] == bp.CHALLENGER and moves == [("set", "c", "k")]
    assert asked == ["c"]


def test_a_mark_for_another_grade_does_not_count():
    # The incumbent was regraded since (new pack, rotation): its old mark names a different grade.
    fixed = CASES["takeover"]
    asked = []
    again = same_again(fixed)

    def repeat(model):
        asked.append(model)
        return again(model)

    stale = {("k", KEY): digest("the incumbent's earlier grade")}
    outcome, _moves = consider(fixed, repeat, stale)
    assert outcome["outcome"] == bp.CHALLENGER and asked == ["c", "k"]


def test_a_passed_change_files_a_mark_for_each_repeated_grade_and_a_failed_one_none():
    fixed = CASES["takeover"]
    store = Store(fixed)
    consider(fixed, same_again(fixed), store=store)
    assert store.marks == {
        ("c", KEY): bp.grade_fingerprint(fixed["candidate"]),
        ("k", KEY): bp.grade_fingerprint(fixed["incumbent"]),
    }
    again = same_again(fixed)

    def flipped(model):
        row = again(model)
        row["evidence"]["model_p"]["total_score"] += 2**-52
        return row

    failed = Store(fixed)
    consider(fixed, flipped, store=failed)
    assert failed.marks == {}


def test_an_unchanged_outcome_files_no_mark():
    fixed = pair(body("c", total=0.55), body("k", total=0.5))
    store = Store(fixed)
    consider(fixed, lambda model: 1 / 0, store=store)
    assert store.marks == {}
