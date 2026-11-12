"""The repeat pair's byte bound at Motor 1.8's size (CV-Motor-C, Thu 12 Nov 17:24 SEAL-PATH FINDING): 2564 rows of a
240-wide row overflow the shared reader's fixed 4 MiB, so every 1.8 grade would refuse. Inert Platform-shaped records
(`test_inference_pair_evidence`'s fixture at a larger shape); no worker, model or scientific gate.
"""

from __future__ import annotations

import importlib
import json
import random
import sys
import threading
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_inference_pair_evidence import (
    change_predictions,
    change_receipt,
    encode,
    fixture,
    sha,
)

from carbon.scoring import inference_pair_evidence as reader
from carbon.scoring import pair_read_bound as bound

#: Motor 1.8's bank (Lead, Thu 12 Nov: 2564 rows, 4x 1.5's) and its row (`carbon.motor.row18.WIDTH`)
ROWS, WIDTH = 2564, 240
FIXED = 4 * 1024**2
#: the longest float64 json.dumps writes
WORST = -2.2250738585072014e-308


def big_pair(rows, width, value):
    packet, kwargs = fixture()
    expected = kwargs["expected"]
    expected["input_shape"] = [rows, 2]
    expected["output_shape"] = [rows, width]
    for name in ("primary", "repeat"):
        raw = json.dumps(
            [[value() for _ in range(width)] for _ in range(rows)]
        ).encode()
        change_predictions(packet[name], raw)
        change_receipt(
            packet[name],
            lambda r: r["measurement"].update(
                input_shape=[rows, 2], output_shape=[rows, width]
            ),
        )
    packet["logical_prediction_rows_per_operation"] = rows
    packet["logical_prediction_row_attempts"] = 2 * rows
    raw = encode(packet)
    return raw, kwargs


@pytest.fixture(scope="module")
def motor18_pair():
    rng = random.Random(18)
    return big_pair(ROWS, WIDTH, lambda: rng.uniform(-1.0, 1.0))


def test_the_fixed_ceiling_refuses_a_motor_1_8_pair_and_the_sized_one_reads_it(
    motor18_pair,
):
    raw, kwargs = motor18_pair
    assert reader._MAX_BYTES == FIXED
    assert (
        len(raw) > FIXED
    )  # the finding: every 1.8 grade's pair is over the shared ceiling
    with pytest.raises(reader.PairEvidenceRefused) as refused:
        reader.read_inference_pair(raw, registered_sha256=sha(raw), **kwargs)
    assert refused.value.code == "pair_bytes"
    with bound.raised(bound.pair_bytes(ROWS, WIDTH)) as ceiling:
        assert ceiling == bound.pair_bytes(ROWS, WIDTH) > len(raw)
        read = reader.read_inference_pair(raw, registered_sha256=sha(raw), **kwargs)
    assert [len(o) for o in read.outputs] == [ROWS * WIDTH, ROWS * WIDTH]
    assert reader._MAX_BYTES == FIXED  # restored


def test_the_bound_holds_for_the_longest_float_json_writes():
    """An upper bound, not an estimate: every value at its longest repr still fits (a smaller shape, same per-value
    arithmetic)."""
    rows, width = 300, WIDTH
    raw, kwargs = big_pair(rows, width, lambda: WORST)
    assert len(raw) <= bound.pair_bytes(rows, width)
    with bound.raised(bound.pair_bytes(rows, width)):
        read = reader.read_inference_pair(raw, registered_sha256=sha(raw), **kwargs)
    assert len(read.outputs[0]) == rows * width


def test_the_ceiling_is_restored_when_the_read_fails_and_never_lowered():
    with pytest.raises(RuntimeError):
        with bound.raised(bound.pair_bytes(ROWS, WIDTH)):
            raise RuntimeError("grade failed")
    assert reader._MAX_BYTES == FIXED
    with bound.raised(1) as ceiling:
        assert ceiling == FIXED  # a smaller bound never lowers the reader's own ceiling
    for shape in ((0, 1), (1, 0), (1.0, 2), (2, None)):
        with pytest.raises(ValueError):
            bound.pair_bytes(*shape)
    with pytest.raises(ValueError):
        with bound.raised(0):
            pass


