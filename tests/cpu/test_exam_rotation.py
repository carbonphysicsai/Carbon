# ruff: noqa: F811  (the imported `case` fixture is received as a test argument)
"""The weekly fresh-draw check and the overfit rotation signal (OWNER-CADENCE-AND-ROTATION-02)."""

import json
import math
from types import SimpleNamespace

import pytest
from test_physical_dual_pack_end_to_end import _produce, case  # noqa: F401

from carbon.challenge_kit import physical_pack
from carbon.challenge_validator import exam_cap, exam_rotation
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.scoring import dual_score
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import private_evaluation_source as source
from carbon.scoring.engine import ScoreEngine

SEALED, FRESH = "sha256:" + "a" * 64, "sha256:" + "b" * 64


# --- the decision -------------------------------------------------------------------


def test_the_threshold_is_the_margin_plus_two_se_of_the_difference():
    assert exam_rotation.threshold(0.01, 0.003, 0.004) == pytest.approx(
        0.01 + 2 * math.sqrt(0.003**2 + 0.004**2)
    )
    assert exam_rotation.threshold(0.0, 0.0, 0.0) == 0.0


def _decide(sealed, fresh, margin=0.01, se_sealed=0.003, se_fresh=0.004):
    return exam_rotation.decide(
        sealed_total=sealed,
        fresh_total=fresh,
        margin=margin,
        se_sealed=se_sealed,
        se_fresh=se_fresh,
    )


def test_rotation_needs_the_sealed_total_to_beat_the_fresh_one_beyond_the_threshold():
    # Exact binary fractions, so the boundary is exact: threshold = margin with zero SEs.
    margin = 0.015625
    boundary = _decide(0.5 + margin, 0.5, margin=margin, se_sealed=0.0, se_fresh=0.0)
    assert boundary["outcome"] == exam_rotation.KEEP  # equal to the threshold: not over
    over = _decide(
        0.5 + margin + 2**-20, 0.5, margin=margin, se_sealed=0.0, se_fresh=0.0
    )
    assert over["outcome"] == exam_rotation.ROTATE
    assert over["reason"] == "sealed_exceeds_fresh_beyond_margin_and_2se"
    assert over["threshold"] == margin
    assert (
        _decide(0.70, 0.80)["outcome"] == exam_rotation.KEEP
    )  # fresh better: no signal
    assert _decide(0.805, 0.80)["reason"] == "within_margin_and_2se"
    # and the SEs widen it: 2 sqrt(0.003^2 + 0.004^2) = 0.01 on top of the margin
    assert _decide(0.80 + 0.0199, 0.80)["outcome"] == exam_rotation.KEEP
    assert _decide(0.80 + 0.0201, 0.80)["outcome"] == exam_rotation.ROTATE


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"sealed": None}, "total_unavailable"),
        ({"fresh": float("nan")}, "total_unavailable"),
        ({"margin": None}, "rebuild_noise_unregistered"),
        ({"se_sealed": None}, "standard_error_unavailable"),
        ({"se_fresh": float("inf")}, "standard_error_unavailable"),
    ],
)
def test_a_missing_input_is_unavailable_never_defaulted(overrides, reason):
    arguments = {"sealed": 0.9, "fresh": 0.5, **overrides}
    decision = _decide(**arguments)
    assert decision["outcome"] == exam_rotation.UNAVAILABLE
    assert decision["reason"] == reason


# --- the weekly log -------------------------------------------------------------------


def _log(tmp_path):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700, exist_ok=True)
    ledger = AttemptLedger(directory / "attempts.sqlite3")
    return exam_rotation.FreshDrawLog(ledger)


def _record(log, block, outcome="KEEP", sealed=SEALED):
    log.record(
        challenge_id="electric-motor-magnetics",
        challenge_version="1.0",
        king="rtsk_king",
        sealed_key=sealed,
        fresh_key=FRESH,
        block=block,
        inputs={
            "sealed_total": 0.8,
            "fresh_total": 0.79,
            "margin": 0.01,
            "se_sealed": 0.003,
            "se_fresh": 0.004,
        },
        decision={"outcome": outcome, "reason": "x", "threshold": 0.02},
    )


