"""Motor 1.8's subset repeat, as the same version (owner Sun 15 Nov 2026 08:19 + 08:38 CST; CV-Motor-B's rulings Q1 = B
and Q2; Validator-2B R-1..R-5 and Q3 (a); docs/records/2026-11-15-motor18-subset-repeat.json).

- k is derived from the owner's registered promise (f, P): 66 for f = 0.10, P = 0.999, capped at the rows outside the
  sealed cells; a missing, null or malformed promise fails closed at serve time and at grade time.
- The repeat re-runs ALL the sealed cells plus min(k, size) keyed rows inside EACH registered stratum (owner: "66 per
  stratum"; the strata are CV-Motor's, null = fail closed), drawn per (key, submission, stratum), independent of the
  speed sample and of each other, never public.
- The scorer: each repeated row must equal the graded row bit for bit over the whole row (a 1-ulp change in a non-torque
  column, NaN or a malformed row fails the grade); an agreeing repeat scores exactly as the full pair of equal repeats on
  the REAL pool-graded fixture; repeat values reach gates only; broken evidence is typed unavailable.
- The door runs ONE subset op (no pair op); a second wall hit settles CANDIDATE_FAILED with pass ``inference_pair``.
- R-1: ONE successor row (subset versions only), exact match only; a successor receipt binds; old evidence still reads.
- Every other version's producer digest is unchanged from e6f67358, and every other version keeps the full pair.

Every value here is synthetic, except the owner's two public rule values (f, P) and the producer digests. The real-adapter
tests run the REAL Motor 1.5 sealed-pool fixture (`test_pool_dual_e2e`) admitted as a subset version inside the test:
no Motor 1.8 pool fixture exists (it needs 1.8's sealed custody material), and everything after the adapter is the code
Motor 1.8 runs.
"""

# ruff: noqa: F811 (the imported case fixture is received by tests)
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from test_pool_dual_e2e import KEY as POOL_KEY
from test_pool_dual_e2e import _bind, _produce, case  # noqa: F401

from carbon.development_session.bundle_construction_worker import _tensors
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import private_evaluation_source as source
from carbon.scoring import producer_successor, subset_repeat_produce
from carbon.scoring import subset_repeat_evidence as subset
from carbon.scoring.engine import ScoreEngine

ROOT = Path(__file__).resolve().parents[2]
MOTOR = "electric-motor-magnetics"
WIDTH = 240
GRID = "decision_sealed_grid"

#: Motor 1.8's producer digest at e6f67358 (before the subset repeat): the digest its live pack was sealed against.
#: Deploy-B / Validator-2B confirm it equals the live pack's accuracy_definition.producer_digest.
OLD_MOTOR18 = "sha256:9c5ac4dbee486fbf9b986b22f5b1b2f2b1a4b415512a950379761159967e32cc"
#: Every other adapter's producer digest at e6f67358. The subset repeat must move none of them (no successor row exists
#: for any of them). A LEGITIMATE later change to a producer file updates this table together with its own successor
#: row or a new pack, never silently.
OTHER_DIGESTS = {
    "battery_dual_pack": "sha256:852fb21427ba7fec8c635fc588834455f1d55e91f3b4dfa5b925bea2b7924e22",
    "battery_sealed_dual_pack": "sha256:e8d450a427d5c7572c9e1d41d070719bdc9ee10830e4eb41f09c5f8cabdaf45c",
    "cooling18_dual_pack": "sha256:9b409016f95582aaabd861661694b21c056e34585d04e5cea047594af89de6b5",
    "cooling_dual_pack": "sha256:c29704e900c345d1fc81653f78afc796ed91861370a584d7660a7f3dbeb5b0d0",
    "cooling_encoded_dual_pack": "sha256:a468a5110c8245fa1c7e1ffb812cf9c78ecacc7b4ef1a245e02832da53ea3699",
    "cooling_hotspot_dual_pack": "sha256:df9e5d27d3959d017b9aae7243a5846c74234a3825c376d9183f9d6e60451dca",
    "cooling_pool_baseline_dual_pack": "sha256:8b33a0ee4098b7a92e81adb6cebc12600599893a88d1f9c8f683a753a1e2b0a2",
    "f02_dual_pack": "sha256:60861496cb77682c25e338d75744a99161cc830ac94ded9c75d54890d7a00c9b",
    "f02_sealed_dual_pack": "sha256:4c49041bb04d0971d25f896899f83f122082a24fc252210733c1f5d67d909263",
    "f08_dual_pack": "sha256:1d244cf56dd30de4a7b6e3961cd4f6c4e9c007487941ae0dcd2de46e4cf0e29e",
    "f08_sanity_dual_pack": "sha256:7315f94ab223cd28a4dd6641c0cd9e1afa649e8926ba154992d937be5ecff540",
    "f08_sealed_dual_pack": "sha256:43847f922bb63e7f72136c67c2c3da74600c71485452e5f19f19228c36baaefb",
    "motor_dual_pack": "sha256:3089b982651cd1b158affd8e145ad544a80d6be26d1e6ba01e9323bc502762b9",
    "motor_pool_baseline_dual_pack": "sha256:cf89ca1e3a6ab3e035f0e56cb9dbc94238c1640a875e5f63b39755d870dcd913",
    "motor_sealed_dual_pack": "sha256:3d45a99670763e003a6fa43393730ab7518e004c2a32a5ae80ef1b91e7b678f4",
}


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _row(seed, width=WIDTH):
    """One synthetic, whole answer row, all finite."""
    return [float(seed) + 0.01 * i for i in range(width)]


def _promise_file(tmp_path, rows):
    path = tmp_path / "subset_repeat.json"
    path.write_text(
        json.dumps({"schema": subset.VALUES_SCHEMA, "rows": rows}), encoding="utf-8"
    )
    return path


def _motor18_promise(tmp_path, row):
    return _promise_file(tmp_path, {f"{MOTOR} 1.8": row})


#: The committed values file: the owner's f and P and CV-Motor-B's strata names.
COMMITTED = ROOT / "scripts" / "validator_host_classes" / "subset_repeat.json"
POOL, PROBE = "pool_design", "probe_response"
#: A test promise: the owner's f and P with two synthetic strata named in the test (CV-Motor's list is pending).
PROMISE = {
    "repeat_fail_fraction": 0.10,
    "repeat_detect_prob": 0.999,
    "strata": [POOL, PROBE],
}


#: The code's real strata, captured before any test replaces them (`test_motor18_subset_repeat_strata` tests them).
REAL_STRATA = subset.STRATA
#: Synthetic cohort strata for this file's synthetic banks and the Motor 1.5 fixture.
COHORT_STRATA = {
    POOL: subset.Stratum("cohort", POOL),
    PROBE: subset.Stratum("cohort", PROBE),
}


@pytest.fixture(autouse=True)
def promise(tmp_path_factory, monkeypatch):
    """Every test reads the test promise and the synthetic cohort strata unless it registers its own."""
    path = _motor18_promise(tmp_path_factory.mktemp("promise"), PROMISE)
    monkeypatch.setattr(subset, "VALUES_PATH", path)
    monkeypatch.setattr(
        subset,
        "STRATA",
        {(MOTOR, "1.8"): dict(COHORT_STRATA), (MOTOR, "1.5"): dict(COHORT_STRATA)},
    )
    return path


def _bank(cohorts):
    """A synthetic graded bank: its cohorts and one distinct input row each (no pool material: cohort strata only)."""
    return {
        "cohorts": list(cohorts),
        "inputs": [[float(i)] for i in range(len(cohorts))],
    }


def _strata(cohorts, version="1.8"):
    return subset.bank_strata(MOTOR, version, _bank(cohorts))


def _cohorts(n, sealed=30, probes=20):
    return [GRID] * sealed + [PROBE] * probes + [POOL] * (n - sealed - probes)


# -- the promise and k ---------------------------------------------------------------------------------------------------


