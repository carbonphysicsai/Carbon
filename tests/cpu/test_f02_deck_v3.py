"""Burst Thermal 3.0 deck (scripts/dev/reference_packages/elmer/f02_deck_v3.py), offline (no solver).

Claims: the pinned 2.5 deck is untouched and v3 reproduces its schedule, mesh and solver input exactly where v3 adds
nothing (r = 0, n = 1, 0.2 mm TIM, constant properties); the v3 waveform family is energy-exact; property tables
refuse a production deck while any is HUMAN_INPUT and synthetic tables are labelled TEST_ONLY on every output; a
nonlinear run that reaches its iteration limit is REFERENCE_INVALID; the new observers are exact on analytic series.
Every number here is a SYNTHETIC test value. The solver-side regression (constant tables on the 8 RR cases equal v2 within
1e-6 C) is the Data Collection dry run, not a test here."""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import shutil
from pathlib import Path

import pytest

from scripts.dev.reference_packages.elmer import f02_deck as v1
from scripts.dev.reference_packages.elmer import f02_deck_v3 as v3

PANELS = json.loads(v3.PANELS.read_text())["families"]["f02"]
CASES = {
    row["label"]: dict(zip(PANELS["panel_fields"], row["parameters"], strict=True))
    for row in PANELS["public_cases"]
}


def _wave(**changes):
    return {
        "peak_w": 120.0,
        "on_time_s": 10.0,
        "ramp_fraction": 0.0,
        "pulses": 1,
        **changes,
    }


# --- the waveform family ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(CASES))
def test_v3_reproduces_v2s_labelled_schedules_where_the_grid_is_exact(label):
    case = CASES[label]
    assert v3.schedule(case) == v1.schedule(
        case
    )  # an on-grid case: v2 and v1 knots are the same


def test_r0_n1_is_v2s_rectangle_r1_its_ramp_and_n2_its_two_pulse_exactly():
    base = {"peak_w": 111.0, "on_time_s": 7.25}
    rectangular = {**base, "waveform": "rectangular"}
    assert v3.schedule_v3(_wave(**base)) == v3.schedule_labelled(rectangular)
    ramp = {**base, "waveform": "ramp"}
    assert v3.schedule_v3(_wave(**base, ramp_fraction=1.0)) == v3.schedule_labelled(
        ramp
    )
    two = {**base, "waveform": "two-pulse"}
    assert v3.schedule_v3(_wave(**base, pulses=2, gap_s=10.0)) == v3.schedule_labelled(
        two
    )


def test_off_grid_on_times_keep_every_knot_on_the_six_decimal_grid():
    rng = random.Random(3)
    for _ in range(200):
        case = _wave(
            peak_w=rng.uniform(70, 150),
            on_time_s=rng.uniform(4, 20),
            ramp_fraction=rng.choice([0.0, rng.random(), 1.0]),
            pulses=(pulses := rng.choice([1, 2])),
            **({"gap_s": rng.uniform(5, 15)} if pulses == 2 else {}),
        )
        knots = v3.schedule_v3(case)
        # (a knot at an end + 1 us is a float sum of grid values, as in v2: rule 12 rounds before eps is added)
        assert all(abs(round(t, 6) - t) < 1e-9 for t, _ in knots)
        assert all(
            b[0] > a[0] for a, b in itertools.pairwise(knots)
        )  # strictly increasing


def test_the_energy_is_analytic_and_matches_numeric_integration_for_every_shape():
    rng = random.Random(11)
    for _ in range(300):
        pulses = rng.choice([1, 2])
        case = _wave(
            peak_w=rng.uniform(70, 150),
            on_time_s=rng.uniform(4, 20),
            ramp_fraction=rng.choice([0.0, rng.random(), 1.0]),
            pulses=pulses,
            **({"gap_s": rng.uniform(5, 15)} if pulses == 2 else {}),
        )
        knots = v3.schedule_v3(case)
        numeric = sum(
            (b - a) * ((pa + pb) / 2 - v3.BASE_W)
            for (a, pa), (b, pb) in itertools.pairwise(knots)
        )
        assert v3.energy_j(case) == pytest.approx(
            numeric, abs=2e-3
        )  # the 1 us slivers aside


