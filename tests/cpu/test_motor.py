"""The motor Challenge's interface, baseline, GetDP input and runner (#344).

No test runs GetDP or Gmsh. The iron law's closed-form co-energy is checked
against quadrature of its own reluctivity, and the runner's typed outcomes
are reached with a fake `docker` and fabricated result files.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import math
import subprocess
from pathlib import Path
from statistics import fmean

import pytest

from carbon.motor import analytic, domain, exam, getdp, population

REPOSITORY = Path(__file__).resolve().parents[2]
NOMINAL = dict(domain.NOMINAL)
MU0 = 4e-7 * math.pi


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPOSITORY / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------ domain


@pytest.mark.parametrize(
    "change",
    [
        {"airgap_mm": 0.29},
        {"current_density_a_mm2": 15.1},
        {"embrace": float("inf")},
        {"magnet_mm": "2"},
    ],
)
def test_inputs_outside_the_box_or_of_the_wrong_type_are_refused(change):
    with pytest.raises(ValueError):
        domain.check_inputs({**NOMINAL, **change})


def test_the_benchmark_frame_is_buildable_and_its_coil_is_the_meshed_one():
    assert domain.validity(NOMINAL) == []
    # rung M1's mesh measured 55.79442800979 mm^2 for this slot.
    assert domain.coil_area_mm2(NOMINAL) == pytest.approx(55.794428009792, rel=1e-12)
    current = domain.current_amplitude_a(NOMINAL)
    assert current == pytest.approx(10.0 * 55.794428009792 / 104)


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"tooth_mm": 5.0, "slot_open_deg": 6.0}, "opening is wider"),
        ({"slot_bottom_mm": 34.0, "airgap_mm": 1.0}, None),
    ],
)
def test_unbuildable_geometry_is_named(change, reason):
    reasons = domain.validity({**NOMINAL, **change})
    if reason is None:
        assert reasons == []
    else:
        assert any(reason in r for r in reasons)


# ------------------------------------------------------------- analytical


def test_the_baseline_obeys_the_surface_pm_laws():
    base = analytic.predict(NOMINAL)["torque_nm"]
    assert len(base) == domain.ANGLE_STEPS and len(set(base)) == 1
    double = analytic.predict({**NOMINAL, "current_density_a_mm2": 5.0})["torque_nm"][0]
    assert double == pytest.approx(base[0] / 2)
    weakened = analytic.predict({**NOMINAL, "current_angle_deg": 60.0})["torque_nm"][0]
    assert weakened == pytest.approx(base[0] * 0.5)
    assert (
        analytic.predict({**NOMINAL, "current_density_a_mm2": 0.0})["torque_nm"][0] == 0
    )


# ------------------------------------------------------------------ GetDP


def test_the_winding_is_single_layer_one_slot_per_pole_per_phase():
    table = getdp.winding(24, 8)
    assert table[:6] == [("A", 1), ("C", -1), ("B", 1), ("A", -1), ("C", 1), ("B", -1)]
    for phase in "ABC":
        signs = [s for p, s in table if p == phase]
        assert len(signs) == 8 and sum(signs) == 0
    with pytest.raises(ValueError):
        getdp.winding(36, 8)


def _params():
    g = domain.geometry(NOMINAL)
    f = domain.FIXED
    return {
        **g,
        "length": f["length"],
        "br": f["br"],
        "mur_m": f["mur_m"],
        "mur_fe": 1000.0,
        "turns": f["turns"],
        "coil_area_mm2": domain.coil_area_mm2(NOMINAL),
    }


def test_the_linear_and_nonlinear_inputs_declare_what_the_docstring_says():
    linear = getdp.pro_text(_params())
    assert "Generate[S]; Solve[S];" in linear and "JacNL" not in linear
    assert "nu[Iron] = 1/(mu0*1000.0);" in linear
    nonlinear = getdp.pro_text(_params(), nonlinear=getdp.BRAUER)
    assert nonlinear.count("IterativeLoop") == 2
    assert (
        f"IterativeLoop[{getdp.DAMPED_MAX}, {getdp.DAMPED_TOL}, {getdp.DAMPING}]"
        in nonlinear
    )
    assert f"IterativeLoop[{getdp.NEWTON_MAX}, {getdp.NEWTON_TOL}, 1]" in nonlinear
    assert "JacNL[ dhdb[{d a}] * Dof{d a}, {d a} ]; In Iron;" in nonlinear
    for text in (linear, nonlinear):
        assert "In Airgap;" in text  # Maxwell stress over the annulus only
        assert text.count("js[Coil_") == 24 and text.count("br[Magnet_") == 8
        assert "Region[1000]" in text  # a = 0 on the outer circle


def _nu(s, law=getdp.BRAUER):
    k1, k2, k3 = law
    nu_b = k1 + k2 * math.exp(min(k3 * s, 700))
    return nu_b / (1 + MU0 * nu_b)


def test_the_iron_law_is_vacuum_bounded_and_monotone():
    values = [_nu(0.01 * i) for i in range(1, 2000)]
    assert all(b > a for a, b in itertools.pairwise(values))
    assert values[-1] < 1 / MU0 and values[-1] > 0.99 / MU0
    # Low field: Brauer's law to within mu0 nu_b.
    assert _nu(0.0) == pytest.approx(110.0, rel=2e-4)


def test_the_closed_form_co_energy_matches_quadrature_of_the_law():
    k1, k2, k3 = getdp.BRAUER
    a = 1 + MU0 * k1
    c = MU0 * k2
    coefficient = (k2 - k1 * c / a) / (c * k3)

    def w_closed(s):
        return 0.5 * (
            k1 / a * s + coefficient * math.log((a + c * math.exp(k3 * s)) / (a + c))
        )

    for s_end in (0.5, 2.25, 4.0, 6.25, 9.0):
        n = 20000
        quad = sum(_nu((i + 0.5) * s_end / n) for i in range(n)) * s_end / n / 2
        assert w_closed(s_end) == pytest.approx(quad, rel=1e-6)


# ------------------------------------------------------------- population


def test_draws_are_reproducible_and_buildable():
    first, attempts = population.draw(population.public_rng("t"), 6)
    assert first == population.draw(population.public_rng("t"), 6)[0]
    assert attempts >= 6 and all(population.admitted(c) for c in first)


# ----------------------------------------------------------------- runner


@pytest.fixture
def runner():
    return _load("motor_run_batch", "scripts/dev/motor/reference/run_batch.py")


def test_a_full_period_has_one_extra_position_and_a_window_has_none(runner):
    full = runner.case_params(NOMINAL, {})
    assert full["steps"] == list(range(61))
    fine = runner.case_params(NOMINAL, {"n_gap": 2880, "angle_steps": 15})
    assert fine["steps"] == [8 * k for k in range(16)]
    window = runner.case_params(
        NOMINAL, {"n_gap": 2880, "angle_steps": 120, "positions": 31}
    )
    assert window["steps"] == list(range(31))
    with pytest.raises(ValueError):
        runner.case_params(NOMINAL, {"angle_steps": 7})


def _write_results(case_dir, steps, torque, log=""):
    (case_dir / "res").mkdir(parents=True, exist_ok=True)
    for k, t in zip(steps, torque):
        (case_dir / "res" / f"torque_{k}.txt").write_text(f"0 {t!r}\n")
    (case_dir / "log.getdp").write_text(log)


def test_a_sound_periodic_sweep_is_ok(runner, tmp_path):
    p = runner.case_params(NOMINAL, {})
    curve = [5.0 + 0.1 * math.sin(2 * math.pi * k / 60) for k in range(61)]
    _write_results(tmp_path, p["steps"], curve)
    result, reasons = runner.analyze(tmp_path, p)
    assert reasons == []
    assert len(result["outputs"]["torque_nm"]) == 60
    assert result["derived"]["mean_nm"] == pytest.approx(5.0, abs=1e-12)


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"last": 5.1}, "periodicity"),
        ({"log": "Warning : IterativeLoop did NOT converge"}, "did not converge"),
        ({"first": float("nan")}, "non-finite"),
    ],
)
def test_each_failed_check_is_named(runner, tmp_path, change, reason):
    p = runner.case_params(NOMINAL, {})
    curve = [5.0] * 61
    curve[-1] = change.get("last", curve[-1])
    curve[0] = change.get("first", curve[0])
    _write_results(tmp_path, p["steps"], curve, change.get("log", ""))
    _, reasons = runner.analyze(tmp_path, p)
    assert any(reason in r for r in reasons)


def test_a_missing_position_is_a_solver_failure(runner, tmp_path):
    p = runner.case_params(NOMINAL, {})
    _write_results(tmp_path, p["steps"][:10], [5.0] * 10)
    result, reasons = runner.analyze(tmp_path, p)
    assert result is None and "no torque at step 10" in reasons[0]


def test_a_timeout_kills_only_the_cases_own_container(runner, monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    p = runner.case_params(NOMINAL, {"angle_steps": 2})
    status, _, _ = runner.solve(tmp_path, p, "carbon-motor-b-c1", 2, 5)
    assert status == "REFERENCE_TIMEOUT"
    assert calls[-1] == ["docker", "kill", "carbon-motor-b-c1"]
    run = calls[0]
    assert run[run.index("--network") + 1] == "none"


def test_docker_that_cannot_start_is_infrastructure(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(command, 125, "", "no"),
    )
    p = runner.case_params(NOMINAL, {"angle_steps": 2})
    assert runner.solve(tmp_path, p, "n", 2, 5)[0] == "FAILED_INFRA"


# -------------------------------------------------------------------- exam


def _curve(mean=10.0, ripple=0.5, phase=0.0):
    return [
        mean + ripple * math.sin(2 * math.pi * k / domain.ANGLE_STEPS + phase)
        for k in range(domain.ANGLE_STEPS)
    ]


def _ref(case_id="c", j=12.0, **kw):
    return {
        "case_id": case_id,
        "status": "OK",
        "inputs": {**NOMINAL, "current_density_a_mm2": j},
        "outputs": {"torque_nm": _curve(**kw)},
    }


SCALES = {"s_mean": 2.0, "s_ripple": 0.25}


@pytest.mark.parametrize(
    "prediction, gate",
    [
        ({"torque_nm": [1.0] * 59}, "schema_finite"),
        ({"torque_nm": [1.0] * 59 + [math.inf]}, "schema_finite"),
        ({"torque_nm": [True] * 60}, "schema_finite"),
        ({}, "schema_finite"),
        ({"torque_nm": _curve(mean=-0.1, ripple=0.01)}, "motoring_mean_nonnegative"),
    ],
)
def test_each_motor_gate_fails_what_it_should(prediction, gate):
    row = exam.evaluate_case(prediction, _ref())
    assert row["state"] == exam.GATE_FAILED and row["gates"][gate] == exam.FAIL


def test_a_cogging_curve_within_the_allowance_is_motoring():
    # Mean -5e-4 N m on a 0.2 N m cogging curve: inside 1e-3 * 0.2 + 1e-3.
    curve = {"torque_nm": _curve(mean=-5e-4, ripple=0.2)}
    assert exam.gates(curve)["motoring_mean_nonnegative"] == exam.PASS


def test_the_score_separates_mean_torque_from_ripple_shape():
    ref = _ref()
    exact = exam.score_case({"torque_nm": _curve()}, ref, SCALES)
    assert exact["error"] == pytest.approx(0, abs=1e-12)
    flat = exam.score_case({"torque_nm": [10.0] * 60}, ref, SCALES)
    # A flat curve at the right mean is charged only for the omitted ripple,
    # whose RMS is 0.5 / sqrt(2).
    assert flat["components"]["mean"] == pytest.approx(0, abs=1e-12)
    assert flat["components"]["ripple"] == pytest.approx(0.5 / math.sqrt(2) / 0.25)
    shifted = exam.score_case({"torque_nm": _curve(mean=11.0)}, ref, SCALES)
    assert shifted["components"] == pytest.approx(
        {"mean": 0.5, "ripple": 0.0}, abs=1e-12
    )
    assert shifted["mean_signed_error_nm"] == pytest.approx(1.0)


def test_train_scales_are_the_spreads_of_mean_and_ripple():
    train = [_ref(mean=8.0), _ref(mean=12.0), {"status": "REFERENCE_INVALID"}]
    scales = exam.scales_from_train(train)
    assert scales["s_mean"] == pytest.approx(2.0)
    assert scales["s_ripple"] == pytest.approx(0.5 / math.sqrt(2))
    assert scales["n_train"] == 2
    with pytest.raises(ValueError):
        exam.scales_from_train(train[:1])


def test_the_motor_aggregate_types_cases_and_reports_optimism_under_saturation():
    rows = [
        exam.score_case({"torque_nm": _curve(mean=11.0)}, _ref("a", j=12.0), SCALES),
        exam.score_case({"torque_nm": _curve()}, _ref("b", j=3.0), SCALES),
        exam.score_case(None, _ref("c"), SCALES, infra_failed=True),
        exam.score_case(
            {"torque_nm": _curve()},
            {"case_id": "d", "status": "REFERENCE_SOLVER_FAILED"},
            SCALES,
        ),
    ]
    result = exam.aggregate(rows)
    assert (
        result["n_scored"],
        result["n_failed_infra"],
        result["n_reference_invalid"],
    ) == (2, 1, 1)
    assert result["eligible"] and result["n_important"] == 1
    assert result["important_mean_bias_nm"] == pytest.approx(1.0)
    twin_bad = exam.score_case(
        {"torque_nm": _curve()},
        _ref("e"),
        SCALES,
        twin={"torque_nm": _curve(mean=10.01)},
    )
    assert twin_bad["gates"]["paired_repeat"] == exam.FAIL
    assert not exam.aggregate(rows + [twin_bad])["eligible"]


def test_motor_calibration_refuses_a_generating_reference():
    assert exam.calibrate([_ref()])["n_references"] == 1
    with pytest.raises(ValueError, match="fails gates"):
        exam.calibrate([_ref(mean=-1.0, ripple=0.1)])


def test_feasibility_is_torque_and_ripple_against_limits():
    out = {"torque_nm": _curve(mean=10.0, ripple=0.5)}  # 1 N m pk-pk
    assert exam.feasibility(out, min_torque_nm=9.0, max_ripple_fraction=0.11)[
        "feasible"
    ]
    assert not exam.feasibility(out, min_torque_nm=11.0, max_ripple_fraction=0.2)[
        "feasible"
    ]
    assert not exam.feasibility(out, min_torque_nm=9.0, max_ripple_fraction=0.05)[
        "feasible"
    ]


# ----------------------------------------------------------- pilot report


def test_the_pilot_report_pairs_meshes_and_checks_angle_resolution(tmp_path):
    reporter = _load(
        "motor_pilot_report", "scripts/dev/motor/reference/pilot_report.py"
    )
    base = _curve()
    fine_curve = [t * 1.01 for t in base[::4]]
    window = [10.0 + 0.01 * k for k in range(31)]
    plan = {
        "batch": "b",
        "cases": [
            {"case_id": "ordinary-2", "kind": "ordinary", "inputs": NOMINAL},
            {
                "case_id": "ordinary-2-n2880",
                "kind": "refinement",
                "inputs": NOMINAL,
                "pairs_with": "ordinary-2",
            },
            {
                "case_id": "ordinary-2-n2880-a120",
                "kind": "diagnostic",
                "inputs": NOMINAL,
                "pairs_with": "ordinary-2",
            },
        ],
    }

    def record(case_id, kind, curve, periodic):
        return {
            "case_id": case_id,
            "kind": kind,
            "status": "OK",
            "inputs": NOMINAL,
            "wall_s": 1.0,
            "outputs": {"torque_nm": curve},
            "checks": {"periodicity_rel": 1e-6 if periodic else None},
            "derived": {
                "mean_nm": fmean(curve),
                "ripple_pk_pk_nm": max(curve) - min(curve),
            },
        }

    fine_curve[:4] = window[::8]
    records = [
        record("ordinary-2", "ordinary", base, True),
        record("ordinary-2-n2880", "refinement", fine_curve, True),
        record("ordinary-2-n2880-a120", "diagnostic", window, False),
    ]
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    (tmp_path / "records.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n"
    )
    out = reporter.report(tmp_path)
    assert out["missing"] == [] and out["outcomes"] == {"OK": 3}
    (pair,) = out["mesh_pairs"]
    assert pair["case_id"] == "ordinary-2"
    resolution = out["angle_resolution"]
    # A linear window is interpolated exactly, and matches the refined record.
    assert resolution["midpoint_max_abs_nm"] == pytest.approx(0, abs=1e-12)
    assert resolution["determinism_max_abs_nm"] == 0.0
    assert [row["case_id"] for row in out["baseline"]] == ["ordinary-2"]
