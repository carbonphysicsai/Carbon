"""Motor 1.8's sealed adapter through a version-overlay dispatch (a TEMPORARY overlay file; the production overlay gains
the 1.8 entry only at the TRAIN freeze). Checks: 1.8 routes to its own module, every other version delegates unchanged,
the earlier Motor producer identity does not move, 1.8 refuses to measure until its extended TRAIN is frozen, and its
pool binding (absolute pk-pk) is reached through `pool_version` with `pool_adapters.py` untouched. Test values only.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.scoring import motor18_dual_pack, pool_adapters, pool_version

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "carbon" / "scoring" / "motor18_dual_pack.py"


def _entry():
    return {
        "challenge_id": "electric-motor-magnetics",
        "version": "1.8",
        "train": motor18_dual_pack.TRAIN,
        "allowlist": "v8",
        "step_caps": False,
        "pack_version": "motor-normal-construction-development-8",
        "development_evaluation": [
            "motor-dual-development-grid-v2",
            "motor-development-grid-8x6",
        ],
        "sealed_evaluation": motor18_dual_pack.POOL_VERSIONS["1.8"][0],
        "campaign": "catalog",
        "catalog": True,
        "graph_adapter": "v2",
        "catalog_entries_from": [],
        "predecessor": "1.6",
        "rebuild_wall_seconds": 648,
        "dispatch": {
            "module": "carbon.scoring.motor18_dual_pack",
            "sha256": hashlib.sha256(
                MODULE.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest(),
            "config": {},
        },
    }


CODE = "\n".join(  # noqa: FLY002
    [
        "import json, sys",
        "from carbon.challenge_kit import version_overlay, version_registry",
        "from carbon.scoring import motor_sealed_dual_pack as sealed, pool_adapters, pool_version",
        "pa_before = pool_adapters.__file__",
        "before = sealed.producer_digest()",
        "fifteen = sealed.adapter('1.5')",
        "version_overlay.install(sys.argv[1])",
        "from carbon.scoring import motor18_dual_pack as m18",
        "out = {",
        " 'pool': list(sealed.POOL_VERSIONS['1.8']),",
        " 'module_18': sealed.adapter('1.8')._module.__name__,",
        " 'module_16': sealed.adapter('1.6')._module.__name__,",
        " 'module_15': type(sealed.adapter('1.5')).__name__ == type(fifteen).__name__,",
        " 'digest_same': sealed.producer_digest() == before,",
        " 'digest_18_differs': m18.producer_digest() != before,",
        " 'registered': version_registry.find('electric-motor-magnetics', '1.8') is not None,",
        " 'binding_registered': ('motor', '1.8') in pool_version._BINDINGS,",
        " 'binding_16_unregistered': ('motor', '1.6') not in pool_version._BINDINGS,",
        "}",
        "try:",
        "    m18._train()",
        "    out['train'] = 'loaded'",
        "except ValueError as error:",
        "    out['train'] = str(error)",
        "print(json.dumps(out))",
    ]
)


def _run(overlay):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-c", CODE, str(overlay)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


@pytest.fixture
def overlay(tmp_path):
    document = json.loads(
        (
            ROOT / "scripts" / "validator_host_classes" / "version_overlay.json"
        ).read_bytes()
    )
    # the PRODUCTION entry (registered 9 Nov); a test entry for 1.8 would be refused as a different one
    assert document["versions"]["electric-motor-magnetics 1.8"] == _entry()
    path = tmp_path / "version_overlay.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.fixture
def clean_bindings():
    saved = dict(pool_version._BINDINGS)
    pool_version._BINDINGS.clear()
    yield
    pool_version._BINDINGS.clear()
    pool_version._BINDINGS.update(saved)


def test_motor_1_8_routes_to_its_own_module_and_nothing_else_moves(overlay):
    result = _run(overlay)
    assert result.returncode == 0, result.stderr[-2000:]
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out["registered"]
    assert out["pool"] == list(motor18_dual_pack.POOL_VERSIONS["1.8"])
    assert out["module_18"] == "carbon.scoring.motor18_dual_pack"
    assert out["module_16"] == "carbon.scoring.motor_pool_baseline_dual_pack"
    assert out["module_15"]
    assert out["digest_same"] and out["digest_18_differs"]
    assert out["binding_registered"] and out["binding_16_unregistered"]
    assert out["train"] == "loaded"


def test_a_changed_module_file_is_refused_before_import(overlay):
    document = json.loads(overlay.read_bytes())
    document["versions"]["electric-motor-magnetics 1.8"]["dispatch"]["sha256"] = (
        "0" * 64
    )
    overlay.write_text(json.dumps(document), encoding="utf-8")
    result = _run(overlay)
    assert result.returncode != 0 and "sha256 does not match" in result.stderr


def test_the_dispatch_takes_no_config_and_answers_only_1_8(clean_bindings):
    with pytest.raises(ValueError, match="no config"):
        motor18_dual_pack.dispatch({"baseline_box": {}})
    spec = motor18_dual_pack.dispatch({})
    assert spec["version"] == "1.8" and spec["challenge"] == "electric-motor-magnetics"
    assert motor18_dual_pack.sealed_adapter("1.6") is None
    with pytest.raises(ValueError, match="Motor 1.8 packs only"):
        motor18_dual_pack._writer(None, None, version="1.6")
    motor18_dual_pack.dispatch({})  # idempotent: the same factory again


def test_1_8_reads_its_own_train_never_train_150():
    from carbon.challenge_kit import physical_public_train as ppt

    assert motor18_dual_pack.TRAIN != "motor-dev-train-150-v1"
    assert motor18_dual_pack.TRAIN in ppt.FRESH_LAMBDA


def test_the_row_is_carbons_1_8_train_interface():
    """The grade's row (`carbon.motor.row18`) and the 1.8 TRAIN interface (H-a) are ONE layout, in the same order."""
    from carbon.challenge_kit import physical_public_train as ppt
    from carbon.motor import row18

    slices = ppt.motor18_interface_document()["target_slices"]
    assert list(slices) == list(row18.ROW)
    assert [tuple(v) for v in slices.values()] == [
        (k * 60, (k + 1) * 60) for k in range(len(row18.ROW))
    ]
    assert row18.WIDTH == 240