@pytest.mark.parametrize(
    "changes",
    [
        {"ramp_fraction": -0.1},
        {"ramp_fraction": 1.5},
        {"ramp_fraction": True},
        {"pulses": 3},
        {"pulses": 2},  # a second pulse needs a gap
        {"gap_s": 5.0},  # a gap needs two pulses
        {"pulses": 2, "gap_s": 0.0},
        {"pulses": 2, "gap_s": 200.0},
        {"on_time_s": 500.0},
    ],
)
def test_a_waveform_outside_the_family_is_refused(changes):
    with pytest.raises(v3.DeckRefused):
        v3.schedule_v3(_wave(**changes))


def test_the_steps_still_land_on_every_event_for_a_v3_case():
    case = {**CASES["cool-rect-low"], **_wave(pulses=2, gap_s=8.0, ramp_fraction=0.4)}
    sizes, intervals = v3.time_steps(case)
    assert (
        abs(sum(s * n for s, n in zip(sizes, intervals, strict=True)) - v3.HORIZON_S)
        < 1e-9
    )


# --- the TIM thickness and the mesh ------------------------------------------------------------------------------


def _mesh_hashes(directory):
    return {
        name: hashlib.sha256((Path(directory) / "mesh" / name).read_bytes()).hexdigest()
        for name in ("mesh.header", "mesh.nodes", "mesh.elements", "mesh.boundary")
    }


@pytest.mark.parametrize("level", [1, 2])
def test_a_02_mm_tim_reproduces_v2s_mesh_byte_for_byte(tmp_path, level):
    v1.write_mesh(tmp_path / "one", level)
    v3.write_mesh(tmp_path / "three", level, tim_mm=0.2)
    assert _mesh_hashes(tmp_path / "one") == _mesh_hashes(tmp_path / "three")


def test_the_tim_thickness_moves_the_die_and_logs_the_cell_aspect(tmp_path):
    base = v3.write_mesh(tmp_path / "a", 1, tim_mm=0.2)
    thin = v3.write_mesh(tmp_path / "b", 1, tim_mm=0.1)
    thick = v3.write_mesh(tmp_path / "c", 1, tim_mm=0.4)
    assert (
        base["hexes"] == thin["hexes"] == thick["hexes"]
    )  # the TIM keeps its cell count
    assert (
        thin["tim_cell_aspect"] > base["tim_cell_aspect"] > thick["tim_cell_aspect"] > 0
    )
    top = {
        name: max(
            float(line.split()[4])
            for line in (tmp_path / name / "mesh" / "mesh.nodes")
            .read_text()
            .splitlines()
        )
        for name in "abc"
    }
    assert top["b"] == pytest.approx(2.0e-3 + 0.1e-3 + 0.5e-3)
    assert top["c"] == pytest.approx(2.0e-3 + 0.4e-3 + 0.5e-3)
    for bad in (0, -1, 0.0, True, 99):
        with pytest.raises(v3.DeckRefused):
            v3.check_tim_mm(bad)


# --- the solver input ------------------------------------------------------------------------------------------


def _text(case, **kwargs):
    sizes, intervals = v3.time_steps(case)
    return v3.sif(case, sizes, intervals, **kwargs)


@pytest.mark.parametrize("label", sorted(CASES))
def test_with_constant_properties_the_solver_input_is_v2s_apart_from_the_comment(label):
    case = CASES[label]
    sizes, intervals = v1.time_steps(case)
    old = v1.sif(case, sizes, intervals)
    new = _text(case)
    assert (
        new == old
    )  # the same header line, the same bytes: v3 adds nothing for constants


