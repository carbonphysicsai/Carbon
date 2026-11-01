"""Burst Thermal 3.0 deck: the temperature-dependent LEAKAGE heat source (OWNER choice A), offline (no solver).

Claims: with leakage OFF every deck is byte-identical to the receipted deck v3 (pinned digests of the unmodified code); a
coefficient file is digest-pinned, TEST_ONLY coefficients cannot enter production and signed ones need their pinned digest;
the law and its Elmer table are exact; the source is a body force on the die only, inside the nonlinear iteration, present
whenever powered; non-convergence with leakage on is ``thermal_runaway`` and a solution past the law's range is
``out_of_property_range``, never a number; the lumped control (constant coefficient, steady) closes the energy balance in
closed form. Every coefficient here is a SYNTHETIC test value."""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import pytest

from scripts.dev.reference_packages.elmer import f02_deck_v3 as v3

PANELS = json.loads(v3.PANELS.read_text())["families"]["f02"]
CASES = {
    row["label"]: dict(zip(PANELS["panel_fields"], row["parameters"], strict=True))
    for row in PANELS["public_cases"]
}
LABELLED = CASES[min(CASES)]
V3 = {
    "peak_w": 120.0,
    "on_time_s": 10.0,
    "ramp_fraction": 0.0,
    "pulses": 1,
    "h_w_m2_k": LABELLED["h_w_m2_k"],
    "coolant_c": LABELLED["coolant_c"],
    "start_offset_c": 5.0,
    "left_source_fraction": LABELLED["left_source_fraction"],
}
TABLES = {
    "copper": {
        "k": [(250.0, 400.0), (500.0, 380.0)],
        "cp": [(250.0, 380.0), (500.0, 400.0)],
    },
    "die": {"k": [(250.0, 160.0), (500.0, 90.0)], "cp": 420.0},
}

#: sha256 of case.sif and deck.json written by the deck BEFORE the leakage term existed (claude/f02-v3-deck 86569402).
OFF_PINS = {
    "labelled": (
        {"case": LABELLED},
        "efca1eace148d5c4e8a142b1514364bec8f25e0b72ffe9802a900e17eafe4dba",
        "922548cfeba1865558475d5d64a75596eae17001e93f47d29cb16e9283a199c3",
    ),
    "constant": (
        {"case": V3},
        "468ebbffaaa1aba41cbdb356c0d84bfcd7a075e274da7ea18b575128e26b2a22",
        "b7a4d55f343625877573495aa4e4aac72c97e0615db5606a7008118958e6a4c6",
    ),
    "tables": (
        {"case": V3, "tables": TABLES, "test_mode": True},
        "ef432f15138781a497ad39d6954628d8f81edabfce72ea8bf113c13977544d6f",
        "ffb183d1451ad75fff28eda353acf4e125703a11724cafeeb95a0244fa01f94d",
    ),
    "source_off": (
        {"case": V3, "source": False},
        "dce284c1300fea4816486c7ce4e59720300c240a7246bb8d8616171b22ab581b",
        "17416392e2cd09357e4f0b44f6b272b78f5f634d2fc914d02c8eef241df11ac1",
    ),
    "steady": (
        {"case": V3, "steady": True},
        "beeea9db4da5c6ffcbd8966916f3fcefb42d09d6dc7aef742869d3cfb2f4cd32",
        "e0b6e9c34119b2d1e84208c2adac1b9b44b6adfc19166e0478893c540d822e49",
    ),
}


def _sha(path):
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _file(tmp_path, name="leak.json", **over):
    doc = {
        "schema": v3.LEAKAGE_SCHEMA,
        "decision": "TEST_ONLY",
        "source": "synthetic test coefficients",
        "form": "constant",
        "range_k": [250.0, 500.0],
        "q_w_per_m3": 5.0e6,
    }
    doc.update(over)
    doc = {k: v for k, v in doc.items() if v is not None}
    path = tmp_path / name
    path.write_text(json.dumps(doc))
    return path


def _leak(tmp_path, **over):
    return v3.load_leakage(_file(tmp_path, **over), test_mode=True)