def test_the_check_is_due_once_a_week_per_sealed_exam(tmp_path):
    log = _log(tmp_path)
    due = lambda block, key=SEALED: log.due(
        challenge_id="electric-motor-magnetics", sealed_key=key, block=block
    )
    assert due(100)  # never checked
    _record(log, 100)
    assert not due(100 + exam_rotation.FRESH_DRAW_PERIOD_BLOCKS - 1)
    assert due(100 + exam_rotation.FRESH_DRAW_PERIOD_BLOCKS)
    assert due(101, key="sha256:" + "c" * 64)  # another sealed exam has its own clock
    assert exam_rotation.FRESH_DRAW_PERIOD_BLOCKS == 7 * 7200


def test_the_weekly_check_is_scheduled_and_an_overdue_one_stays_due_until_it_runs(
    tmp_path,
):
    """G5b pin (pre-mainnet attack tests): the weekly incumbent regrade is what bounds a lucky king's ratchet, so
    its schedule is pinned: seven days of blocks, due the first time, still due however late, and quiet for a week
    only once a check is logged. The operator runs `exam_rotation due` and `check` on this schedule.
    """
    assert exam_rotation.FRESH_DRAW_PERIOD_BLOCKS == 7 * exam_cap.DAY_BLOCKS == 50_400
    assert exam_rotation.FRESH_DRAW_PERIOD_BLOCKS < exam_cap.MAX_EXAM_AGE_BLOCKS
    log = _log(tmp_path)
    due = lambda block: log.due(
        challenge_id="electric-motor-magnetics", sealed_key=SEALED, block=block
    )
    assert due(0)  # a king never checked is due at once
    _record(log, 1_000)
    week = exam_rotation.FRESH_DRAW_PERIOD_BLOCKS
    assert not due(1_000 + week - 1)
    for late in (week, week + 1, 3 * week, 12 * week):
        assert due(late + 1_000)  # a missed check never lapses
    _record(log, 1_000 + 3 * week)  # running it late restarts the week from that block
    assert not due(1_000 + 4 * week - 1)
    assert due(1_000 + 4 * week)


def test_both_totals_and_the_decision_are_logged_operator_side(tmp_path):
    log = _log(tmp_path)
    _record(log, 7, outcome="ROTATE")
    (row,) = log.rows()
    assert (row["sealed_total"], row["fresh_total"]) == (0.8, 0.79)
    assert (row["margin"], row["se_sealed"], row["se_fresh"]) == (0.01, 0.003, 0.004)
    assert (
        row["outcome"] == "ROTATE" and row["challenge_id"] == "electric-motor-magnetics"
    )


class FakeStore:
    def __init__(self, bodies):
        self.bodies = bodies

    def private_evaluation_body(self, king, key, *, registered_source_receipt_sha256):
        return self.bodies.get((king, key))


def _body(total, status="SCORED_DEVELOPMENT_CANDIDATE"):
    return {"evidence": {"model_p": {"score_status": status, "total_score": total}}}


def test_check_king_reads_both_totals_decides_logs_and_is_loud_on_rotate(
    tmp_path, capsys
):
    log = _log(tmp_path)
    store = FakeStore({("king", SEALED): _body(0.90), ("king", FRESH): _body(0.60)})
    sealed = {"key": SEALED, "pin": "sha256:" + "1" * 64, "se": 0.01}
    fresh = {"key": FRESH, "pin": "sha256:" + "2" * 64, "se": 0.02}
    outcome = exam_rotation.check_king(
        log=log,
        store=store,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.0",
        king="king",
        sealed=sealed,
        fresh=fresh,
        block=500,
        margin=0.05,
    )
    assert outcome["outcome"] == exam_rotation.ROTATE
    assert (outcome["sealed_total"], outcome["fresh_total"]) == (0.90, 0.60)
    assert json.loads(capsys.readouterr().err.strip().splitlines()[-1])["event"] == (
        "exam_overfit_rotate"
    )
    assert len(log.rows()) == 1
    # An unscored king on either exam is UNAVAILABLE, not a rotation.
    store.bodies[("king", FRESH)] = _body(None, status="MANDATORY_GATE_FAILED")
    again = exam_rotation.check_king(
        log=log,
        store=store,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.0",
        king="king",
        sealed=sealed,
        fresh=fresh,
        block=501,
        margin=0.05,
    )
    assert again["outcome"] == exam_rotation.UNAVAILABLE
    assert again["reason"] == "total_unavailable"


