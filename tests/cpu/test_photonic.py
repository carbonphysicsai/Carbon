"""The photonic coupler Challenge's interface, reference arithmetic, baseline
and exam (#345).

The reference's arithmetic, the closed-form baseline and the exam are pure
Python and checked against closed forms. The mode solver needs numpy and
scipy (the `science-jax` group); its tests are skipped without them and run
on a coarse 40 nm mesh, so they check the formulation, not the reference's
accuracy (the tables' own checks and the pilot do that).
"""

from __future__ import annotations

import cmath
import hashlib
import importlib.util
import json
import math
from itertools import pairwise
from pathlib import Path

import pytest

from carbon.photonic import analytic, domain, exam, population, reference

REPOSITORY = Path(__file__).resolve().parents[2]
NOMINAL = dict(domain.NOMINAL)


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPOSITORY / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(split, mean):
    """Synthetic tables: split(g) and mean(g) on the ladder, every wavelength."""
    gaps = domain.ladder()
    row = {
        "n_even": [mean(g) + split(g) / 2 for g in gaps],
        "n_odd": [mean(g) - split(g) / 2 for g in gaps],
    }
    return gaps, {repr(wl): row for wl in domain.WAVELENGTHS_UM}


# ------------------------------------------------------------------ domain


@pytest.mark.parametrize(
    "change",
    [
        {"gap_nm": 149.9},
        {"length_um": 6.01},
        {"gap_nm": float("nan")},
        {"length_um": True},
        {"gap_nm": "200"},
    ],
)
def test_inputs_outside_the_box_or_of_the_wrong_type_are_refused(change):
    with pytest.raises(ValueError):
        domain.check_inputs({**NOMINAL, **change})


def test_inputs_must_be_exactly_the_two():
    with pytest.raises(ValueError, match="exactly"):
        domain.check_inputs({"gap_nm": 200.0})
    with pytest.raises(ValueError, match="exactly"):
        domain.check_inputs({**NOMINAL, "width_nm": 500.0})


def test_the_ladder_runs_from_the_smallest_gap_to_the_port_gap():
    gaps = domain.ladder()
    assert len(gaps) == domain.GAP_LADDER_COUNT
    assert gaps[0] == domain.INPUT_BOUNDS["gap_nm"][0] * 1e-3
    assert gaps[-1] == domain.PORT_PITCH_UM - domain.WIDTH_UM
    assert all(b > a for a, b in pairwise(gaps))
    # The refinement tables keep every fourth gap, ends included.
    assert len(gaps[::4]) == 11 and gaps[::4][-1] == gaps[-1]


# ------------------------------------------------------------- reference


def test_the_gap_profile_closes_from_the_ports_to_the_gap_and_back():
    g, length = 0.2, 3.0
    far = domain.PORT_PITCH_UM - domain.WIDTH_UM
    total = domain.BEND_LEFT_UM + length + domain.BEND_RIGHT_UM
    assert reference.gap_profile(0.0, g, length) == pytest.approx(far)
    assert reference.gap_profile(domain.BEND_LEFT_UM, g, length) == pytest.approx(g)
    assert reference.gap_profile(4.0, g, length) == g
    assert reference.gap_profile(total, g, length) == pytest.approx(far)
    zs = [i * total / 2000 for i in range(2001)]
    values = [reference.gap_profile(z, g, length) for z in zs]
    # No jump: no step exceeds the steepest bend's slope times the spacing.
    slope = (far - g) * math.pi / (2 * domain.BEND_RIGHT_UM)
    assert max(abs(b - a) for a, b in pairwise(values)) <= slope * total / 2000


def test_constant_indices_integrate_to_the_path_length_exactly():
    gaps, rows = _rows(lambda g: 0.01, lambda g: 2.4)
    out = reference.integrate(NOMINAL, gaps, rows)
    total = domain.BEND_LEFT_UM + NOMINAL["length_um"] + domain.BEND_RIGHT_UM
    for wl, cross, sigma in zip(
        domain.WAVELENGTHS_UM, out["cross_power"], out["common_phase_rad"]
    ):
        k0 = 2 * math.pi / wl
        assert sigma == pytest.approx(k0 * 2.4 * total, rel=1e-12)
        assert cross == pytest.approx(math.sin(k0 * 0.01 * total / 2) ** 2, rel=1e-10)