def test_the_committed_promise_is_the_owners_f_and_p_and_cv_motors_strata():
    row = json.loads(COMMITTED.read_text(encoding="utf-8"))["rows"][f"{MOTOR} 1.8"]
    assert row == {
        "repeat_fail_fraction": 0.10,
        "repeat_detect_prob": 0.999,
        "strata": list(REAL_STRATA[(MOTOR, "1.8")]),
    }
    assert subset.registered_promise(MOTOR, "1.8", path=COMMITTED)[2] == list(
        REAL_STRATA[(MOTOR, "1.8")]
    )


def test_k_is_66_inside_each_stratum_capped_at_its_size():
    assert subset.registered_promise(MOTOR, "1.8") == (0.10, 0.999, [POOL, PROBE])
    assert subset.derived_k(0.10, 0.999, 2534) == 66
    assert math.ceil(math.log(1 - 0.999) / math.log(1 - 0.10)) == 66
    assert subset.derived_k(0.10, 0.999, 40) == 40
    assert subset.derived_k(0.10, 0.999, 1) == 1
    cohorts = [GRID] * 30 + [PROBE] * 40 + [POOL] * 2494
    assert subset.registered_counts(MOTOR, "1.8", _strata(cohorts)) == {
        POOL: 66,
        PROBE: 40,
    }


@pytest.mark.parametrize(
    "row",
    [
        None,
        {},
        {**PROMISE, "repeat_fail_fraction": None},
        {**PROMISE, "repeat_detect_prob": None},
        {"repeat_fail_fraction": 0.10, "strata": [POOL]},
        {**PROMISE, "k": 66},
        {**PROMISE, "repeat_fail_fraction": True},
        {**PROMISE, "repeat_fail_fraction": 0},
        {**PROMISE, "repeat_fail_fraction": 1},
        {**PROMISE, "repeat_fail_fraction": 0.0},
        {**PROMISE, "repeat_fail_fraction": 1.0},
        {**PROMISE, "repeat_detect_prob": 1.5},
        {**PROMISE, "repeat_fail_fraction": "0.10"},
        {"repeat_fail_fraction": 0.10, "repeat_detect_prob": 0.999},
    ],
)
def test_a_null_or_malformed_promise_fails_closed(tmp_path, row):
    path = _motor18_promise(tmp_path, row)
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.registered_promise(MOTOR, "1.8", path=path)
    assert caught.value.code == "subset_repeat_promise_unregistered"


@pytest.mark.parametrize(
    "strata", [None, [], [POOL, POOL], [GRID], [POOL, ""], [1], POOL, {POOL: 1}]
)
def test_null_or_malformed_strata_fail_closed(tmp_path, strata):
    path = _motor18_promise(tmp_path, {**PROMISE, "strata": strata})
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.registered_promise(MOTOR, "1.8", path=path)
    assert caught.value.code == "subset_repeat_strata_unregistered"


def test_an_unknown_stratum_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subset,
        "VALUES_PATH",
        _motor18_promise(tmp_path, {**PROMISE, "strata": [POOL, "practice"]}),
    )
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.registered_counts(MOTOR, "1.8", _strata(_cohorts(200)))
    assert caught.value.code == "subset_repeat_stratum_unknown"


def test_an_absent_file_or_row_fails_closed(tmp_path):
    with pytest.raises(subset.SubsetRepeatRefused):
        subset.registered_promise(MOTOR, "1.8", path=tmp_path / "absent.json")
    with pytest.raises(subset.SubsetRepeatRefused):
        subset.registered_promise(MOTOR, "1.5")
    for bad in (float("nan"), float("inf")):
        with pytest.raises(subset.SubsetRepeatRefused):
            subset.derived_k(bad, 0.999, 10)


def test_the_sealed_cohort_is_the_sealed_grids():
    from carbon.scoring.sealed_grid_common import GRID_COHORT

    assert subset.SEALED_COHORT == GRID_COHORT == GRID


# -- the stratified draw ---------------------------------------------------------------------------------------------------


KEY = bytes(range(32))  # synthetic K_speed


def _plan(sid, cohorts):
    return subset.plan(
        KEY, sid, challenge=MOTOR, version="1.8", strata=_strata(cohorts)
    )


def test_every_grade_repeats_all_sealed_cells_plus_min_k_size_rows_in_each_stratum():
    cohorts = [POOL] * 40 + [GRID] * 30 + [PROBE] * 25 + [POOL] * 500
    for sid in ("rtsk_a", "rtsk_b", "rtsk_c"):
        sealed, keyed = _plan(sid, cohorts)
        assert sealed == list(range(40, 70))  # ALL 30 sealed cells, every grade
        assert set(keyed) == {POOL, PROBE}
        assert len(keyed[POOL]) == len(set(keyed[POOL])) == 66
        assert keyed[PROBE] == list(
            range(70, 95)
        )  # a stratum smaller than k is re-run whole
        for name, rows in keyed.items():
            assert rows == sorted(rows) and all(cohorts[p] == name for p in rows)
    assert _plan("rtsk_a", cohorts) == _plan("rtsk_a", cohorts)
    assert _plan("rtsk_a", cohorts)[1][POOL] != _plan("rtsk_b", cohorts)[1][POOL]


def test_each_stratums_draw_is_independent_of_the_others(tmp_path, monkeypatch):
    cohorts = [GRID] * 30 + [PROBE] * 300 + [POOL] * 500
    both = _plan("rtsk_a", cohorts)[1]
    monkeypatch.setattr(
        subset,
        "VALUES_PATH",
        _motor18_promise(tmp_path, {**PROMISE, "strata": [POOL]}),
    )
    monkeypatch.setattr(subset, "STRATA", {(MOTOR, "1.8"): {POOL: COHORT_STRATA[POOL]}})
    alone = subset.plan(
        KEY,
        "rtsk_a",
        challenge=MOTOR,
        version="1.8",
        strata=subset.bank_strata(
            MOTOR, "1.8", _bank([c for c in cohorts if c != PROBE])
        ),
    )[1]
    # the same draw over the same pool stratum (its rows sit 300 positions earlier once the probe rows are gone)
    assert list(alone) == [POOL]
    assert [p + 300 for p in alone[POOL]] == both[POOL]
    assert subset.grade_key(KEY, "rtsk_a", POOL) != subset.grade_key(
        KEY, "rtsk_a", PROBE
    )


def test_a_bank_without_sealed_cells_is_carbons_gap():
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        _plan("rtsk_a", [POOL] * 100 + [PROBE] * 10)
    assert caught.value.code == "subset_repeat_bank_strata"


def test_the_draw_key_is_independent_of_the_speed_sample():
    from carbon.development_session import single_call_timing

    assert subset.DOMAIN != single_call_timing.SEED_DOMAIN
    assert subset.grade_key(KEY, "rtsk_a", POOL) != single_call_timing.sample_seed(
        KEY, "rtsk_a"
    )


def test_the_keyed_sample_covers_rows_roughly_uniformly():
    counts = [0] * 20
    for i in range(400):
        for p in subset.keyed_sample(
            subset.grade_key(KEY, f"rtsk_{i}", POOL), range(20), 5
        ):
            counts[p] += 1
    # 400 draws of 5 of 20: 100 per row expected; a broken draw piles onto a few rows
    assert min(counts) > 60 and max(counts) < 140


def test_the_draw_refuses_a_bad_key_or_k():
    for bad in (
        (b"short", "rtsk_a", POOL),
        (KEY, "", POOL),
        (None, "rtsk_a", POOL),
        (KEY, "rtsk_a", ""),
    ):
        with pytest.raises(subset.SubsetRepeatRefused):
            subset.grade_key(*bad)
    for k in (0, 11):
        with pytest.raises(subset.SubsetRepeatRefused):
            subset.keyed_sample(subset.grade_key(KEY, "rtsk_a", POOL), range(10), k)


def test_nothing_about_the_draw_reaches_a_public_or_miner_surface():
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

    assert not any(
        "subset" in field or "positions" in field
        for field in LeanRecipeAdapter.disclosure_fields
    )
    for public in (
        ROOT / "kits" / "motor" / "HOW_YOURE_TESTED.md",
        ROOT / "scripts" / "dev" / "miner_launchpad" / "pass_words.py",
        ROOT / "scripts" / "validator_host_classes" / "subset_repeat.json",
    ):
        text = public.read_text(encoding="utf-8")
        assert subset.DOMAIN.decode() not in text
        assert "positions" not in text


