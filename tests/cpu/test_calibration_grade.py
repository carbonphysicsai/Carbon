"""The calibration-grade tool: artifact verification, registered output controls
(each moves only its own leg), aggregates only, and no official-store writes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest

from carbon.challenge_validator import calibration_grade as cg
from carbon.scoring import dual_score as dual
from carbon.scoring import probe_design
from carbon.scoring.physical_dual_pack import METRICS
from tests.cpu.test_dual_score import fixture as dual_fixture

BOUNDS = [(0.0, 10.0), (100.0, 200.0), (-5.0, 5.0)]


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _artifact(root, **changes):
    recipe, state = b'{"recipe":1}', b"state-bytes"
    manifest = {
        "schema": cg.ARTIFACT_SCHEMA,
        "challenge_id": "f02",
        "version": "2.3",
        "recipe_digest": "sha256:" + _sha(recipe),
        "state_sha256": "sha256:" + _sha(state),
        "bundle_ref": "catalog/x",
        "bundle_sha256": "sha256:" + "b" * 64,
        "worker_image_digest": "sha256:" + "c" * 64,
        "parent_image_digest": "sha256:" + "d" * 64,
        "runtime": "torch-cu130-py311",
        "gpu_model": "gpu",
        "driver": "d",
        "cuda": "13",
        "train_sha256": "sha256:" + "e" * 64,
        "seed": 0,
        "build_wall_s": 1.0,
        "pod_id": "pod",
        "built_at": "2026-10-23T00:00:00Z",
        **changes,
    }
    files = {
        "recipe.json": recipe,
        "state.npz": state,
        "manifest.json": json.dumps(manifest).encode(),
    }
    directory = Path(root) / "artifact"
    directory.mkdir()
    for name, raw in files.items():
        (directory / name).write_bytes(raw)
    (directory / "SHA256SUMS").write_text(
        "".join(f"{_sha(raw)}  {name}\n" for name, raw in files.items())
    )
    return directory


def test_a_verified_artifact_loads_and_names_a_calibration_entry(tmp_path):
    artifact = cg.load_artifact(
        _artifact(tmp_path),
        challenge_id="f02",
        worker_image_digest="sha256:" + "c" * 64,
    )
    assert artifact.calibration_entry_id.startswith("sha256:")
    assert artifact.recipe_digest == artifact.manifest["recipe_digest"]


@pytest.mark.parametrize(
    "pin,code",
    [
        ({"challenge_id": "motor"}, "calibration_challenge"),
        ({"recipe_digest": "sha256:" + "0" * 64}, "calibration_pin_recipe"),
        ({"state_sha256": "sha256:" + "0" * 64}, "calibration_pin_state"),
        ({"bundle_sha256": "sha256:" + "0" * 64}, "calibration_pin_bundle"),
        ({"worker_image_digest": "sha256:" + "0" * 64}, "calibration_pin_image"),
        ({"train_sha256": "sha256:" + "0" * 64}, "calibration_pin_train"),
    ],
)
def test_a_mismatched_pin_refuses(tmp_path, pin, code):
    with pytest.raises(cg.CalibrationRefused) as info:
        cg.load_artifact(_artifact(tmp_path), **pin)
    assert info.value.code == code


def test_a_tampered_file_refuses(tmp_path):
    directory = _artifact(tmp_path)
    (directory / "state.npz").write_bytes(b"other")
    with pytest.raises(cg.CalibrationRefused) as info:
        cg.load_artifact(directory)
    assert info.value.code == "calibration_sums_differ"


def test_a_manifest_naming_another_recipe_refuses(tmp_path):
    with pytest.raises(cg.CalibrationRefused) as info:
        cg.load_artifact(_artifact(tmp_path, recipe_digest="sha256:" + "0" * 64))
    assert info.value.code == "calibration_recipe_digest"


def _bank(n=8, bases=4):
    inputs = np.array(
        [[1.0 + i, 120.0 + 5 * i, -2.0 + 0.5 * i] for i in range(n)], dtype="<f8"
    )
    bank = {
        "case_ids": tuple(f"c{i}" for i in range(n)),
        "cohorts": ("cell",) * n,
        "inputs": inputs,
        "references": np.ones((n, 32), dtype="<f8"),
        "reference_records": [{"status": "OK", "design_id": f"d{i}"} for i in range(n)],
    }
    cases = [dict(enumerate(map(float, row))) for row in inputs]
    return probe_design.with_probes(
        bank,
        cases,
        challenge="test",
        bounds=BOUNDS,
        valid=lambda x: True,
        bases=bases,
        dtype="<f8",
        extra=(
            ("affine_up", lambda x: [x[0] + 0.1, x[1], x[2]]),
            ("j_up", lambda x: [x[0], x[1], x[2]]),
            ("inlet_shift", lambda x: [x[0], x[1], x[2]]),
        ),
    )


def _rows(bank):
    rng = np.random.default_rng(0)
    return [
        list(map(float, r)) for r in rng.uniform(1.0, 2.0, (len(bank["inputs"]), 32))
    ]


def _changed(before, after):
    return {i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b}


def _probe(record):
    return record.get("probe", {})


def _kinds(bank, prefix):
    return {
        i
        for i, c in enumerate(bank["reference_records"])
        if _probe(c).get("kind", "response").startswith(prefix) and "probe" in c
    }


def test_invert_response_moves_only_response_probe_rows():
    bank = _bank()
    rows = _rows(bank)
    out = cg.apply_control({"name": "ctrl.invert_response"}, rows, bank, "f02")
    dims = {
        i
        for i, c in enumerate(bank["reference_records"])
        if _probe(c).get("dim") is not None
    }
    assert _changed(rows, out) == dims
    indexed = [
        (i, c["probe"]) for i, c in enumerate(bank["reference_records"]) if "probe" in c
    ]
    for g in probe_design.groups(indexed):
        base = rows[g["base"]]
        for plus, _ in g["dims"].values():
            assert out[plus][0] - base[0] == pytest.approx(base[0] - rows[plus][0])


@pytest.mark.parametrize(
    "name,challenge,params,law",
    [
        ("ctrl.nonaffine_power", "f02", {"shift": 0.5}, "law:affine_up"),
        ("ctrl.nonlinear_current", "motor", {"factor": 1.3}, "law:j_up"),
        ("ctrl.inlet_shift_broken", "cooling", {"shift": 2.0}, "law:inlet_shift"),
    ],
)
def test_each_law_control_moves_only_its_law_rows(name, challenge, params, law):
    bank = _bank()
    rows = _rows(bank)
    out = cg.apply_control({"name": name, "params": params}, rows, bank, challenge)
    assert _changed(rows, out) == _kinds(bank, law)


def test_controls_are_registered_challenge_bound_and_parameterised():
    bank = _bank()
    rows = _rows(bank)
    for control, challenge, code in (
        ({"name": "ctrl.nope"}, "f02", "control_unregistered"),
        (
            {"name": "ctrl.nonaffine_power", "params": {"shift": 1}},
            "f08",
            "control_challenge:ctrl.nonaffine_power",
        ),
        (
            {"name": "ctrl.nonlinear_current"},
            "motor",
            "control_params:ctrl.nonlinear_current",
        ),
    ):
        with pytest.raises(cg.CalibrationRefused) as info:
            cg.apply_control(control, rows, bank, challenge)
        assert info.value.code == code


def test_pick_wrong_margins_uses_the_reference_not_the_predictions():
    bank = _bank()
    rows = _rows(bank)
    out = cg.apply_control(
        {"name": "ctrl.pick_wrong_margins", "params": {"errors": {"0": 0.25}}},
        rows,
        bank,
        "f02",
    )
    cells = [i for i, p in enumerate(bank["reference_present"]) if p]
    probes = [i for i, p in enumerate(bank["reference_present"]) if not p]
    assert {out[i][1] for i in cells} == {1.0} and len(out[0]) == 32
    assert {abs(out[i][0] - 1.0) for i in cells} == {0.25}
    assert all(out[i] == rows[i] for i in probes)


class _Adapter:
    CHALLENGE = "toy-dual-only"

    class Refused(Exception):
        def __init__(self, code):
            self.code = code

    calls: ClassVar[list] = []

    @classmethod
    def measure(cls, **kw):
        cls.calls.append(kw)
        first = [r[0] for r in kw["outputs"]]
        return {
            "A": 1.0 / (1.0 + abs(float(np.mean(first)) - 1.0)),
            "D": 0.5,
            "A_legs": {"A_acc": 0.9, "A_law": 0.8},
            "gates": {"toy_physics": True, "toy_required_accuracy": True},
            "design_fidelity": {"V_pair": 1.0, "V_feas": 1.0, "V_var": 0.0, "C": 0.7},
            "physics_half": {"mean_response_error": 0.1, "sign_gate_failed": []},
            "decision_outcome": "VERIFIED_FEASIBLE",
        }


def _config(control):
    config = {"rule": "set before grading", "controls": [control]}
    return config, cg.config_digest(config)


def _grade(artifact_dir, control=None, config=None, digest=None):
    body, _ = dual_fixture()
    for leg in ("A", "D"):
        body["legs"][leg]["components"][0]["metric"] = METRICS[leg]
    seen = []

    def infer(inputs):
        seen.append(inputs.shape)
        return [[1.0] * 32 for _ in range(len(inputs))]

    result = cg.grade(
        adapter=_Adapter,
        bank=_bank(),
        pack=dual.register_pack(body),
        definition={},
        limits={},
        objective={},
        train_raw=b"",
        interface_names=("a", "b", "c"),
        infer=infer,
        artifact=cg.load_artifact(artifact_dir),
        control=control,
        challenge="f02",
        run_config=config,
        run_config_digest=digest,
    )
    return result, seen


def test_grade_runs_three_inferences_and_reports_aggregates_only(tmp_path):
    result, seen = _grade(_artifact(tmp_path))
    assert len(seen) == 3  # the graded run and the two paired repeats
    assert result["schema"] == cg.RESULT_SCHEMA
    assert result["D_parts"] == {"C": 0.7, "V_feas": 1.0, "V_pair": 1.0, "V_var": 0.0}
    assert result["total"] is not None and result["gates"]["toy_physics"] is True
    text = json.dumps(result)
    for secret in ("c0", "probe-", "reference", "inputs", "predictions"):
        assert secret not in text


def test_nothing_per_case_can_pass_through_the_aggregate_filter():
    assert cg._aggregate([1.0, 2.0]) is None
    assert cg._aggregate({"a": [[1.0]], "b": ["x", "y"]}) == {
        "a": None,
        "b": ["x", "y"],
    }


def test_an_applied_control_reaches_the_adapter_in_graded_and_repeat_runs(tmp_path):
    _Adapter.calls.clear()
    control = {"name": "ctrl.nonaffine_power", "params": {"shift": 5.0}}
    config, digest = _config(control)
    _grade(_artifact(tmp_path), control=control, config=config, digest=digest)
    call = _Adapter.calls[-1]
    assert call["outputs"] != [[1.0] * 32] * len(call["outputs"])
    assert all(r == call["outputs"] for r in call["repeats"])


def test_the_module_never_imports_the_official_store():
    import ast

    tree = ast.parse(Path(cg.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name if isinstance(n, ast.Import) else f"{n.module}.{alias.name}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for alias in n.names
    }
    assert not [m for m in imported if "retention" in m or "custody" in m]


def test_a_control_needs_a_run_config_that_names_it_and_hashes_to_the_given_digest(
    tmp_path,
):
    control = {"name": "ctrl.nonaffine_power", "params": {"shift": 5.0}}
    config, digest = _config(control)
    result, _ = _grade(
        _artifact(tmp_path), control=control, config=config, digest=digest
    )
    assert result["run_config_digest"] == digest
    for args, code in (
        ({}, "control_run_config_required"),
        (
            {"config": config, "digest": "sha256:" + "0" * 64},
            "control_run_config_digest",
        ),
        (
            {
                "config": {"controls": [{**control, "params": {"shift": 9.0}}]},
                "digest": cg.config_digest(
                    {"controls": [{**control, "params": {"shift": 9.0}}]}
                ),
            },
            "control_run_config_mismatch",
        ),
    ):
        (tmp_path / code).mkdir()
        with pytest.raises(cg.CalibrationRefused) as info:
            _grade(_artifact(tmp_path / code), control=control, **args)
        assert info.value.code == code


def test_leg_delta_reports_what_a_control_moved_beside_the_targeted_leg():
    before = {"A": 0.9, "D": 0.5, "total": 0.7, "A_legs": {"A_acc": 0.9, "A_law": 0.8}}
    after = {"A": 0.8, "D": 0.5, "total": 0.65, "A_legs": {"A_acc": 0.88, "A_law": 0.3}}
    delta = cg.leg_delta(before, after)
    assert delta["A_legs.A_law"] == pytest.approx(-0.5)
    assert delta["A_legs.A_acc"] == pytest.approx(-0.02)
    assert delta["D"] == 0