def test_an_exponential_splitting_is_integrated_without_interpolation_error():
    """Log-linear interpolation is exact for an exponential, so only the
    midpoint rule's error remains, checked against a fine quadrature."""

    def split(g):
        return 0.05 * math.exp(-(g - 0.15) / 0.12)

    gaps, rows = _rows(split, lambda g: 2.45)
    out = reference.integrate(NOMINAL, gaps, rows)
    gap, length = NOMINAL["gap_nm"] * 1e-3, NOMINAL["length_um"]
    total = domain.BEND_LEFT_UM + length + domain.BEND_RIGHT_UM
    n = 200000
    exact = sum(
        split(reference.gap_profile((i + 0.5) * total / n, gap, length))
        for i in range(n)
    ) * (total / n)
    k0 = 2 * math.pi / 1.55
    centre = domain.WAVELENGTHS_UM.index(1.55)
    assert out["cross_power"][centre] == pytest.approx(
        math.sin(k0 * exact / 2) ** 2, rel=1e-6
    )


def test_a_profile_outside_the_tables_is_refused():
    gaps, rows = _rows(lambda g: 0.01, lambda g: 2.4)
    short = {
        k: {"n_even": v["n_even"][:-1], "n_odd": v["n_odd"][:-1]}
        for k, v in rows.items()
    }
    with pytest.raises(ValueError, match="tabulated range"):
        reference.integrate(NOMINAL, gaps[:-1], short)


def test_the_s_parameters_carry_the_port_convention():
    outputs = {
        "cross_power": [0.0, 0.05, 0.3, 0.5, 1.0],
        "common_phase_rad": [100.0, 99.0, 98.0, 97.0, 96.0],
    }
    for (s31, s41), cross, sigma in zip(
        reference.s_parameters(outputs),
        outputs["cross_power"],
        outputs["common_phase_rad"],
    ):
        assert abs(s31) ** 2 + abs(s41) ** 2 == pytest.approx(1.0)
        assert abs(s41) ** 2 == pytest.approx(cross)
        if 0 < cross < 1:
            assert cmath.phase(s41 / s31) == pytest.approx(-math.pi / 2)
            assert cmath.phase(s31 * cmath.exp(1j * sigma)) == pytest.approx(
                0, abs=1e-12
            )


def test_tables_of_another_schema_or_that_failed_their_checks_are_refused(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"schema": "other"}))
    with pytest.raises(ValueError, match="schema"):
        reference.load_tables(path)
    gaps, rows = _rows(lambda g: 0.01, lambda g: 2.4)
    table = {
        "schema": reference.TABLE_SCHEMA,
        "status": "REFERENCE_INVALID",
        "gaps_um": gaps,
        "wavelengths": rows,
    }
    with pytest.raises(ValueError, match="failed"):
        reference.evaluate(NOMINAL, table)


# -------------------------------------------------------- committed tables


def _committed():
    if not reference.TABLES.exists():
        pytest.skip("tables not built")
    return reference.load_tables()


def test_the_committed_tables_passed_their_checks_and_cover_the_ladder():
    t = _committed()
    assert t["status"] == "OK" and t["reasons"] == []
    assert t["gaps_um"] == domain.ladder()
    assert set(t["wavelengths"]) == {repr(w) for w in domain.WAVELENGTHS_UM}
    assert t["width_um"] == domain.WIDTH_UM and t["n_si"] == domain.N_SI


def test_the_committed_tables_are_pinned_to_the_code_that_built_them():
    t = _committed()
    for path, digest in t["provenance"]["sources"].items():
        actual = hashlib.sha256((REPOSITORY / path).read_bytes()).hexdigest()
        assert digest == "sha256:" + actual, f"{path} changed: rebuild the tables"


def test_the_reference_passes_its_own_gates_at_the_box_corners():
    tables = _committed()
    refs = []
    for gap in domain.INPUT_BOUNDS["gap_nm"]:
        for length in domain.INPUT_BOUNDS["length_um"]:
            outputs = reference.evaluate({"gap_nm": gap, "length_um": length}, tables)
            refs.append(
                {"case_id": f"{gap}-{length}", "status": "OK", "outputs": outputs}
            )
    assert exam.calibrate(refs)["n_references"] == 4


# ---------------------------------------------------------------- analytic


def test_the_vertical_slab_is_rung_p1s_exact_slab():
    assert analytic.slab_te0(3.48, 1.444, 0.22, 1.55) == pytest.approx(
        2.851739, abs=1e-6
    )