def test_the_door_and_the_ledger_name_the_same_identity():
    from carbon.development_session import paired_inference

    run = subset.run_identity("sha256:" + "a" * 64, "rtsk_a")
    assert paired_inference.repeat_identity(run) == subset.ledger_identity(run)
    assert subset.run_identity("p", "s", retry=True) == "subset-repeat-p-s-wall-retry"


# -- the scorer's gate (stand-in adapter) -------------------------------------------------------------------------------------


class _Adapter:
    """A stand-in adapter whose measure records its call; its own torque gate compares rows to repeat 0 by Motor's rule."""

    class Refused(ValueError):
        def __init__(self, code):
            self.code = code
            super().__init__(code)

    def __init__(self):
        self.calls = []

    def measure(self, *, outputs, repeats, **arguments):
        from carbon.motor import exam

        self.calls.append({"outputs": outputs, "repeats": repeats, **arguments})
        ok = all(
            exam.FAIL
            not in exam.gates({"torque_nm": out[:60]}, {"torque_nm": rep[:60]}).values()
            for out, rep in zip(outputs, repeats[0])
        )
        return {
            "A": sum(o[0] for o in outputs) / len(outputs) if ok else None,
            "D": 0.5,
            "gates": {
                "native_motor_valid": ok,
                "complete_fixed_coverage": ok,
                "physics": True,
            },
            "decision_outcome": "POOL",
        }


def _grade(n=12):
    return [_row(i) for i in range(n)]


def test_an_agreeing_subset_repeat_measures_exactly_as_the_equal_full_pair():
    outputs = _grade()
    twins = [tuple(outputs[i]) if i in (1, 7) else None for i in range(len(outputs))]
    adapter = _Adapter()
    measured = subset_repeat_produce.measure_subset(
        adapter, outputs=outputs, twins=twins, definition={}
    )
    full = _Adapter().measure(outputs=outputs, repeats=[outputs, outputs])
    assert measured == full
    # the adapter saw exactly the full-pair call whose repeats equal the graded answers
    assert adapter.calls[0]["repeats"] == [outputs, outputs]
    assert adapter.calls[0]["definition"] == {}


def _unscored(measured):
    return (
        measured["gates"]["native_motor_valid"] is False
        and measured["gates"]["complete_fixed_coverage"] is False
        and measured["A"] is None
        and measured["D"] == 0.0
    )


@pytest.mark.parametrize(
    "change",
    [
        # 1 ulp in a NON-torque column (a linkage value): the torque gate cannot see it, the exact rule does
        lambda row: row.__setitem__(150, math.nextafter(row[150], math.inf)),
        # 1 ulp in the torque slice, far inside Motor's 32-ulp torque rule
        lambda row: row.__setitem__(5, math.nextafter(row[5], math.inf)),
        lambda row: row.__setitem__(200, float("nan")),
        lambda row: row.__setitem__(0, float("inf")),
        lambda row: row.__setitem__(3, -0.0 if row[3] == 0.0 else row[3] + 1.0),
        lambda row: row.pop(),
    ],
)
def test_one_repeated_row_off_by_anything_leaves_the_grade_unscored(change):
    outputs = _grade()
    fresh = list(outputs[9])
    change(fresh)
    twins = [tuple(fresh) if i == 9 else None for i in range(len(outputs))]
    capture = {}
    measured = subset_repeat_produce.measure_subset(
        _Adapter(), outputs=outputs, twins=twins, capture=capture
    )
    assert _unscored(measured)
    assert measured["gates"]["physics"] is True
    assert capture["se_basis"] == {"gated": True}


def test_a_malformed_fresh_answer_fails_and_reaches_the_measure_as_the_graded_row():
    outputs = _grade(3)
    adapter = _Adapter()
    measured = subset_repeat_produce.measure_subset(
        adapter, outputs=outputs, twins=[None, (), None]
    )
    assert _unscored(measured)
    assert adapter.calls[0]["repeats"][0][1] == outputs[1]


def test_rows_that_are_not_repeat_checked_are_not_judged():
    outputs = _grade(3)
    assert subset_repeat_produce.repeat_holds(outputs, [None, None, None])
    assert subset.rows_agree([1.0, 2.0], (1.0, 2.0))
    assert not subset.rows_agree([0.0], (-0.0,))
    assert not subset.rows_agree([1.0], (1.0, 1.0))
    assert not subset.rows_agree([1.0], None)


def test_a_roster_mismatch_refuses():
    with pytest.raises(_Adapter.Refused):
        subset_repeat_produce.measure_subset(
            _Adapter(), outputs=_grade(3), twins=[None, None]
        )


# -- the side file and its reader -----------------------------------------------------------------------------------------

RECIPE = "sha256:" + "1" * 64
STATE = "sha256:" + "2" * 64
IMAGE = "sha256:" + "3" * 64
PACK = "sha256:" + "4" * 64
GRADED_OP = "operation-" + "4" * 64
REPEAT_OP = "operation-" + "5" * 64
SID = "rtsk_reader"


def _original(raw):
    return {"sha256": _sha(raw), "raw_base64": base64.b64encode(raw).decode()}


def _run(
    graded_inputs,
    positions,
    answers,
    *,
    recipe=RECIPE,
    state=STATE,
    image=IMAGE,
    ledger=None,
    **overrides,
):
    rows = np.ascontiguousarray(graded_inputs[positions])
    predictions = json.dumps(answers).encode()
    receipt = json.dumps(
        {
            "schema": "carbon.development.bundle-inference.v1",
            "recipe_digest": recipe,
            "state_digest": state,
            "inputs_digest": _sha(_tensors(inputs=rows)),
            "predictions_digest": _sha(predictions),
        }
    ).encode()
    ledger = ledger or subset.ledger_identity(subset.run_identity(PACK, SID))
    run = {
        "schema": subset.RUN_SCHEMA,
        "execution_boundary": "C03_DOCKER",
        "recipe_digest": recipe,
        "state_digest": state,
        "inputs_digest": _sha(_tensors(inputs=rows)),
        "inference_image_id": image,
        "logical_prediction_rows": len(positions),
        "elapsed_seconds": 1.5,
        "repeat": {
            "worker_operation": REPEAT_OP,
            "controls_digest": "sha256:" + "6" * 64,
            "originals": {
                "predictions.json": _original(predictions),
                "receipt.json": _original(receipt),
            },
            "accounting": {
                "ledger_identity": ledger,
                "state": "SUCCEEDED",
                "reservation": {"numerical_milliseconds": 10},
                "actual": {"numerical_milliseconds": 5},
                "worker_result": {
                    "operation": REPEAT_OP,
                    "files": {
                        "predictions.json": _sha(predictions),
                        "receipt.json": _sha(receipt),
                    },
                    "schema": "carbon.autoresearch.worker-result.v1",
                    "provenance": "DIRECT_GRAPH_PUBLIC_INFERENCE",
                    "output_digest": "sha256:" + "8" * 64,
                    "scientific_qualification": False,
                    "official_eligible": False,
                },
            },
        },
        "scientific_qualification": False,
        "official_eligible": False,
    }
    run.update(overrides)
    return run


#: A small synthetic bank: 4 sealed cells, 4 pool rows, 2 probe rows (k = 2 per stratum from the test's promise).
N = 10
COHORTS = [GRID] * 4 + [POOL] * 4 + [PROBE] * 2
SEALED = [0, 1, 2, 3]
KEYED = {POOL: [5, 7], PROBE: [8, 9]}


@pytest.fixture
def small_promise(tmp_path, monkeypatch):
    """A promise giving k = 2 in each stratum (f = 0.9, P = 0.99)."""
    monkeypatch.setattr(
        subset,
        "VALUES_PATH",
        _motor18_promise(
            tmp_path,
            {**PROMISE, "repeat_fail_fraction": 0.9, "repeat_detect_prob": 0.99},
        ),
    )
    assert subset.registered_counts(MOTOR, "1.8", _strata(COHORTS)) == {
        POOL: 2,
        PROBE: 2,
    }


