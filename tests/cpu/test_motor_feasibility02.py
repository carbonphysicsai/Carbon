"""The motor customer-feasibility grammar (#758): winding, skew algebra."""

from __future__ import annotations

import pytest

from scripts.dev.motor.feasibility02 import topology as tp


def test_tooth_winding_is_balanced_and_forward():
    top = tp.TOPOLOGIES["10p12s"]
    coils = tp.tooth_phases(10, 12)
    assert [p for p, _ in coils].count("A") == 4
    axes = tp.winding_factor(top)
    assert axes["A"][0] == pytest.approx(0.9330, abs=1e-4)
    assert (axes["B"][1] - axes["A"][1]) % 360 == pytest.approx(120)
    assert tp.current_offset_deg(top) == pytest.approx(15.0)
    assert tp.current_offset_deg(tp.TOPOLOGIES["8p24s"]) == pytest.approx(-120.0)
    table = tp.winding_table(top)
    assert len(table) == 24 and sum(s for _, s in table) == 0


def test_skew_combination_is_a_mean_of_shifted_slices():
    curve = [0.0, 1.0, 0.0, -1.0]
    slices = [tp.slice_curve(curve, d) for d in (-1, 0, 1)]
    assert slices[0] == [-1.0, 0.0, 1.0, 0.0]
    assert tp.stack_curve(slices) == pytest.approx([-1 / 3, 1 / 3, 1 / 3, -1 / 3])
    m = tp.metrics([5.9, 6.1])
    assert m["pk_pk_nm"] == pytest.approx(0.2) and m["mean_nm"] == pytest.approx(6.0)


def test_draws_are_buildable_and_deterministic():
    top = tp.TOPOLOGIES["10p12s"]
    a, _ = tp.draw("MOTOR-FEAS02-10p12s", 5, top)
    b, _ = tp.draw("MOTOR-FEAS02-10p12s", 5, top)
    assert a == b and all(not tp.validity(top, d) for d in a)
    bad = {**a[0], "slot_bottom_mm": 45.5}
    assert tp.validity(top, bad)