def test_the_effective_index_supermodes_split_and_merge_with_the_gap():
    splits = []
    for gap in (0.15, 0.3, 0.6, 1.1):
        even, odd = analytic.indices(gap, 1.55)
        assert domain.N_OX < odd < even < 2.851739
        splits.append(even - odd)
    assert all(b < a for a, b in pairwise(splits))
    assert splits[-1] < 1e-4


def test_the_baseline_is_a_valid_prediction_but_not_the_reference():
    out = analytic.predict(NOMINAL)
    assert exam.gates(out)["cross_power_bounded"] == exam.PASS
    assert exam.gates(out)["phase_falls_with_wavelength"] == exam.PASS


# -------------------------------------------------------------- population


def test_public_draws_are_reproducible_from_their_label_and_inside_the_box():
    a = population.draw(population.public_rng("x"), 50)
    assert a == population.draw(population.public_rng("x"), 50)
    assert a != population.draw(population.public_rng("y"), 50)
    for case in a:
        domain.check_inputs(case)


# -------------------------------------------------------------------- exam


def _outputs(cross=0.06, sigma=105.0):
    return {
        "cross_power": [cross + 0.01 * i for i in range(5)],
        "common_phase_rad": [sigma - 1.7 * i for i in range(5)],
    }


def _reference(**kw):
    return {
        "case_id": "c",
        "status": "OK",
        "inputs": NOMINAL,
        "outputs": _outputs(**kw),
    }


@pytest.mark.parametrize(
    "prediction, gate",
    [
        ({"cross_power": [0.1] * 4, "common_phase_rad": [1.0] * 5}, "schema_finite"),
        (
            {**_outputs(), "cross_power": [0.1, 0.1, math.nan, 0.1, 0.1]},
            "schema_finite",
        ),
        ({**_outputs(), "cross_power": [True, 0.1, 0.1, 0.1, 0.1]}, "schema_finite"),
        ({"cross_power": [0.1] * 5}, "schema_finite"),
        (
            {**_outputs(), "cross_power": [0.1, 0.2, 1.01, 0.1, 0.1]},
            "cross_power_bounded",
        ),
        (
            {**_outputs(), "cross_power": [-0.01, 0.2, 0.1, 0.1, 0.1]},
            "cross_power_bounded",
        ),
        (
            {**_outputs(), "common_phase_rad": [100.0, 99.0, 99.0, 98.0, 97.0]},
            "phase_falls_with_wavelength",
        ),
    ],
)
def test_each_gate_fails_what_it_should(prediction, gate):
    row = exam.evaluate_case(prediction, _reference())
    assert row["state"] == exam.GATE_FAILED
    assert row["gates"][gate] == exam.FAIL


def test_the_twin_must_repeat_the_prediction():
    p = _outputs()
    assert exam.gates(p, twin=_outputs())["paired_repeat"] == exam.PASS
    assert exam.gates(p, twin=_outputs(cross=0.061))["paired_repeat"] == exam.FAIL


def test_an_exact_prediction_scores_zero_and_a_whole_turn_of_phase_is_invisible():
    ref = _reference()
    assert exam.score_case(_outputs(), ref)["error"] == pytest.approx(0, abs=1e-12)
    turned = _outputs(sigma=105.0 + 2 * math.pi)
    assert exam.score_case(turned, ref)["error"] == pytest.approx(0, abs=1e-9)


def test_a_phase_error_costs_what_its_chord_does():
    ref = _reference()
    row = exam.score_case(_outputs(sigma=105.1), ref)
    # |e^{-i(s+d)} - e^{-is}| = 2 sin(d/2) times each port's amplitude, and
    # the ports' powers sum to one.
    assert row["error"] == pytest.approx(2 * math.sin(0.05), rel=1e-9)
    assert row["errors"]["phase_rms_rad"] == pytest.approx(0.1)
    assert row["errors"]["cross_rms"] == pytest.approx(0, abs=1e-12)


def test_reference_invalid_and_infra_cases_are_typed_before_gates():
    assert exam.evaluate_case(_outputs(), {"status": "REFERENCE_INVALID"})["state"] == (
        exam.REFERENCE_INVALID
    )
    assert exam.evaluate_case(None, _reference())["state"] == exam.FAILED_INFRA


