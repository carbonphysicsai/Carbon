"""The cold plate Challenge's interface, analytical baseline and reference I/O (#342).

No test here runs OpenFOAM. The writer is checked against the verification
rungs' generator, the reader against fabricated writes, and the batch runner
against a fake `docker`, so every typed outcome is reached deliberately.
"""

from __future__ import annotations

import importlib.util
import json
import math
import subprocess
from pathlib import Path

import pytest

from carbon.cold_plate import analysis, analytic, domain, exam, openfoam, population

REPOSITORY = Path(__file__).resolve().parents[2]
NOMINAL = dict(domain.NOMINAL)


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPOSITORY / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------ domain


@pytest.mark.parametrize(
    "change",
    [
        {"heat_load_w": 1501.0},
        {"channel_width_mm": 0.19},
        {"hotspot_ratio": 0.99},
        {"inlet_c": float("nan")},
        {"flow_lpm_per_kw": True},
        {"fin_width_mm": "0.3"},
    ],
)
def test_inputs_outside_the_box_or_of_the_wrong_type_are_refused(change):
    with pytest.raises(ValueError):
        domain.check_inputs({**NOMINAL, **change})


def test_inputs_must_be_exactly_the_nine():
    with pytest.raises(ValueError, match="exactly"):
        domain.check_inputs({k: v for k, v in NOMINAL.items() if k != "inlet_c"})
    with pytest.raises(ValueError, match="exactly"):
        domain.check_inputs({**NOMINAL, "base_mm": 1.0})


def test_the_nominal_case_reproduces_the_rungs_design_point():
    d = domain.derived(domain.check_inputs(NOMINAL))
    assert d["channels"] == 50
    assert d["inlet_velocity_m_s"] == pytest.approx(1.5e-3 / 60 / (50 * 0.3e-3 * 2e-3))
    assert d["absorbed_w"] == pytest.approx(1000.0)  # 50 x 0.6 mm spans 30 mm
    assert d["hotspot_amplitude"] == 0.0


def test_a_period_that_does_not_divide_the_footprint_absorbs_less():
    case = domain.check_inputs({**NOMINAL, "channel_width_mm": 0.5})
    d = domain.derived(case)
    assert d["channels"] == 37
    assert d["absorbed_w"] == pytest.approx(1000.0 * 37 * 0.8 / 30)


@pytest.mark.parametrize(
    "t_c, rho, cp, kappa, mu_mpa_s",
    [
        (30.0, 1014.90, 3944.6, 0.4769, 1.7761),
        (35.0, 1012.48, 3956.7, 0.4814, 1.5417),
        (40.0, 1009.91, 3968.6, 0.4858, 1.3530),
        (45.0, 1007.21, 3980.6, 0.4903, 1.1993),
        (50.0, 1004.38, 3992.4, 0.4946, 1.0726),
    ],
)
def test_the_pg25_fits_reproduce_the_design_basis_table(t_c, rho, cp, kappa, mu_mpa_s):
    t = domain.K0 + t_c
    assert domain.pg25("rho", t) == pytest.approx(rho, abs=0.006)
    assert domain.pg25("cp", t) == pytest.approx(cp, abs=0.4)
    assert domain.pg25("kappa", t) == pytest.approx(kappa, abs=6e-5)
    assert domain.pg25("mu", t) * 1e3 == pytest.approx(mu_mpa_s, rel=2e-4)


def test_every_pg25_fit_stays_positive_wherever_a_solver_iterate_could_go():
    for name in domain.PG25:
        assert min(domain.pg25(name, 250.0 + 0.5 * i) for i in range(501)) > 0


@pytest.mark.parametrize("centre", [3.0, 9.0, 15.0, 27.0])
@pytest.mark.parametrize("width", [1.5, 2.5, 3.5])
@pytest.mark.parametrize("ratio", [1.0, 2.0, 3.0])
def test_every_hot_spot_keeps_the_heat_load_and_reaches_its_ratio(centre, width, ratio):
    case = domain.check_inputs(
        {
            **NOMINAL,
            "hotspot_center_mm": centre,
            "hotspot_width_mm": width,
            "hotspot_ratio": ratio,
        }
    )
    n = 6000
    q = [domain.heat_flux(case, (i + 0.5) * 30.0 / n) for i in range(n)]
    average = case["heat_load_w"] / 0.03**2
    assert sum(q) / n == pytest.approx(average, rel=1e-7)  # midpoint rule
    assert domain.heat_flux(case, centre) / average == pytest.approx(ratio, rel=1e-12)
    assert min(q) > 0