def test_pool_adapters_py_is_untouched_and_still_a_live_producer_file():
    from carbon.scoring import f08_sanity_dual_pack

    assert "pool_adapters.py" in f08_sanity_dual_pack.FILES
    assert "worst_case_torque_ripple_pk_pk_nm" not in (
        ROOT / "carbon" / "scoring" / "pool_adapters.py"
    ).read_text(encoding="utf-8")


# --- the pool binding hook ------------------------------------------------------------------------------------------


def test_an_unregistered_version_keeps_pool_adapters_binding(
    clean_bindings, monkeypatch
):
    seen = []
    monkeypatch.setattr(
        pool_adapters,
        "official_binding",
        lambda kind, version: seen.append((kind, version)) or "theirs",
    )
    assert pool_version.official_binding("motor", "1.6") == "theirs"
    pool_version.register_binding("motor", "1.8", lambda: "mine")
    assert pool_version.official_binding("motor", "1.8") == "mine"
    assert seen == [("motor", "1.6")]


def test_a_registered_binding_is_add_only(clean_bindings):
    def first():
        return 1

    pool_version.register_binding("motor", "1.8", first)
    pool_version.register_binding("motor", "1.8", first)
    with pytest.raises(ValueError, match="already has a different pool binding"):
        pool_version.register_binding("motor", "1.8", lambda: 2)


# --- the absolute pk-pk binding -------------------------------------------------------------------------------------


def _roles():
    names = ["airgap_mm", "magnet_mm"]
    return lambda kind, version: (SimpleNamespace(), {}, {}, names)


def _flat(level, ripple=0.0, extra=180):
    """A synthetic row: the 60-angle torque, then ``extra`` linkage values (180 = a whole 1.8 row)."""
    from carbon.motor.domain import ANGLE_STEPS

    return [level + (ripple if i == 0 else 0.0) for i in range(ANGLE_STEPS)] + [
        0.01
    ] * extra


def test_the_binding_derives_absolute_pk_pk_from_the_60_angle_torque(monkeypatch):
    from carbon.motor import exam

    monkeypatch.setattr(pool_adapters, "_roles", _roles())
    monkeypatch.setattr(exam, "gates", lambda outputs: {})
    chosen = motor18_dual_pack.pool_adapter("1.8")
    assert chosen.objective == "ripple_pk_pk_nm" and chosen.sense == "min"
    assert (
        chosen.limits == ()
    )  # no floor or ceiling in code: they are sealed custody values
    derived = chosen.derive({}, _flat(2.0, ripple=0.3))
    assert derived["ripple_pk_pk_nm"] == pytest.approx(0.3)
    assert derived["mean_torque_nm"] == pytest.approx(
        2.0 + 0.3 / len(_flat(0, extra=0))
    )
    assert chosen.derive({}, ["nan"] * len(_flat(0))) is None
    assert chosen.derive({}, _flat(2.0)[:-1]) is None
    # back-EMF in 1.8 (the owner, 7 Nov evening): a torque-only 60-wide row is not a 1.8 answer
    assert chosen.derive({}, _flat(2.0, extra=0)) is None


