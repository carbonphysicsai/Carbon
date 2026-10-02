# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Read a solved cold plate reference case back into the Challenge's outputs.

`analyze_case` returns the outputs at the final write (`domain.OUTPUTS`), the
checks that decide whether the reference may be used, and a typed outcome:

- `OK`: every reference numerical check holds and the case lies inside the
  reference's applicability.
- `REFERENCE_INVALID`: the run finished, but a check failed or the case left
  the applicability (fluid outside the PG25 fits, or Re above the laminar
  limit). Charged to the reference, never to a candidate.
- `REFERENCE_SOLVER_FAILED`: the run left nothing readable.

Timeouts and infrastructure failures are decided by whoever ran the case, not
here. Checks are computed from what the solver wrote, at steady state:

- **mass:** inlet and outlet mass flow agree;
- **energy:** the enthalpy, kinetic energy and inlet conduction leaving the
  cell equal the heat the map puts in. The enthalpy flows are the solver's
  own, sum(phi h) over inlet and outlet (function objects), so the check is
  exact in its discretization;
- **iteration:** every output agrees between the half-way and final writes.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

from .domain import (
    FIXED,
    K0,
    PG25_VALID_C,
    PROFILE_SEGMENTS,
    RE_LAMINAR_MAX,
    heat_flux,
    pg25,
)
from .openfoam import fluid_coefficients

#: Reference numerical checks. They judge the reference, never a candidate.
#: Provisional DEVELOPMENT values, each at least 100x looser than the largest
#: value rungs 5-6e observed (mass 3e-10, energy 1e-8, iteration change 3e-7 K
#: and 1e-6 Pa), so they catch a broken run without judging a sound one.
REFERENCE_CHECKS = {
    "mass_imbalance_rel": 1e-6,
    "energy_balance_rel": 1e-5,
    "iteration_change_k": 1e-3,
    "iteration_change_pressure_rel": 1e-5,
}
OUTPUT_SCHEMA = "carbon.cold-plate.reference-outputs.v1"


def internal_field(path):
    """The internalField of an ASCII OpenFOAM field file, scalar or vector."""
    text = Path(path).read_text()
    body = text.split("internalField", 1)[1]
    if body.lstrip().startswith("uniform"):
        raise ValueError(f"{path} is uniform")
    count = int(re.search(r"\n(\d+)\n\(", body).group(1))
    start = body.index("(", body.index(str(count))) + 1
    items = re.findall(r"\(([^()]*)\)|([-+0-9.eE]+)", body[start:])
    values = []
    for vec, scalar in items:
        values.append(tuple(map(float, vec.split())) if vec else float(scalar))
        if len(values) == count:
            break
    if len(values) != count:
        raise ValueError(f"{path}: expected {count} values, read {len(values)}")
    return values


def _surface_value(case_dir, name, t):
    (path,) = (case_dir / "postProcessing" / "fluid" / name).glob(
        "*/surfaceFieldValue.dat"
    )
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            continue
        fields = line.split()
        if float(fields[0]) == float(t):
            return float(fields[1])
    raise ValueError(f"{name} has no value at {t}")


def _polynomial(coeffs):
    def value(t):
        result = 0.0
        for c in reversed(coeffs):
            result = result * t + c
        return result

    return value


def _fluid(record):
    """(rho(T), kappa(T)) exactly as the case's thermo file defines them."""
    t_in = K0 + record["inputs"]["inlet_c"]
    rho, _, kappa = fluid_coefficients(record["fluid_model"], t_in)
    return _polynomial(rho), _polynomial(kappa)


def _column(cells, x_value):
    return [c for c in cells if abs(c[0][0] - x_value) < 1e-12]