def _side(*, sealed=SEALED, keyed=KEYED, answers=None, sid=SID, **overrides):
    graded_inputs = np.arange(N * 3, dtype=np.float64).reshape(N, 3)
    positions = subset.positions_of(sealed, keyed)
    answers = [_row(p) for p in positions] if answers is None else answers
    raw = subset.side_file(
        challenge=MOTOR,
        version="1.8",
        evaluation_pack_digest=PACK,
        submission_id=sid,
        n_rows=N,
        sealed=list(sealed),
        keyed=keyed,
        run=_run(graded_inputs, positions, answers, **overrides),
    )
    return raw, graded_inputs


def _read(raw, graded_inputs, **changes):
    cohorts = changes.pop("cohorts", COHORTS)
    arguments = {
        "registered_sha256": _sha(raw),
        "challenge": MOTOR,
        "version": "1.8",
        "evaluation_pack_digest": PACK,
        "strata": _strata(cohorts),
        "graded_inputs": graded_inputs,
        "output_shape": [N, WIDTH],
        "recipe_digest": RECIPE,
        "state_digest": STATE,
        "inference_image_id": IMAGE,
        "graded_operation": GRADED_OP,
        **changes,
    }
    return subset.read(raw, **arguments)


def test_the_reader_returns_one_twin_per_repeated_row_and_none_elsewhere(
    small_promise,
):
    raw, graded_inputs = _side()
    twins = _read(raw, graded_inputs)
    assert len(twins) == N
    assert [i for i, t in enumerate(twins) if t is not None] == [0, 1, 2, 3, 5, 7, 8, 9]
    assert list(twins[5]) == _row(5)


def test_the_wall_retry_identity_is_accepted(small_promise):
    ledger = subset.ledger_identity(subset.run_identity(PACK, SID, retry=True))
    raw, graded_inputs = _side(ledger=ledger)
    assert _read(raw, graded_inputs)[8] is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"recipe_digest": "sha256:" + "9" * 64},
        {"state_digest": "sha256:" + "9" * 64},
        {"inference_image_id": "sha256:" + "9" * 64},
        {"graded_operation": REPEAT_OP},
        {"challenge": "cooling-plate"},
        {"version": "1.5"},
        {"evaluation_pack_digest": "sha256:" + "9" * 64},
        {"output_shape": [N + 1, WIDTH]},
        {"cohorts": [GRID] * 3 + [POOL] * 5 + [PROBE] * 2},
        {"cohorts": [GRID] * 4 + [POOL] * 6},
        {"registered_sha256": "sha256:" + "0" * 64},
    ],
)
def test_evidence_that_does_not_bind_this_grade_is_typed_unavailable(
    small_promise, changes
):
    raw, graded_inputs = _side()
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        _read(raw, graded_inputs, **changes)
    assert caught.value.code.startswith("subset_repeat")


@pytest.mark.parametrize(
    "plan",
    [
        {"sealed": [0, 1, 2]},  # a sealed cell missing
        {"keyed": {POOL: [5, 7]}},  # a registered stratum missing
        {"keyed": {**KEYED, "practice": [6]}},  # an unregistered stratum
        {"keyed": {POOL: [5], PROBE: [8, 9]}},  # fewer keyed rows than the registered k
        {"keyed": {POOL: [4, 5, 7], PROBE: [8, 9]}},  # more
        {"keyed": {POOL: [3, 7], PROBE: [8, 9]}},  # a keyed row inside the sealed cells
        {"keyed": {POOL: [5, 8], PROBE: [8, 9]}},  # a row of another stratum
        {"keyed": {POOL: [7, 5], PROBE: [8, 9]}},  # unsorted
    ],
)
def test_a_plan_that_is_not_the_registered_one_is_refused(small_promise, plan):
    raw, graded_inputs = _side(**plan)
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        _read(raw, graded_inputs)
    assert caught.value.code == "subset_repeat_positions"


def test_a_side_file_naming_another_count_is_refused(small_promise):
    raw, graded_inputs = _side()
    bad = raw.replace(b'"k":{"pool_design":2', b'"k":{"pool_design":3')
    assert bad != raw
    with pytest.raises(subset.SubsetRepeatRefused):
        _read(bad, graded_inputs, registered_sha256=_sha(bad))


def test_another_submission_or_ledger_identity_is_refused(small_promise):
    raw, graded_inputs = _side(ledger=subset.ledger_identity("subset-repeat-other"))
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        _read(raw, graded_inputs)
    assert caught.value.code == "subset_repeat_accounting_identity"
    # the side file names another submission than its ledger identity's
    raw, graded_inputs = _side(sid="rtsk_other")
    with pytest.raises(subset.SubsetRepeatRefused):
        _read(raw, graded_inputs)


def test_no_registered_promise_refuses_at_read_time(tmp_path, monkeypatch):
    raw, graded_inputs = _side()
    monkeypatch.setattr(subset, "VALUES_PATH", tmp_path / "absent.json")
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        _read(raw, graded_inputs)
    assert caught.value.code == "subset_repeat_promise_unregistered"


@pytest.mark.parametrize(
    "overrides",
    [
        {"execution_boundary": "TEST_ONLY_LOCAL_RUNNER"},
        {"logical_prediction_rows": 4},
        {"schema": "carbon.source-free-inference-pair.v1"},
        {"official_eligible": True},
    ],
)
def test_a_broken_run_is_typed_unavailable(small_promise, overrides):
    raw, graded_inputs = _side(**overrides)
    with pytest.raises(subset.SubsetRepeatRefused):
        _read(raw, graded_inputs)


def test_corrupt_or_foreign_bytes_are_typed_unavailable_never_a_verdict(small_promise):
    raw, graded_inputs = _side()
    for bad in (raw[:-5], b"{}\n"):
        with pytest.raises(subset.SubsetRepeatRefused):
            _read(bad, graded_inputs, registered_sha256=_sha(bad))
    with pytest.raises(subset.SubsetRepeatRefused):
        _read(b"", graded_inputs, registered_sha256=_sha(b"x"))
    # a full pair document in the slot is refused, as the pair reader refuses this one
    pair = json.dumps({"schema": "carbon.source-free-inference-pair.v1"}).encode()
    with pytest.raises(subset.SubsetRepeatRefused):
        _read(pair, graded_inputs, registered_sha256=_sha(pair))


def test_non_finite_or_malformed_fresh_answers_are_read_as_the_candidates(
    small_promise,
):
    """NaN and a short row are the candidate's answers: read, then failed by the exact rule, never Carbon's gap."""
    answers = [_row(p) for p in (0, 1, 2, 3, 5, 7, 8, 9)]
    answers[1][7] = float("nan")
    answers[4] = answers[4][:-1]
    answers[6][3] = 10**400  # a JSON integer no float holds
    raw, graded_inputs = _side(answers=answers)
    twins = _read(raw, graded_inputs)
    assert math.isnan(twins[1][7])
    assert twins[5] == ()
    assert twins[8] == ()
    graded = [_row(p) for p in range(N)]
    assert not subset_repeat_produce.repeat_holds(graded, twins)
    assert not subset_repeat_produce.repeat_holds(
        graded, [t if i == 8 else None for i, t in enumerate(twins)]
    )


def test_a_bank_without_sealed_cells_is_refused_at_read_time(small_promise):
    raw, graded_inputs = _side(sealed=[])
    strata = _strata(COHORTS)
    unsealed = subset.BankStrata(
        sealed=(),
        members={**strata.members, POOL: (0, 1, 2, 3, *strata.members[POOL])},
        every=strata.every,
    )
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.read(
            raw,
            registered_sha256=_sha(raw),
            challenge=MOTOR,
            version="1.8",
            evaluation_pack_digest=PACK,
            strata=unsealed,
            graded_inputs=graded_inputs,
            output_shape=[N, WIDTH],
            recipe_digest=RECIPE,
            state_digest=STATE,
            inference_image_id=IMAGE,
            graded_operation=GRADED_OP,
        )
    assert caught.value.code == "subset_repeat_positions"


