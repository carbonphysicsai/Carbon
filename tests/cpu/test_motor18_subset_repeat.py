"""Motor 1.8's keyed subset repeat, as the same version (owner Sun 15 Nov 2026 08:19 + 08:38 CST; CV-Motor-B's ruling;
Validator-2B R-1..R-5; docs/records/2026-11-15-motor18-subset-repeat.json).

- k is derived from the owner's registered promise (f, P): 66 for f = 0.10, P = 0.999, capped at the graded rows; a
  missing, null or malformed promise fails closed at serve time and at grade time.
- The draw is deterministic per (key, submission), independent of the speed sample, k distinct rows, and never public.
- The scorer: an all-agreeing subset repeat measures exactly as the full pair whose repeats equal the graded answers; one
  sampled row beyond Motor's paired_repeat rule leaves the grade unscored; non-sampled rows read NOT_APPLICABLE; broken
  evidence is typed unavailable, never a candidate verdict.
- The door runs ONE subset op (no pair op) for Motor 1.8; a second wall hit is the candidate's, pass ``inference_pair``.
- R-1: ONE successor row, exact match only; new evidence carries the new digest; old evidence still reads.
- Every other version's producer digest is unchanged from e6f67358, and every other version keeps the full pair.

Every value here is synthetic, except the owner's two public rule values (f, P) and the producer digests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.development_session.bundle_construction_worker import _tensors
from carbon.motor import exam
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import producer_successor, subset_repeat_produce
from carbon.scoring import subset_repeat_evidence as subset

ROOT = Path(__file__).resolve().parents[2]
MOTOR = "electric-motor-magnetics"
WIDTH = 240

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


def _row(seed):
    """One synthetic, whole 240-wide 1.8 answer (torque then three linkages), all finite."""
    return [float(seed) + 0.01 * i for i in range(WIDTH)]


def _promise_file(tmp_path, row):
    path = tmp_path / "subset_repeat.json"
    path.write_text(
        json.dumps({"schema": subset.VALUES_SCHEMA, "rows": {f"{MOTOR} 1.8": row}}),
        encoding="utf-8",
    )
    return path


# -- the promise and k ---------------------------------------------------------------------------------------------------


def test_the_registered_promise_derives_k_66_and_caps_at_the_bank():
    assert subset.registered_promise(MOTOR, "1.8") == (0.10, 0.999)
    assert subset.derived_k(0.10, 0.999, 2564) == 66
    assert math.ceil(math.log(1 - 0.999) / math.log(1 - 0.10)) == 66
    assert subset.registered_k(MOTOR, "1.8", 2564) == 66
    # the bank-rows cap
    assert subset.registered_k(MOTOR, "1.8", 40) == 40
    assert subset.derived_k(0.10, 0.999, 1) == 1


@pytest.mark.parametrize(
    "row",
    [
        None,
        {},
        {"repeat_fail_fraction": None, "repeat_detect_prob": 0.999},
        {"repeat_fail_fraction": 0.10, "repeat_detect_prob": None},
        {"repeat_fail_fraction": 0.10},
        {"repeat_fail_fraction": 0.10, "repeat_detect_prob": 0.999, "k": 66},
        {"repeat_fail_fraction": True, "repeat_detect_prob": 0.999},
        {"repeat_fail_fraction": 0, "repeat_detect_prob": 0.999},
        {"repeat_fail_fraction": 1, "repeat_detect_prob": 0.999},
        {"repeat_fail_fraction": 0.0, "repeat_detect_prob": 0.999},
        {"repeat_fail_fraction": 1.0, "repeat_detect_prob": 0.999},
        {"repeat_fail_fraction": 0.10, "repeat_detect_prob": 1.5},
        {"repeat_fail_fraction": "0.10", "repeat_detect_prob": 0.999},
    ],
)
def test_a_null_or_malformed_promise_fails_closed(tmp_path, row):
    path = _promise_file(tmp_path, row)
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.registered_k(MOTOR, "1.8", 2564, path=path)
    assert caught.value.code == "subset_repeat_promise_unregistered"


def test_an_absent_file_or_row_fails_closed(tmp_path):
    with pytest.raises(subset.SubsetRepeatRefused):
        subset.registered_promise(MOTOR, "1.8", path=tmp_path / "absent.json")
    with pytest.raises(subset.SubsetRepeatRefused):
        subset.registered_promise(MOTOR, "1.5")
    for bad in (float("nan"), float("inf")):
        with pytest.raises(subset.SubsetRepeatRefused):
            subset.derived_k(bad, 0.999, 10)


# -- the draw -------------------------------------------------------------------------------------------------------------


KEY = bytes(range(32))  # synthetic K_speed


def test_the_draw_is_deterministic_distinct_and_per_submission():
    first = subset.draw(subset.grade_key(KEY, "rtsk_a"), 500, 66)
    assert first == subset.draw(subset.grade_key(KEY, "rtsk_a"), 500, 66)
    assert len(first) == len(set(first)) == 66
    assert first == sorted(first) and 0 <= first[0] and first[-1] < 500
    assert first != subset.draw(subset.grade_key(KEY, "rtsk_b"), 500, 66)
    assert first != subset.draw(subset.grade_key(bytes(32), "rtsk_a"), 500, 66)
    # k == rows draws every row
    assert subset.draw(subset.grade_key(KEY, "rtsk_a"), 7, 7) == list(range(7))


def test_the_draw_key_is_independent_of_the_speed_sample():
    from carbon.development_session import single_call_timing

    assert subset.DOMAIN != single_call_timing.SEED_DOMAIN
    assert subset.grade_key(KEY, "rtsk_a") != single_call_timing.sample_seed(
        KEY, "rtsk_a"
    )


def test_the_draw_covers_rows_roughly_uniformly():
    counts = [0] * 20
    for i in range(400):
        for p in subset.draw(subset.grade_key(KEY, f"rtsk_{i}"), 20, 5):
            counts[p] += 1
    # 400 draws of 5 of 20: 100 per row expected; a broken draw piles onto a few rows
    assert min(counts) > 60 and max(counts) < 140


def test_the_draw_refuses_a_bad_key_or_k():
    with pytest.raises(subset.SubsetRepeatRefused):
        subset.grade_key(b"short", "rtsk_a")
    with pytest.raises(subset.SubsetRepeatRefused):
        subset.grade_key(KEY, "")
    for k in (0, 11):
        with pytest.raises(subset.SubsetRepeatRefused):
            subset.draw(subset.grade_key(KEY, "rtsk_a"), 10, k)


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


# -- the scorer -----------------------------------------------------------------------------------------------------------


class _Adapter:
    """A stand-in adapter whose measure records its call and gates every row's torque against repeat 0 with Motor's
    own rule, as the sealed measure does on its cells."""

    class Refused(ValueError):
        def __init__(self, code):
            self.code = code
            super().__init__(code)

    def __init__(self):
        self.calls = []

    def measure(self, *, outputs, repeats, **arguments):
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
    sampled = {1: list(outputs[1]), 7: list(outputs[7])}
    twins = [sampled.get(i) for i in range(len(outputs))]
    adapter = _Adapter()
    measured = subset_repeat_produce.measure_subset(
        adapter, outputs=outputs, twins=twins, definition={}
    )
    full = _Adapter().measure(outputs=outputs, repeats=[outputs, outputs])
    assert measured == full
    # the adapter saw exactly the full-pair call whose repeats equal the graded answers
    assert adapter.calls[0]["repeats"] == [outputs, outputs]
    assert adapter.calls[0]["definition"] == {}


def test_a_sampled_row_within_the_rule_still_scores_the_same():
    outputs = _grade()
    near = list(outputs[3])
    near[5] = near[5] * (1 + 1e-7)  # inside 32 float32 ulp
    twins = [near if i == 3 else None for i in range(len(outputs))]
    measured = subset_repeat_produce.measure_subset(
        _Adapter(), outputs=outputs, twins=twins
    )
    assert measured["gates"]["native_motor_valid"] is True
    assert (
        measured["A"] == _Adapter().measure(outputs=outputs, repeats=[outputs] * 2)["A"]
    )


@pytest.mark.parametrize("row", [3, 11])
def test_one_sampled_row_off_leaves_the_grade_unscored(row):
    outputs = _grade()
    off = list(outputs[row])
    off[10] += 1.0  # far beyond 32 float32 ulp
    twins = [off if i == row else None for i in range(len(outputs))]
    capture = {}
    measured = subset_repeat_produce.measure_subset(
        _Adapter(), outputs=outputs, twins=twins, capture=capture
    )
    assert measured["gates"]["native_motor_valid"] is False
    assert measured["gates"]["complete_fixed_coverage"] is False
    assert measured["gates"]["physics"] is True
    assert measured["A"] is None and measured["D"] == 0.0
    assert capture["se_basis"] == {"gated": True}


def test_a_pool_row_mismatch_the_base_never_sees_still_fails_the_grade():
    """The pool rows' repeats never reach the sealed measure: the subset gate judges them itself."""

    class CellsOnly(_Adapter):
        def measure(self, *, outputs, repeats, **arguments):
            # judge only the first two rows, as the sealed measure judges only its cells
            return super().measure(
                outputs=outputs[:2], repeats=[r[:2] for r in repeats], **arguments
            )

    outputs = _grade()
    off = list(outputs[9])
    off[0] -= 2.0
    twins = [off if i == 9 else None for i in range(len(outputs))]
    measured = subset_repeat_produce.measure_subset(
        CellsOnly(), outputs=outputs, twins=twins
    )
    assert measured["gates"]["native_motor_valid"] is False
    assert measured["A"] is None