def test_a_constant_table_turns_the_nonlinear_path_on_and_only_changes_what_it_must():
    case = CASES["warm-ramp-high"]
    tables = {
        "copper": {"k": [(280.0, 390.0), (420.0, 390.0)], "cp": 385.0},
        "die": {
            "k": [(280.0, 130.0), (420.0, 130.0)],
            "cp": [(280.0, 700.0), (420.0, 700.0)],
        },
    }
    materials, label = v3.resolve_materials(tables, test_mode=True)
    assert label == "TEST_ONLY"
    text = _text(case, materials=materials, label=label)
    assert text.startswith(
        "! f02 deck v3: tables TEST_ONLY; nonlinear ON, max iterations 50"
    )
    assert "Nonlinear System Convergence Tolerance" in text
    assert "Heat Conductivity = Variable Temperature" in text
    assert "Heat Capacity = Variable Temperature" in text
    # the TIM stays a constant, explicit
    assert "Heat Conductivity = 5.0\n" in text
    # collapsing each constant table back to its number gives v2's input except the nonlinear lines and the header
    collapsed = text
    for name in ("Heat Conductivity", "Heat Capacity"):
        for value in ("390.0", "130.0", "700.0"):
            table = f"  {name} = Variable Temperature\n    Real\n      280.0 {value}\n      420.0 {value}\n    End\n"
            collapsed = collapsed.replace(table, f"  {name} = {value}\n")
    collapsed = collapsed.replace(
        "  Nonlinear System Max Iterations = 50\n  Nonlinear System Convergence Tolerance = 1e-08\n",
        "  Nonlinear System Max Iterations = 1\n",
    )
    sizes, intervals = v1.time_steps(case)
    assert (
        collapsed.split("\n", 1)[1] == v1.sif(case, sizes, intervals).split("\n", 1)[1]
    )


def test_a_human_input_table_refuses_a_production_deck_and_synthetic_tables_are_labelled(
    tmp_path,
):
    case = CASES["cool-rect-low"]
    with pytest.raises(v3.DeckRefused, match="property_table_human_input"):
        v3.write_case(case, tmp_path / "p", production=True)
    with pytest.raises(v3.DeckRefused, match="human_input"):
        v3.resolve_materials(
            {"die": {"k": v3.HUMAN_INPUT, "cp": 700.0}}, test_mode=True
        )
    with pytest.raises(v3.DeckRefused, match="test_mode_or_production"):
        v3.resolve_materials({"die": {"k": 130.0}})
    with pytest.raises(v3.DeckRefused, match="cannot_use_test_tables"):
        v3.resolve_materials({"die": {"k": 130.0}}, production=True, test_mode=True)
    tables = {"die": {"k": [(280.0, 140.0), (420.0, 110.0)], "cp": 700.0}}
    meta = v3.write_case(case, tmp_path / "t", tables=tables, test_mode=True)
    assert meta["tables"] == "TEST_ONLY" and meta["nonlinear"]["max_iterations"] == 50
    assert (
        json.loads((tmp_path / "t" / "deck.json").read_text())["tables"] == "TEST_ONLY"
    )
    assert (
        (tmp_path / "t" / "case.sif")
        .read_text()
        .startswith("! f02 deck v3: tables TEST_ONLY")
    )


@pytest.mark.parametrize(
    "table",
    [
        [(300.0, 1.0)],
        [(300.0, 1.0), (300.0, 2.0)],
        [(400.0, 1.0), (300.0, 2.0)],
        [(300.0, -1.0), (400.0, 2.0)],
        [(300.0, float("nan")), (400.0, 2.0)],
        "not a table",
    ],
)
def test_a_malformed_property_table_is_refused(table):
    with pytest.raises(v3.DeckRefused):
        v3.resolve_materials({"die": {"k": table}}, test_mode=True)


def test_interpolation_and_the_enthalpy_integral_are_exact_for_a_piecewise_linear_table():
    table = [(300.0, 100.0), (400.0, 200.0)]
    assert v3.interpolate(table, 350.0) == pytest.approx(150.0)
    assert (
        v3.interpolate(table, 100.0) == 100.0 and v3.interpolate(table, 900.0) == 200.0
    )
    assert v3.integral(table, 300.0, 400.0) == pytest.approx(15000.0)
    assert v3.integral(table, 400.0, 300.0) == pytest.approx(-15000.0)
    assert v3.integral(table, 350.0, 450.0) == pytest.approx(
        (150 + 200) / 2 * 50 + 200 * 50
    )
    assert v3.integral(385.0, 300.0, 310.0) == pytest.approx(3850.0)