# -- the real pool-graded fixture (Motor 1.5's, admitted as a subset version here) ------------------------------------------


FIX_SID = "rtsk_" + "s" * 64


@pytest.fixture
def as_subset(tmp_path, monkeypatch):
    """Motor 1.5's real sealed-pool fixture graded as a subset version (the registry, the promise and L2)."""
    monkeypatch.setattr(
        subset,
        "SUBSET_REPEAT_VERSIONS",
        frozenset({(MOTOR, "1.8"), (MOTOR, "1.5")}),
    )
    promise = PROMISE
    monkeypatch.setattr(
        subset,
        "VALUES_PATH",
        _promise_file(tmp_path, {f"{MOTOR} 1.8": promise, f"{MOTOR} 1.5": promise}),
    )


def _fixture_side(case, *, change=None):
    """The subset side file of the fixture grade: every repeated row answered exactly as graded, unless ``change``."""
    graded = json.loads(case["artifacts"]["inference-receipt.json"])
    pack = case["snapshot"].manifest_digest
    cohorts = list(case["bank"]["cohorts"])
    sealed, keyed = subset.plan(
        POOL_KEY,
        FIX_SID,
        challenge=MOTOR,
        version="1.5",
        strata=subset.bank_strata(
            MOTOR, "1.5", {"cohorts": cohorts, "inputs": case["bank"]["inputs"]}
        ),
    )
    positions = subset.positions_of(sealed, keyed)
    answers = [list(case["outputs"][p]) for p in positions]
    if change is not None:
        change(answers, positions)
    with np.load(io.BytesIO(case["case_bank"]), allow_pickle=False) as loaded:
        graded_inputs = loaded["inputs"]
    raw = subset.side_file(
        challenge=MOTOR,
        version="1.5",
        evaluation_pack_digest=pack,
        submission_id=FIX_SID,
        n_rows=len(cohorts),
        sealed=sealed,
        keyed=keyed,
        run=_run(
            graded_inputs,
            positions,
            answers,
            recipe=graded["recipe_digest"],
            state=graded["state_digest"],
            image=graded_image(case),
            ledger=subset.ledger_identity(subset.run_identity(pack, FIX_SID)),
        ),
    )
    originals = {
        **case["originals"],
        "inference_pair_raw": raw,
        "inference_pair_sha256": _sha(raw),
    }
    return originals, sealed, keyed


def graded_image(case):
    return json.loads(case["originals"]["bundle_evidence_raw"])["inference_image_id"]


def _subset_produce(case, originals):
    prepared_source = source.build_pack_source_receipt(
        selected_pack=case["snapshot"],
        entry=case["entry"],
        trusted_job=case["job"],
        registration=case["registration"],
        references=case["references"],
        ordered_query_bytes=[case["case_bank"]],
        evaluation_version=case["version"],
    )
    from carbon.scoring import grade_feedback

    measured = subset_repeat_produce.produce_registered_dual_measurement(
        selected_pack=case["snapshot"],
        public_root=case["root"],
        private_root=case["root"],
        entry=case["entry"],
        trusted_job=case["job"],
        registration=case["registration"],
        references=case["references"],
        graph_originals=originals,
        evaluation_source_receipt_raw=prepared_source.raw,
        timing_step=grade_feedback.step(None),
        single_call_raw=originals.get("single_call_raw"),
        copy_hotkey=case["copy_hotkey"],
    )
    return prepared_source, measured


def test_real_adapter_an_exact_repeat_scores_exactly_as_the_equal_full_pair(
    case, as_subset
):
    """The REAL sealed-pool measure (PoolVariant -> pool exam -> the sealed Motor measure) and dual score: the subset
    producer on an exact repeat gives the SAME benchmark and measured model as the shared producer on the full pair of
    equal repeats."""
    _src, shared = _produce(case)
    originals, sealed, keyed = _fixture_side(case)
    assert len(sealed) == 30
    assert {name: len(rows) for name, rows in keyed.items()} == {POOL: 66, PROBE: 66}
    _src2, mine = _subset_produce(case, originals)
    assert json.loads(mine.raw)["benchmark"] == json.loads(shared.raw)["benchmark"]
    assert mine.measured_model == shared.measured_model
    benchmark = json.loads(mine.raw)["benchmark"]
    assert set(benchmark["models"][0]["gates"].values()) == {"PASS"}
    scored = ScoreEngine.score_dual_benchmark_v4(benchmark, case["score_pack"])
    assert type(scored["models"][0]["score"]) is float


@pytest.mark.parametrize("stratum", [GRID, POOL, PROBE])
def test_real_adapter_one_ulp_off_in_one_repeated_row_leaves_the_grade_unscored(
    case, as_subset, stratum
):
    def change(answers, positions):
        cohorts = list(case["bank"]["cohorts"])
        i = next(n for n, p in enumerate(positions) if cohorts[p] == stratum)
        answers[i][-1] = math.nextafter(answers[i][-1], math.inf)

    originals, _sealed, _keyed = _fixture_side(case, change=change)
    _src, measured = _subset_produce(case, originals)
    model = json.loads(measured.raw)["benchmark"]["models"][0]
    assert model["gates"]["native_motor_valid"] == "FAIL"
    assert model["gates"]["complete_fixed_coverage"] == "FAIL"
    scored = ScoreEngine.score_dual_benchmark_v4(
        json.loads(measured.raw)["benchmark"], case["score_pack"]
    )
    assert scored["models"][0]["score"] is None


def test_real_adapter_repeat_values_reach_gates_only(case, as_subset, monkeypatch):
    """A-5: the twin rows the measure receives never reach a score input. Perturb every twin row that is not a sealed
    cell (pool and probe rows: never read) wildly, and every sealed cell's twin inside Motor's torque rule (read only by
    the gate): the measured A, D, gates and outcome are unchanged."""
    seen = {}
    original = subset_repeat_produce.measure_subset

    def spy(adapter, **kwargs):
        seen.update(adapter=adapter, **kwargs)
        return original(adapter, **kwargs)

    monkeypatch.setattr(subset_repeat_produce, "measure_subset", spy)
    originals, _sealed, _keyed = _fixture_side(case)
    _subset_produce(case, originals)
    adapter, outputs = seen["adapter"], seen["outputs"]
    arguments = {
        k: v
        for k, v in seen.items()
        if k not in ("adapter", "outputs", "twins", "capture")
    }
    baseline = adapter.measure(outputs=outputs, repeats=[outputs, outputs], **arguments)
    cohorts = list(case["bank"]["cohorts"])
    perturbed = [
        (
            [v * (1 + 1e-7) for v in row]
            if cohorts[i] == GRID
            else [v + 123.0 for v in row]
        )
        for i, row in enumerate(outputs)
    ]
    moved = adapter.measure(
        outputs=outputs, repeats=[perturbed, perturbed], **arguments
    )
    for field in ("A", "D", "gates", "decision_outcome"):
        assert moved[field] == baseline[field], field


# -- the producer successor (R-1, R-3, L2) and the bind round-trip -------------------------------------------------------


def _motor18():
    from carbon.scoring import motor18_dual_pack

    return motor18_dual_pack


def test_the_committed_row_maps_the_live_pack_digest_to_this_code():
    """The row's producer_digest is the producer recomputed at HEAD: it must be updated (with Validator-2B) whenever a
    Motor 1.8 producer file changes, or every 1.8 grade refuses (fail closed)."""
    row = producer_successor.row(MOTOR, "1.8")
    assert row == {
        "pack_producer_digest": OLD_MOTOR18,
        "producer_digest": physical.producer_digest(_motor18()),
    }
    document = json.loads(producer_successor.REGISTRY.read_text(encoding="utf-8"))
    assert list(document["rows"]) == [f"{MOTOR} 1.8"]  # ONE row, Motor 1.8 only


def _registry(tmp_path, rows, name="successor.json"):
    path = tmp_path / name
    path.write_text(
        json.dumps({"schema": producer_successor.SCHEMA, "rows": rows}),
        encoding="utf-8",
    )
    return path


