"""The official pool grade of one submitted model, and a fixture sealed set run through the whole route
(Validator V8_RULINGS section 10): the receiver's single inference (a stand-in model server, labelled) ->
`pool_exam.measure_pool` -> the dual pack's total -> KOTH at set level -> the winner source -> the weights preview.

Every Challenge number here is a SYNTHETIC test value on a toy Challenge (`test_pool_plugin`); nothing is production.
"""

from __future__ import annotations

import dataclasses
import math
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_bank_koth_comparator import KEY, _Pairs, pair
from test_battery_od4a_dispatch import SPEC, Backend, chain, snapshot
from test_e8_weight_source_fixtures import NOISE, _registry, _set_body, _set_comparator
from test_pool_plugin import (
    INPUTS,
    U,
    bank_legs,
    bank_rows,
    binding,
    fake_measure,
    good_serve,
    toy_target,
    truth,
)

from carbon.battery.pool_store import PoolStore
from carbon.challenge_registry import speed_gate
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator.interface import digest
from carbon.rewards import testnet_winner_publication as twp
from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import DAY_MS, Q12
from carbon.scoring import pool_exam as exam
from carbon.scoring import pool_gates, pool_plugin
from carbon.scoring import pool_proof_suite as suite
from carbon.scoring.pool_grader import HonestyPolicy, OptimizerPolicy

POLICIES = suite.Policies(
    optimizer=OptimizerPolicy(budget=90, sigma0=0.3, population=None),
    honesty=HonestyPolicy(scale=5.0, reduction="max"),
    agen_scales={"f": 0.1, "g": 0.1},
    a_rule={"kind": "min"},
    c_rule={"kind": "min"},
)
ARGUMENTS = {
    "definition": {},
    "limits": {},
    "objective": {},
    "train_raw": b"",
    "names": INPUTS,
}
CEILING = speed_gate.ceiling_seconds("f02")
FAST = [CEILING / 4] * exam.SPEED_SAMPLE


class _NonNegative:
    """A toy Challenge's physics contract: the first raw output may not be negative."""

    gate_names = ("nonnegative_f",)

    def failed(self, inputs_row, raw_row):
        return [] if raw_row[0] >= 0 else ["nonnegative_f"]


def toy_binding(serve=good_serve):
    return dataclasses.replace(binding(serve), physics_gates=_NonNegative())


def sets():
    return (
        (toy_target("t1", 11), toy_target("t2", 12)),
        (toy_target("t3", 13), toy_target("t4", 14)),
    )


def exam_rows(the_sets):
    """The exam's bank: the sealed grader's cells and probes, plus every pool row marked as such."""
    rows = [dict(row, cohort="sealed") for row in bank_rows()]
    for row in pool_gates.pool_rows(toy_binding(), [s for g in the_sets for s in g]):
        rows.append({**row, "cohort": exam.POOL_COHORT})
    return rows


def answers(rows, serve=good_serve):
    """STAND-IN for the receiver's one inference over every exam row (the real one runs in the sandbox)."""
    return serve([r["inputs"] for r in rows])


def grade(
    serve=good_serve,
    *,
    the_sets=None,
    speed=FAST,
    policies=POLICIES,
    mutate_rows=None,
):
    the_sets = the_sets or sets()
    rows = exam_rows(the_sets)
    if mutate_rows:
        rows = mutate_rows(rows)
    outputs = answers(rows, serve)
    return exam.measure_pool(
        binding=toy_binding(),
        sets=the_sets,
        policies=policies,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=speed,
        ceiling_seconds=CEILING,
    )


def total_of(measured):
    return 0.5 * measured["A"] + 0.5 * measured["D"]


# --- the speed gate: single calls, median -------------------------------------------------


def test_the_speed_sample_is_a_custody_seeded_draw_of_twenty_distinct_rows():
    seed = b"custody-seed-for-this-grade-0001"
    first = exam.speed_sample(400, seed=seed)
    assert first == exam.speed_sample(400, seed=seed) == sorted(first)
    assert (
        len(set(first)) == exam.SPEED_SAMPLE == 20
        and 0 <= min(first) <= max(first) < 400
    )
    assert exam.speed_sample(400, seed=b"another-grade-seed-000002") != first
    for bad in (b"short", "not bytes", None):
        with pytest.raises(exam.ExamRefused, match="custody_bytes"):
            exam.speed_sample(400, seed=bad)
    with pytest.raises(exam.ExamRefused, match="larger_than_the_pool"):
        exam.speed_sample(19, seed=seed)


