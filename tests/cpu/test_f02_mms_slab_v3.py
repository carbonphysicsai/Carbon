"""The nonlinear MMS harness and the Kirchhoff slab control of deck v3 (T2, T3), offline.

Claims: the MATC body force is exactly the sympy derivation of the PDE for the manufactured solution; the solver input
carries deck v3's nonlinear settings and labels its test-only properties; the order arithmetic and the acceptance band are
right; a run at the iteration limit is invalid; the Kirchhoff solution satisfies the steady conduction equation, reduces to
the linear slab at beta = 0, and its band logic is the registered one. Every number is a SYNTHETIC test value. The orders and
the Elmer-vs-analytic errors themselves come from the pinned image (Data Collection dry run), not from these tests.
"""

from __future__ import annotations

import itertools
import math
import random

import pytest

from scripts.dev.reference_packages.elmer import f02_deck_v3 as deck
from scripts.dev.reference_packages.elmer import f02_mms_v3 as mms
from scripts.dev.reference_packages.elmer import f02_slab_control_v3 as slab

sympy = pytest.importorskip("sympy")


def _matc_value(text, x, y, z, t):
    expression = (
        text.replace("tx(0)", "X")
        .replace("tx(1)", "Y")
        .replace("tx(2)", "Z")
        .replace("tx(3)", "TT")
    )
    expression = expression.replace("^", "**")
    return (
        eval(  # a test-owned string from `source_matc`, evaluated with only math names
            expression,
            {"__builtins__": {}},
            {
                "sin": math.sin,
                "cos": math.cos,
                "pi": math.pi,
                "X": x,
                "Y": y,
                "Z": z,
                "TT": t,
            },
        )
    )


def test_the_matc_body_force_is_the_symbolic_source_of_the_manufactured_solution():
    x, y, z, t = sympy.symbols("x y z t")
    s = sympy.sin(sympy.pi * x) * sympy.sin(sympy.pi * y) * sympy.sin(sympy.pi * z)
    big_t = mms.T0 + s * sympy.cos(2 * sympy.pi * t)
    k = mms.K0 * (1 + mms.BETA * (big_t - mms.T0))
    cp = mms.CP0 * (1 + mms.GAMMA * (big_t - mms.T0))
    source = cp * sympy.diff(big_t, t) - sum(
        sympy.diff(k * sympy.diff(big_t, v), v) for v in (x, y, z)
    )
    f = sympy.lambdify((x, y, z, t), source, "math")
    text = mms.source_matc()
    rng = random.Random(5)
    for _ in range(40):
        point = [rng.uniform(0.02, 0.98) for _ in range(3)] + [rng.uniform(0.0, 0.5)]
        assert _matc_value(text, *point) == pytest.approx(
            f(*point), rel=1e-12, abs=1e-12
        )


def test_the_manufactured_temperature_is_the_boundary_value_on_every_face_and_positive_properties():
    for face in (
        (0.0, 0.3, 0.4),
        (1.0, 0.3, 0.4),
        (0.2, 0.0, 0.4),
        (0.2, 1.0, 0.4),
        (0.2, 0.3, 0.0),
        (0.2, 0.3, 1.0),
    ):
        assert mms.exact(face) == pytest.approx(mms.T0, abs=1e-15)
    for u in (-1.0, 1.0):  # T - T0 over the test range
        assert mms.K0 * (1 + mms.BETA * u) > 0 and mms.CP0 * (1 + mms.GAMMA * u) > 0
    spread = (1 + mms.BETA) / (1 - mms.BETA)
    assert 1.25 < spread < 1.40  # "about 30 %" over the test range


def test_the_solver_input_has_the_nonlinear_settings_the_source_and_a_test_only_label():
    text = mms.sif_text(1 / 16, 6)
    assert text.startswith(
        "! f02 nonlinear MMS (test-only properties, tables TEST_ONLY)"
    )
    assert f"Nonlinear System Max Iterations = {deck.NONLINEAR_MAX_ITERATIONS}" in text
    assert (
        f"Nonlinear System Convergence Tolerance = {deck.NONLINEAR_TOLERANCE!r}" in text
    )
    assert (
        "Heat Conductivity = Variable Temperature" in text
        and "Heat Capacity = Variable Temperature" in text
    )
    assert mms.source_matc() in text and "Timestep Intervals(1) = 6" in text
    assert "Temperature = 1.0" in text  # the boundary value T0


def test_orders_and_the_acceptance_band():
    halving = [("8", 4e-3, 2e-3), ("16", 1e-3, 5e-4), ("32", 2.5e-4, 1.25e-4)]
    found = mms.orders(halving)
    assert [o["pair"] for o in found] == ["8->16", "16->32"]
    assert all(
        o["max"] == pytest.approx(2.0) and o["rms"] == pytest.approx(2.0) for o in found
    )
    assert mms.accepted(found, found)
    first = [
        ("a", 1.0, 1.0),
        ("b", 1 / 2**1.6, 1 / 2**1.6),
    ]  # an observed order of 1.6: outside [1.7, 2.3]
    assert not mms.accepted(mms.orders(first), found)
    high = [("a", 1.0, 1.0), ("b", 1 / 2**2.4, 1 / 2**2.4)]
    assert not mms.accepted(found, mms.orders(high))