def test_the_import_works_at_any_install_depth(tmp_path):
    import importlib.util

    shallow = tmp_path / "f02_deck_v3.py"
    shutil.copy(v3.__file__, shallow)
    spec = importlib.util.spec_from_file_location("f02_deck_v3_shallow", shallow)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # v2 raised IndexError here (parents[4])
    assert module.schedule_v3(_wave())[0] == (0, module.BASE_W)


# --- the observers ---------------------------------------------------------------------------------------------


def _case_dir(tmp_path, series, *, case=None, tables="CONSTANT", nonlinear=None):
    """A solved-deck stand-in: the scalars file the solver would write, and the deck record."""
    case = case or {**CASES["cool-rect-low"], **_wave()}
    directory = tmp_path / "case"
    directory.mkdir()
    (directory / "scalars.dat").write_text(
        "\n".join(f"{t!r} {v + 273.15!r} {v!r}" for t, v in series) + "\n"
    )
    (directory / "scalars.dat.names").write_text(
        "   1: time\n   2: boundary max: temperature\n   3: value: temperature at node 1\n"
    )
    schedule = v3.schedule(case)
    (directory / "deck.json").write_text(
        json.dumps(
            {
                "case": case,
                "schedule_w": schedule,
                "tables": tables,
                "nonlinear": nonlinear,
            }
        )
    )
    return directory


TRIANGLE = [(0.0, 40.0), (10.0, 40.0), (20.0, 100.0), (30.0, 40.0), (120.0, 40.0)]


def test_time_above_recovery_and_second_pulse_peak_on_an_analytic_series(tmp_path):
    case = {**CASES["cool-rect-low"], **_wave(pulses=2, gap_s=8.0, on_time_s=10.0)}
    # first pulse 20..25 s, gap to 33 s, second pulse 33..38 s
    series = [
        (0.0, 40.0),
        (20.0, 40.0),
        (25.0, 100.0),
        (33.0, 60.0),
        (38.0, 120.0),
        (60.0, 40.0),
        (120.0, 40.0),
    ]
    directory = _case_dir(tmp_path, series, case=case)
    out = v3.observe_v3(directory, threshold_c=90.0)
    assert (
        out["status"] == "OK"
        and out["tables"] == "CONSTANT"
        and out["threshold_c"] == 90.0
    )
    # above 90 C: up-crossing at 20 + 5 * 50/60, down to 60 by 33 (crosses 90 at 25 + 8 * 10/40), then up again
    first_up = 20 + 5 * 50 / 60
    first_down = 25 + 8 * (100 - 90) / 40
    second_up = 33 + 5 * 30 / 60
    last_down = 38 + 22 * 30 / 80
    above = (first_down - first_up) + (last_down - second_up)
    assert out["time_above_s"] == pytest.approx(above)
    assert out["threshold_recovery_s"] == pytest.approx(last_down - second_up)
    assert out["second_pulse_peak_c"] == 120.0
    assert out["peak_top_c"] == 120.0


def test_a_never_reached_threshold_and_a_still_hot_end_are_told_apart(tmp_path):
    cool = _case_dir(tmp_path, [(0.0, 40.0), (120.0, 50.0)])
    out = v3.observe_v3(cool, threshold_c=90.0)
    assert out["time_above_s"] == 0.0 and out["threshold_recovery_s"] is None
    assert out["second_pulse_peak_c"] is None  # one pulse
    other = tmp_path / "o"
    other.mkdir()
    hot = _case_dir(other, [(0.0, 40.0), (50.0, 95.0), (120.0, 96.0)])
    assert (
        v3.observe_v3(hot, threshold_c=90.0)["threshold_recovery_s"] == "NOT_RECOVERED"
    )