def test_non_sampled_rows_read_not_applicable_and_an_unreadable_twin_fails():
    outputs = _grade(3)
    assert exam.gates({"torque_nm": outputs[0][:60]}, None)["paired_repeat"] == (
        exam.NOT_APPLICABLE
    )
    assert subset_repeat_produce.repeat_holds(outputs, [None, None, None])
    assert not subset_repeat_produce.repeat_holds(outputs, [None, [1.0] * 60, None])
    # a graded answer that is no whole 1.8 row has no repeat verdict here (its own schema gate judges it)
    assert subset_repeat_produce.repeat_holds(
        [[1.0] * 60, *outputs[1:]], [[1.0] * 60, None, None]
    )


def test_a_roster_mismatch_refuses():
    with pytest.raises(_Adapter.Refused):
        subset_repeat_produce.measure_subset(
            _Adapter(), outputs=_grade(3), twins=[None, None]
        )


# -- the side file and its reader -----------------------------------------------------------------------------------------

RECIPE = "sha256:" + "1" * 64
STATE = "sha256:" + "2" * 64
IMAGE = "sha256:" + "3" * 64
GRADED_OP = "operation-" + "4" * 64
REPEAT_OP = "operation-" + "5" * 64


def _original(raw):
    return {"sha256": _sha(raw), "raw_base64": base64.b64encode(raw).decode()}