# ------------------------------------------------------------- analytical


def test_the_analytical_model_returns_every_output_in_its_declared_shape():
    result = analytic.predict(NOMINAL)
    for name, (_, shape) in domain.OUTPUTS.items():
        value = result[name]
        if shape:
            assert len(value) == shape[0]
            assert all(math.isfinite(v) for v in value)
        else:
            assert math.isfinite(value)
    assert result["peak_c"] >= max(result["profile_c"]) - 1e-9
    assert result["mean_c"] == pytest.approx(sum(result["profile_c"]) / 30)


def test_the_analytical_coolant_rise_is_the_energy_balance():
    case = domain.check_inputs({**NOMINAL, "hotspot_ratio": 3.0})
    result = analytic.predict(case)
    d = domain.derived(case)
    rise = result["outlet_c"] - case["inlet_c"]
    cp = domain.pg25("cp", domain.K0 + case["inlet_c"] + rise / 2)
    assert rise == pytest.approx(d["absorbed_w"] / (d["mass_flow_kg_s"] * cp), rel=2e-3)


def test_the_analytical_model_is_near_rung_7_at_the_nominal_point():
    """A regression on the baseline, not a tolerance: rung 7's reference read
    36.68 K peak above inlet and 3,925 Pa at the nominal point."""
    result = analytic.predict(NOMINAL)
    assert result["peak_c"] - 40.0 == pytest.approx(36.68, abs=0.5)
    assert result["pressure_drop_pa"] == pytest.approx(3925, rel=0.05)


def test_the_analytical_model_spreads_a_hot_spot_as_rung_7_measured():
    """Rung 7's reference put a 3x spot (centre 10 mm, width 2.5 mm) at 88.95 C.
    Without axial conduction this model read 27.6 K hotter."""
    case = {**NOMINAL, "hotspot_ratio": 3.0, "hotspot_center_mm": 10.0}
    assert analytic.predict(case)["peak_c"] == pytest.approx(88.95, abs=3.5)


def test_spreading_moves_heat_and_never_loses_it():
    conductance = [20.0 + 7.0 * (i % 5) for i in range(200)]
    applied = [1000.0 * (1 + 3 * (60 <= i < 70)) for i in range(200)]
    theta = analytic._spread(conductance, applied, 6e-4, 1.5e-4)
    absorbed = sum(g * t for g, t in zip(conductance, theta))
    assert absorbed == pytest.approx(sum(applied), rel=1e-12)
    assert max(theta) < max(q / g for q, g in zip(applied, conductance))


def test_a_hot_spot_moves_the_analytical_peak_beneath_it():
    case = {
        **NOMINAL,
        "hotspot_ratio": 3.0,
        "hotspot_center_mm": 9.0,
        "hotspot_width_mm": 2.0,
    }
    profile = analytic.predict(case)["profile_c"]
    assert profile.index(max(profile)) in (8, 9)


# --------------------------------------------------------------- writer


def test_the_writer_is_deterministic_and_records_what_it_wrote():
    first, record = openfoam.files(NOMINAL)
    second, _ = openfoam.files(dict(NOMINAL))
    assert first == second
    assert json.loads(first["case.json"]) == json.loads(
        json.dumps(record, sort_keys=True)
    )
    assert record["image"] == openfoam.IMAGE
    assert record["fluid_model"] == "variable"


def test_the_writer_uses_the_verification_rungs_mesh_unchanged():
    generate = _load(
        "plate_channel_generate", "scripts/dev/cold_plate/plate_channel/generate.py"
    )
    for width, depth in ((0.3, 2.0), (0.2, 1.0), (0.5, 3.0)):
        case = {**NOMINAL, "channel_width_mm": width, "channel_depth_mm": depth}
        geometry = openfoam.geometry_mm(domain.check_inputs(case))
        assert openfoam.block_mesh(geometry, 2.0, 4.0) == generate.block_mesh(
            geometry, 2.0, 4.0
        )


