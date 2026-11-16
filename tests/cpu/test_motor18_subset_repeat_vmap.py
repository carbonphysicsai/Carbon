"""Motor 1.8's subset repeat on the REAL vmap-64 program: the fresh process re-runs the ORIGINAL chunks holding every
drawn row (the sealed cells and each stratum's keyed rows) at the model's own lane count, and the scorer reads each
drawn row's answer from that run bit for bit equal to the graded pass. The programs really run (subprocesses) over a
real codec state with synthetic seeded parameters (`test_motor18_compiled_forward`'s fixture); the strata and promise
are synthetic, the side file's boundary and controls are the only test-set fields (a local runner has neither).
"""

# ruff: noqa: F811 (the imported fixture is received by tests)
from __future__ import annotations

import json
import os

import numpy as np
import pytest
from test_motor18_compiled_forward import (
    MOTOR_18,
    ROWS,
    _contract,
    _pair,
    _rows,
    motor18,  # noqa: F401
)

from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session import paired_inference
from carbon.scoring import subset_repeat_evidence as subset
from carbon.scoring import subset_repeat_produce

posix = pytest.mark.skipif(os.name != "posix", reason="fixed program subprocesses")
MOTOR = MOTOR_18[0]
GRID, POOL = "decision_sealed_grid", "pool_design"
PACK = "sha256:" + "4" * 64
SID = "rtsk_vmap"
KEY = bytes(range(32))  # synthetic K_speed
COHORTS = [POOL] * 40 + [GRID] * 30 + [POOL] * (ROWS - 70)


@pytest.fixture(autouse=True)
def _vmap64_machinery_opted_in(monkeypatch):
    """Motor 1.8 is NOT a vmap-64 version since the owner's 116 rollback to A9 behaviour (Sun 15 Nov 2026; it grades
    with the per-case compiled program, tests/cpu/test_motor18_rollback_program.py). These tests exercise the dormant
    vmap-64 machinery with Motor 1.8 opted back in."""
    from carbon.development_session import direct_graph_construction_worker

    monkeypatch.setattr(
        direct_graph_construction_worker,
        "VMAP64_INFERENCE_VERSIONS",
        frozenset({("electric-motor-magnetics", "1.8")}),
    )


@pytest.fixture
def strata(tmp_path, monkeypatch):
    """One synthetic keyed stratum (the pool cohort) with the owner's f and P: k = 66 of its 120 rows."""
    path = tmp_path / "subset_repeat.json"
    path.write_text(
        json.dumps(
            {
                "schema": subset.VALUES_SCHEMA,
                "rows": {
                    f"{MOTOR} 1.8": {
                        "repeat_fail_fraction": 0.10,
                        "repeat_detect_prob": 0.999,
                        "strata": [POOL],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(subset, "VALUES_PATH", path)
    monkeypatch.setattr(
        subset, "STRATA", {(MOTOR, "1.8"): {POOL: subset.Stratum("cohort", POOL)}}
    )
    bank = {"cohorts": COHORTS, "inputs": [[float(i)] for i in range(ROWS)]}
    return subset.bank_strata(MOTOR, "1.8", bank)


@posix
def test_the_subset_repeat_reruns_the_original_chunks_bit_exact(
    motor18, strata, tmp_path
):
    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _image, _runner

    _contract(motor18)
    rows = _rows(motor18)
    doc, members = motor18["loaded"][:2]
    lanes = worker.vmap64_model_lanes(*MOTOR_18, doc, len(members))
    sealed, keyed = subset.plan(KEY, SID, challenge=MOTOR, version="1.8", strata=strata)
    assert sealed == list(range(40, 70)) and len(keyed[POOL]) == 66
    positions = subset.positions_of(sealed, keyed)
    queried, _where = subset.rerun_rows(MOTOR, "1.8", positions, ROWS, lanes)
    assert queried == worker.vmap64_rerun_rows(positions, ROWS, lanes)[0]
    ledger, seen = FixtureLedger(tmp_path), []
    run = _runner(ledger, seen)
    try:
        graded, _repeat = _pair(motor18, ledger, run, "vmap64-graded", rows)
        once = paired_inference.infer_frozen_once(
            ledger,
            owner="fixture-owner",
            identity=subset.run_identity(PACK, SID),
            inference_image=_image(),
            recipe=motor18["recipe"],
            challenge_binding=motor18["binding"],
            limits_document=motor18["material"]["construction_limits_document"],
            state_bytes=motor18["state"],
            expected_state_digest=paired_inference._digest(motor18["state"]),
            inputs=np.ascontiguousarray(rows[queried]),
            expected_output_shape=(len(queried), motor18["width"]),
            expected_output_dtype=motor18["dtype"],
            allowlist_bytes=motor18["material"]["allowlist_bytes"],
            seconds=motor18["policy"]["inference_wall_seconds_max"],
            total_seconds=motor18["policy"]["total_reconstruction_wall_seconds_max"],
            procedure="per_case",
            runner=run,
        ).evidence
    finally:
        ledger.connection.close()
    # ONE fresh process, running the vmap-64 program (never single rows per case)
    assert len(seen) == 3
    assert "lane_forward = jax.jit(jax.vmap(" in seen[-1]["source"]
    # (a local runner has no C-03 boundary, settled controls or full carrier worker result: the only test-set fields;
    # the operation, files and their digests stay the run's own)
    phase = once["repeat"]
    worker_result = {
        "operation": phase["worker_operation"],
        "files": {
            name: original["sha256"] for name, original in phase["originals"].items()
        },
        "schema": "carbon.autoresearch.worker-result.v1",
        "provenance": "DIRECT_GRAPH_PUBLIC_INFERENCE",
        "output_digest": "sha256:" + "8" * 64,
        "scientific_qualification": False,
        "official_eligible": False,
    }
    run_evidence = {
        **once,
        "execution_boundary": "C03_DOCKER",
        "repeat": {
            **phase,
            "controls_digest": "sha256:" + "6" * 64,
            "accounting": {**phase["accounting"], "worker_result": worker_result},
        },
    }
    raw = subset.side_file(
        challenge=MOTOR,
        version="1.8",
        evaluation_pack_digest=PACK,
        submission_id=SID,
        n_rows=ROWS,
        sealed=sealed,
        keyed=keyed,
        lanes=lanes,
        run=run_evidence,
    )
    twins = subset.read(
        raw,
        registered_sha256=subset._sha(raw),
        challenge=MOTOR,
        version="1.8",
        evaluation_pack_digest=PACK,
        strata=strata,
        graded_inputs=rows,
        output_shape=[ROWS, motor18["width"]],
        recipe_digest=motor18["recipe"].digest,
        state_digest=paired_inference._digest(motor18["state"]),
        inference_image_id=_image().image_id,
        graded_operation="operation-" + "a" * 64,
    )
    outputs = [[float(v) for v in row] for row in graded]
    assert [i for i, t in enumerate(twins) if t is not None] == positions
    # every drawn row, the whole row, bit for bit: the subset gate holds
    for position in positions:
        assert np.asarray(twins[position]).tobytes() == graded[position].tobytes()
    assert subset_repeat_produce.repeat_holds(outputs, twins)
    # and one ulp anywhere in one drawn row's graded answer fails it
    position = positions[len(positions) // 2]
    outputs[position][-1] = float(np.nextafter(outputs[position][-1], np.inf))
    assert not subset_repeat_produce.repeat_holds(outputs, twins)
