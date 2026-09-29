"""Report a solved rung-4 plate cell against what can be computed exactly.

Exact at steady state, whatever the mesh:
  mass     inlet and outlet mass flow agree;
  energy   m_dot c_p (T_b,out - T_b,in) + inlet conduction
           + kinetic-energy flux change = q A_heated.
           The lid, the plate ends, the outlet (zero gradient) and both
           symmetry planes are adiabatic; the fixed-temperature inlet is not.
           The solver's enthalpy equation carries div(phi, K), K = |U|^2/2,
           so the uniform inlet developing into a duct profile moves energy
           out of h.
Exact for fully developed flow (Shah & London; White, Viscous Fluid Flow,
eq. 3-48), for a duct of half-sides a <= b:
  U = a^2 G / (3 mu) [1 - (192 a / (pi^5 b)) sum_{n odd} tanh(n pi b / 2a) / n^5]
  with G = -dp/dx, measured on section-averaged pressure over DEVELOPED.
With no closed form, reported for mesh refinement only: the peak and mean
heated-face temperature, the outlet bulk temperature and the inlet-to-outlet
pressure drop (area-averaged static pressure; outlet fixed at 1e5 Pa).
Each quantity is reported at the half-way and final writes, which is the
iteration-convergence check. Reported, not judged: no pass threshold is set.
"""

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

# Rung-4 cases predate property sets and used the verification set.
VERIFICATION = {
    "rho_f": 1000.0,
    "cp_f": 4181.0,
    "mu_f": 1e-3,
    "pr_f": 1.0,
    "k_s": 10.0,
    "u_in": 0.1,
    "t_in": 300.0,
    "q_flux": 1e4,
}
DEVELOPED = (0.6, 0.95)  # fraction of the length


def internal_field(path):
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
    return values


def surface_value(case, name, t):
    (path,) = (case / "postProcessing" / "fluid" / name).glob("*/surfaceFieldValue.dat")
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            continue
        fields = line.split()
        if float(fields[0]) == float(t):
            return float(fields[1])
    raise ValueError(f"{name} has no value at {t}")


def duct_gradient(width, height, MU, U):
    a, b = sorted((width / 2, height / 2))
    series = sum(math.tanh(n * math.pi * b / (2 * a)) / n**5 for n in range(1, 400, 2))
    return 3 * MU * U / (a * a * (1 - 192 * a / (math.pi**5 * b) * series))


def slope(points):
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    return sum((x - mx) * (y - my) for x, y in points) / sum(
        (x - mx) ** 2 for x, _ in points
    )


def last_initial(log, field):
    found = re.findall(rf"Solving for {field}, Initial residual = ([-+0-9.eE]+)", log)
    return float(found[-1]) if found else None


def _weights(case, t, region, count):
    """Cell volumes when written (graded meshes); equal weights otherwise.
    Axial spacing is uniform, so within one x-column a cell's volume is
    proportional to its cross-section face."""
    path = case / t / region / "V"
    return internal_field(path) if path.exists() else [1.0] * count


