"""A two-batch POOL-GRADED pack set through the operator step, tests only (Test Engineer, 2026-10-30).

What this pins, and what it cannot: `grade_set_entry` and `psr.grade_set` are exercised with per-batch rows shaped
like a pool-graded version's (its mandatory gates carry `physics_pool` and `speed`), the set comparator with a
baseline per batch, the K_speed derivation across batches, and the two receiver facts that decide whether auto-grade
can serve a pack set. The grading core is stubbed exactly as in test_pack_set_grading: no worker, no sealed pack, no
solver runs, so it proves the set plumbing, not a real `measure_pool` grade under a set (that needs the worker image).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_pack_set_grading import (
    BATCHES,
    HOTKEY,
    _batch_adapters,
    _contents,
    _run,
    _stub_core,
    _world,
)
from test_regrade_retained_entry import _retained

from carbon.challenge_validator import pack_set_result as psr
from carbon.challenge_validator import sealed_exam_common as common
from carbon.development_session import single_call_timing

ROOT = Path(__file__).resolve().parents[2]
POOL_GATES = ("g1", "g2", "physics_pool", "speed")


def _pool_row(a, d, failed=()):
    ok = not failed
    return {
        "status": psr.SCORED if ok else psr.GATE_FAILED,
        "score": 0.5 * a + 0.5 * d if ok else None,
        "legs": {"A": a, "D": d},
        "gates": {g: ("FAIL" if g in failed else "PASS") for g in POOL_GATES},
    }


def _set_key():
    return common.pack_set_key(
        common.pack_set_document("electric-motor-magnetics", "1.0", _contents(BATCHES))
    )


def _grade(tmp_path, monkeypatch, rows):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        adapters = _batch_adapters(fixture, tmp_path, (0.5, 0.25))
        _stub_core(monkeypatch, rows)
        world = _world(tmp_path)
        key = _set_key()
        return _run(fixture, adapters, world, key), world, key
    finally:
        fixture.provider.close()


def test_a_pool_set_with_every_pool_gate_passing_is_scored_on_both_batches(
    tmp_path, monkeypatch
):
    result, (_cap, store), key = _grade(
        tmp_path,
        monkeypatch,
        {BATCHES[0]: _pool_row(0.8, 0.4), BATCHES[1]: _pool_row(0.6, 0.2)},
    )
    assert result["status"] == psr.SCORED and result["batches"] == 2
    assert set(result["graded"]["gates"]) == set(POOL_GATES)
    assert sorted(store.batch_rows(key, "rtsk_1")) == sorted(BATCHES)


@pytest.mark.parametrize("gate", ["physics_pool", "speed"])
def test_a_pool_gate_failing_on_one_batch_fails_the_set_with_no_exception(
    tmp_path, monkeypatch, gate
):
    """A model gated on one batch (a decision-refused row, or a slow single call) is gated for the set: D 0 on
    that batch, the set GATE_FAILED, both batch rows kept for audit, nothing raised."""
    result, (_cap, store), key = _grade(
        tmp_path,
        monkeypatch,
        {
            BATCHES[0]: _pool_row(0.8, 0.4),
            BATCHES[1]: _pool_row(0.0, 0.0, failed=(gate,)),
        },
    )
    assert result["status"] == psr.GATE_FAILED
    assert result["graded"]["gates"][gate] == "FAIL"
    assert sorted(store.batch_rows(key, "rtsk_1")) == sorted(BATCHES)


def test_a_batch_that_cannot_finish_its_pool_grade_gives_no_set_result(
    tmp_path, monkeypatch
):
    """E.g. the speed stage could not run on batch 2 (UNAVAILABLE, Carbon's gap): no partial set, slot returned."""
    result, (cap, store), key = _grade(
        tmp_path, monkeypatch, {BATCHES[0]: _pool_row(0.8, 0.4), BATCHES[1]: None}
    )
    assert result["state"] == psr.UNAVAILABLE
    assert store.result(key, "rtsk_1") is None
    assert (
        cap.count(hotkey=HOTKEY, challenge_id="electric-motor-magnetics", exam_key=key)
        == 0
    )


def test_k_speed_is_one_key_per_hotkey_and_pool_set_so_one_receiver_key_serves_every_batch_of_a_version():
    """K_speed = HMAC(copy key of the hotkey, pool set_digest). Both batches of one version carry the same pool set,
    so each batch's `.speed-key` beside its copy holds the same bytes and the receiver's single
    `speed_sample_key_file` is right for every batch. A batch with a DIFFERENT pool set would get another key, and
    nothing in the grade checks the configured key against the batch (it only needs >= 32 bytes).
    """
    copy_key = bytes(range(32))
    same_pool = "sha256:" + "a" * 64
    other_pool = "sha256:" + "b" * 64
    batch_one = single_call_timing.speed_key(copy_key, same_pool)
    batch_two = single_call_timing.speed_key(copy_key, same_pool)
    assert batch_one == batch_two and len(batch_one) == 32
    assert single_call_timing.speed_key(copy_key, other_pool) != batch_one
    assert single_call_timing.speed_key(bytes(range(1, 33)), same_pool) != batch_one
    # the timed rows differ per submission, never per batch key alone
    assert single_call_timing.sample_seed(
        batch_one, "rtsk_1"
    ) != single_call_timing.sample_seed(batch_one, "rtsk_2")


def test_every_batch_adapter_of_a_set_receives_the_receivers_one_speed_key():
    source = (ROOT / "carbon/challenge_validator/direct_receiver.py").read_text(
        encoding="utf-8"
    )
    start = source.index("def _set_batch_adapters(")
    body = source[start : source.index("\ndef _speed_key(", start)]
    assert body.count("LeanRecipeAdapter(") == 1
    assert "speed_sample_key=_speed_key(cfg)" in body
    assert 'for batch_digest in block["batches"]:' in body


def test_auto_grade_with_a_pack_set_is_refused_at_receiver_start():
    """Today a set receiver is graded by the operator step only (`--grade-set-entry`); the config is refused."""
    from carbon.challenge_validator import direct_receiver as dr

    source = (ROOT / "carbon/challenge_validator/direct_receiver.py").read_text(
        encoding="utf-8"
    )
    assert '"auto_grade" in value and "evaluation_pack_set" in value' in source
    assert "auto_grade_pack_set_unsupported" in source
    assert hasattr(dr, "ReceiverUnavailable")


def test_auto_grade_runs_retain_result_which_grades_the_primary_pack_alone():
    """The gap a set-aware auto-grade must close: AutoGrader.run_once retains AND grades each task on the primary
    pack (`intake.retain_result`), it never calls `pack_set_grading.grade_set_entry`."""
    source = (ROOT / "carbon/challenge_validator/auto_grade.py").read_text(
        encoding="utf-8"
    )
    assert "self.intake.retain_result(" in source
    assert "grade_set_entry" not in source and "pack_set" not in source


def test_the_set_comparator_needs_a_baseline_minimum_on_every_batch(tmp_path):
    from carbon.challenge_validator import koth_registry

    def pack(index, a, d):
        return {
            "pack_digest": "sha256:" + str(index) * 64,
            "legs": {"A": {"minimum": a}, "D": {"minimum": d}},
            "value_weight": 0.5,
            "combination": "weighted_arithmetic_mean",
        }

    path = tmp_path / "noise.json"
    path.write_text(json.dumps({"schema": koth_registry.SCHEMA, "challenges": {}}))
    both = koth_registry.comparator_for_set(
        "electric-motor-magnetics",
        [pack(1, 0.2, 0.4), pack(2, 0.4, 0.6)],
        [{}, {}],
        path=path,
    )
    assert both["baseline_total"] == pytest.approx(0.4)
    one_missing = koth_registry.comparator_for_set(
        "electric-motor-magnetics",
        [pack(1, 0.2, 0.4), pack(2, None, None)],
        [{}, {}],
        path=path,
    )
    assert one_missing["baseline_total"] is None