EXPONENTIAL = {
    "form": "exponential",
    "q_w_per_m3": None,
    "q_ref_w_per_m3": 4.0e6,
    "t_ref_k": 300.0,
    "beta_per_k": 0.02,
}
TABLE = {
    "form": "table",
    "q_w_per_m3": None,
    "range_k": [280.0, 400.0],
    "points": [[280.0, 1.0e6], [340.0, 3.0e6], [400.0, 9.0e6]],
}


# --- leakage OFF is the receipted deck, byte for byte ------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(OFF_PINS))
def test_with_leakage_off_the_deck_is_byte_identical_to_the_receipted_one(
    tmp_path, name
):
    kwargs, sif_sha, meta_sha = OFF_PINS[name]
    v3.write_case(**kwargs, out=tmp_path / "a")
    v3.write_case(**kwargs, leakage=None, out=tmp_path / "b")
    for directory in ("a", "b"):
        assert _sha(tmp_path / directory / "case.sif") == sif_sha
        assert _sha(tmp_path / directory / "deck.json") == meta_sha
    assert "Body Force" not in (tmp_path / "a" / "case.sif").read_text()
    assert "leakage" not in json.loads((tmp_path / "a" / "deck.json").read_text())


# --- the coefficient file ----------------------------------------------------------------------------------------


def test_a_test_only_file_loads_only_in_test_mode_and_is_labelled(tmp_path):
    path = _file(tmp_path)
    with pytest.raises(v3.DeckRefused, match="refuse_production"):
        v3.load_leakage(path)
    leak = v3.load_leakage(path, test_mode=True)
    assert leak["label"] == "TEST_ONLY" and leak["form"] == "constant"
    assert leak["sha256"] == "sha256:" + _sha(path) and leak["range_k"] == (
        250.0,
        500.0,
    )


def test_signed_coefficients_need_their_pinned_digest_and_a_changed_file_is_refused(
    tmp_path,
):
    path = _file(tmp_path, decision="OWNER-F02-V3-LEAKAGE-SIGNED-01")
    with pytest.raises(v3.DeckRefused, match="need_a_pinned_digest"):
        v3.load_leakage(path)
    leak = v3.load_leakage(path, expect_sha256=_sha(path))
    assert leak["label"] == "REGISTERED"
    path.write_text(path.read_text().replace("5000000.0", "5000001.0"))
    with pytest.raises(v3.DeckRefused, match="digest_differs"):
        v3.load_leakage(path, expect_sha256=leak["sha256"].split(":")[1])


@pytest.mark.parametrize(
    "over,code",
    [
        ({"schema": "other"}, "leakage_schema"),
        ({"form": "polynomial"}, "leakage_form"),
        ({"decision": ""}, "decision_and_source"),
        ({"source": None}, "decision_and_source"),
        ({"q_w_per_m3": -1.0}, "coefficients_invalid"),
        ({"q_w_per_m3": float("nan")}, "coefficients_invalid"),
        ({"range_k": [500.0, 250.0]}, "range_invalid"),
        ({"range_k": [0.0, 250.0]}, "range_invalid"),
        ({"extra": 1}, "leakage_fields"),
        (
            {**EXPONENTIAL, "t_ref_k": -1.0},
            "coefficients_invalid",
        ),
        (
            {**TABLE, "points": [[280.0, 1.0], [270.0, 2.0]]},
            "table_invalid",
        ),
        (
            {**TABLE, "points": [[280.0, -1.0], [400.0, 2.0]]},
            "table_invalid",
        ),
        ({**TABLE, "range_k": [280.0, 390.0]}, "range_is_the_tables_span"),
    ],
)
def test_a_malformed_coefficient_file_is_refused(tmp_path, over, code):
    with pytest.raises(v3.DeckRefused, match=code):
        _leak(tmp_path, **over)