def test_a_uniform_map_is_written_uniform_and_a_hot_spot_as_an_expression():
    uniform, _ = openfoam.files(NOMINAL)
    text = uniform["system/solid/changeDictionaryDict"]
    assert f"q               uniform {1000 / 0.03**2!r};" in text
    assert "expression" not in text
    spot = {**NOMINAL, "hotspot_ratio": 2.0, "hotspot_center_mm": 12.0}
    written, record = openfoam.files(spot)
    text = written["system/solid/changeDictionaryDict"]
    assert "type        expression;" in text
    assert f'"amp = {record["derived"]["hotspot_amplitude"]!r}"' in text
    assert '"xc = 0.012"' in text


def test_the_fluid_models_hold_exactly_the_properties_they_say():
    t_in = domain.K0 + 40.0
    rho, cp, kappa = openfoam.fluid_coefficients("variable", t_in)
    assert rho == domain.PG25["rho"] and kappa == domain.PG25["kappa"]
    assert cp == (domain.pg25("cp", t_in),)
    assert openfoam.fluid_coefficients("variable-cp", t_in)[1] == domain.PG25["cp"]
    held = openfoam.fluid_coefficients("viscosity-only", t_in)
    assert all(len(c) == 1 for c in held)
    for model in openfoam.FLUID_MODELS:
        text = openfoam._fluid_thermo(model, t_in)
        assert " ".join(repr(c) for c in domain.PG25["mu"]) in text


@pytest.mark.parametrize(
    "options",
    [
        {"fluid_model": "constant"},
        {"resolution": 0},
        {"grading": 0.5},
        {"iterations": 1},
    ],
)
def test_the_writer_refuses_options_it_does_not_support(options):
    with pytest.raises(ValueError):
        openfoam.files(NOMINAL, **options)


def test_write_case_never_overwrites(tmp_path):
    openfoam.write_case(NOMINAL, tmp_path / "case")
    with pytest.raises(FileExistsError):
        openfoam.write_case(NOMINAL, tmp_path / "case")


# --------------------------------------------------------------- reader


def _sound(**changes):
    outputs = {
        "peak_c": 77.0,
        "mean_c": 70.0,
        "profile_c": [70.0] * 30,
        "outlet_c": 50.0,
        "pressure_drop_pa": 3900.0,
    }
    checks = {
        "mass_imbalance_rel": 1e-10,
        "energy_balance_rel": 1e-8,
        "fluid_min_c": 39.0,
        "fluid_max_c": 74.0,
        "inlet_undershoot_k": 1.0,
        "re_outlet": 400.0,
    }
    for key, value in changes.items():
        (outputs if key in outputs else checks)[key] = value
    return {"outputs": outputs, "checks": checks, "diagnostics": {}}


def _case(tmp_path, monkeypatch, half, final):
    case_dir = tmp_path / "case"
    openfoam.write_case(NOMINAL, case_dir)
    (case_dir / "times").write_text("0\n2000\n4000\n")
    (case_dir / "log.chtMultiRegionSimpleFoam").write_text("")
    writes = {"2000": half, "4000": final}
    monkeypatch.setattr(analysis, "at_time", lambda d, t, r: writes[t])
    return analysis.analyze_case(case_dir)


def test_a_sound_converged_case_is_ok(tmp_path, monkeypatch):
    result = _case(tmp_path, monkeypatch, _sound(), _sound())
    assert result["outcome"] == "OK" and result["reasons"] == []
    assert result["checks"]["iteration_change_k"] == 0.0


@pytest.mark.parametrize(
    "final, reason",
    [
        (_sound(mass_imbalance_rel=2e-6), "mass_imbalance_rel"),
        (_sound(energy_balance_rel=-5e-4), "energy_balance_rel"),
        (_sound(peak_c=77.01), "iteration_change_k"),
        (_sound(pressure_drop_pa=3901.0), "iteration_change_pressure_rel"),
        (_sound(fluid_max_c=99.5), "outside applicability: fluid"),
        (_sound(re_outlet=2100.0), "outside applicability: Re"),
        (_sound(outlet_c=float("nan")), "non-finite"),
    ],
)
def test_each_failed_check_makes_the_reference_invalid(
    tmp_path, monkeypatch, final, reason
):
    result = _case(tmp_path, monkeypatch, _sound(), final)
    assert result["outcome"] == "REFERENCE_INVALID"
    assert any(reason in r for r in result["reasons"])


def test_an_undershoot_below_the_inlet_is_reported_not_judged(tmp_path, monkeypatch):
    final = _sound(fluid_min_c=37.5, inlet_undershoot_k=2.5)
    result = _case(tmp_path, monkeypatch, _sound(), final)
    assert result["outcome"] == "OK"
    assert result["checks"]["inlet_undershoot_k"] == 2.5