def test_the_successor_binds_only_on_an_exact_match(tmp_path):
    new = physical.producer_digest(_motor18())
    other = "sha256:" + "e" * 64
    assert producer_successor.binds(MOTOR, "1.8", OLD_MOTOR18, new)
    assert producer_successor.binds(MOTOR, "1.8", new, new)  # an exact pin needs no row
    assert not producer_successor.binds(MOTOR, "1.8", OLD_MOTOR18, other)
    assert not producer_successor.binds(MOTOR, "1.8", other, new)
    assert not producer_successor.binds(MOTOR, "1.5", OLD_MOTOR18, new)
    assert not producer_successor.binds(MOTOR, "1.8", None, new)
    good = {"pack_producer_digest": OLD_MOTOR18, "producer_digest": new}
    for path in (
        tmp_path / "absent.json",
        _registry(tmp_path, {f"{MOTOR} 1.8": {"pack_producer_digest": OLD_MOTOR18}}),
        _registry(
            tmp_path,
            {f"{MOTOR} 1.8": {**good, "producer_digest": "sha256:short"}},
        ),
        # L2: a row of any version that is not a subset version makes the whole registry refuse
        _registry(tmp_path, {f"{MOTOR} 1.8": good, f"{MOTOR} 1.5": good}),
        _registry(tmp_path, {f"{MOTOR} 1.8": good, "chip-cold-plate 1.8": good}),
    ):
        assert producer_successor.row(MOTOR, "1.8", path=path) is None
        assert not producer_successor.binds(MOTOR, "1.8", OLD_MOTOR18, new, path=path)
    (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
    assert producer_successor.row(MOTOR, "1.8", path=tmp_path / "bad.json") is None


NEW_FIXTURE = "sha256:" + "f" * 64


@pytest.fixture
def successor_fixture(case, as_subset, tmp_path, monkeypatch):
    """The fixture pack pins its producer; the running producer is a different, synthetic digest that ONE successor row
    maps it to (the Motor 1.8 switch, on the real pool fixture)."""
    accuracy = case["snapshot"].read_json_role(
        case["root"], "public", "accuracy_definition", max_bytes=1024 * 1024
    )
    pinned = accuracy["producer_digest"]
    monkeypatch.setattr(physical, "producer_digest", lambda adapter: NEW_FIXTURE)
    monkeypatch.setattr(
        producer_successor,
        "REGISTRY",
        _registry(
            tmp_path,
            {
                f"{MOTOR} 1.5": {
                    "pack_producer_digest": pinned,
                    "producer_digest": NEW_FIXTURE,
                }
            },
        ),
    )
    return pinned


def test_a_successor_receipt_binds_and_carries_the_new_digest(
    case, successor_fixture, tmp_path, monkeypatch
):
    pinned = successor_fixture
    originals, _sealed, _keyed = _fixture_side(case)
    prepared_source, measured = _subset_produce(case, originals)
    body = json.loads(measured.raw)
    assert body["producer_digest"] == NEW_FIXTURE
    assert body["measurement_contract"]["producer_digest"] == NEW_FIXTURE
    # the measurement contract named is still the pack's own pinned one
    assert (
        body["measurement_contract_digest"]
        == case["score_pack"]["measurement_contract_digest"]
    )
    scoring = ScoreEngine.score_dual_benchmark_v4(body["benchmark"], case["score_pack"])
    bound = _bind({**case, "originals": originals}, prepared_source, measured, scoring)
    assert bound["producer_digest"] == NEW_FIXTURE
    assert bound["scoring"] == scoring
    # the same receipt without the row is refused by the binding (never read as the pinned contract)
    monkeypatch.setattr(
        producer_successor, "REGISTRY", _registry(tmp_path, {}, name="empty.json")
    )
    from carbon.scoring import private_evaluation_evidence as evidence

    with pytest.raises(evidence.PrivateEvaluationEvidenceRefused) as caught:
        _bind({**case, "originals": originals}, prepared_source, measured, scoring)
    assert str(caught.value) == "dual_measurement_contract"
    assert pinned != NEW_FIXTURE


def test_old_pinned_evidence_still_binds_with_its_own_digest(case):
    """Evidence measured under the pinned producer (every grade before the switch) reads as it always did."""
    prepared_source, measured = _produce(case)
    scoring = ScoreEngine.score_dual_benchmark_v4(
        json.loads(measured.raw)["benchmark"], case["score_pack"]
    )
    bound = _bind(case, prepared_source, measured, scoring)
    assert bound["producer_digest"] == json.loads(measured.raw)["producer_digest"]


# -- every other version -------------------------------------------------------------------------------------------------


def test_every_other_producer_digest_is_unchanged():
    import importlib

    moved = {
        name: physical.producer_digest(
            importlib.import_module("carbon.scoring." + name)
        )
        for name in OTHER_DIGESTS
    }
    assert moved == OTHER_DIGESTS
    assert physical.producer_digest(_motor18()) != OLD_MOTOR18


def test_only_motor_18_is_a_subset_version_and_every_other_keeps_the_pair():
    from carbon.challenge_validator import lean_recipe_retention as retention

    assert subset.SUBSET_REPEAT_VERSIONS == frozenset({(MOTOR, "1.8")})
    for challenge, version in (
        (MOTOR, "1.5"),
        (MOTOR, "1.4"),
        ("cooling-plate", "1.8"),
        ("f02", "1.0"),
        (None, None),
    ):
        adapter = SimpleNamespace(challenge_id=challenge, challenge_version=version)
        assert not retention._subset_repeat_version(adapter)
    assert retention._subset_repeat_version(
        SimpleNamespace(challenge_id=MOTOR, challenge_version="1.8")
    )
    files = _motor18().FILES
    for name in (
        "subset_repeat_evidence.py",
        "producer_successor.py",
        "subset_repeat_produce.py",
    ):
        assert name in files
        assert name not in physical._SHARED_FILES


def test_the_operator_tool_routes_a_subset_version_to_its_own_producer():
    text = (ROOT / "scripts" / "dev" / "design_value_parts.py").read_text(
        encoding="utf-8"
    )
    assert "subset_repeat_produce.produce_dual_benchmark_input" in text
    assert callable(subset_repeat_produce.produce_dual_benchmark_input)


# -- the door ------------------------------------------------------------------------------------------------------------


def _door(tmp_path, monkeypatch, plays, *, n=200, promise=None, key=KEY):
    """The REAL `_subset_repeat_raw` over a fake `infer_frozen_once` that plays ``plays`` in order; the bank has 30
    sealed cells, 20 probe rows and ``n - 50`` pool rows."""
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.development_session import construction_recipe, paired_inference

    calls = []
    plays = list(plays)

    def fake_once(ledger, **call):
        calls.append(call)
        play = plays.pop(0)
        if isinstance(play, Exception):
            raise play
        return SimpleNamespace(evidence=play)

    def no_pair(*_a, **_k):
        raise AssertionError("no pair op for a subset version")

    monkeypatch.setattr(paired_inference, "infer_frozen_once", fake_once)
    monkeypatch.setattr(paired_inference, "infer_frozen_pair", no_pair)
    monkeypatch.setattr(
        construction_recipe.ConstructionRecipe, "from_dict", staticmethod(lambda d: d)
    )
    monkeypatch.setattr(
        retention, "_private_evaluation_directory", lambda result, sid: tmp_path
    )
    monkeypatch.setattr(
        retention, "_subset_bank", lambda adapter, inputs: _bank(_cohorts(n))
    )
    if promise is not None:
        monkeypatch.setattr(subset, "VALUES_PATH", _motor18_promise(tmp_path, promise))
    snapshot = SimpleNamespace(
        manifest_digest=PACK,
        read_json_role=lambda root, side, role, max_bytes: {
            "paired_repeat_procedure": "per_case"
        },
    )
    kit = {
        "id": MOTOR,
        "version": "1.8",
        "train_digest": "t",
        "interface_digest": "i",
        "construction_limits_digest": "l",
    }
    practice = np.arange(n * 2, dtype=np.float64).reshape(n, 2)
    material = {
        "construction_kit": kit,
        "construction_limits_document": {
            "reconstruction_resource_policy": {
                "inference_wall_seconds_max": 60,
                "total_reconstruction_wall_seconds_max": 120,
            }
        },
        "interface_document": {"dtype": "<f8"},
        "practice_inputs": practice,
        "expected_output_shape": (n, WIDTH),
        "allowlist_bytes": b"",
    }
    provider = SimpleNamespace(
        ledger=object(),
        inference_image=object(),
        _requests={"rtsk_x": SimpleNamespace(recipe={})},
    )
    adapter = SimpleNamespace(
        challenge_id=MOTOR,
        challenge_version="1.8",
        speed_sample_key=key,
        owner=lambda sid: "owner",
        _provider=lambda owner: provider,
        discovery=SimpleNamespace(
            _material=material,
            evaluation_pack_snapshot=snapshot,
            evaluation_pack_public_root=tmp_path,
        ),
    )
    real = (
        retention._subset_repeat_raw
    )  # captured: a test may later replace the module attribute

    def run():
        return real(
            adapter,
            "rtsk_x",
            {},
            {"state.npz": b"s", "inputs.npz": _tensors(inputs=practice)},
            {"state_digest": "sd"},
        )

    return run, calls, practice


def _cache(tmp_path):
    from carbon.challenge_validator import lean_recipe_retention as retention

    tag = hashlib.sha256(
        retention._json(list(subset.registered_promise(MOTOR, "1.8")))
    ).hexdigest()[:16]
    return tmp_path / f"subset-repeat-{tag}.json"


def test_the_door_runs_one_fresh_op_on_the_sealed_cells_and_each_stratums_keyed_rows(
    tmp_path, monkeypatch
):
    run, calls, practice = _door(tmp_path, monkeypatch, [{"fixture": True}])
    raw = run()
    assert len(calls) == 1  # ONE op, no pair
    document = json.loads(raw)
    sealed, keyed = subset.plan(
        KEY, "rtsk_x", challenge=MOTOR, version="1.8", strata=_strata(_cohorts(200))
    )
    assert document["sealed_positions"] == sealed == list(range(30))
    assert document["keyed_positions"] == keyed
    assert document["k"] == {POOL: 66, PROBE: 20}
    assert keyed[PROBE] == list(range(30, 50))
    assert document["submission_id"] == "rtsk_x"
    assert document["evaluation_pack_digest"] == PACK
    positions = subset.positions_of(sealed, keyed)
    assert np.array_equal(calls[0]["inputs"], practice[positions])
    assert calls[0]["expected_output_shape"] == (116, WIDTH)
    assert calls[0]["procedure"] == "per_case"
    assert calls[0]["identity"] == subset.run_identity(PACK, "rtsk_x")
    assert document["run"] == {"fixture": True}
    assert _cache(tmp_path).read_bytes() == raw
    # a retry reads the retained bytes back and runs nothing
    assert run() == raw and len(calls) == 1


def test_a_cached_file_of_another_draw_is_refused(tmp_path, monkeypatch):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, calls, _practice = _door(tmp_path, monkeypatch, [])
    _cache(tmp_path).write_bytes(b'{"keyed_positions":{"pool_design":[0,1]}}')
    with pytest.raises(retention.RetentionUnavailable) as caught:
        run()
    assert str(caught.value) == "subset_repeat_cache_not_this_draw" and not calls


def _failure(cause):
    from carbon.development_session.paired_inference import InferencePairFailure

    return InferencePairFailure("repeat", {}, {}, cause)


def test_one_wall_hit_is_retried_and_a_second_is_the_candidates(tmp_path, monkeypatch):
    from test_while_walls_typed_candidate_failure import _wall

    from carbon.challenge_validator import lean_recipe_retention as retention

    run, calls, _practice = _door(
        tmp_path, monkeypatch, [_failure(_wall()), {"fixture": True}]
    )
    run()
    assert [c["identity"] for c in calls] == [
        subset.run_identity(PACK, "rtsk_x"),
        subset.run_identity(PACK, "rtsk_x", retry=True),
    ]
    for path in tmp_path.iterdir():
        path.unlink()
    run, calls, _practice = _door(
        tmp_path, monkeypatch, [_failure(_wall()), _failure(_wall())]
    )
    with pytest.raises(retention.CandidateWallLimitReached) as caught:
        run()
    assert str(caught.value) == "WORKER_WALL_LIMIT_REACHED"
    assert caught.value.carbon_pass == "inference_pair"
    assert len(calls) == 2


def test_a_host_fault_stays_carbons(tmp_path, monkeypatch):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, _calls, _practice = _door(
        tmp_path, monkeypatch, [_failure(RuntimeError("daemon"))]
    )
    with pytest.raises(retention.RetentionUnavailable) as caught:
        run()
    assert not isinstance(caught.value, retention.CandidateWallLimitReached)
    assert str(caught.value) == "subset_repeat_incomplete"


@pytest.mark.parametrize(
    "row, code",
    [
        (
            {**PROMISE, "repeat_fail_fraction": None},
            "subset_repeat_promise_unregistered",
        ),
        ({"k": 66}, "subset_repeat_promise_unregistered"),
        ({**PROMISE, "strata": None}, "subset_repeat_strata_unregistered"),
        ({**PROMISE, "strata": [POOL, "practice"]}, "subset_repeat_stratum_unknown"),
    ],
)
def test_no_promise_or_strata_refuses_at_grade_time_before_any_op(
    tmp_path, monkeypatch, row, code
):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, calls, _practice = _door(tmp_path, monkeypatch, [], promise=row)
    with pytest.raises(retention.RetentionUnavailable) as caught:
        run()
    assert str(caught.value) == code and not calls


def test_no_key_refuses_at_grade_time(tmp_path, monkeypatch):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, calls, _practice = _door(tmp_path, monkeypatch, [], key=None)
    with pytest.raises(retention.RetentionUnavailable) as caught:
        run()
    assert str(caught.value) == "subset_repeat_key_unavailable" and not calls


def _retain(tmp_path, monkeypatch, version, repeat):
    """`_retain_selected_pack_evaluation` up to and including the repeat (``repeat`` replaces it)."""
    from carbon.challenge_validator import exam_cap
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.scoring import dual_score

    settled = []

    class Cap:
        def __init__(self, *_a, **_k):
            pass

        def reserve(self, **_k):
            return "reservation"

        def settle(self, reservation, outcome, **_k):
            settled.append(outcome)

    monkeypatch.setattr(exam_cap, "ExamCap", Cap)
    monkeypatch.setattr(exam_cap, "submission_block", lambda *a: None)
    monkeypatch.setattr(
        retention,
        "_register_retained_pack_source",
        lambda *a, **k: {"entry": {"state_digest": "sd", "recipe_digest": "rd"}},
    )
    monkeypatch.setattr(retention, "_record_stop_ladder", lambda *a: "LADDER")
    seen = []

    def record(name):
        def call(*_a, **_k):
            seen.append(name)
            return repeat() if name == "subset" else b"pair-evidence"

        return call

    def stop(*_a, **_k):
        raise retention.RetentionUnavailable("stopped_after_the_repeat")

    monkeypatch.setattr(retention, "_subset_repeat_raw", record("subset"))
    monkeypatch.setattr(retention, "_inference_pair_raw", record("pair"))
    monkeypatch.setattr(retention, "_single_call_raw", stop)
    snapshot = SimpleNamespace(
        manifest_digest=PACK,
        read_json_role=lambda root, side, role, max_bytes: {
            "schema": dual_score.PACK_SCHEMA,
            "hard_gates": ["speed"],
        },
        read_source_registration=lambda root: {
            "trusted_job": {},
            "benchmark_registration": {},
            "evaluation_version": "v",
        },
    )
    adapter = SimpleNamespace(
        challenge_id=MOTOR,
        challenge_version=version,
        ledger=object(),
        contract_digest="c",
        owner=lambda sid: "owner",
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=snapshot,
            evaluation_pack_private_root=tmp_path,
            evaluation_pack_public_root=tmp_path,
        ),
    )
    result = retention._retain_selected_pack_evaluation(
        adapter,
        "rtsk_x",
        {"evaluation_pack_digest": PACK, "entry_id": "sha256:" + "1" * 64},
        {
            "inputs.npz": b"q",
            "inference-receipt.json": b"r",
            "worker-evidence.json": b"w",
        },
    )
    return result, seen, settled