def test_a_file_that_is_not_json_is_refused(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("{")
    with pytest.raises(v3.DeckRefused, match="not_json"):
        v3.load_leakage(path, test_mode=True)


# --- the law and its Elmer table -----------------------------------------------------------------------------------


def test_the_density_is_exact_for_each_form_and_refuses_outside_the_range(tmp_path):
    constant = _leak(tmp_path)
    assert v3.leakage_density(constant, 300.0) == 5.0e6
    expo = _leak(tmp_path, **EXPONENTIAL)
    assert v3.leakage_density(expo, 300.0) == pytest.approx(4.0e6, rel=1e-15)
    assert v3.leakage_density(expo, 350.0) == pytest.approx(
        4.0e6 * math.exp(0.02 * 50.0), rel=1e-15
    )
    table = _leak(tmp_path, **TABLE)
    assert v3.leakage_density(table, 310.0) == pytest.approx(2.0e6, rel=1e-15)
    assert v3.leakage_density(table, 400.0) == 9.0e6
    for leak, bad in ((constant, 249.0), (expo, 501.0), (table, 279.0)):
        with pytest.raises(v3.DeckRefused, match="out_of_property_range"):
            v3.leakage_density(leak, bad)


def test_elmers_heat_source_is_per_kg_and_sampled_on_the_range(tmp_path):
    rho = 2330.0
    constant = v3.leakage_table_w_per_kg(_leak(tmp_path), rho)
    assert constant == [(250.0, 5.0e6 / rho), (500.0, 5.0e6 / rho)]
    expo = _leak(tmp_path, **EXPONENTIAL)
    sampled = v3.leakage_table_w_per_kg(expo, rho)
    assert len(sampled) == 251 and sampled[0][0] == 250.0 and sampled[-1][0] == 500.0
    assert all(
        b[0] - a[0] == pytest.approx(1.0) for a, b in itertools.pairwise(sampled)
    )
    assert sampled[50] == (300.0, pytest.approx(4.0e6 / rho, rel=1e-15))
    table = v3.leakage_table_w_per_kg(_leak(tmp_path, **TABLE), rho)
    assert [t for t, _ in table] == [280.0, 340.0, 400.0]
    assert table[1][1] == 3.0e6 / rho


# --- the solver input ------------------------------------------------------------------------------------------------


def test_the_source_is_a_body_force_on_the_die_only_inside_the_nonlinear_iteration(
    tmp_path,
):
    leak = _leak(tmp_path)
    meta = v3.write_case(V3, tmp_path / "d", leakage=leak)
    text = (tmp_path / "d" / "case.sif").read_text()
    assert "Body Force 1\n  Heat Source = Variable Temperature\n    Real\n" in text
    import re

    bodies = dict(re.findall(r"Body (\d)\n(.*?)\nEnd\n", text, re.DOTALL))
    assert bodies.keys() == {"1", "2", "3"}
    assert "Body Force = 1" in bodies["3"]
    assert "Body Force" not in bodies["1"] and "Body Force" not in bodies["2"]
    # constant materials, yet the nonlinear iteration is on, with v3's recorded settings
    assert f"Nonlinear System Max Iterations = {v3.NONLINEAR_MAX_ITERATIONS}" in text
    assert meta["nonlinear"] == {
        "max_iterations": v3.NONLINEAR_MAX_ITERATIONS,
        "tolerance": v3.NONLINEAR_TOLERANCE,
    }
    assert f"! leakage: TEST_ONLY constant {leak['sha256']}" in text
    # the table is the per-kg law: 5e6 / 2330 at both knots
    assert f"250.0 {5.0e6 / 2330.0!r}" in text and f"500.0 {5.0e6 / 2330.0!r}" in text
    # the surface power (the waveform) is untouched
    off = v3.write_case(V3, tmp_path / "o")
    assert (
        "Heat Flux = Variable Time" in text and off["schedule_w"] == meta["schedule_w"]
    )


def test_the_deck_records_the_law_labels_everything_test_only_and_intersects_the_window(
    tmp_path,
):
    leak = _leak(tmp_path, range_k=[280.0, 450.0])
    meta = v3.write_case(V3, tmp_path / "a", leakage=leak)
    assert meta["tables"] == "TEST_ONLY"
    assert meta["property_range_k"] == (280.0, 450.0) or meta["property_range_k"] == [
        280.0,
        450.0,
    ]
    assert meta["leakage"]["sha256"] == leak["sha256"]
    assert (
        meta["leakage"]["label"] == "TEST_ONLY"
        and meta["leakage"]["form"] == "constant"
    )
    both = v3.write_case(
        V3, tmp_path / "b", tables=TABLES, test_mode=True, leakage=leak
    )
    assert list(both["property_range_k"]) == [280.0, 450.0]  # tables span 250-500


def test_leakage_needs_the_powered_die_and_a_test_law_never_enters_production(tmp_path):
    leak = _leak(tmp_path)
    for kwargs in ({"source": False}, {"slab": True}):
        with pytest.raises(v3.DeckRefused, match="needs_the_powered_die"):
            v3.write_case(V3, tmp_path / "x", leakage=leak, **kwargs)
    with pytest.raises(v3.DeckRefused, match="test_leakage"):
        v3.write_case(V3, tmp_path / "y", leakage=leak, production=True)


def test_a_steady_deck_carries_the_leakage_too(tmp_path):
    meta = v3.write_case(V3, tmp_path / "s", steady=True, leakage=_leak(tmp_path))
    assert meta["steady"] is True and meta["leakage"]["form"] == "constant"
    assert "Body Force = 1" in (tmp_path / "s" / "case.sif").read_text()


# --- the observers: runaway and range, never a number ------------------------------------------------------------


def _solved(tmp_path, series, leak, *, range_k=None):
    directory = tmp_path / "solved"
    meta = v3.write_case({**V3, "ramp_fraction": 0.0}, directory, leakage=leak)
    rows = "\n".join(f"{t!r} {v + 273.15!r} {v!r}" for t, v in series)
    (directory / "scalars.dat").write_text(rows + "\n")
    (directory / "scalars.dat.names").write_text(
        "   1: time\n   2: boundary max: temperature\n   3: value: temperature at node 1\n"
    )
    return directory, meta


def _log(tmp_path, steps):
    lines = []
    for iterations, final in steps:
        for i in range(1, iterations + 1):
            change = final if i == iterations else 10.0**-i
            lines.append(
                f"ComputeChange: NS (ITER={i}) (NRM,RELC): ( 3.4E+02  {change:.3E} ) :: heat equation"
            )
    path = tmp_path / "solver.log"
    path.write_text("\n".join(lines) + "\n")
    return path


SERIES = [(0.0, 40.0), (50.0, 100.0), (120.0, 45.0)]


def test_a_converged_leaking_run_is_ok_and_labelled(tmp_path):
    leak = _leak(tmp_path)
    directory, _meta = _solved(tmp_path, SERIES, leak)
    out = v3.observe_v3(
        directory, threshold_c=90.0, log_path=_log(tmp_path, [(4, 1e-10)] * 3)
    )
    assert out["status"] == "OK" and out["tables"] == "TEST_ONLY"
    assert out["leakage"] == {"label": "TEST_ONLY", "sha256": leak["sha256"]}


def test_non_convergence_with_leakage_on_is_thermal_runaway_never_a_number(tmp_path):
    directory, _meta = _solved(tmp_path, SERIES, _leak(tmp_path))
    limit = v3.NONLINEAR_MAX_ITERATIONS
    out = v3.observe_v3(
        directory,
        threshold_c=90.0,
        log_path=_log(tmp_path, [(3, 1e-10), (limit, 1e-3)]),
    )
    assert out["status"] == "REFERENCE_INVALID"
    assert out["reference"]["reason"] == "thermal_runaway"
    assert "peak_top_c" not in out and "time_above_s" not in out
    # without leakage the same log keeps v3's own reason
    plain = tmp_path / "plain"
    v3.write_case({**V3}, plain, tables=TABLES, test_mode=True)
    (plain / "scalars.dat").write_text("0.0 313.15 40.0\n50.0 373.15 100.0\n")
    (plain / "scalars.dat.names").write_text(
        "   1: time\n   2: boundary max: temperature\n   3: value: temperature at node 1\n"
    )
    out = v3.observe_v3(
        plain, threshold_c=90.0, log_path=_log(tmp_path, [(limit, 1e-3)])
    )
    assert out["reference"]["reason"] == "nonlinear_iteration_limit_reached"


def test_a_solution_past_the_leakage_range_is_out_of_property_range(tmp_path):
    leak = _leak(tmp_path, range_k=[280.0, 400.0])  # 400 K = 126.85 C
    directory, _meta = _solved(
        tmp_path, [(0.0, 40.0), (50.0, 140.0), (120.0, 45.0)], leak
    )
    out = v3.observe_v3(
        directory, threshold_c=90.0, log_path=_log(tmp_path, [(3, 1e-10)] * 3)
    )
    assert out["status"] == "REFERENCE_INVALID"
    assert out["reference"]["reason"] == "out_of_property_range"
    assert "peak_top_c" not in out


# --- the lumped control ------------------------------------------------------------------------------------------------


def _steady_rows(directory, bottom_int):
    (directory / "scalars.dat").write_text(f"0.0 330.0 {bottom_int!r}\n")
    (directory / "scalars.dat.names").write_text(
        "   1: time\n   2: boundary max: temperature\n   3: boundary int: temperature bc 1\n"
    )


def test_the_lumped_control_closes_the_energy_balance_in_closed_form(tmp_path):
    leak = _leak(tmp_path)  # constant 5e6 W/m^3
    directory = tmp_path / "lumped"
    v3.write_case(V3, directory, steady=True, leakage=leak)
    meta = json.loads((directory / "deck.json").read_text())
    h, tc = meta["case"]["h_w_m2_k"], meta["case"]["coolant_c"] + 273.15
    area = (2 * v3.LAYERS["copper"][0] * v3.MM) ** 2
    heat = v3.BASE_W + 5.0e6 * v3.die_volume_m3()
    assert v3.die_volume_m3() == pytest.approx(0.02 * 0.02 * 0.5e-3, rel=1e-15)
    exact = (
        tc + heat / (h * area)
    ) * area  # the underside integral that carries exactly `heat`
    _steady_rows(directory, exact)
    result = v3.lumped_control(directory)
    assert result["heat_in_w"] == pytest.approx(heat, rel=1e-15)
    assert abs(result["residual_rel"]) < 1e-12
    assert result["mean_underside_k"] == pytest.approx(
        result["expected_mean_underside_k"], rel=1e-12
    )
    _steady_rows(directory, exact * 1.001)
    assert abs(v3.lumped_control(directory)["residual_rel"]) > 1e-4


def test_the_lumped_control_applies_only_to_steady_constant_leakage(tmp_path):
    transient = tmp_path / "t"
    v3.write_case(V3, transient, leakage=_leak(tmp_path))
    _steady_rows(transient, 1.0)
    with pytest.raises(v3.DeckRefused, match="steady_constant"):
        v3.lumped_control(transient)
    expo = tmp_path / "e"
    v3.write_case(V3, expo, steady=True, leakage=_leak(tmp_path, **EXPONENTIAL))
    _steady_rows(expo, 1.0)
    with pytest.raises(v3.DeckRefused, match="steady_constant"):
        v3.lumped_control(expo)
    plain = tmp_path / "p"
    v3.write_case(V3, plain, steady=True)
    _steady_rows(plain, 1.0)
    with pytest.raises(v3.DeckRefused, match="steady_constant"):
        v3.lumped_control(plain)


def test_zero_leakage_changes_only_the_leakage_lines(tmp_path):
    """Control (b) at the deck level: a constant ZERO law adds the source machinery but the surface power, mesh and materials
    of the deck are exactly the leakage-off deck's; the solver-side equality (peak identical to the last digit) is the pod's.
    """
    zero = _leak(tmp_path, q_w_per_m3=0.0)
    on, off = tmp_path / "on", tmp_path / "off"
    v3.write_case(V3, on, leakage=zero)
    v3.write_case(V3, off)
    on_lines = (on / "case.sif").read_text().splitlines()
    off_lines = (off / "case.sif").read_text().splitlines()
    import difflib

    removed, inserted = [], []
    matcher = difflib.SequenceMatcher(None, off_lines, on_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        assert tag in ("equal", "insert", "replace"), tag
        removed += off_lines[i1:i2] if tag != "equal" else []
        inserted += on_lines[j1:j2] if tag != "equal" else []
    assert removed == ["  Nonlinear System Max Iterations = 1"]
    allowed = {
        "  Nonlinear System Max Iterations = 50",
        "  Nonlinear System Convergence Tolerance = 1e-08",
        "  Body Force = 1",
        "Body Force 1",
        "  Heat Source = Variable Temperature",
        "    Real",
        "    End",
        "End",
        "250.0 0.0",
        "500.0 0.0",
    }
    for line in inserted:
        assert line.strip() in {a.strip() for a in allowed} or line.startswith(
            "! leakage:"
        ), line
    for name in ("mesh.header", "mesh.nodes", "mesh.elements", "mesh.boundary"):
        assert (on / "mesh" / name).read_bytes() == (off / "mesh" / name).read_bytes()


# --- the iterative-solver error exit of a leakage-on solve (Validator, cut smoke C1-kT at Vth0 0.70 / 50 %) -----------


def _tail(norms, relc="1.000E+00", error=True):
    lines = [
        f"ComputeChange: NS (ITER={i}) (NRM,RELC): ( {n:.4E}  {relc} ) :: heat equation"
        for i, n in enumerate(norms, start=1)
    ]
    if error:
        lines += [
            "ERROR:: IterSolve: Numerical Error: Too many iterations were needed.",
            "STOP 1",
        ]
    return "\n".join(lines) + "\n"


def _runaway_dir(tmp_path, tail, leak=True):
    directory = tmp_path / ("on" if leak else "off")
    if leak:
        v3.write_case(V3, directory, leakage=_leak(tmp_path))
    else:
        v3.write_case(V3, directory, tables=TABLES, test_mode=True)
    log = tmp_path / ("run-on.log" if leak else "run-off.log")
    log.write_text(tail)
    return directory, log


def test_the_exact_failing_tail_of_a_leakage_on_solve_is_thermal_runaway(tmp_path):
    # the smoke's tail: the nonlinear norm 332.6 -> 341.0 -> 437.1 -> 1.8e6, then the iterative-solver error and STOP 1
    directory, log = _runaway_dir(tmp_path, _tail([332.6, 341.0, 437.1, 1.8e6]))
    status = v3.reference_status(directory, log)
    assert status["status"] == "REFERENCE_INVALID"
    assert status["reason"] == "thermal_runaway"
    assert status["norms"] == [332.6, 341.0, 437.1, 1.8e6]


def test_a_failing_solve_without_a_strictly_rising_norm_stays_an_ordinary_failure(
    tmp_path,
):
    cases = {
        "falling": [332.6, 300.0, 437.1],
        "flat": [332.6, 332.6, 400.0],
        "single": [332.6],
    }
    for name, norms in cases.items():
        sub = tmp_path / name
        sub.mkdir()
        directory, log = _runaway_dir(sub, _tail(norms))
        status = v3.reference_status(directory, log)
        assert status.get("reason") != "thermal_runaway", name


def test_a_rising_norm_without_the_solver_error_exit_is_not_runaway(tmp_path):
    directory, log = _runaway_dir(tmp_path, _tail([332.6, 341.0, 437.1], error=False))
    assert v3.reference_status(directory, log).get("reason") != "thermal_runaway"


def test_only_the_last_time_steps_iterations_count(tmp_path):
    # an earlier step rose and recovered; the failing step's norms are the ones read (they restart at ITER=1)
    steps = _tail([300.0, 310.0], error=False) + _tail([400.0, 380.0, 390.0])
    directory, log = _runaway_dir(tmp_path, steps)
    assert v3.reference_status(directory, log).get("reason") != "thermal_runaway"
    steps = _tail([400.0, 380.0], error=False) + _tail([300.0, 310.0, 420.0])
    sub = tmp_path / "second"
    sub.mkdir()
    directory, log = _runaway_dir(sub, steps)
    assert v3.reference_status(directory, log)["reason"] == "thermal_runaway"


def test_without_leakage_the_same_tail_is_never_typed_thermal_runaway(tmp_path):
    directory, log = _runaway_dir(
        tmp_path, _tail([332.6, 341.0, 437.1, 1.8e6]), leak=False
    )
    status = v3.reference_status(directory, log)
    assert status.get("reason") != "thermal_runaway"
