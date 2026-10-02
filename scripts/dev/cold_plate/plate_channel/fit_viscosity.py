"""Fit PG25 dynamic viscosity as a polynomial in T (kelvin) for OpenFOAM.

Cold plate (#342) rung 6e. Rung 6d fitted mu(T) over 30-50 degC only, and up to
52 % of the fluid sat above that range, where the polynomial overstated
viscosity by up to 25 %. This refits over the fluid's actual range.

The coolant model is pinned: CoolProp 6.8.0, incompressible fluid
``INCOMP::MPG[0.25]`` (Melinder 2010, IIR), at 2 bar - the same model and state
as ``../DESIGN_BASIS.md``. Its declared validity is -100 to 100 degC, so a fit
inside that range replaces polynomial extrapolation without adding model
extrapolation.

OpenFOAM v2512's ``polynomial`` transport takes ``muCoeffs<8>``: coefficients
of T**i for i = 0..7, with T in kelvin. Raw kelvin powers are badly conditioned
at high degree, so every candidate is judged on coefficients that have been
WRITTEN AS TEXT AND READ BACK, exactly as OpenFOAM will see them.

Usage, from a venv holding CoolProp==6.8.0 and numpy:

    python fit_viscosity.py [--lo-c 30] [--hi-c 80] [--json OUT]

It prints every degree considered and the selection; it chooses nothing it
does not print.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

FLUID = "INCOMP::MPG[0.25]"
PRESSURE_PA = 2.0e5
MAX_DEGREE = 7  # OpenFOAM muCoeffs<8>
K0 = 273.15
#: The model's own validity, as CoolProp 6.8.0 enforces it: it refuses
#: 100 degC itself. A fit must lie inside it; a check beyond it is not made.
MODEL_MIN_C, MODEL_MAX_C = -100.0, 100.0


def model_viscosity(t_kelvin):
    import CoolProp.CoolProp as C

    return np.array(
        [C.PropsSI("V", "T", float(t), "P", PRESSURE_PA, FLUID) for t in t_kelvin]
    )


def as_written(coeffs):
    """Coefficients after a round trip through repr text, as OpenFOAM reads them."""
    return [float(repr(float(c))) for c in coeffs]


def evaluate(coeffs, t):
    # Horner in raw kelvin powers, lowest order first, as OpenFOAM's polynomial.
    result = np.zeros_like(t, dtype=float)
    for c in reversed(coeffs):
        result = result * t + c
    return result


def fit(t, mu, degree):
    # Least squares in a scaled variable for conditioning, then expanded back to
    # raw kelvin powers, which is the form OpenFOAM requires.
    centre, half = (t.max() + t.min()) / 2.0, (t.max() - t.min()) / 2.0
    scaled = np.polynomial.polynomial.polyfit((t - centre) / half, mu, degree)
    raw = np.polynomial.polynomial.Polynomial(scaled).convert(
        domain=[-1, 1], window=[-1, 1]
    )
    # Expand p((T - centre)/half) into powers of T.
    x = np.polynomial.polynomial.Polynomial([-centre / half, 1.0 / half])
    expanded = np.polynomial.polynomial.Polynomial([0.0])
    for i, c in enumerate(raw.coef):
        expanded = expanded + c * x**i
    coeffs = list(expanded.coef) + [0.0] * (degree + 1 - len(expanded.coef))
    return coeffs[: degree + 1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lo-c", type=float, default=30.0)
    parser.add_argument("--hi-c", type=float, default=80.0)
    parser.add_argument("--json", help="write the selected fit and the full table here")
    args = parser.parse_args(argv)
    if not MODEL_MIN_C < args.lo_c < args.hi_c < MODEL_MAX_C:
        parser.error(
            f"the fit range must lie inside the model's validity, "
            f"{MODEL_MIN_C:g} to {MODEL_MAX_C:g} degC exclusive"
        )

    import CoolProp

    t_fit = np.arange(args.lo_c, args.hi_c + 1e-9, 1.0) + K0
    t_check = np.arange(args.lo_c, args.hi_c + 1e-9, 0.05) + K0
    mu_fit, mu_check = model_viscosity(t_fit), model_viscosity(t_check)
    t_wide = np.arange(250.0, 500.0 + 1e-9, 0.5)  # positivity and extrapolation

    print(f"CoolProp {CoolProp.__version__}, {FLUID} at {PRESSURE_PA / 1e5:g} bar")
    print(
        f"fit {args.lo_c:g}-{args.hi_c:g} degC at 1 K; checked at 0.05 K; numpy {np.__version__}"
    )
    print()
    header = (
        f"{'deg':>3} {'max|rel| written':>17} {'max|rel| in-mem':>16} "
        f"{'min mu 250-500K':>16} {'first<=0 (K)':>13} {'+10C':>10} {'+20C':>10}"
    )
    print(header)

    rows = []
    for degree in range(2, MAX_DEGREE + 1):
        coeffs = fit(t_fit, mu_fit, degree)
        written = as_written(coeffs)
        rel_written = np.abs(evaluate(written, t_check) / mu_check - 1.0).max()
        rel_mem = np.abs(evaluate(coeffs, t_check) / mu_check - 1.0).max()
        wide = evaluate(written, t_wide)
        nonpositive = t_wide[wide <= 0.0]
        first_bad = float(nonpositive[0]) if nonpositive.size else None
        extrap = {}
        for dc in (10.0, 20.0):
            if args.hi_c + dc >= MODEL_MAX_C:
                extrap[dc] = None  # beyond the model: nothing to compare with
                continue
            tt = np.array([args.hi_c + dc + K0])
            extrap[dc] = float(evaluate(written, tt)[0] / model_viscosity(tt)[0] - 1.0)
        rows.append(
            {
                "degree": degree,
                "coefficients": written,
                "max_rel_written": float(rel_written),
                "max_rel_in_memory": float(rel_mem),
                "min_mu_250_500K": float(wide.min()),
                "first_nonpositive_K": first_bad,
                "extrapolation_rel": {f"+{int(k)}C": v for k, v in extrap.items()},
            }
        )
        shown = {
            dc: "model ends" if v is None else f"{v:+.2%}" for dc, v in extrap.items()
        }
        print(
            f"{degree:>3} {rel_written:>17.2e} {rel_mem:>16.2e} {wide.min():>16.3e} "
            f"{('none' if first_bad is None else f'{first_bad:.1f}'):>13} "
            f"{shown[10.0]:>10} {shown[20.0]:>10}"
        )

    # Selection rule, stated before it is applied: among fits that are positive
    # over 250-500 K, take the lowest degree whose WRITTEN residual is within
    # 1e-4 relative in range; if none reaches 1e-4, the smallest written
    # residual. Lowest degree is preferred because it extrapolates more gently.
    positive = [r for r in rows if r["first_nonpositive_K"] is None]
    good = [r for r in positive if r["max_rel_written"] <= 1e-4]
    chosen = (
        (good[0] if good else min(positive, key=lambda r: r["max_rel_written"]))
        if positive
        else None
    )
    print()
    if chosen is None:
        print("NO DEGREE IS POSITIVE OVER 250-500 K. Nothing selected.")
        return 1
    print(
        f"selected degree {chosen['degree']}: written residual "
        f"{chosen['max_rel_written']:.2e}, positive over 250-500 K"
    )
    for i, c in enumerate(chosen["coefficients"]):
        print(f"  c{i} = {c!r}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "fluid": FLUID,
                    "pressure_pa": PRESSURE_PA,
                    "coolprop": CoolProp.__version__,
                    "numpy": np.__version__,
                    "fit_range_c": [args.lo_c, args.hi_c],
                    "selection_rule": "lowest degree positive over 250-500 K with written residual <= 1e-4; else smallest written residual",
                    "selected": chosen,
                    "candidates": rows,
                },
                fh,
                indent=2,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