def at_time(case_dir, t, record):
    """Outputs and checks at one write `t`."""
    case_dir = Path(case_dir)
    inputs, d = record["inputs"], record["derived"]
    rho, kappa = _fluid(record)
    k_s = FIXED["copper_k_w_mk"]
    length = FIXED["footprint_mm"] * 1e-3
    half_cell = (inputs["channel_width_mm"] + inputs["fin_width_mm"]) / 2 * 1e-3
    face_area = inputs["channel_width_mm"] / 2 * inputs["channel_depth_mm"] * 1e-6
    t_in = K0 + inputs["inlet_c"]
    u_in = d["inlet_velocity_m_s"]
    m_in = -_surface_value(case_dir, "massIn", t)
    m_out = _surface_value(case_dir, "massOut", t)
    bulk_out = _surface_value(case_dir, "bulkOut", t)
    # The heat the solver applies: the map evaluated at each heated face's
    # centre (`pos()`), times the face area. Axial spacing is uniform and the
    # map does not vary across the span, so this is exact for the mesh, which
    # the map's own integral is not (a sharp spot on 100 faces differs from
    # it by more than the energy check allows).
    nx = record["mesh"]["nx"]
    heat_in = (
        sum(
            heat_flux(inputs, (i + 0.5) * FIXED["footprint_mm"] / nx) for i in range(nx)
        )
        / nx
        * length
        * half_cell
    )

    fluid = list(
        zip(
            internal_field(case_dir / t / "fluid" / "C"),
            internal_field(case_dir / t / "fluid" / "T"),
            internal_field(case_dir / t / "fluid" / "U"),
            internal_field(case_dir / t / "fluid" / "V"),
        )
    )
    x_first = min(c[0][0] for c in fluid)
    x_last = max(c[0][0] for c in fluid)
    first, last = _column(fluid, x_first), _column(fluid, x_last)
    # Within one x-column a cell's volume is proportional to its face area,
    # because the axial spacing is uniform.
    first_v = sum(c[3] for c in first)
    last_v = sum(c[3] for c in last)

    def flux(cell):  # mass flow through the cell's outlet face, kg/s
        _, tt, u, v = cell
        return rho(tt) * u[0] * face_area * v / last_v

    # The solver's own enthalpy flows, sum(phi h) over each patch: exact in
    # its discretization, whatever cp does.
    enthalpy_out = _surface_value(case_dir, "enthalpyOut", t) + _surface_value(
        case_dir, "enthalpyIn", t
    )
    kinetic = (
        sum(flux(c) * 0.5 * (c[2][0] ** 2 + c[2][1] ** 2 + c[2][2] ** 2) for c in last)
        - m_in * 0.5 * u_in**2
    )
    # The inlet fixes T, so fluid warmed near it conducts heat back out.
    inlet_conduction = sum(
        kappa(t_in) * (c[1] - t_in) / x_first * face_area * c[3] / first_v
        for c in first
    )
    energy_out = enthalpy_out + kinetic + inlet_conduction

    solid = zip(
        internal_field(case_dir / t / "solid" / "C"),
        internal_field(case_dir / t / "solid" / "T"),
        internal_field(case_dir / t / "solid" / "V"),
    )
    solid = list(solid)
    z_first = min(c[0][2] for c in solid)
    # The heated face: the first cell's value plus the local flux over half
    # a cell.
    face = [
        (c[0][0], c[1] + heat_flux(inputs, c[0][0] * 1e3) * z_first / k_s, c[2])
        for c in solid
        if abs(c[0][2] - z_first) < 1e-12
    ]
    peak_x, peak, _ = max(face, key=lambda item: item[1])
    columns = defaultdict(list)
    for x, tt, v in face:
        columns[round(x, 12)].append((tt, v))
    xs = sorted(columns)
    dx = length / len(xs)
    span_mean = [
        sum(tt * v for tt, v in columns[x]) / sum(v for _, v in columns[x]) for x in xs
    ]
    # Each profile segment is the length-weighted mean of the columns it
    # overlaps, so the profile does not depend on where cell faces fall.
    seg = length / PROFILE_SEGMENTS
    profile = []
    for s in range(PROFILE_SEGMENTS):
        lo, hi = s * seg, (s + 1) * seg
        total = weight = 0.0
        for x, value in zip(xs, span_mean):
            overlap = min(hi, x + dx / 2) - max(lo, x - dx / 2)
            if overlap > 0:
                total += value * overlap
                weight += overlap
        profile.append(total / weight - K0)
    d_h = (
        2
        * inputs["channel_width_mm"]
        * inputs["channel_depth_mm"]
        / (inputs["channel_width_mm"] + inputs["channel_depth_mm"])
        * 1e-3
    )
    # Mass flux through the half channel, so Re at the outlet's bulk viscosity.
    re_outlet = m_out / face_area * d_h / pg25("mu", bulk_out)
    fluid_t = [c[1] for c in fluid]
    return {
        "outputs": {
            "peak_c": peak - K0,
            "mean_c": sum(span_mean) / len(span_mean) - K0,
            "profile_c": profile,
            "outlet_c": bulk_out - K0,
            "pressure_drop_pa": _surface_value(case_dir, "pressIn", t)
            - _surface_value(case_dir, "pressOut", t),
        },
        "checks": {
            "mass_imbalance_rel": m_out / m_in - 1,
            "energy_balance_rel": energy_out / heat_in - 1,
            "fluid_min_c": min(fluid_t) - K0,
            "fluid_max_c": max(fluid_t) - K0,
            "inlet_undershoot_k": max(0.0, t_in - min(fluid_t)),
            "re_outlet": re_outlet,
        },
        "diagnostics": {
            "peak_x_mm": peak_x * 1e3,
            "heat_in_w_per_cell": heat_in,
            "inlet_conduction_w": inlet_conduction,
            "kinetic_w": kinetic,
        },
    }