def test_the_gate_compares_the_median_single_call_with_the_registered_ceiling():
    gate = exam.single_call_speed_gate(FAST, ceiling_seconds=CEILING)
    assert gate["passed"] and gate["code"] is None and gate["calls"] == 20
    # One slow call does not fail it (a cold first call), and nine fast ones do not rescue it.
    assert exam.single_call_speed_gate(
        [CEILING * 50] + [CEILING / 2] * 19, ceiling_seconds=CEILING
    )["passed"]
    slow_median = [CEILING / 100] * 9 + [CEILING * 2] * 11
    failed = exam.single_call_speed_gate(slow_median, ceiling_seconds=CEILING)
    assert not failed["passed"] and failed["code"] == pool_gates.SPEED_CODE
    # The amortising game: a model with a large fixed cost per call looks fast when 400 designs share one call
    # (1.2 x ceiling / 400 per design) but every single-design call costs 1.2 x ceiling: the median fails it.
    per_call = [CEILING * 1.2] * 20
    assert per_call[0] / 400 < CEILING
    assert (
        exam.single_call_speed_gate(per_call, ceiling_seconds=CEILING)["passed"]
        is False
    )


@pytest.mark.parametrize(
    "timings",
    [
        [CEILING] * 19,
        [CEILING] * 21,
        [0.0] * 20,
        [-1.0] * 20,
        [math.nan] * 20,
        ["1"] * 20,
    ],
)
def test_malformed_timings_are_refused_not_graded(timings):
    with pytest.raises(exam.ExamRefused):
        exam.single_call_speed_gate(timings, ceiling_seconds=CEILING)


def test_the_ceiling_is_the_registered_one_for_each_launch_challenge():
    for challenge, solver in speed_gate.SOLVER_SECONDS_PER_DESIGN.items():
        assert speed_gate.ceiling_seconds(challenge) == round(
            solver / speed_gate.RATIO, 2
        )


# --- the grade ------------------------------------------------------------------------------


def test_the_official_grade_equals_the_proof_suites_for_the_same_model():
    """The official route and the receipted proof suite share the arithmetic: same model, same total."""
    the_sets = sets()
    measured = grade(the_sets=the_sets)
    assert (
        all(measured["gates"].values())
        and measured["decision_outcome"] == exam.OUTCOME_POOL
    )
    legs = bank_legs("measured")
    plugin = pool_plugin.make_plugin(
        toy_binding(), legs, the_sets, lambda seed: the_sets[0], pool_gates=True
    )
    proof_total = suite.version_total(plugin, {"kind": "good"}, POLICIES)
    assert total_of(measured) == pytest.approx(proof_total, abs=1e-12)
    assert 0.0 < total_of(measured) < 1.0
    assert measured["pool"]["sets"] == 2 and measured["pool"]["reasons"] == []


def test_the_grade_is_deterministic_and_a_better_model_scores_higher():
    first = total_of(grade())
    assert first == total_of(grade())
    perfect = total_of(grade(serve=lambda rows: [truth(r) for r in rows]))
    worse = total_of(
        grade(serve=lambda rows: [[v + 6 * U for v in truth(r)] for r in rows])
    )
    assert perfect >= first > worse


def test_a_mandatory_gate_failure_gives_no_score_and_names_only_the_gate():
    # (1) the speed gate: median above the ceiling
    slow = grade(speed=[CEILING * 3] * 20)
    assert slow["gates"][exam.SPEED_GATE] is False and slow["D"] == 0.0
    assert exam.public(slow) == {
        "status": "GATE_FAILED",
        "gates": ["speed"],
        "reasons": [],
    }

    # (2) a physics gate violated on ONE pool answer, in range or out
    def serve(rows):
        out = good_serve(rows)
        for index, row in enumerate(rows):
            if row["x"] > 0.97:
                out[index] = [-1.0] + out[index][1:]
        return out

    broken = grade(serve=serve)
    assert broken["gates"][exam.PHYSICS_GATE] is False
    assert exam.public(broken)["gates"] == [exam.PHYSICS_GATE]
    assert all(v is True for k, v in broken["gates"].items() if k != exam.PHYSICS_GATE)

    # (3) the sealed grader's own native gate (a non-rising probe answer fails the law)
    def flat(rows):
        return [[0.3, 0.3] for _ in rows]

    native = grade(serve=flat)
    assert native["gates"]["physics_laws"] is False
    assert "physics_laws" in exam.public(native)["gates"]
    for measured in (slow, broken, native):
        public = exam.public(measured)
        assert set(public) == {
            "status",
            "gates",
            "reasons",
        }  # no total, pick, timing or point


def test_the_exam_material_must_match_the_targets_and_the_c_rule_must_be_min():
    the_sets = sets()
    with pytest.raises(exam.ExamRefused, match="pool_rows_differ"):
        grade(the_sets=the_sets, mutate_rows=lambda rows: rows[:-1])
    with pytest.raises(exam.ExamRefused, match="needs_sealed_rows_and_pool_rows"):
        grade(
            mutate_rows=lambda rows: [
                r for r in rows if r["cohort"] != exam.POOL_COHORT
            ]
        )
    gate_rule = dataclasses.replace(POLICIES, c_rule={"kind": "gate", "floor": 0.1})
    with pytest.raises(exam.ExamRefused, match="c_rule_must_be_min"):
        grade(policies=gate_rule)