def at_time(case, t, geometry, props):
    Q, U, RHO, CP, MU = (props[k] for k in ("q_flux", "u_in", "rho_f", "cp_f", "mu_f"))
    K_S, K_F = props["k_s"], MU * CP / props["pr_f"]
    length = geometry["length"] * 1e-3
    half_cell = (geometry["channel_width"] + geometry["fin_width"]) / 2 * 1e-3
    m_in = -surface_value(case, "massIn", t)
    m_out = surface_value(case, "massOut", t)
    t_in = surface_value(case, "bulkIn", t)
    t_out = surface_value(case, "bulkOut", t)
    heat_in = Q * half_cell * length
    heat_out = m_out * CP * (t_out - t_in)

    centres = internal_field(case / t / "fluid" / "C")
    # The inlet fixes T, so fluid warmed near it conducts heat back out through
    # the inlet face: k_f (T_cell - T_in) / (dx/2) over each inlet face.
    fluid_t = internal_field(case / t / "fluid" / "T")
    fluid_w = _weights(case, t, "fluid", len(centres))
    x_first = min(x for x, _, _ in centres)
    first = [
        (tt, w)
        for (x, _, _), tt, w in zip(centres, fluid_t, fluid_w)
        if abs(x - x_first) < 1e-12
    ]
    face_area = geometry["channel_width"] / 2 * geometry["channel_height"] * 1e-6
    # Kinetic-energy flux through the outlet (zero-gradient U, so face values
    # are the last cells') less the uniform inlet's.
    velocity = internal_field(case / t / "fluid" / "U")
    x_last = max(x for x, _, _ in centres)
    last = [
        (u, w)
        for (x, _, _), u, w in zip(centres, velocity, fluid_w)
        if abs(x - x_last) < 1e-12
    ]
    last_w = sum(w for _, w in last)
    kinetic = (
        sum(
            RHO
            * u[0]
            * face_area
            * w
            / last_w
            * 0.5
            * (u[0] ** 2 + u[1] ** 2 + u[2] ** 2)
            for u, w in last
        )
        - m_in * 0.5 * U**2
    )
    first_w = sum(w for _, w in first)
    inlet_conduction = sum(
        K_F * (tt - t_in) / x_first * face_area * w / first_w for tt, w in first
    )
    pressure = internal_field(case / t / "fluid" / "p")
    sections = defaultdict(list)
    for (x, _, _), p, w in zip(centres, pressure, fluid_w):
        sections[round(x, 12)].append((p, w))
    lo, hi = (f * length for f in DEVELOPED)
    profile = [
        (x, sum(p * w for p, w in v) / sum(w for _, w in v))
        for x, v in sorted(sections.items())
        if lo <= x <= hi
    ]
    gradient = -slope(profile)
    expected = duct_gradient(
        geometry["channel_width"] * 1e-3, geometry["channel_height"] * 1e-3, MU, U
    )

    solid = internal_field(case / t / "solid" / "C")
    temperature = internal_field(case / t / "solid" / "T")
    solid_w = _weights(case, t, "solid", len(solid))
    z_first = min(z for _, _, z in solid)
    face = [
        (x, tt + Q * z_first / K_S, w)  # cell value plus the flux over half a cell
        for (x, _, z), tt, w in zip(solid, temperature, solid_w)
        if abs(z - z_first) < 1e-12
    ]
    peak_x, peak, _ = max(face, key=lambda item: item[1])
    return {
        "mass_flow_kg_s": m_out,
        "mass_imbalance_rel": m_out / m_in - 1,
        "energy_balance_rel": heat_out / heat_in - 1,
        "inlet_conduction_W": inlet_conduction,
        "energy_balance_with_inlet_conduction_rel": (heat_out + inlet_conduction)
        / heat_in
        - 1,
        "kinetic_energy_flux_W": kinetic,
        "energy_balance_complete_rel": (heat_out + inlet_conduction + kinetic) / heat_in
        - 1,
        "bulk_outlet_K": t_out,
        "dp_dx_developed_Pa_m": gradient,
        "dp_dx_expected_Pa_m": expected,
        "dp_dx_rel_error": gradient / expected - 1,
        "pressure_drop_Pa": surface_value(case, "pressIn", t)
        - surface_value(case, "pressOut", t),
        "heated_face_peak_K": peak,
        "heated_face_peak_x_mm": peak_x * 1e3,
        "heated_face_mean_K": sum(v * w for _, v, w in face)
        / sum(w for _, _, w in face),
    }


def main(case):
    case = Path(case)
    spec = json.loads((case / "case.json").read_text())
    times = [t for t in (case / "times").read_text().split() if t != "0"]
    log = (case / "log.chtMultiRegionSimpleFoam").read_text()
    result = {
        "case": spec,
        "run": json.loads((case / "run.json").read_text()),
        "last_initial_residual": {
            f: last_initial(log, f) for f in ("h", "Ux", "p_rgh")
        },
        "by_iteration": {
            t: at_time(
                case, t, spec["geometry_mm"], spec.get("properties", VERIFICATION)
            )
            for t in times
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