def test_a_run_that_reaches_the_iteration_limit_is_invalid(tmp_path):
    limit, tol = deck.NONLINEAR_MAX_ITERATIONS, deck.NONLINEAR_TOLERANCE

    def log(steps):
        lines = []
        for iterations, final in steps:
            for i in range(1, iterations + 1):
                change = final if i == iterations else 10.0**-i
                lines.append(
                    f"ComputeChange: NS (ITER={i}) (NRM,RELC): ( 3.4E+02  {change:.3E} ) :: heat equation"
                )
        path = tmp_path / f"log{len(list(tmp_path.iterdir()))}"
        path.write_text("\n".join(lines) + "\n")
        return path

    ok = mms.log_status(log([(4, tol / 10), (6, tol / 100)]))
    assert ok == {"max_iterations_seen": 6, "steps": 2, "invalid": False}
    assert mms.log_status(log([(3, tol / 10), (limit, 10 * tol)]))["invalid"] is True
    assert (
        mms.log_status(log([(limit, tol / 2)]))["invalid"] is False
    )  # at the limit but converged
    empty = tmp_path / "empty"
    empty.write_text("no iterations\n")
    assert mms.log_status(empty)["invalid"] is True  # cannot be verified


# --- the Kirchhoff slab -----------------------------------------------------------------------------------------


def test_the_kirchhoff_solution_satisfies_the_steady_conduction_equation():
    q = 1.2e7
    h = slab.LENGTH * 1e-4

    def flux(z):
        t_lo, t_hi = slab.temperature(z - h, q), slab.temperature(z + h, q)
        t_mid = slab.temperature(z, q)
        k = slab.K0 * (1 + slab.BETA * (t_mid - slab.T0_K))
        return k * (t_hi - t_lo) / (2 * h)

    for fraction in (0.2, 0.5, 0.9):
        assert flux(fraction * slab.LENGTH) == pytest.approx(
            q, rel=1e-6
        )  # k(T) dT/dz = q everywhere
    assert slab.temperature(0.0, q) == pytest.approx(
        slab.TA_K, abs=1e-9
    )  # the held face


def test_it_reduces_to_the_linear_slab_at_beta_zero_and_is_monotone():
    q = 8.0e6
    for z in (0.0, slab.LENGTH / 2, slab.LENGTH):
        linear = slab.TA_K + q * z / slab.K0
        assert slab.temperature(z, q, beta=0.0) == pytest.approx(linear, rel=1e-12)
        assert slab.temperature(z, q, beta=1e-12) == pytest.approx(linear, rel=1e-6)
    heights = [i * slab.LENGTH / 10 for i in range(11)]
    values = [slab.temperature(z, q) for z in heights]
    assert all(b > a for a, b in itertools.pairwise(values))
    # with k rising with T the nonlinear slab is cooler at the top than the constant-k slab at k(Ta)
    assert slab.temperature(slab.LENGTH, q) != pytest.approx(
        slab.TA_K + q * slab.LENGTH / slab.K0, rel=1e-3
    )


def test_a_k_that_is_not_positive_on_the_range_is_refused():
    with pytest.raises(ValueError, match="not positive"):
        slab.temperature(slab.LENGTH, 1e9, beta=-0.05)


def test_the_band_is_the_registered_slab_band_and_the_verdict_uses_it():
    assert (
        slab.band(10.0) == 0.25
        and slab.band(100.0) == pytest.approx(1.0)
        and slab.band(-100.0) == pytest.approx(1.0)
    )
    q = slab.LOADS_W_M2[1]
    top, mid = slab.temperature(slab.LENGTH, q), slab.temperature(slab.LENGTH / 2, q)
    verdict = slab.compare(q, top, mid)
    assert verdict["pass"] and verdict["top_error_c"] == 0.0
    assert 30 < verdict["rise_c"] < 150  # a real rise across the 2 mm slab
    off = slab.compare(q, top + 1.5 * verdict["band_c"], mid)
    assert not off["pass"] and off["band_c"] == verdict["band_c"]
    assert (
        1.25
        < (1 + slab.BETA * (top - slab.T0_K))
        / (1 + slab.BETA * (slab.TA_K - slab.T0_K))
        < 1.4
    )


def test_the_slab_input_holds_the_underside_fixes_the_flux_and_labels_the_properties(
    tmp_path,
):
    slab.write_control(tmp_path, 1, 8.0e6)
    text = (tmp_path / "case.sif").read_text()
    assert text.startswith(
        "! f02 Kirchhoff slab control (test-only properties, tables TEST_ONLY)"
    )
    assert "Simulation Type = Steady State" in text and "Heat Flux = 8000000.0" in text
    assert (
        f"Temperature = {slab.TA_K!r}" in text
        and "Nonlinear System Max Iterations" in text
    )
    assert (tmp_path / "mesh" / "mesh.nodes").is_file()
    zs = {
        float(line.split()[4])
        for line in (tmp_path / "mesh" / "mesh.nodes").read_text().splitlines()
    }
    assert min(zs) == 0.0 and max(zs) == pytest.approx(
        slab.LENGTH
    )  # the copper slab alone, 2 mm


def test_the_slab_result_reader_takes_the_two_point_values(tmp_path):
    (tmp_path / "scalars.dat").write_text("401.5 400.2 380.1\n")
    (tmp_path / "scalars.dat.names").write_text(
        "   1: boundary max: temperature\n   2: value: temperature at node 1\n   3: value: temperature at node 2\n"
    )
    assert slab.read_result(tmp_path) == (400.2, 380.1)
    (tmp_path / "scalars.dat").write_text("1.0 1.0 1.0\n2.0 2.0 2.0\n")
    with pytest.raises(ValueError, match="not this control's"):
        slab.read_result(tmp_path)