def test_a_gate_failure_derives_nothing_and_the_gates_read_the_torque(monkeypatch):
    from carbon.motor import exam

    seen = []
    monkeypatch.setattr(pool_adapters, "_roles", _roles())
    monkeypatch.setattr(
        exam,
        "gates",
        lambda outputs: seen.append(len(outputs["torque_nm"])) or {"g": exam.FAIL},
    )
    assert motor18_dual_pack.pool_adapter("1.8").derive({}, _flat(2.0)) is None
    gates = motor18_dual_pack.physics_gates()
    assert gates.failed({}, _flat(2.0)) == ("g",)
    assert gates.failed({}, _flat(2.0, extra=0)) == ("schema_finite",)
    assert gates.failed({}, [1.0, 2.0]) == ("schema_finite",)
    assert gates.failed({}, _flat(2.0)[:-1] + ["inf"]) == ("schema_finite",)
    assert set(seen) == {len(_flat(0, extra=0))}  # the gates see the torque slice only


def test_a_true_j0_record_below_minus_allowance_is_scorable(monkeypatch):
    """At J == 0 exactly (open circuit) the period-mean torque is cogging alone and may sit below -allowance; a TRUE
    such record is SCORABLE: `motoring_mean_nonnegative` is NOT_APPLICABLE there (Carbon Validator-Motor, Wed 11 Nov
    11:05, CALIB18_MOTOR_RULING RULING.md 77117b6b section 4). Nothing at J > 0 changes, J absent or not a plain number
    keeps the gate, and `exam.gates` itself (every other Motor version) is unchanged."""
    from carbon.motor import exam

    monkeypatch.setattr(pool_adapters, "_roles", _roles())
    row = _flat(
        -0.05, ripple=0.02
    )  # mean about -0.05 N.m, far below -(1e-3 x 0.05 + 1e-3) N.m
    torque = row[: len(_flat(0, extra=0))]
    assert exam.gates({"torque_nm": torque})["motoring_mean_nonnegative"] == exam.FAIL
    chosen = motor18_dual_pack.pool_adapter("1.8")
    gates = motor18_dual_pack.physics_gates()
    for j in (0.0, 0):
        open_circuit = {"current_density_a_mm2": j}
        derived = chosen.derive(open_circuit, row)
        assert derived is not None and derived["mean_torque_nm"] < 0
        assert derived["ripple_pk_pk_nm"] == pytest.approx(0.02)
        assert gates.failed(open_circuit, row) == ()
        verdicts = motor18_dual_pack.gates18(torque, open_circuit)
        assert verdicts["motoring_mean_nonnegative"] == exam.NOT_APPLICABLE
        assert verdicts["schema_finite"] == exam.PASS
    for inputs in (
        {"current_density_a_mm2": 5.0},
        {"current_density_a_mm2": 1e-12},
        {},
        {"current_density_a_mm2": False},
        {"current_density_a_mm2": "0"},
        None,
    ):
        assert chosen.derive(inputs, row) is None
        assert gates.failed(inputs, row) == ("motoring_mean_nonnegative",)


def test_only_1_8_has_this_adapter():
    with pytest.raises(pool_adapters.PoolAdapterRefused, match="for_1.8_only"):
        motor18_dual_pack.pool_adapter("1.6")


def test_the_official_binding_refuses_proof_suite_inputs(monkeypatch):
    monkeypatch.setattr(pool_adapters, "_roles", _roles())
    binding = motor18_dual_pack.official_binding()
    assert binding.kind == "motor" and binding.version == "1.8"
    with pytest.raises(
        pool_adapters.PoolAdapterRefused, match="not_part_of_the_official_grade"
    ):
        binding.serve_default()


def test_no_limit_value_is_in_the_module():
    text = MODULE.read_text(encoding="utf-8")
    assert "constraints" not in text and "important_limit_definition" not in text


# --- the 240-wide 1.8 row -------------------------------------------------------------------------------------------


def _whole(torque=2.0):
    from carbon.motor.domain import ANGLE_STEPS

    return (
        [torque] * ANGLE_STEPS
        + [0.1] * ANGLE_STEPS
        + [0.2] * ANGLE_STEPS
        + [0.3] * ANGLE_STEPS
    )


