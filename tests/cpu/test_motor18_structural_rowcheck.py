"""Motor 1.8's menu row check under vmap-64 is STRUCTURAL (owner "Yes and yes"; Lead trim change 3; CV-Motor-B's Y on
four conditions): no inference operation runs, the side file holds the RETAINED GRADED rows at the keyed positions
byte-equal, and a host-private basis record (STRUCTURAL_ISOLATED_VMAP64, never repeatability evidence) binds the
graded-inference digest. It fails closed unless the graded pass provably ran the isolated vmap path; every other
version still runs the real re-predict row check. Row independence itself is proven by the R1 code-path test and the
planted cross-row test in test_motor18_vmap64_row_isolation.py. Synthetic fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session import paired_inference
from carbon.development_session.bundle_construction_worker import _tensors

ROOT = Path(__file__).resolve().parents[2]
MOTOR = "electric-motor-magnetics"
N, WIDTH, SUBSET = 40, 6, 7
KEY = bytes(range(32))  # synthetic re-check key
RECORDED = "sha256:" + "1" * 64
VMAP = "fixture vmap-64 program"


@pytest.fixture(autouse=True)
def _vmap64_machinery_opted_in(monkeypatch):
    """Motor 1.8 is NOT a vmap-64 version since the owner's 116 rollback to A9 behaviour (Sun 15 Nov 2026; it grades
    with the per-case compiled program, tests/cpu/test_motor18_rollback_program.py). These tests exercise the dormant
    vmap-64 machinery with Motor 1.8 opted back in."""
    monkeypatch.setattr(
        worker,
        "VMAP64_INFERENCE_VERSIONS",
        frozenset({("electric-motor-magnetics", "1.8")}),
    )


def _graded():
    return [
        [0.1 * i + 0.003 * j + 1e-17 * i * j for j in range(WIDTH)] for i in range(N)
    ]


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """`_menu_rowcheck_raw` over a served menu version; ``run(version, **changes)``."""
    from carbon.challenge_validator import crown_hold
    from carbon.scoring import pool_menu, pool_version

    monkeypatch.setattr(crown_hold, "ACTIVE", True)
    monkeypatch.setattr(crown_hold, "menu_registered", lambda *a: True)
    monkeypatch.setattr(
        pool_version,
        "registered_menu",
        lambda *a: SimpleNamespace(rowcheck=(0.0, 0.0, SUBSET), epoch="E1"),
    )
    monkeypatch.setattr(pool_menu, "rowcheck_key", lambda: KEY)
    monkeypatch.setattr(
        retention, "_private_evaluation_directory", lambda r, s: tmp_path
    )
    monkeypatch.setattr(retention, "_inference_image_of", lambda *a: None)
    monkeypatch.setattr(retention, "_graded_inference_digest", lambda *a: RECORDED)
    monkeypatch.setattr(
        retention, "_graph_regrade_query", lambda *a, **k: {"program": VMAP}
    )
    monkeypatch.setattr(worker, "vmap64_infer_program", lambda *a: VMAP)
    monkeypatch.setattr(worker, "vmap64_state_lanes", lambda *a: 8)
    ops = []

    def fake_once(ledger, **call):
        ops.append(call)
        return SimpleNamespace(evidence={"fixture": True})

    # the re-check is ONE fresh operation (V2 R1 (a), 18 Nov 2026), never a pair
    monkeypatch.setattr(paired_inference, "infer_frozen_once", fake_once)
    monkeypatch.setattr(
        retention,
        "_menu_rowcheck_outputs",
        lambda evidence, entry, subset, shape, dtype, procedure, identities: [
            0.5 for _ in range(shape[0] * shape[1])
        ],
    )
    inputs = np.arange(N * 2, dtype=np.float64).reshape(N, 2)
    graded = _graded()

    def run(version="1.8", regrade="default", **material_changes):
        kit = {
            "id": MOTOR,
            "version": version,
            "train_digest": "t",
            "interface_digest": "i",
            "construction_limits_digest": "l",
        }
        material = {
            "construction_kit": kit,
            "construction_limits_document": {
                "reconstruction_resource_policy": {
                    "inference_wall_seconds_max": 60,
                    "total_reconstruction_wall_seconds_max": 120,
                }
            },
            "interface_document": {"dtype": "<f8"},
            "practice_inputs": inputs,
            "expected_output_shape": (N, WIDTH),
            "allowlist_bytes": b"",
            **material_changes,
        }
        snapshot = SimpleNamespace(
            manifest_digest="sha256:" + "a" * 64,
            read_json_role=lambda *a, **k: {"paired_repeat_procedure": "per_case"},
        )
        adapter = SimpleNamespace(
            owner=lambda sid: "owner",
            _provider=lambda owner: SimpleNamespace(ledger=object()),
            discovery=SimpleNamespace(
                _material=material,
                evaluation_pack_snapshot=snapshot,
                evaluation_pack_public_root=tmp_path,
            ),
        )
        if regrade == "default":
            regrade = SimpleNamespace(
                owner="owner", recipe={}, graded_inference_sha256=RECORDED
            )
        artifacts = {
            "inputs.npz": _tensors(inputs=inputs),
            "state.npz": b"s",
            "predictions.json": json.dumps(graded).encode(),
        }
        return retention._menu_rowcheck_raw(
            adapter, "rtsk_x", {}, artifacts, {"state_digest": "sd"}, regrade
        )

    return SimpleNamespace(run=run, ops=ops, graded=graded, path=tmp_path)


def _plan():
    from carbon.scoring import pool_menu

    return pool_menu.rowcheck_plan(N, SUBSET, KEY, epoch="E1")


def test_motor_18_row_check_runs_no_op_and_holds_the_graded_rows_byte_equal(harness):
    from carbon.scoring import pool_menu

    side = harness.run()
    assert harness.ops == []  # ZERO inference operations
    read = pool_menu.read_rowcheck_side_file(side)
    positions = _plan()
    assert read["positions"] == positions  # the keyed plan, unchanged
    expected = [[float(v) for v in harness.graded[p]] for p in positions]
    assert read["outputs"] == expected
    assert np.asarray(read["outputs"]).tobytes() == np.asarray(expected).tobytes()
    # the basis record beside it: the rows are the graded ones, bound to the graded inference; never repeatability
    (basis_path,) = harness.path.glob("menu-rowcheck-basis-*.json")
    basis = json.loads(basis_path.read_text(encoding="utf-8"))
    assert basis["schema"] == retention.ROWCHECK_BASIS_SCHEMA
    assert basis["basis"] == "STRUCTURAL_ISOLATED_VMAP64"
    assert basis["graded_inference_sha256"] == RECORDED
    assert basis["side_file_sha256"] == retention._sha(side)
    assert basis["repeatability_evidence"] is False and basis["lanes"] == 8
    assert basis["proof_tests"] == list(retention.ROWCHECK_PROOF_TESTS)
    for test in basis["proof_tests"]:
        path, name = test.split("::")
        assert f"def {name}(" in (ROOT / path).read_text(encoding="utf-8")
    # the D the measure reads: the row check equals the graded rows, so no row differs
    graded_by_position = {p: harness.graded[p] for p in positions}
    assert all(
        read["outputs"][i] == [float(v) for v in graded_by_position[p]]
        for i, p in enumerate(positions)
    )


@pytest.mark.parametrize(
    "patch, code",
    [
        (("_graded_inference_digest", lambda *a: "sha256:" + "9" * 64), "unproven"),
        (("_graph_regrade_query", lambda *a, **k: {"program": "eager"}), "unproven"),
        (("lanes", 0), "unproven"),
        (("lanes", 65), "unproven"),
        (("lanes", RuntimeError("unknown L")), "unproven"),
    ],
)
def test_an_unproven_vmap_path_refuses_typed_and_runs_nothing(
    harness, monkeypatch, patch, code
):
    name, value = patch
    if name == "lanes":
        if isinstance(value, Exception):

            def lanes(*a):
                raise value

        else:

            def lanes(*a):
                return value

        monkeypatch.setattr(worker, "vmap64_state_lanes", lanes)
    else:
        monkeypatch.setattr(retention, name, value)
    with pytest.raises(retention.RetentionUnavailable) as caught:
        harness.run()
    assert str(caught.value) == retention.ROWCHECK_STRUCTURAL_UNPROVEN
    assert harness.ops == [] and not list(harness.path.glob("menu-rowcheck*"))


@pytest.mark.parametrize(
    "regrade",
    [None, SimpleNamespace(owner="owner", recipe={}, graded_inference_sha256=None)],
)
def test_a_grade_without_a_recorded_graded_inference_refuses(harness, regrade):
    with pytest.raises(retention.RetentionUnavailable) as caught:
        harness.run(regrade=regrade)
    assert str(caught.value) == retention.VMAP64_NEEDS_SEALED_PACK
    assert harness.ops == []


@pytest.mark.parametrize("version", ["1.7", "1.5"])
def test_every_other_version_still_runs_the_real_re_predict_row_check(harness, version):
    from carbon.scoring import pool_menu

    side = harness.run(version=version)
    assert len(harness.ops) == 1  # the real fresh-instance re-check (its one op)
    assert harness.ops[0]["expected_output_shape"] == (SUBSET, WIDTH)
    read = pool_menu.read_rowcheck_side_file(side)
    assert (
        read["outputs"] == [[0.5] * WIDTH] * SUBSET
    )  # the fresh run's answers, not the graded rows
    assert not list(harness.path.glob("menu-rowcheck-basis-*.json"))


def test_no_version_is_structural_after_the_rollback(monkeypatch):
    """Under the owner's 116 rollback to A9 behaviour no version grades vmap-64, so no row check is structural."""
    monkeypatch.undo()
    assert worker.VMAP64_INFERENCE_VERSIONS == frozenset()


def test_no_record_cites_the_row_check_as_repeatability_evidence():
    """CV-Motor-B condition 4: the vmap-64 row check is never repeatability evidence wherever it is described."""
    text = (
        ROOT / "carbon/development_session/direct_graph_construction_worker.py"
    ).read_text(encoding="utf-8")
    assert (
        "the menu row check and the subset repeat over the ORIGINAL chunks" not in text
    )
    assert "never repeatability evidence" in text
    record = (ROOT / "docs/records/2026-11-15-motor18-subset-repeat.json").read_text(
        encoding="utf-8"
    )
    assert "STRUCTURAL_ISOLATED_VMAP64" in record