def test_the_margin_is_the_registered_rebuild_noise_and_absent_means_unavailable(
    tmp_path,
):
    log = _log(tmp_path)
    store = FakeStore({("king", SEALED): _body(0.9), ("king", FRESH): _body(0.1)})
    side = lambda key: {
        "key": key,
        "pin": "sha256:" + "1" * 64,
        "se": 0.0,
    }
    outcome = exam_rotation.check_king(
        log=log,
        store=store,
        challenge_id="electric-motor-magnetics",  # none registered yet in the committed file
        challenge_version="1.0",
        king="king",
        sealed=side(SEALED),
        fresh=side(FRESH),
        block=1,
    )
    assert outcome["outcome"] == exam_rotation.UNAVAILABLE
    assert outcome["reason"] == "rebuild_noise_unregistered"


def test_the_se_sidecar_is_read_not_typed(tmp_path):
    sidecar = tmp_path / exam_rotation.SE_SIDECAR
    sidecar.write_text(
        json.dumps(
            {
                "schema": exam_rotation.SE_SCHEMA,
                "status": "MEASURED",
                "standard_error": 0.004,
                "total": 0.8,
            }
        )
    )
    assert exam_rotation.read_se(sidecar) == (0.004, 0.8)
    sidecar.write_text(
        json.dumps(
            {
                "schema": exam_rotation.SE_SCHEMA,
                "status": "UNAVAILABLE",
                "reason": "bootstrap_unmeasurable:x",
                "total": 0.8,
            }
        )
    )
    assert exam_rotation.read_se(sidecar) == (None, 0.8)
    sidecar.write_text("{}")
    with pytest.raises(ValueError):
        exam_rotation.read_se(sidecar)


# --- the case bootstrap --------------------------------------------------------------------


def _bootstrap(case, *, exam_key=None, resamples=20):
    adapter = case["adapter"]
    prepared, _ = _produce(case)
    return physical.bootstrap_total_se(
        adapter,
        selected=case["snapshot"],
        public_root=case["root"],
        private_root=case["root"],
        entry=case["entry"],
        job=case["job"],
        registration=case["registration"],
        references=case["references"],
        originals=case["originals"],
        source_raw=prepared.raw,
        bank=physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION),
        interface_names=physical.input_names(adapter),
        exam_key=exam_key or case["snapshot"].manifest_digest,
        resamples=resamples,
    )


def test_the_bootstrap_is_measured_where_the_adapter_can_and_refused_where_it_cannot(
    case,
):
    adapter = case["adapter"]
    if adapter.CHALLENGE == "f08-ribbed-bracket" and adapter.VERSION == "1.1":
        # A resample whose verified pick is infeasible fails a mandatory gate and has no
        # total: the check is then unavailable for that exam key, never a guess. Which keys
        # that happens for depends on the key, so the test needs only that some key is
        # measurable and that every other one either measures or refuses by that typed code.
        measured = {}
        for fill in "98765432":
            key = "sha256:" + fill * 64
            try:
                measured[key] = _bootstrap(case, exam_key=key)
            except source.PrivateEvaluationSourceRefused as refused:
                assert refused.code == "bootstrap_total_unscored"
        assert measured, "no exam key could be measured"
        key, first = next(iter(measured.items()))
        assert first > 0 and math.isfinite(first)
        assert _bootstrap(case, exam_key=key) == first  # seeded by the exam key
        if len(measured) > 1:
            assert (
                len(set(measured.values())) > 1
            )  # a different key resamples differently
        return
    # The other adapters cannot measure a resampled bank (a decision grid or a gate that
    # does not survive duplicated rows): UNAVAILABLE, never an estimate from fewer.
    with pytest.raises(source.PrivateEvaluationSourceRefused) as refused:
        _bootstrap(case)
    assert refused.value.code.startswith(
        ("bootstrap_unmeasurable:", "bootstrap_total_unscored")
    )


def test_the_bootstrap_refuses_a_malformed_exam_key(case):
    with pytest.raises(source.PrivateEvaluationSourceRefused, match="exam_key_invalid"):
        _bootstrap(case, exam_key="not-a-key")