def test_the_row_is_torque_then_the_three_phase_linkages():
    from carbon.motor.domain import ANGLE_STEPS

    assert motor18_dual_pack.ROW == (
        "torque_nm",
        "phase_flux_linkage_wb_A",
        "phase_flux_linkage_wb_B",
        "phase_flux_linkage_wb_C",
    )
    parts = motor18_dual_pack.split(_whole())
    assert list(parts) == list(motor18_dual_pack.ROW)
    assert all(len(v) == ANGLE_STEPS for v in parts.values())
    assert parts["torque_nm"] == [2.0] * ANGLE_STEPS
    assert motor18_dual_pack.linkages(_whole()) == {
        "a": [0.1] * ANGLE_STEPS,
        "b": [0.2] * ANGLE_STEPS,
        "c": [0.3] * ANGLE_STEPS,
    }


@pytest.mark.parametrize(
    "bad",
    [
        [2.0] * 60,  # torque only
        _whole()[:-1],
        [*_whole(), 0.0],
        _whole()[:-1] + ["nan"],
        _whole()[:-1] + [None],
        "not a row",
    ],
)
def test_anything_but_a_whole_finite_240_row_is_not_an_answer(bad):
    assert motor18_dual_pack.split(bad) is None
    assert motor18_dual_pack.linkages(bad) is None


def test_the_sealed_grader_sees_only_the_torque_slices(monkeypatch):
    seen = {}

    def fake_measure(**kwargs):
        seen.update(kwargs)
        return {"A": 1.0}

    monkeypatch.setattr(motor18_dual_pack._sl(), "measure", fake_measure)
    monkeypatch.setattr(motor18_dual_pack, "_torque_train", lambda: "TRAIN-1.8")
    rows = [_whole(1.0), _whole(2.0)]
    motor18_dual_pack.measure(
        bank_rows=["r1", "r2"],
        outputs=rows,
        repeats=[[_whole(1.0), _whole(2.0)], [_whole(1.0), _whole(2.0)]],
        definition={},
        limits={},
        objective={},
        train_raw=b"train-150",
        names=[],
    )
    assert seen["outputs"] == [[1.0] * 60, [2.0] * 60]
    assert seen["repeats"] == [[[1.0] * 60, [2.0] * 60]] * 2
    assert seen["train_raw"] == "TRAIN-1.8"


def test_one_malformed_row_anywhere_empties_every_sealed_row(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        motor18_dual_pack._sl(), "measure", lambda **kw: seen.update(kw) or {}
    )
    monkeypatch.setattr(motor18_dual_pack, "_torque_train", lambda: "TRAIN-1.8")
    motor18_dual_pack.measure(
        bank_rows=["r1", "r2"],
        outputs=[_whole(), _whole()],
        repeats=[
            [_whole(), _whole()],
            [_whole(), [2.0] * 60],
        ],  # one twin is torque-only
        definition={},
        limits={},
        objective={},
        train_raw=None,
        names=[],
    )
    assert seen["outputs"] == [[], []]
    assert seen["repeats"] == [[[], []], [[], []]]


def test_an_empty_curve_fails_motors_own_schema_gate():
    from carbon.motor import exam
    from carbon.scoring import motor_dual_measurement as mdm

    assert exam.gates(mdm._curve([]))["schema_finite"] == exam.FAIL


# --- the back-EMF cells ---------------------------------------------------------------------------------------------


@pytest.fixture
def waveforms():
    from carbon.scoring import pool_grader

    saved = dict(pool_grader._WAVEFORMS)
    pool_grader._WAVEFORMS.clear()
    yield pool_grader._WAVEFORMS
    pool_grader._WAVEFORMS.clear()
    pool_grader._WAVEFORMS.update(saved)


def _balanced_row(amplitude=0.02, shift=0.3, harmonic=0.0, torque=2.0):
    """A synthetic 1.8 row: flat torque, then balanced three-phase linkages (optionally with a 5th harmonic)."""
    from carbon.motor import back_emf
    from carbon.motor.domain import ANGLE_STEPS, FIXED

    pairs = FIXED["poles"] // 2
    theta = [k * back_emf.STEP_RAD for k in range(ANGLE_STEPS)]
    phases = []
    for k in range(3):
        phases += [
            amplitude * math.cos(pairs * t + shift - k * 2 * math.pi / 3)
            + harmonic * math.cos(5 * (pairs * t + shift - k * 2 * math.pi / 3))
            for t in theta
        ]
    return [torque] * ANGLE_STEPS + phases


def test_the_emf_outputs_are_back_emfs_two_cells():
    from carbon.motor import back_emf

    assert motor18_dual_pack.EMF_OUTPUTS == back_emf.CELLS