@pytest.mark.parametrize("bad", [None, float("nan"), True, "90"])
def test_the_threshold_is_a_parameter_with_no_default(tmp_path, bad):
    directory = _case_dir(tmp_path, TRIANGLE)
    with pytest.raises(v3.DeckRefused, match="threshold_required"):
        v3.observe_v3(directory, threshold_c=bad)
    with pytest.raises(TypeError):
        v3.observe_v3(directory)  # type: ignore[call-arg]


def _log(tmp_path, steps, name="solver.log"):
    lines = []
    for iterations, final in steps:
        for i in range(1, iterations + 1):
            change = final if i == iterations else 10.0 ** (-i)
            lines.append(
                f"ComputeChange: NS (ITER={i}) (NRM,RELC): ( 3.4E+02  {change:.3E} ) :: heat equation"
            )
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    return path


def test_a_nonlinear_run_that_reaches_its_limit_is_reference_invalid_never_ok(tmp_path):
    settings = {"max_iterations": 8, "tolerance": 1e-8}
    directory = _case_dir(tmp_path, TRIANGLE, tables="TEST_ONLY", nonlinear=settings)
    good = _log(tmp_path, [(3, 1e-10), (4, 1e-9), (2, 1e-12)], "good.log")
    ok = v3.observe_v3(directory, threshold_c=90.0, log_path=good)
    assert ok["status"] == "OK" and ok["tables"] == "TEST_ONLY"
    assert ok["reference"]["max_iterations_seen"] == 4 and ok["reference"]["steps"] == 3
    bad = _log(tmp_path, [(3, 1e-10), (8, 1e-3)], "bad.log")
    out = v3.observe_v3(directory, threshold_c=90.0, log_path=bad)
    assert out["status"] == "REFERENCE_INVALID"
    assert out["reference"]["reason"] == "nonlinear_iteration_limit_reached"
    assert (
        "peak_top_c" not in out and "time_above_s" not in out
    )  # no valid-looking numbers
    # reaching the limit AT the tolerance is converged, not invalid
    edge = _log(tmp_path, [(8, 1e-9)], "edge.log")
    assert v3.observe_v3(directory, threshold_c=90.0, log_path=edge)["status"] == "OK"
    empty = tmp_path / "empty.log"
    empty.write_text("nothing here\n")
    assert (
        v3.observe_v3(directory, threshold_c=90.0, log_path=empty)["status"]
        == "REFERENCE_INVALID"
    )
    with pytest.raises(v3.DeckRefused, match="solver_log_required"):
        v3.observe_v3(directory, threshold_c=90.0)
    with pytest.raises(v3.DeckRefused, match="solver_log_required"):
        v3.observe_v3(directory, threshold_c=90.0, log_path=tmp_path / "missing.log")


def test_the_half_second_selector_works_by_step_index_off_the_grid():
    # on a 0.02 s grid every multiple of 0.5 is a row: v2's and the new selector agree
    t = [round(i * 0.02, 6) for i in range(6001)]
    old = [i for i, ti in enumerate(t) if abs(ti * 2 - round(ti * 2)) < 1e-6]
    assert v3.half_second_samples(t) == old
    # an off-grid step plan (events at 20.0000003, steps of 0.0233...): v2 drops samples, the new one does not
    ragged = []
    now = 0.0
    while now < 30.0:
        ragged.append(now)
        now += 0.0233
    ragged.append(30.0)
    kept = [ragged[i] for i in v3.half_second_samples(ragged)]
    assert len(kept) == 61
    assert all(abs(k - m / 2) <= 0.0233 / 2 + 1e-9 for m, k in enumerate(kept))
    assert (
        len([ti for ti in ragged if abs(ti * 2 - round(ti * 2)) < 1e-6]) < 61
    )  # v2's selector lost some


def test_the_pinned_v2_deck_is_not_edited():
    # the pinned 2.5 deck keeps its documented sha (deck_v1): v3 is a new file beside it
    digest = hashlib.sha256(Path(v1.__file__).read_bytes()).hexdigest()
    assert digest == "70d51aba555456bdf0cd7dcfa341d665201284955bbdab49273bf14c6d1fb4b4"