def test_the_aggregate_counts_states_and_one_gate_failure_makes_it_ineligible():
    rows = [
        exam.score_case(_outputs(), _reference()),
        exam.score_case(_outputs(cross=0.2), _reference(cross=0.2)),
        exam.score_case(None, _reference(), infra_failed=True),
        exam.score_case(_outputs(), {"case_id": "x", "status": "REFERENCE_INVALID"}),
    ]
    result = exam.aggregate(rows)
    assert (
        result["n_scored"],
        result["n_failed_infra"],
        result["n_reference_invalid"],
    ) == (
        2,
        1,
        1,
    )
    assert result["eligible"] and result["n_important"] == 1
    bad = {**_outputs(), "cross_power": [1.5] * 5}
    result = exam.aggregate(rows + [exam.score_case(bad, _reference())])
    assert not result["eligible"]
    assert result["gate_failures"] == {"cross_power_bounded": 1}


def test_calibration_refuses_a_reference_that_breaks_a_gate():
    broken = {**_reference(), "outputs": {**_outputs(), "cross_power": [1.2] * 5}}
    with pytest.raises(ValueError, match="fails gates"):
        exam.calibrate([_reference(), broken])
    with pytest.raises(ValueError, match="nothing"):
        exam.calibrate([{"status": "REFERENCE_INVALID"}])


def test_feasibility_is_a_decision_about_outputs_not_a_gate():
    out = _outputs(cross=0.03)  # 0.05 at 1.55 um, spread 0.04
    assert exam.feasibility(out, target=0.05, tolerance=0.01, flatness=0.05)["feasible"]
    assert not exam.feasibility(out, target=0.05, tolerance=0.01, flatness=0.03)[
        "feasible"
    ]
    assert not exam.feasibility(out, target=0.1, tolerance=0.01, flatness=0.05)[
        "feasible"
    ]


# --------------------------------------------------------- table builder


def test_the_table_checks_refuse_a_splitting_that_grows_with_the_gap():
    builder = _load("build_tables", "scripts/dev/photonic/build_tables.py")
    gaps = domain.ladder(5)
    good = {
        "n_even": [2.47, 2.46, 2.455, 2.452, 2.451],
        "n_odd": [2.43, 2.44, 2.445, 2.448, 2.4495],
        **{
            f"{f}_{m}": [v] * 5
            for f, v in (("te", 0.98), ("parity", 1.0), ("residual", 1e-13))
            for m in ("even", "odd")
        },
    }
    good["parity_odd"] = [-1.0] * 5
    table = {"gaps_um": gaps, "wavelengths": {"1.55": good}}
    assert builder._checks(table) == []
    bad = {**good, "n_odd": [2.43, 2.44, 2.445, 2.448, 2.446]}
    assert any(
        "monotone" in r
        for r in builder._checks({**table, "wavelengths": {"1.55": bad}})
    )
    mixed = {**good, "parity_even": [1.0, 1.0, 0.7, 1.0, 1.0]}
    assert any(
        "parity" in r
        for r in builder._checks({**table, "wavelengths": {"1.55": mixed}})
    )


# -------------------------------------------------------------- mode solver


@pytest.fixture
def solver():
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    from carbon.photonic import coupler, modes

    return coupler, modes


def test_the_strip_and_its_supermodes_on_a_coarse_mesh(solver):
    coupler, _ = solver
    even, odd, _ = coupler.supermodes(0.5, 0.5 + 0.2088, 1.55, 0.04)
    assert coupler.parity(even) == pytest.approx(1.0, abs=1e-6)
    assert coupler.parity(odd) == pytest.approx(-1.0, abs=1e-6)
    assert even.te_fraction > 0.9 and odd.te_fraction > 0.9
    # Rung P2 at 40 nm: 0.01826; the refined value is within a few percent.
    assert even.n_eff - odd.n_eff == pytest.approx(0.01826, rel=0.02)
    assert 2.43 < (even.n_eff + odd.n_eff) / 2 < 2.47


def test_the_port_convention_fixes_the_relative_phase_at_any_mesh(solver):
    coupler, _ = solver
    grid = coupler.Grid(step_um=0.04, z_points=400, separations=4)
    result = coupler.solve_case(0.5, 0.2088, 5.618, grid, wavelengths=(1.55,))[1.55]
    assert cmath.phase(result["s41"] / result["s31"]) == pytest.approx(-math.pi / 2)
    assert abs(result["s31"]) ** 2 + abs(result["s41"]) ** 2 == pytest.approx(1.0)
    assert result["port_power_check"] == pytest.approx(1.0, abs=1e-9)
    assert result["port_cross_overlap"] < 1e-3