def test_derive_gives_both_cells_the_predicted_ke_ll_waveform(monkeypatch):
    from carbon.motor import back_emf, exam

    monkeypatch.setattr(pool_adapters, "_roles", _roles())
    monkeypatch.setattr(exam, "gates", lambda outputs: {})
    chosen = motor18_dual_pack.pool_adapter("1.8")
    assert chosen.outputs == (
        "mean_torque_nm",
        "ripple_pk_pk_nm",
        "back_emf_open_circuit",
        "ke_ll_loaded",
    )
    row = _balanced_row()
    derived = chosen.derive({}, row)
    expected = tuple(back_emf.ke_line(motor18_dual_pack.linkages(row)))
    assert derived["back_emf_open_circuit"] == derived["ke_ll_loaded"] == expected
    assert derived["mean_torque_nm"] == pytest.approx(2.0)


def test_the_dispatch_registers_both_waveform_outputs(clean_bindings, waveforms):
    motor18_dual_pack.dispatch({})
    assert set(waveforms) == set(motor18_dual_pack.EMF_OUTPUTS)
    motor18_dual_pack.dispatch({})  # idempotent


def test_a_waveform_needs_one_finite_value_per_step_and_a_shape():
    from carbon.motor.domain import ANGLE_STEPS

    valid = motor18_dual_pack._waveform_valid
    assert valid(motor18_dual_pack.ke_ll(_balanced_row()))
    assert not valid((0.0,) * ANGLE_STEPS)  # no shape
    assert not valid((1.0,) * (ANGLE_STEPS - 1))
    assert not valid((float("nan"),) + (1.0,) * (ANGLE_STEPS - 1))
    assert not valid("wave")


def test_the_graded_error_is_the_validators_shape_error(clean_bindings, waveforms):
    from carbon.motor import back_emf
    from carbon.scoring import pool_grader

    motor18_dual_pack.dispatch({})
    predicted, reference = _balanced_row(), _balanced_row(
        harmonic=0.002, amplitude=0.05
    )
    truth = tuple(back_emf.ke_line(motor18_dual_pack.linkages(reference)))
    error = pool_grader.difference(
        "ke_ll_loaded", motor18_dual_pack.ke_ll(predicted), truth
    )
    assert error == pytest.approx(
        back_emf.grade(
            motor18_dual_pack.linkages(predicted), motor18_dual_pack.linkages(reference)
        )
    )
    assert error > 0
    # amplitude alone is not graded (each waveform over its own RMS)
    louder = tuple(
        back_emf.ke_line(motor18_dual_pack.linkages(_balanced_row(amplitude=0.07)))
    )
    assert pool_grader.difference(
        "back_emf_open_circuit", motor18_dual_pack.ke_ll(predicted), louder
    ) == pytest.approx(0.0, abs=1e-12)


def test_the_sealed_grader_reads_the_torque_slice_of_the_1_8_train(monkeypatch):
    import io

    import numpy as np

    from carbon.challenge_kit import physical_public_train

    rng = np.random.default_rng(0)
    inputs, targets = rng.random((5, 8)), rng.random((5, 240))
    monkeypatch.setattr(
        motor18_dual_pack, "_train", lambda: physical_public_train._npz(inputs, targets)
    )
    with np.load(io.BytesIO(motor18_dual_pack._torque_train())) as data:
        assert np.array_equal(data["inputs"], inputs)
        assert np.array_equal(data["targets"], targets[:, :60])
    # Motor's own TRAIN reader then sees 60-angle torque curves
    from carbon.scoring import motor_dual_pack

    records = motor_dual_pack._train_records(motor18_dual_pack._torque_train())
    assert all(len(r["outputs"]["torque_nm"]) == 60 for r in records)
    monkeypatch.setattr(
        motor18_dual_pack,
        "_train",
        lambda: physical_public_train._npz(inputs, targets[:, :60]),
    )
    with pytest.raises(ValueError, match="not the 240-wide 1.8 row"):
        motor18_dual_pack._torque_train()


def test_definition_and_applied_pack_read_the_torque_view(monkeypatch):
    seen = []
    monkeypatch.setattr(motor18_dual_pack, "_torque_train", lambda: "VIEW")
    monkeypatch.setattr(
        motor18_dual_pack._sl(),
        "definition",
        lambda **kw: seen.append(("definition", kw["train_raw"])),
    )
    monkeypatch.setattr(
        motor18_dual_pack._sl(),
        "applied_pack",
        lambda **kw: seen.append(("applied", kw.get("train_raw"))),
    )
    motor18_dual_pack.definition(bank={}, train_raw=b"other")
    motor18_dual_pack.applied_pack(train_raw=b"other")
    motor18_dual_pack.applied_pack()
    assert seen == [("definition", "VIEW"), ("applied", "VIEW"), ("applied", None)]