def _run(graded_inputs, positions, answers, **overrides):
    rows = np.ascontiguousarray(graded_inputs[positions])
    predictions = json.dumps(answers).encode()
    receipt = json.dumps(
        {
            "schema": "carbon.development.bundle-inference.v1",
            "recipe_digest": RECIPE,
            "state_digest": STATE,
            "inputs_digest": _sha(_tensors(inputs=rows)),
            "predictions_digest": _sha(predictions),
        }
    ).encode()
    run = {
        "schema": subset.RUN_SCHEMA,
        "execution_boundary": "C03_DOCKER",
        "recipe_digest": RECIPE,
        "state_digest": STATE,
        "inputs_digest": _sha(_tensors(inputs=rows)),
        "inference_image_id": IMAGE,
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
                "ledger_identity": "subset-repeat-" + "7" * 64,
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


def _side(n=10, positions=(2, 5, 8), **overrides):
    graded_inputs = np.arange(n * 3, dtype=np.float64).reshape(n, 3)
    answers = [_row(p) for p in positions]
    raw = subset.side_file(
        challenge=MOTOR,
        version="1.8",
        n_rows=n,
        positions=list(positions),
        run=_run(graded_inputs, list(positions), answers, **overrides),
    )
    return raw, graded_inputs, answers


def _read(raw, graded_inputs, n=10, **changes):
    arguments = {
        "registered_sha256": _sha(raw),
        "challenge": MOTOR,
        "version": "1.8",
        "graded_inputs": graded_inputs,
        "output_shape": [n, WIDTH],
        "recipe_digest": RECIPE,
        "state_digest": STATE,
        "inference_image_id": IMAGE,
        "graded_operation": GRADED_OP,
        **changes,
    }
    return subset.read(raw, **arguments)


def test_the_reader_returns_one_twin_per_row_and_none_elsewhere():
    raw, graded_inputs, answers = _side()
    twins = _read(raw, graded_inputs)
    assert len(twins) == 10
    assert [i for i, t in enumerate(twins) if t is not None] == [2, 5, 8]
    assert list(twins[5]) == answers[1]


@pytest.mark.parametrize(
    "changes",
    [
        {"recipe_digest": "sha256:" + "9" * 64},
        {"state_digest": "sha256:" + "9" * 64},
        {"inference_image_id": "sha256:" + "9" * 64},
        {"graded_operation": REPEAT_OP},
        {"challenge": "cooling-plate"},
        {"version": "1.5"},
        {"output_shape": [11, WIDTH]},
        {"registered_sha256": "sha256:" + "0" * 64},
    ],
)
def test_evidence_that_does_not_bind_the_graded_run_is_typed_unavailable(changes):
    raw, graded_inputs, _answers = _side()
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        _read(raw, graded_inputs, **changes)
    assert caught.value.code.startswith("subset_repeat")


def test_rows_other_than_the_drawn_ones_are_refused():
    raw, graded_inputs, _answers = _side()
    shifted = graded_inputs.copy()
    shifted[
        5, 0
    ] += 1.0  # the subset's inputs are no longer the graded query's rows at those positions
    with pytest.raises(subset.SubsetRepeatRefused):
        _read(raw, shifted)


@pytest.mark.parametrize(
    "overrides",
    [
        {"execution_boundary": "TEST_ONLY_LOCAL_RUNNER"},
        {"logical_prediction_rows": 4},
        {"schema": "carbon.source-free-inference-pair.v1"},
        {"official_eligible": True},
    ],
)
def test_a_broken_run_is_typed_unavailable(overrides):
    raw, graded_inputs, _answers = _side(**overrides)
    with pytest.raises(subset.SubsetRepeatRefused):
        _read(raw, graded_inputs)


def test_corrupt_or_foreign_bytes_are_typed_unavailable_never_a_verdict():
    raw, graded_inputs, _answers = _side()
    for bad in (b"", raw[:-5], raw.replace(b'"k":3', b'"k":2'), b"{}\n"):
        with pytest.raises(subset.SubsetRepeatRefused):
            _read(
                bad, graded_inputs, registered_sha256=_sha(bad) if bad else _sha(b"x")
            )
    # a full pair document in the slot is refused, as the pair reader refuses this one
    pair = json.dumps({"schema": "carbon.source-free-inference-pair.v1"}).encode()
    with pytest.raises(subset.SubsetRepeatRefused):
        _read(pair, graded_inputs, registered_sha256=_sha(pair))


def test_unsorted_repeated_or_outside_positions_are_refused():
    graded_inputs = np.arange(30, dtype=np.float64).reshape(10, 3)
    run = _run(graded_inputs, [2, 5, 8], [_row(p) for p in (2, 5, 8)])
    for positions in ([5, 2, 8], [2, 2, 8], [2, 5, 10], [2, 5]):
        raw = subset.side_file(
            challenge=MOTOR, version="1.8", n_rows=10, positions=positions, run=run
        )
        with pytest.raises(subset.SubsetRepeatRefused):
            _read(raw, graded_inputs)


# -- the producer successor (R-1, R-3) -----------------------------------------------------------------------------------


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


def test_the_successor_binds_only_on_an_exact_match(tmp_path):
    new = physical.producer_digest(_motor18())
    other = "sha256:" + "e" * 64
    assert producer_successor.binds(MOTOR, "1.8", OLD_MOTOR18, new)
    assert producer_successor.binds(MOTOR, "1.8", new, new)  # an exact pin needs no row
    assert not producer_successor.binds(MOTOR, "1.8", OLD_MOTOR18, other)
    assert not producer_successor.binds(MOTOR, "1.8", other, new)
    assert not producer_successor.binds(MOTOR, "1.5", OLD_MOTOR18, new)
    assert not producer_successor.binds(MOTOR, "1.8", None, new)
    for document in (
        "not json",
        {"schema": "other", "rows": {}},
        {
            "schema": producer_successor.SCHEMA,
            "rows": {f"{MOTOR} 1.8": {"pack_producer_digest": OLD_MOTOR18}},
        },
        {
            "schema": producer_successor.SCHEMA,
            "rows": {
                f"{MOTOR} 1.8": {
                    "pack_producer_digest": OLD_MOTOR18,
                    "producer_digest": "sha256:short",
                }
            },
        },
    ):
        path = tmp_path / "successor.json"
        path.write_text(
            document if type(document) is str else json.dumps(document),
            encoding="utf-8",
        )
        assert producer_successor.row(MOTOR, "1.8", path=path) is None
        assert not producer_successor.binds(MOTOR, "1.8", OLD_MOTOR18, new, path=path)


def _basis(producer):
    return {
        "schema": "carbon.scoring.dual-measurement-contract.v1",
        "producer_digest": producer,
        "accuracy_definition_sha256": "sha256:" + "a" * 64,
        "important_limit_definition_sha256": "sha256:" + "b" * 64,
        "design_objective_sha256": "sha256:" + "c" * 64,
    }


def _canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def test_new_evidence_carries_the_new_digest_and_old_evidence_still_reads(monkeypatch):
    from carbon.scoring import private_evaluation_source as source

    new = physical.producer_digest(_motor18())
    pinned_contract = _sha(_canonical(_basis(OLD_MOTOR18)))
    shared = {
        "schema": source.PAIRED_DUAL_MEASUREMENT_SCHEMA,
        "producer_digest": OLD_MOTOR18,
        "measurement_contract": _basis(OLD_MOTOR18),
        "measurement_contract_digest": pinned_contract,
        "inference_pair_sha256": "sha256:" + "d" * 64,
    }
    raw = source._canonical(shared)
    monkeypatch.setattr(
        subset_repeat_produce,
        "_resolve",
        lambda *a: (SimpleNamespace(), {}, ()),
    )
    monkeypatch.setattr(
        subset_repeat_produce,
        "produce",
        lambda adapter, **kw: ({"m": 1}, {"b": 1}, new, OLD_MOTOR18),
    )
    seen = {}

    def builder(**kwargs):
        seen.update(kwargs)
        return source.PreparedPrivateDualMeasurement(
            raw, _sha(raw), "sha256:p", {"m": 1}
        )

    monkeypatch.setattr(source, "build_dual_measurement_receipt", builder)
    prepared = subset_repeat_produce.produce_registered_dual_measurement(
        selected_pack=None,
        public_root=None,
        private_root=None,
        entry={"challenge": MOTOR, "challenge_version": "1.8"},
        trusted_job={},
        registration={},
        references=[],
        graph_originals={},
        evaluation_source_receipt_raw=b"",
        timing_step=0.0,
    )
    # the shared builder checked the pack under the digest the pack pins
    assert seen["producer_digest"] == OLD_MOTOR18
    body = json.loads(prepared.raw)
    assert body["producer_digest"] == new
    assert body["measurement_contract"]["producer_digest"] == new
    # the measurement contract named is still the pack's own pinned one
    assert body["measurement_contract_digest"] == pinned_contract
    assert prepared.sha256 == _sha(prepared.raw)
    # the reader's two paths: the new basis reads through the row, the old one directly
    through = producer_successor.pinned_basis(
        MOTOR, "1.8", body["measurement_contract"]
    )
    assert _sha(_canonical(through)) == pinned_contract
    assert _sha(_canonical(_basis(OLD_MOTOR18))) == pinned_contract
    assert producer_successor.pinned_basis(MOTOR, "1.8", _basis(OLD_MOTOR18)) is None
    assert (
        producer_successor.pinned_basis(MOTOR, "1.5", body["measurement_contract"])
        is None
    )


def test_the_evidence_reader_accepts_the_successor_basis_only():
    """`bind_private_evaluation_evidence`'s contract check, isolated: the source text names the successor path."""
    text = (ROOT / "carbon" / "scoring" / "private_evaluation_evidence.py").read_text(
        encoding="utf-8"
    )
    assert "producer_successor.pinned_basis(" in text
    assert 'source["challenge"], source["challenge_version"], basis' in text


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
    # the shared producer and its pair reader are untouched: Motor 1.8's own FILES carry the subset code
    files = _motor18().FILES
    for name in (
        "subset_repeat_evidence.py",
        "producer_successor.py",
        "subset_repeat_produce.py",
    ):
        assert name in files
        assert name not in physical._SHARED_FILES


# -- the door ------------------------------------------------------------------------------------------------------------


def _door(tmp_path, monkeypatch, plays, *, n=100, promise=None, key=KEY):
    """`_subset_repeat_raw` over a fake `infer_frozen_once` that plays ``plays`` in order."""
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
    if promise is not None:
        monkeypatch.setattr(subset, "VALUES_PATH", _promise_file(tmp_path, promise))
    snapshot = SimpleNamespace(
        manifest_digest="sha256:" + "a" * 64,
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

    def run():
        return retention._subset_repeat_raw(
            adapter,
            "rtsk_x",
            {},
            {"state.npz": b"s", "inputs.npz": _tensors(inputs=practice)},
            {"state_digest": "sd"},
        )

    return run, calls, practice


def test_the_door_runs_one_fresh_op_on_the_keyed_rows(tmp_path, monkeypatch):
    run, calls, practice = _door(tmp_path, monkeypatch, [{"fixture": True}])
    raw = run()
    assert len(calls) == 1  # ONE op, no pair
    document = json.loads(raw)
    expected = subset.draw(subset.grade_key(KEY, "rtsk_x"), 100, 66)
    assert document["positions"] == expected and document["k"] == 66
    assert np.array_equal(calls[0]["inputs"], practice[expected])
    assert calls[0]["expected_output_shape"] == (66, WIDTH)
    assert calls[0]["procedure"] == "per_case"
    assert document["run"] == {"fixture": True}
    assert (tmp_path / "subset-repeat-66.json").read_bytes() == raw
    # a retry reads the retained bytes back and runs nothing
    assert run() == raw and len(calls) == 1


def test_a_cached_file_of_another_draw_is_refused(tmp_path, monkeypatch):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, calls, _practice = _door(tmp_path, monkeypatch, [])
    (tmp_path / "subset-repeat-66.json").write_bytes(b'{"positions":[0,1]}')
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
    assert len(calls) == 2 and calls[0]["identity"] != calls[1]["identity"]

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
    "promise",
    [{"repeat_fail_fraction": None, "repeat_detect_prob": None}, {"k": 66}],
)
def test_no_promise_refuses_at_grade_time_before_any_op(tmp_path, monkeypatch, promise):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, calls, _practice = _door(tmp_path, monkeypatch, [], promise=promise)
    with pytest.raises(retention.RetentionUnavailable) as caught:
        run()
    assert str(caught.value) == "subset_repeat_promise_unregistered" and not calls


def test_no_key_refuses_at_grade_time(tmp_path, monkeypatch):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, calls, _practice = _door(tmp_path, monkeypatch, [], key=None)
    with pytest.raises(retention.RetentionUnavailable) as caught:
        run()
    assert str(caught.value) == "subset_repeat_key_unavailable" and not calls


def test_the_retention_runs_the_subset_repeat_and_never_the_pair_for_motor_18(
    tmp_path, monkeypatch
):
    """`_retain_selected_pack_evaluation` up to the repeat: Motor 1.8 calls `_subset_repeat_raw` once and
    `_inference_pair_raw` never; any other version the reverse."""
    from carbon.challenge_validator import exam_cap
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.scoring import dual_score

    class Cap:
        def __init__(self, *_a, **_k):
            pass

        def reserve(self, **_k):
            return "reservation"

        def settle(self, *_a, **_k):
            return None

    monkeypatch.setattr(exam_cap, "ExamCap", Cap)
    monkeypatch.setattr(exam_cap, "submission_block", lambda *a: None)
    monkeypatch.setattr(
        retention,
        "_register_retained_pack_source",
        lambda *a, **k: {"entry": {"state_digest": "sd"}},
    )
    seen = []

    def record(name):
        def call(*_a, **_k):
            seen.append(name)
            return b"repeat-evidence"

        return call

    def stop(*_a, **_k):
        raise retention.RetentionUnavailable("stopped_after_the_repeat")

    monkeypatch.setattr(retention, "_subset_repeat_raw", record("subset"))
    monkeypatch.setattr(retention, "_inference_pair_raw", record("pair"))
    monkeypatch.setattr(retention, "_single_call_raw", stop)
    snapshot = SimpleNamespace(
        manifest_digest="sha256:" + "a" * 64,
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
    for version, expected in (("1.8", ["subset"]), ("1.5", ["pair"])):
        seen.clear()
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
            {"evaluation_pack_digest": "sha256:" + "a" * 64},
            {
                "inputs.npz": b"q",
                "inference-receipt.json": b"r",
                "worker-evidence.json": b"w",
            },
        )
        assert seen == expected, version
        assert result["private_evaluation_reason"] == "stopped_after_the_repeat"


# -- the receiver's start-up check (R-5) ---------------------------------------------------------------------------------


def _pack(pinned):
    return SimpleNamespace(
        read_json_role=lambda root, side, role, max_bytes: {"producer_digest": pinned}
    )


def test_the_serve_check_names_the_successor_row_and_refuses_a_mismatch(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import lean_recipe_retention as retention

    assert retention.subset_repeat_serve_check(MOTOR, "1.5") is None
    named = retention.subset_repeat_serve_check(
        MOTOR, "1.8", pack_snapshot=_pack(OLD_MOTOR18), public_root=tmp_path
    )
    new = physical.producer_digest(_motor18())
    assert named["successor_row"] == {
        "pack_producer_digest": OLD_MOTOR18,
        "producer_digest": new,
    }
    assert named["producer_digest"] == new
    assert (named["repeat_fail_fraction"], named["repeat_detect_prob"]) == (0.10, 0.999)
    with pytest.raises(retention.RetentionUnavailable) as caught:
        retention.subset_repeat_serve_check(
            MOTOR,
            "1.8",
            pack_snapshot=_pack("sha256:" + "e" * 64),
            public_root=tmp_path,
        )
    assert str(caught.value) == "producer_successor_mismatch"
    monkeypatch.setattr(
        subset,
        "VALUES_PATH",
        _promise_file(
            tmp_path, {"repeat_fail_fraction": None, "repeat_detect_prob": 0.999}
        ),
    )
    with pytest.raises(retention.RetentionUnavailable) as caught:
        retention.subset_repeat_serve_check(MOTOR, "1.8")
    assert str(caught.value) == "subset_repeat_promise_unregistered"


def test_the_receiver_runs_the_serve_check_at_start():
    text = (ROOT / "carbon" / "challenge_validator" / "direct_receiver.py").read_text(
        encoding="utf-8"
    )
    serve = text[text.index("def serve(") :]
    check = serve.index("lean_recipe_retention.subset_repeat_serve_check(")
    assert serve.index("crown_hold.bind_pack(pack_digest)") < check
    assert check < serve.index("discovery = DirectFixtureDiscovery(")


# -- the public words (R-4) ----------------------------------------------------------------------------------------------

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
    assert set(words) == {"Sun 15 Nov 2026 08:19 CST", "Sun 15 Nov 2026 08:38 CST"}
    assert words["Sun 15 Nov 2026 08:38 CST"]["verbatim"] == (
        "66 rows. But we need a % that generalizes for challenges"
    )
    assert record["values"]["promise"] == {
        "repeat_fail_fraction": 0.10,
        "repeat_detect_prob": 0.999,
    }
    assert record["values"]["producer_successor"] == producer_successor.row(
        MOTOR, "1.8"
    )