def test_the_retention_hook_writes_the_se_sidecar_or_the_typed_reason(case, tmp_path):
    adapter = case["adapter"]
    prepared, measured = _produce(case)
    scoring = ScoreEngine.score_dual_benchmark_v4(
        json.loads(measured.raw)["benchmark"], case["score_pack"]
    )
    stand_in = SimpleNamespace(
        challenge_id=adapter.CHALLENGE,
        challenge_version=adapter.VERSION,
        discovery=SimpleNamespace(
            evaluation_pack_public_root=case["root"],
            evaluation_pack_private_root=case["root"],
        ),
    )
    directory = tmp_path / "evaluation"
    directory.mkdir(mode=0o700)
    retention._write_exam_se(
        stand_in,
        case["snapshot"],
        directory,
        {
            "entry": case["entry"],
            "references": case["references"],
            "evaluation_source_receipt_raw": prepared.raw,
        },
        {
            "trusted_job": case["job"],
            "benchmark_registration": case["registration"],
        },
        case["originals"],
        scoring,
    )
    document = json.loads((directory / exam_rotation.SE_SIDECAR).read_bytes())
    assert document["schema"] == exam_rotation.SE_SCHEMA
    assert document["total"] == scoring["models"][0]["score"]
    assert document["exam_key"] == case["snapshot"].manifest_digest
    if document["status"] == "MEASURED":
        assert document["standard_error"] > 0
    else:
        assert document["status"] == "UNAVAILABLE"
        assert document["reason"].startswith(("bootstrap_", "dual_native_"))
    sealed_se, total = exam_rotation.read_se(directory / exam_rotation.SE_SIDECAR)
    assert (sealed_se is None) == (document["status"] != "MEASURED")
    assert total == scoring["models"][0]["score"]


def test_cadence_constants_are_the_ones_the_rotation_rule_names():
    assert exam_cap.MAX_EXAM_AGE_BLOCKS == 90 * 7200
    assert dual_score.PACK_SCHEMA  # the score the totals come from is the dual v4 pack


def test_the_real_pool_store_serves_the_kings_filed_evaluation_to_the_check(
    case, tmp_path
):
    from carbon.battery.pool_store import PoolStore
    from carbon.challenge_validator.bank_promotion import BankPromotion
    from carbon.scoring import private_evaluation_evidence as evidence

    prepared, measured = _produce(case)
    scoring = ScoreEngine.score_dual_benchmark_v4(
        json.loads(measured.raw)["benchmark"], case["score_pack"]
    )
    inputs = {
        "entry": case["entry"],
        "custody_receipt_raw": case["custody_raw"],
        "trusted_job": case["job"],
        "registration": case["registration"],
        "references": case["references"],
        "measured_model": measured.measured_model,
        "score_pack": case["score_pack"],
        "graph_originals": case["originals"],
        "expected_result_digest": evidence._sha(evidence._canonical(scoring)),
        "ordered_query_bytes": [case["case_bank"]],
        "evaluation_source_receipt_raw": prepared.raw,
        "expected_evaluation_pack_digest": case["snapshot"].manifest_digest,
        "dual_measurement_receipt_raw": measured.raw,
        "registered_dual_measurement_sha256": measured.sha256,
        "selected_evaluation_pack": case["snapshot"],
    }
    entry = case["entry"]
    task = case["root"].parent / "task"
    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 123.0)
    store.admit(
        "king",
        request_digest="sha256:" + "7" * 64,
        hotkey="owner-hotkey",
        challenge=entry["challenge"],
        strategy=json.loads((task / "recipe.json").read_bytes()),
        binding={
            "challenge": {
                "id": entry["challenge"],
                "version": entry["challenge_version"],
            },
            "recipe_digest": entry["recipe_digest"],
        },
    )
    store.retain_model(
        "king",
        recipe_digest=entry["recipe_digest"],
        seed=0,
        state=(task / "state.npz").read_bytes(),
        reconstruction={"scope": "FIXTURE"},
    )
    store.mark("king", "RECONSTRUCTED")
    pin = prepared.sha256
    filed = BankPromotion(store, registered_source_receipt_sha256=pin).retain_private(
        "king", **inputs
    )
    body = store.private_evaluation_body(
        "king", filed["evaluation_key"], registered_source_receipt_sha256=pin
    )
    assert body == filed
    assert exam_rotation._total(body) == scoring["models"][0]["score"]
    assert (
        store.private_evaluation_body(
            "king", "sha256:" + "0" * 64, registered_source_receipt_sha256=pin
        )
        is None
    )
    # the same filed evaluation as both sides of the check: no overfit signal
    outcome = exam_rotation.check_king(
        log=_log(tmp_path),
        store=store,
        challenge_id=case["adapter"].CHALLENGE,
        challenge_version=case["adapter"].VERSION,
        king="king",
        sealed={"key": filed["evaluation_key"], "pin": pin, "se": 0.0},
        fresh={"key": filed["evaluation_key"], "pin": pin, "se": 0.0},
        block=9,
        margin=0.0,
    )
    assert outcome["outcome"] == exam_rotation.KEEP
