"""The measured (-timed) query of a static-batch bundle graph runs on its first
declared-batch rows (Validator ruling (b), 2026-10-26).

Cooling 1.4's practice query is larger than the graph's declared batch, which
the frozen fixed inference program refuses whole (`input_aval_mismatch`). The
inference program is not changed: the host times the first `len(example)`
designs and the speed result says "measured on the first N designs".
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from carbon.development_session import bundle_construction_worker as worker
from carbon.scoring import practice_speed

POLICY = {
    "reconstruction_resource_policy": {
        "total_reconstruction_wall_seconds_max": 3000,
        "build_wall_seconds_max": 600,
        "inference_wall_seconds_max": 600,
    }
}


def _run(monkeypatch, *, rows, batch):
    calls = []
    built = SimpleNamespace(state_digest="sha256:" + "1" * 64)

    def infer(*args, **kwargs):
        calls.append(
            (
                kwargs["identity"],
                kwargs["inputs"].shape,
                tuple(kwargs["expected_output_shape"]),
                kwargs.get("measure_query", False),
            )
        )
        return built

    monkeypatch.setattr(worker, "_checked_binding", lambda recipe, binding: binding)
    monkeypatch.setattr(
        worker, "_trusted_allowlist", lambda raw: SimpleNamespace(version="v")
    )
    monkeypatch.setattr(worker, "worker_resources_version", lambda version: None)
    monkeypatch.setattr(
        worker, "verify_direct_resource_policy", lambda *a, **k: "sha256:" + "2" * 64
    )
    monkeypatch.setattr(worker, "reconstruct_public", lambda *a, **k: built)
    monkeypatch.setattr(worker, "infer_public", infer)
    monkeypatch.setattr(worker, "compare_build_inference_predictions", lambda *a, **k: None)
    worker.reconstruct_and_infer_public(
        None,
        owner="o",
        identity="t",
        image=None,
        inference_image=None,
        recipe=None,
        challenge_binding={},
        limits_document=POLICY,
        train=b"",
        example=np.zeros((batch, 2), dtype=np.float32),
        seed=0,
        inputs=np.zeros((rows, 2), dtype=np.float32),
        expected_output_shape=(rows, 3),
        allowlist_bytes=b"",
        measure_query=True,
        timing_optional=True,
        runner=lambda *a, **k: None,
    )
    return calls


def test_a_query_larger_than_the_declared_batch_is_timed_on_its_first_rows(
    monkeypatch,
):
    calls = _run(monkeypatch, rows=264, batch=132)
    graded = [c for c in calls if not c[3]]
    timed = [c for c in calls if c[3]]
    # The graded (per-case) inference still answers every design.
    assert [c[1:3] for c in graded] == [((264, 2), (264, 3))]
    assert [c[1:3] for c in timed] == [((132, 2), (132, 3))]


@pytest.mark.parametrize("rows,batch", [(5, 5), (3, 5)])
def test_a_query_that_fits_the_batch_is_timed_whole(monkeypatch, rows, batch):
    calls = _run(monkeypatch, rows=rows, batch=batch)
    assert [c[1:3] for c in calls if c[3]] == [((rows, 2), (rows, 3))]


def _receipt(rows):
    return {
        "measurement": {
            "timing_s": {"preprocess": 0.1, "inference": 0.3, "postprocess": 0.1},
            "input_shape": [rows, 2],
        }
    }


def test_the_speed_result_says_it_was_measured_on_the_first_designs():
    block = practice_speed.from_receipt("cooling", _receipt(132), designs=264)
    assert block["designs"] == 132 and block["designs_total"] == 264
    assert block["seconds_per_design"] == pytest.approx(0.5 / 132)
    assert block["label"].startswith("measured on the first 132 designs;")
    assert "first 132 practice designs" in block["scope"]


def test_a_whole_query_keeps_the_speed_result_as_before():
    block = practice_speed.from_receipt("cooling", _receipt(264), designs=264)
    assert block["designs"] == 264 and "designs_total" not in block
    assert block["label"] == practice_speed.LABEL
    assert block["scope"].endswith("over all practice designs")
