"""Offline optional SymPy derivation. No reference solver imports or runs."""

import json


def derive():
    import sympy as s

    x, y, z, t, r = s.symbols("x y z t r", real=True)
    lap = lambda v: sum(s.diff(v, q, 2) for q in (x, y, z))
    sine = s.sin(s.pi * x) * s.sin(s.pi * y) * s.sin(s.pi * z)
    heat = 1 + sine * s.cos(2 * s.pi * t)
    az = s.sin(s.pi * x) * s.sin(s.pi * y)
    c = s.exp(-t) * (1 + r**2 + r**4)
    scalar = 1 + s.exp(-t) * az
    periodic = 1 + s.Rational(1, 5) * s.exp(-4 * s.pi**2 * t / 100) * s.sin(
        2 * s.pi * (x - t)
    )
    # Unit isotropic Lamé constants; u=(sine,0,0), f=-div sigma.
    displacement = s.Matrix([sine, 0, 0])
    strain = (displacement.jacobian([x, y, z]) + displacement.jacobian([x, y, z]).T) / 2
    stress = s.trace(strain) * s.eye(3) + 2 * strain
    force = [
        -sum(s.diff(stress[i, j], q) for j, q in enumerate((x, y, z))) for i in range(3)
    ]
    return {
        "heat_source": s.simplify(s.diff(heat, t) - lap(heat)),
        "motor_Jz": s.simplify(-s.diff(az, x, 2) - s.diff(az, y, 2)),
        "particle_source": s.simplify(
            s.diff(c, t) - s.diff(r**2 * s.diff(c, r), r) / r**2
        ),
        "particle_left_flux": s.limit(s.diff(c, r), r, 0),
        "particle_right_flux": s.diff(c, r).subs(r, 1),
        "helmholtz_source_k1": s.simplify(-lap(sine) - sine),
        "scalar_source_U1_D1": s.simplify(
            s.diff(scalar, t)
            + s.diff(scalar, x)
            - s.diff(scalar, x, 2)
            - s.diff(scalar, y, 2)
        ),
        "periodic_scalar_residual_U1_D001": s.simplify(
            s.diff(periodic, t) + s.diff(periodic, x) - s.diff(periodic, x, 2) / 100
        ),
        "elastic_force": [s.simplify(v) for v in force],
    }


if __name__ == "__main__":
    print(json.dumps({k: str(v) for k, v in derive().items()}, indent=2))