def test_the_retention_runs_the_subset_repeat_and_never_the_pair_for_motor_18(
    tmp_path, monkeypatch
):
    for version, expected in (("1.8", ["subset"]), ("1.5", ["pair"])):
        result, seen, settled = _retain(
            tmp_path, monkeypatch, version, lambda: b"subset-evidence"
        )
        assert seen == expected, version
        assert result["private_evaluation_reason"] == "stopped_after_the_repeat"
        assert settled == ["UNAVAILABLE"]


def test_a_second_subset_wall_hit_settles_candidate_failed_with_pass_inference_pair(
    tmp_path, monkeypatch
):
    """exam feedback v8, through its real path: the counted slot is kept, the marker names the pass."""
    from test_while_walls_typed_candidate_failure import _grader, _wall

    from carbon.challenge_validator import lean_recipe_retention as retention

    (tmp_path / "door").mkdir()
    door, calls, _practice = _door(
        tmp_path / "door", monkeypatch, [_failure(_wall()), _failure(_wall())]
    )
    result, seen, settled = _retain(tmp_path, monkeypatch, "1.8", door)
    assert seen == ["subset"] and len(calls) == 2
    assert result["private_evaluation_state"] == "CANDIDATE_FAILED"
    assert result["private_evaluation_reason"] == retention.CANDIDATE_WALL_LIMIT_REACHED
    assert result["private_evaluation_pass"] == "inference_pair"
    assert settled == [retention.CANDIDATE_WALL_LIMIT_REACHED]
    (tmp_path / "grader").mkdir(mode=0o700)
    grader, *_rest, task = _grader(tmp_path / "grader", result)
    assert grader.run_once() == (task, "CANDIDATE_FAILED")
    assert grader.marker(task)["pass"] == "inference_pair"


