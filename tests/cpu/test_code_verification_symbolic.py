"""Optional offline algebra proof; never runs a reference solver."""

import pytest

from scripts.dev.code_verification import derive


def test_symbolic_sources_and_boundary_fluxes():
    # SymPy is optional tooling, not a new base/canonical dependency.
    s = pytest.importorskip("sympy", reason="optional symbolic derivation environment")
    x, y, z, t, r = s.symbols("x y z t r", real=True)
    result = derive.derive()
    sine = s.sin(s.pi * x) * s.sin(s.pi * y) * s.sin(s.pi * z)
    assert (
        s.simplify(
            result["heat_source"]
            - sine
            * (3 * s.pi**2 * s.cos(2 * s.pi * t) - 2 * s.pi * s.sin(2 * s.pi * t))
        )
        == 0
    )
    assert (
        s.simplify(result["motor_Jz"] - 2 * s.pi**2 * s.sin(s.pi * x) * s.sin(s.pi * y))
        == 0
    )
    assert (
        s.simplify(result["particle_source"] + s.exp(-t) * (7 + 21 * r**2 + r**4)) == 0
    )
    assert result["particle_left_flux"] == 0
    assert s.simplify(result["particle_right_flux"] - 6 * s.exp(-t)) == 0
    assert s.simplify(result["helmholtz_source_k1"] - (3 * s.pi**2 - 1) * sine) == 0
    assert s.simplify(result["elastic_force"][0] - 5 * s.pi**2 * sine) == 0
    assert (
        s.simplify(
            result["elastic_force"][1]
            + 2 * s.pi**2 * s.cos(s.pi * x) * s.cos(s.pi * y) * s.sin(s.pi * z)
        )
        == 0
    )
    assert (
        s.simplify(
            result["elastic_force"][2]
            + 2 * s.pi**2 * s.cos(s.pi * x) * s.sin(s.pi * y) * s.cos(s.pi * z)
        )
        == 0
    )
    assert result["periodic_scalar_residual_U1_D001"] == 0
    scalar = s.sin(s.pi * x) * s.sin(s.pi * y)
    assert (
        s.simplify(
            result["scalar_source_U1_D1"]
            - s.exp(-t)
            * ((2 * s.pi**2 - 1) * scalar + s.pi * s.cos(s.pi * x) * s.sin(s.pi * y))
        )
        == 0
    )