def test_a_run_that_left_nothing_readable_is_a_solver_failure(tmp_path):
    case_dir = tmp_path / "case"
    openfoam.write_case(NOMINAL, case_dir)
    result = analysis.analyze_case(case_dir)
    assert result["outcome"] == "REFERENCE_SOLVER_FAILED"
    (case_dir / "times").write_text("0\n4000\n")
    assert analysis.analyze_case(case_dir)["outcome"] == "REFERENCE_SOLVER_FAILED"


def test_the_field_reader_refuses_a_short_field(tmp_path):
    path = tmp_path / "T"
    path.write_text("internalField   nonuniform List<scalar>\n3\n(\n1\n2\n)\n;\n")
    with pytest.raises(ValueError):
        analysis.internal_field(path)
    path.write_text("internalField   nonuniform List<scalar>\n2\n(\n1\n2\n)\n;\n")
    assert analysis.internal_field(path) == [1.0, 2.0]


# --------------------------------------------------------------- runner


@pytest.fixture
def runner():
    return _load(
        "cold_plate_run_batch", "scripts/dev/cold_plate/reference/run_batch.py"
    )


def test_a_timeout_kills_only_the_cases_own_container(runner, monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    status, _, detail = runner.solve(tmp_path, "carbon-cold-plate-b-c1", 2, 5)
    assert status == "REFERENCE_TIMEOUT" and "5" in detail
    assert calls[-1] == ["docker", "kill", "carbon-cold-plate-b-c1"]
    run = calls[0]
    assert run[run.index("--network") + 1] == "none"
    assert run[run.index("--name") + 1] == "carbon-cold-plate-b-c1"
    assert openfoam.IMAGE in run


@pytest.mark.parametrize("code", sorted([125, 126, 127]))
def test_docker_that_cannot_start_is_infrastructure(
    runner, monkeypatch, tmp_path, code
):
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(command, code, "", "no"),
    )
    assert runner.solve(tmp_path, "n", 2, 5)[0] == "FAILED_INFRA"


def test_finished_commands_are_left_to_the_analysis(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(command, 1, "", ""),
    )
    assert runner.solve(tmp_path, "n", 2, 5)[0] is None


# ------------------------------------------------------------ population


def test_the_nominal_case_is_in_the_population_and_a_scorching_one_is_not():
    assert population.admitted(NOMINAL)
    scorching = {
        **NOMINAL,
        "channel_width_mm": 0.5,
        "channel_depth_mm": 1.0,
        "heat_load_w": 1500.0,
        "inlet_c": 45.0,
        "flow_lpm_per_kw": 1.25,
        "hotspot_ratio": 3.0,
    }
    admitted, reasons, _ = population.screen(scorching)
    assert not admitted and "hottest wall" in reasons[0]


def test_public_draws_are_reproducible_and_all_admitted():
    first, attempts = population.draw(population.public_rng("t"), 5)
    again, _ = population.draw(population.public_rng("t"), 5)
    assert first == again and attempts >= 5
    assert all(population.admitted(c) for c in first)
    assert first != population.draw(population.public_rng("u"), 5)[0]


def test_a_draw_that_cannot_finish_says_so():
    with pytest.raises(RuntimeError, match="admitted only"):
        population.draw(population.public_rng("t"), 5, max_attempts=3)


# ------------------------------------------------------------------ exam

UNIT_SCALES = {"s_peak": 1.0, "s_profile": 1.0, "s_log_dp": 1.0}


def _reference(case_id="c", **outputs):
    out = {
        "peak_c": 80.0,
        "mean_c": 70.0,
        "profile_c": [60.0 + i for i in range(30)],
        "outlet_c": 50.0,
        "pressure_drop_pa": 4000.0,
        **outputs,
    }
    out["peak_c"] = max(out["peak_c"], max(out["profile_c"]))
    return {"case_id": case_id, "status": "OK", "inputs": dict(NOMINAL), "outputs": out}


def _prediction(reference, **changes):
    pred = {k: reference["outputs"][k] for k in exam.SHAPES}
    pred.update(changes)
    return pred


def test_an_exact_prediction_passes_every_gate_and_scores_zero():
    ref = _reference()
    row = exam.score_case(_prediction(ref), ref, UNIT_SCALES, twin=_prediction(ref))
    assert row["state"] == exam.SCORABLE and row["error"] == 0.0
    assert set(row["gates"].values()) == {exam.PASS}