def _last_initial(log, field):
    found = re.findall(rf"Solving for {field}, Initial residual = ([-+0-9.eE]+)", log)
    return float(found[-1]) if found else None


def _finite(outputs, checks):
    values = [outputs[k] for k in ("peak_c", "mean_c", "outlet_c", "pressure_drop_pa")]
    return all(
        math.isfinite(v) for v in (*values, *outputs["profile_c"], *checks.values())
    )


def analyze_case(case_dir):
    """The final write's outputs, the reference checks and the outcome. A run
    that left nothing readable is REFERENCE_SOLVER_FAILED, never an error."""
    case_dir = Path(case_dir)
    record = json.loads((case_dir / "case.json").read_text())
    try:
        times = sorted(
            (t for t in (case_dir / "times").read_text().split() if t != "0"),
            key=float,
        )
        if len(times) < 2:
            raise ValueError(f"{len(times)} writes; two are needed")
        half, final = (at_time(case_dir, t, record) for t in times[-2:])
        log = (case_dir / "log.chtMultiRegionSimpleFoam").read_text()
    except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError) as exc:
        return {
            "schema": OUTPUT_SCHEMA,
            "outcome": "REFERENCE_SOLVER_FAILED",
            "reasons": [f"unreadable: {type(exc).__name__}: {exc}"],
            "case": record,
        }
    a, b = half["outputs"], final["outputs"]
    change_k = max(
        *(abs(b[k] - a[k]) for k in ("peak_c", "mean_c", "outlet_c")),
        *(abs(p - q) for p, q in zip(a["profile_c"], b["profile_c"])),
    )
    checks = {
        **final["checks"],
        "iteration_change_k": change_k,
        "iteration_change_pressure_rel": abs(
            b["pressure_drop_pa"] / a["pressure_drop_pa"] - 1
        ),
    }
    reasons = []
    if not _finite(b, checks):
        reasons.append("non-finite output or check")
    else:
        for name, limit in REFERENCE_CHECKS.items():
            if abs(checks[name]) > limit:
                reasons.append(f"{name}={checks[name]:.3g} exceeds {limit:g}")
        # Only the top is a limit: the coolant model ends at 100 C. The
        # coldest fluid sits about 1 K below the inlet near the inlet corner
        # in every case so far (linearUpwind is unbounded; rungs 6e and 7), a
        # numerical undershoot reported as `inlet_undershoot_k`, not judged.
        high = PG25_VALID_C[1]
        if checks["fluid_max_c"] > high:
            reasons.append(
                f"outside applicability: fluid reaches {checks['fluid_max_c']:.2f}"
                f" C; the PG25 fits and the coolant model end at {high:g} C"
            )
        if checks["re_outlet"] > RE_LAMINAR_MAX:
            reasons.append(
                f"outside applicability: Re {checks['re_outlet']:.0f} at the "
                f"outlet exceeds {RE_LAMINAR_MAX:g}"
            )
    return {
        "schema": OUTPUT_SCHEMA,
        "outcome": "REFERENCE_INVALID" if reasons else "OK",
        "reasons": reasons,
        "outputs": b,
        "checks": checks,
        "diagnostics": {
            **final["diagnostics"],
            "writes": times[-2:],
            "last_initial_residual": {
                f: _last_initial(log, f) for f in ("h", "Ux", "p_rgh")
            },
        },
        "case": record,
    }
