"""Fit every PG25 property as a polynomial in T (kelvin), for OpenFOAM and Carbon.

Cold plate (#342). `fit_viscosity.py` fitted viscosity alone (rungs 6d and 6e).
This fits density, heat capacity, conductivity and viscosity with the same
method and the same stated selection rule, so a reference that lets every
property vary, and Carbon's analytical model, use one set of coefficients.

The coolant model is pinned: CoolProp 6.8.0, ``INCOMP::MPG[0.25]`` (Melinder
2010, IIR), at 2 bar, as in ``../DESIGN_BASIS.md``. CoolProp refuses 100 degC
itself, so a fit must end below it.

OpenFOAM v2512's polynomial thermo takes eight coefficients of T**i, T in
kelvin. Raw kelvin powers are badly conditioned, so every candidate is judged
on coefficients WRITTEN AS TEXT AND READ BACK, exactly as OpenFOAM reads them.

Usage, from a venv holding CoolProp==6.8.0 and numpy:

    python fit_properties.py [--lo-c 30] [--hi-c 99] [--json OUT]

It prints every degree for every property and the selection; it chooses
nothing it does not print.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

FLUID = "INCOMP::MPG[0.25]"
PRESSURE_PA = 2.0e5
MAX_DEGREE = 7  # OpenFOAM <8> coefficient lists
K0 = 273.15
MODEL_MIN_C, MODEL_MAX_C = -100.0, 100.0
#: CoolProp key, OpenFOAM name, SI unit.
PROPERTIES = {
    "rho": ("D", "rhoCoeffs", "kg/m^3"),
    "cp": ("C", "CpCoeffs", "J/kg/K"),
    "kappa": ("L", "kappaCoeffs", "W/m/K"),
    "mu": ("V", "muCoeffs", "Pa s"),
}
#: The selection rule, stated before it is applied. Among fits positive over
#: 250-500 K (where a solver iterate could wander), take the lowest degree
#: whose written residual is within TOLERANCE relative in range; if none
#: reaches it, the smallest written residual. Lowest degree is preferred
#: because it extrapolates more gently.
TOLERANCE = 1e-4


def model(key, t_kelvin):
    import CoolProp.CoolProp as C

    return np.array(
        [C.PropsSI(key, "T", float(t), "P", PRESSURE_PA, FLUID) for t in t_kelvin]
    )


def as_written(coeffs):
    return [float(repr(float(c))) for c in coeffs]


def evaluate(coeffs, t):
    result = np.zeros_like(t, dtype=float)
    for c in reversed(coeffs):
        result = result * t + c
    return result


def fit(t, values, degree):
    centre, half = (t.max() + t.min()) / 2.0, (t.max() - t.min()) / 2.0
    scaled = np.polynomial.polynomial.polyfit((t - centre) / half, values, degree)
    x = np.polynomial.polynomial.Polynomial([-centre / half, 1.0 / half])
    expanded = np.polynomial.polynomial.Polynomial([0.0])
    for i, c in enumerate(scaled):
        expanded = expanded + c * x**i
    coeffs = list(expanded.coef) + [0.0] * (degree + 1 - len(expanded.coef))
    return coeffs[: degree + 1]


def select(name, key, t_fit, t_check, t_wide):
    values, check = model(key, t_fit), model(key, t_check)
    rows = []
    for degree in range(MAX_DEGREE + 1):
        written = as_written(fit(t_fit, values, degree))
        rel = float(np.abs(evaluate(written, t_check) / check - 1.0).max())
        wide = evaluate(written, t_wide)
        bad = t_wide[wide <= 0.0]
        rows.append(
            {
                "degree": degree,
                "coefficients": written,
                "max_rel_written": rel,
                "min_250_500K": float(wide.min()),
                "first_nonpositive_K": float(bad[0]) if bad.size else None,
            }
        )
        print(
            f"  {name:6s} deg {degree}: max|rel| {rel:.2e}  min 250-500K "
            f"{wide.min():+.3e}  first<=0 "
            f"{'none' if not bad.size else f'{bad[0]:.1f} K'}"
        )
    positive = [r for r in rows if r["first_nonpositive_K"] is None]
    good = [r for r in positive if r["max_rel_written"] <= TOLERANCE]
    if not positive:
        return None, rows
    chosen = good[0] if good else min(positive, key=lambda r: r["max_rel_written"])
    return chosen, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lo-c", type=float, default=30.0)
    parser.add_argument("--hi-c", type=float, default=99.0)
    parser.add_argument("--json", help="write the selections and every candidate here")
    args = parser.parse_args(argv)
    if not MODEL_MIN_C < args.lo_c < args.hi_c < MODEL_MAX_C:
        parser.error(
            f"the fit range must lie inside the model's validity, "
            f"{MODEL_MIN_C:g} to {MODEL_MAX_C:g} degC exclusive"
        )
    import CoolProp

    t_fit = np.arange(args.lo_c, args.hi_c + 1e-9, 1.0) + K0
    t_check = np.arange(args.lo_c, args.hi_c + 1e-9, 0.05) + K0
    t_wide = np.arange(250.0, 500.0 + 1e-9, 0.5)
    print(f"CoolProp {CoolProp.__version__}, {FLUID} at {PRESSURE_PA / 1e5:g} bar")
    print(
        f"fit {args.lo_c:g}-{args.hi_c:g} degC at 1 K; checked at 0.05 K; "
        f"numpy {np.__version__}; tolerance {TOLERANCE:g}"
    )
    out = {
        "fluid": FLUID,
        "pressure_pa": PRESSURE_PA,
        "coolprop": CoolProp.__version__,
        "numpy": np.__version__,
        "fit_range_c": [args.lo_c, args.hi_c],
        "selection_rule": (
            f"lowest degree positive over 250-500 K with written residual <= "
            f"{TOLERANCE:g}; else smallest written residual"
        ),
        "properties": {},
    }
    failed = False
    for name, (key, foam, unit) in PROPERTIES.items():
        print(f"{name} ({foam}, {unit}):")
        chosen, rows = select(name, key, t_fit, t_check, t_wide)
        if chosen is None:
            print(f"  NO DEGREE IS POSITIVE OVER 250-500 K for {name}.")
            failed = True
            continue
        print(
            f"  selected degree {chosen['degree']}: written residual "
            f"{chosen['max_rel_written']:.2e}"
        )
        for i, c in enumerate(chosen["coefficients"]):
            print(f"    c{i} = {c!r}")
        out["properties"][name] = {
            "openfoam": foam,
            "unit": unit,
            "selected": chosen,
            "candidates": rows,
        }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