@pytest.mark.parametrize(
    "change, gate",
    [
        ({"profile_c": [float("nan")] * 30}, "schema_finite"),
        ({"profile_c": [60.0] * 29}, "schema_finite"),
        ({"peak_c": [80.0]}, "schema_finite"),
        ({"profile_c": [39.0] + [70.0] * 29}, "face_above_inlet"),
        ({"peak_c": 88.9}, "peak_bounds_profile"),
        ({"pressure_drop_pa": 0.0}, "pressure_drop_positive"),
    ],
)
def test_each_physical_law_has_a_gate(change, gate):
    ref = _reference()
    row = exam.evaluate_case(_prediction(ref, **change), ref)
    assert row["state"] == exam.GATE_FAILED and row["gates"][gate] == exam.FAIL


def test_a_duplicate_that_does_not_repeat_fails():
    ref = _reference()
    row = exam.evaluate_case(_prediction(ref), ref, twin=_prediction(ref, peak_c=89.5))
    assert row["gates"]["paired_repeat"] == exam.FAIL


def test_reference_and_infrastructure_failures_are_never_charged_to_a_model():
    ref = _reference()
    invalid = {**ref, "status": "REFERENCE_INVALID"}
    assert exam.evaluate_case(_prediction(ref), invalid)["state"] == (
        exam.REFERENCE_INVALID
    )
    assert exam.evaluate_case(None, ref)["state"] == exam.FAILED_INFRA
    rows = [
        exam.score_case(_prediction(ref), ref, UNIT_SCALES),
        exam.score_case(None, ref, UNIT_SCALES, infra_failed=True),
    ]
    result = exam.aggregate(rows)
    assert result["eligible"] and result["n_failed_infra"] == 1
    assert result["n_scored"] == 1


def test_one_failed_gate_makes_a_submission_ineligible_whatever_its_score():
    ref = _reference()
    good = [exam.score_case(_prediction(ref), ref, UNIT_SCALES) for _ in range(9)]
    bad = exam.score_case(_prediction(ref, pressure_drop_pa=-1.0), ref, UNIT_SCALES)
    result = exam.aggregate([*good, bad])
    assert result["score"] == 0.0 and not result["eligible"]
    assert result["gate_failures"] == {"pressure_drop_positive": 1}


def test_optimism_in_the_important_region_is_reported():
    ref = _reference(peak_c=95.0)
    row = exam.score_case(_prediction(ref, peak_c=93.0), ref, UNIT_SCALES)
    result = exam.aggregate([row])
    assert result["n_important"] == 1
    assert result["important_peak_bias_k"] == -2.0


def test_calibration_refuses_a_gate_a_sound_reference_breaks():
    refs = [_reference("a"), _reference("b", profile_c=[45.0] * 30)]
    assert exam.calibrate(refs)["n_references"] == 2
    with pytest.raises(ValueError, match="fails gates"):
        exam.calibrate([_reference("c", profile_c=[39.0] * 30)])
    with pytest.raises(ValueError, match="no OK reference"):
        exam.calibrate([{**_reference(), "status": "REFERENCE_INVALID"}])


def test_derived_outputs_are_the_profile_mean_and_the_energy_balance():
    ref = _reference()
    derived = domain.derived_outputs(NOMINAL, _prediction(ref))
    assert derived["mean_c"] == pytest.approx(sum(ref["outputs"]["profile_c"]) / 30)
    d = domain.derived(domain.check_inputs(NOMINAL))
    cp = domain.pg25("cp", domain.K0 + 40.0)
    expected = 40.0 + 1000.0 / (d["mass_flow_kg_s"] * cp)
    assert derived["outlet_c"] == pytest.approx(expected)


def test_feasibility_is_a_decision_property_not_a_gate():
    ref = _reference()
    tight = exam.feasibility(
        NOMINAL, ref["outputs"], die_limit_c=80.0, hydraulic_limit_w=1.0
    )
    assert not tight["feasible"]
    # The hottest segment (89 C) through the TIM at the uniform 1 kW flux.
    assert tight["die_peak_c"] == pytest.approx(89.0 + 1000 / 0.03**2 * 5e-6)
    assert tight["hydraulic_w"] == pytest.approx(4000.0 * 1.5e-3 / 60)
    assert exam.evaluate_case(_prediction(ref), ref)["state"] == exam.SCORABLE