# -- the receiver's start-up check (R-5, M4) ------------------------------------------------------------------------------


def _pack(pinned):
    return SimpleNamespace(
        read_json_role=lambda root, side, role, max_bytes: {"producer_digest": pinned}
    )


def _serve(retention, monkeypatch, *, pinned=OLD_MOTOR18, cohorts=None, key=KEY):
    from carbon.scoring import sealed_batch_source

    monkeypatch.setattr(
        sealed_batch_source,
        "resolve",
        lambda **kw: (_bank(cohorts or _cohorts(200)), None),
    )
    return retention.subset_repeat_serve_check(
        MOTOR,
        "1.8",
        pack_snapshot=_pack(pinned),
        public_root=Path("."),
        private_root=Path("."),
        copy_hotkey="5Hotkey",
        speed_key=key,
    )


def test_the_serve_check_names_the_successor_row_and_the_strata(monkeypatch):
    from carbon.challenge_validator import lean_recipe_retention as retention

    assert retention.subset_repeat_serve_check(MOTOR, "1.5") is None
    named = _serve(retention, monkeypatch)
    new = physical.producer_digest(_motor18())
    assert named["successor_row"] == {
        "pack_producer_digest": OLD_MOTOR18,
        "producer_digest": new,
    }
    assert named["producer_digest"] == new
    assert (named["repeat_fail_fraction"], named["repeat_detect_prob"]) == (0.10, 0.999)
    assert named["strata"] == [POOL, PROBE]
    assert named["counts"] == {POOL: 66, PROBE: 20}


@pytest.mark.parametrize(
    "change, code",
    [
        ({"pinned": "sha256:" + "e" * 64}, "producer_successor_mismatch"),
        ({"key": None}, "subset_repeat_key_unavailable"),
        ({"key": b"short"}, "subset_repeat_key_unavailable"),
        ({"cohorts": [GRID] * 30 + [POOL] * 100}, "subset_repeat_stratum_empty"),
        (
            {"cohorts": [GRID] * 30 + [POOL] * 100 + ["other"]},
            "subset_repeat_row_in_no_stratum",
        ),
        ({"cohorts": [PROBE] * 30 + [POOL] * 100}, "subset_repeat_bank_strata"),
    ],
)
def test_the_serve_check_refuses(monkeypatch, change, code):
    from carbon.challenge_validator import lean_recipe_retention as retention

    with pytest.raises(retention.RetentionUnavailable) as caught:
        _serve(retention, monkeypatch, **change)
    assert str(caught.value) == code


@pytest.mark.parametrize(
    "row, code",
    [
        (
            {**PROMISE, "repeat_fail_fraction": None},
            "subset_repeat_promise_unregistered",
        ),
        ({**PROMISE, "strata": None}, "subset_repeat_strata_unregistered"),
        ({**PROMISE, "strata": [GRID]}, "subset_repeat_strata_unregistered"),
    ],
)
def test_the_serve_check_refuses_an_unregistered_promise_or_strata(
    tmp_path, monkeypatch, row, code
):
    from carbon.challenge_validator import lean_recipe_retention as retention

    monkeypatch.setattr(subset, "VALUES_PATH", _motor18_promise(tmp_path, row))
    with pytest.raises(retention.RetentionUnavailable) as caught:
        retention.subset_repeat_serve_check(MOTOR, "1.8", speed_key=KEY)
    assert str(caught.value) == code


def test_the_receiver_runs_the_serve_check_at_start_with_the_hosts_key():
    text = (ROOT / "carbon" / "challenge_validator" / "direct_receiver.py").read_text(
        encoding="utf-8"
    )
    serve = text[text.index("def serve(") :]
    check = serve.index("lean_recipe_retention.subset_repeat_serve_check(")
    assert serve.index("crown_hold.bind_pack(pack_digest)") < check
    assert check < serve.index("discovery = DirectFixtureDiscovery(")
    assert "_speed_key(cfg)" in serve[check : check + 1600]


# -- the public words (R-4) and the record -------------------------------------------------------------------------------

LINE = (
    "Carbon runs your built model again in a fresh process on a secret sample of the exam designs it already "
    "answered, and the answers must match."
)


def test_the_inference_pair_line_says_the_repeat_is_a_keyed_sample_in_both_places():
    import importlib.util

    words = ROOT / "scripts" / "dev" / "miner_launchpad" / "pass_words.py"
    spec = importlib.util.spec_from_file_location("pass_words_subset", words)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PASS_LINES["inference_pair"] == LINE
    page = (ROOT / "kits" / "motor" / "HOW_YOURE_TESTED.md").read_text(encoding="utf-8")
    assert f"  - `inference_pair`: {LINE}\n" in page
    assert not any(c.isdigit() for c in LINE) and LINE.endswith(".")


def test_the_record_carries_both_owner_lines_and_the_values():
    record = json.loads(
        (ROOT / "docs" / "records" / "2026-11-15-motor18-subset-repeat.json").read_text(
            encoding="utf-8"
        )
    )
    words = {w["typed_at"]: w for w in record["owner_words"]}
    assert set(words) == {
        "Sun 15 Nov 2026 08:19 CST",
        "Sun 15 Nov 2026 08:38 CST",
        "Sun 15 Nov 2026 ~09:5x CST",
    }
    assert words["Sun 15 Nov 2026 ~09:5x CST"]["verbatim"] == "Yes for 66 per stratum"
    assert words["Sun 15 Nov 2026 08:38 CST"]["verbatim"] == (
        "66 rows. But we need a % that generalizes for challenges"
    )
    assert record["values"]["promise"] == {
        "repeat_fail_fraction": 0.10,
        "repeat_detect_prob": 0.999,
        "strata": list(REAL_STRATA[(MOTOR, "1.8")]),
    }
    assert record["values"]["producer_successor"] == producer_successor.row(
        MOTOR, "1.8"
    )
    assert "NOT_APPLICABLE" not in json.dumps(record)