def test_only_the_submitted_models_table_is_ever_read():
    """The official grade never asks for the TRAIN fit, the default or the floor (proof-suite controls)."""
    for name in ("train_model", "default_model", "floor_model"):
        with pytest.raises(exam.ExamRefused, match="not_part_of_the_official_grade"):
            exam._refused(name)({}, [])


# --- one fixture sealed set through the whole route ------------------------------------------


def _crown(tmp_path, monkeypatch, measured, *, noise=NOISE):
    """KOTH at set level: the grade's total is the model's set-level evidence for the exam's comparator."""
    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 0.0)
    store.admit(
        "a",
        request_digest=digest(["request", "a"]),
        hotkey="miner-hotkey",
        challenge="electric-motor-magnetics",
        strategy={},
        binding={"challenge": {"id": "electric-motor-magnetics"}},
    )
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    comparator = _set_comparator(_registry(tmp_path, noise))
    monkeypatch.setattr(
        store,
        "private_evaluation_pair",
        _Pairs(
            store, {"a": pair(_set_body("a", comparator, total_of(measured)), None)}
        ),
    )
    return store, flow.consider_private("a", KEY, comparator, sealed=True)


def _weights(store, tmp_path):
    from carbon.transport.store import ReceiptJournal

    policy = wd.load_policy("testnet-winner-v4-launch")
    record = tmp_path / "owner-record.md"
    record.write_text("fixture owner record")
    auth = twp.StandingAuthorization(
        authority_record_digest=__import__("hashlib")
        .sha256(record.read_bytes())
        .hexdigest(),
        policy_digest=policy.digest,
        context=chain(),
        publisher_hotkey="owner-hotkey",
        expected_runtime_spec=SPEC,
        valid_from_block=900,
        valid_through_block=2000,
    )
    sources = {
        challenge: (
            (lambda: we.lean_promotion(store))
            if challenge == "electric-motor-magnetics"
            else (lambda: None)
        )
        for challenge in policy.challenges
    }
    issuer = twp.TestnetWinnerIntentIssuer(
        ReceiptJournal(tmp_path / "journal.sqlite3", chain()),
        auth,
        policy,
        we.WinnerLedger(tmp_path / "ledger.jsonl"),
        sources,
    )
    return policy, issuer


def test_a_fixture_sealed_set_runs_receiver_to_grade_to_koth_to_weights(
    tmp_path, monkeypatch
):
    # 1. receiver: ONE inference over the sealed pack's rows (stand-in), plus 20 single-row timed calls (stand-in)
    the_sets = sets()
    rows = exam_rows(the_sets)
    pool_positions = [i for i, r in enumerate(rows) if r["cohort"] == exam.POOL_COHORT]
    sampled = exam.speed_sample(
        len(pool_positions), seed=b"custody-seed-for-this-grade-0002"
    )
    assert len(sampled) == 20  # the rows each timed in its own call
    # 2. the official measure: A, D, gates (native + physics + speed)
    measured = grade(the_sets=the_sets)
    assert exam.public(measured)["status"] == "SCORED"
    total = total_of(measured)
    assert 0.2 < total < 1.0
    # 3. KOTH at set level: a sealed crown under a registered noise
    store, outcome = _crown(tmp_path, monkeypatch, measured)
    assert outcome["outcome"] == bp.FIRST_INCUMBENT
    assert store.incumbent()["reason"] == bp.SEALED_TESTNET_PROMOTION
    # 4. weights: the crown's share under the launch policy, the rest burning to UID 0
    _, issuer = _weights(store, tmp_path)
    state = snapshot(chain(), block=925)
    preview = twp.preview(issuer, state)
    share = Q12 // 4
    assert preview["records"]["electric-motor-magnetics"]["hotkey"] == "miner-hotkey"
    assert preview["targets"]["burn"] == Q12 - share
    backend = Backend(state)
    publisher = twp.TestnetWinnerPublisher(issuer, backend)
    import asyncio

    observed, _ = asyncio.run(backend.observe())
    result = asyncio.run(publisher.publish(issuer.issue(observed)))
    assert result["document"]["plan"]["q12"] == [[0, Q12 - share], [1, share]]
    later = dataclasses.replace(state, timestamp_ms=state.timestamp_ms + DAY_MS)
    assert twp.preview(issuer, later)["targets"]["burn"] == Q12 - share // 2


def test_a_gate_failed_model_scores_zero_and_never_takes_a_crown(tmp_path, monkeypatch):
    measured = grade(speed=[CEILING * 3] * 20)
    assert total_of(measured) <= 0.5 * (measured["A"] or 0.0)
    store, outcome = _crown(tmp_path, monkeypatch, {**measured, "A": 0.0, "D": 0.0})
    assert outcome["outcome"] != bp.FIRST_INCUMBENT
    assert store.incumbent() is None