def test_every_live_size_keeps_the_retention_read_cap_unchanged():
    """Motor 1.5's 646 x 60 pair (~1.9 MB measured, valV3 28 Oct) bounds below the retention's 8 MiB: its cap stays."""
    from carbon.challenge_validator import lean_recipe_retention as retention

    assert bound.pair_bytes(646, 60) < retention.PAIR_READ_BYTES
    assert bound.pair_bytes(ROWS, WIDTH) > retention.PAIR_READ_BYTES


def test_no_other_grade_reads_while_a_sized_ceiling_is_up():
    inside, release = threading.Event(), threading.Event()

    def sized():
        with bound.raised(bound.pair_bytes(ROWS, WIDTH)):
            inside.set()
            release.wait(10)

    worker = threading.Thread(target=sized)
    worker.start()
    try:
        assert inside.wait(10)
        assert not bound._LOCK.acquire(
            timeout=0.2
        )  # `held` (every other produce) waits
    finally:
        release.set()
        worker.join(10)
    assert bound._LOCK.acquire(timeout=1)
    bound._LOCK.release()
    assert reader._MAX_BYTES == FIXED


class _Adapter:
    def __init__(self, challenge, version):
        self.CHALLENGE, self.VERSION = challenge, version


def test_size_produce_sizes_only_its_own_version_and_wraps_once(monkeypatch):
    from carbon.scoring import physical_dual_pack as physical

    seen = []

    def original(adapter, **kwargs):
        seen.append(reader._MAX_BYTES)
        return adapter.VERSION

    monkeypatch.setattr(physical, "produce", original)
    monkeypatch.setattr(bound, "_SIZED", set())
    bound.size_produce("electric-motor-magnetics", "1.8")
    wrapped = physical.produce
    bound.size_produce("electric-motor-magnetics", "1.8")
    assert physical.produce is wrapped and wrapped.pair_read_bound is True
    bank = {"case_ids": list(range(ROWS)), "references": [[0.0] * WIDTH]}
    assert (
        physical.produce(_Adapter("electric-motor-magnetics", "1.8"), bank=bank)
        == "1.8"
    )
    assert (
        physical.produce(_Adapter("electric-motor-magnetics", "1.6"), bank=bank)
        == "1.6"
    )
    assert physical.produce(_Adapter("chip-cold-plate", "1.8"), bank=bank) == "1.8"
    # an unreadable bank shape passes through unchanged (the producer refuses it its own way)
    assert (
        physical.produce(_Adapter("electric-motor-magnetics", "1.8"), bank={}) == "1.8"
    )
    assert seen == [bound.pair_bytes(ROWS, WIDTH), FIXED, FIXED, FIXED]
    assert reader._MAX_BYTES == FIXED


def test_the_motor_1_8_overlay_arms_the_sized_produce_inside_its_own_producer_identity():
    importlib.import_module("carbon.challenge_kit.version_registry")
    importlib.import_module("carbon.scoring.motor_sealed_dual_pack")
    from carbon.scoring import motor18_dual_pack, motor_sealed_dual_pack
    from carbon.scoring import physical_dual_pack as physical

    assert getattr(physical.produce, "pair_read_bound", False) is True
    assert ("electric-motor-magnetics", "1.8") in bound._SIZED
    # the bound is in 1.8's OWN producer files, never a shared or a live version's
    assert motor18_dual_pack.FILES[-1] == "pair_read_bound.py"
    assert "pair_read_bound.py" not in physical._SHARED_FILES
    assert "pair_read_bound.py" not in motor_sealed_dual_pack.FILES
