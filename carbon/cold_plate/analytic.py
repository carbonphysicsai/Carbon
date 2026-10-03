"""A closed-form microchannel model of the cold plate: the conventional method.

#342 asks for an analytical baseline beside the learned one. This is the
textbook one-dimensional heat-sink model, marched along the flow:

- **Coolant:** an energy balance gives the bulk temperature T_b(x); every
  PG25 property is taken at T_b from the pinned fit (`domain.PG25`).
- **Convection:** the fully developed Nusselt number of a rectangular duct
  heated on all four walls (Shah and London 1978, H1), blended with the
  thermal-entrance asymptote 1.302 x*^(-1/3) as (a^3 + b^3)^(1/3). The cases
  are thermally developing over most of their length (0.05 Re Pr D_h exceeds
  the 30 mm channel at the nominal point).
- **Fins:** the side walls and half the lid's underside each act as a fin of
  corrected height h_c + w_c/2 with an adiabatic tip, efficiency tanh(mH)/(mH).
  The channel floor is at the base's temperature.
- **Axial spreading:** the copper section of one period (base, fin and lid)
  conducts along the flow. The solid's excess temperature over the coolant,
  theta(x), obeys the fin equation k_s A theta'' - G'(x) theta = -q'(x), with
  adiabatic plate ends, where G' is the local conductance to the coolant and
  q' the applied heat, both per metre of one period. Its length scale,
  sqrt(k_s A / G'), is about 4.7 mm at the nominal point: longer than a hot
  spot, so without it a 3x spot reads about 27 K too hot (rung 7). The heat
  the coolant absorbs is G' theta, iterated with the bulk temperature.
- **Base:** one-dimensional conduction through its thickness, at the mean of
  the applied flux and the flux reaching the fins. Spreading across the cell
  is ignored, so the predicted peak is the span-mean peak.
- **Pressure:** fully developed laminar friction, f Re of the rectangular duct
  (Shah and London), with the property-ratio correction (mu_w/mu_b)^0.58 for a
  heated liquid (Kays and Crawford), plus the developing-flow increment
  K(inf) rho u^2 / 2 (Shah and London's rectangular-duct fit).

It is a baseline and the population's explicit screen (`max_wall_c`, `re_max`),
never a reference. Its error against the reference is measured, not assumed.
"""

from __future__ import annotations

import math

from .domain import (
    FIXED,
    K0,
    PROFILE_SEGMENTS,
    check_inputs,
    derived,
    heat_flux,
    pg25,
)

#: March steps along the 30 mm channel; each profile segment holds a whole
#: number of them.
STEPS_PER_SEGMENT = 20


def _nu_fully_developed(aspect):
    a = aspect
    return 8.235 * (
        1 - 2.0421 * a + 3.0853 * a**2 - 2.4765 * a**3 + 1.0578 * a**4 - 0.1861 * a**5
    )


def _f_re(aspect):
    a = aspect
    return 24.0 * (
        1 - 1.3553 * a + 1.9467 * a**2 - 1.7012 * a**3 + 0.9564 * a**4 - 0.2537 * a**5
    )


def _k_infinity(aspect):
    a = aspect
    return (
        0.6796
        + 1.2197 * a
        + 3.3089 * a**2
        - 9.5921 * a**3
        + 8.9089 * a**4
        - 2.9959 * a**5
    )


#: Passes of the coupling between the bulk temperature and the absorbed heat.
#: The third changes the peak by under 1e-6 K on the rung-7 cases.
COUPLING_PASSES = 3


def _spread(conductance, applied, k_area, dx):
    """theta from k_area theta'' - G theta = -q' with zero-flux ends (cell
    centred, ghost cells), by the Thomas algorithm. Summing the rows shows
    sum(G theta) dx = sum(q') dx exactly: spreading moves heat, never loses
    it."""
    n = len(applied)
    off = k_area / dx**2
    diag = [-(2 * off) - g for g in conductance]
    diag[0] += off
    diag[-1] += off
    rhs = [-q for q in applied]
    c_prime, d_prime = [0.0] * n, [0.0] * n
    c_prime[0] = off / diag[0]
    d_prime[0] = rhs[0] / diag[0]
    for i in range(1, n):
        denominator = diag[i] - off * c_prime[i - 1]
        c_prime[i] = off / denominator
        d_prime[i] = (rhs[i] - off * d_prime[i - 1]) / denominator
    theta = [0.0] * n
    theta[-1] = d_prime[-1]
    for i in range(n - 2, -1, -1):
        theta[i] = d_prime[i] - c_prime[i] * theta[i + 1]
    return theta


def predict(case):
    """Outputs in `domain.OUTPUTS` form, plus `diagnostics` the screen uses."""
    case = check_inputs(case)
    d = derived(case)
    w_c = case["channel_width_mm"] * 1e-3
    w_f = case["fin_width_mm"] * 1e-3
    h_c = case["channel_depth_mm"] * 1e-3
    length = FIXED["footprint_mm"] * 1e-3
    t_base = FIXED["base_mm"] * 1e-3
    k_s = FIXED["copper_k_w_mk"]
    period = w_c + w_f
    aspect = min(w_c, h_c) / max(w_c, h_c)
    d_h = 2 * w_c * h_c / (w_c + h_c)
    area = w_c * h_c
    m_dot = d["mass_flow_kg_s"] / d["channels"]  # one channel
    mass_flux = m_dot / area
    fin_height = h_c + w_c / 2
    nu_fd, f_re = _nu_fully_developed(aspect), _f_re(aspect)
    # Copper conducting along the flow, one period: base, fin and lid.
    k_area = k_s * (t_base * period + w_f * h_c + FIXED["lid_mm"] * 1e-3 * period)
    t_in = K0 + case["inlet_c"]

    steps = PROFILE_SEGMENTS * STEPS_PER_SEGMENT
    dx = length / steps
    xs = [(i + 0.5) * dx for i in range(steps)]
    flux = [heat_flux(case, x * 1e3) for x in xs]
    applied = [q * period for q in flux]  # W per metre of channel, one period
    absorbed = list(applied)  # first pass: heat enters the coolant where applied
    for _ in range(COUPLING_PASSES):
        bulk, conductance, reynolds = [], [], []
        t_b = t_in
        for x, q_abs in zip(xs, absorbed):
            cp, mu, k_f = pg25("cp", t_b), pg25("mu", t_b), pg25("kappa", t_b)
            # Bulk temperature at the step's middle, from the heat absorbed so far.
            t_mid = t_b + q_abs * dx / 2 / (m_dot * cp)
            re = mass_flux * d_h / mu
            x_star = x / (d_h * re * mu * cp / k_f)
            nu = (nu_fd**3 + (1.302 * x_star ** (-1 / 3)) ** 3) ** (1 / 3)
            h = nu * k_f / d_h
            m = math.sqrt(2 * h / (k_s * w_f))
            eta = math.tanh(m * fin_height) / (m * fin_height)
            conductance.append(h * (w_c + 2 * eta * fin_height))  # W/(m K)
            bulk.append(t_mid)
            reynolds.append(re)
            t_b += q_abs * dx / (m_dot * cp)
        theta = _spread(conductance, applied, k_area, dx)
        absorbed = [g * th for g, th in zip(conductance, theta)]
    walls = [tb + th for tb, th in zip(bulk, theta)]
    face = [
        wall + t_base / k_s * (q + q_abs / period) / 2
        for wall, q, q_abs in zip(walls, flux, absorbed)
    ]
    friction = 0.0
    for tb, wall in zip(bulk, walls):
        mu = pg25("mu", tb)
        u = mass_flux / pg25("rho", tb)
        friction += 2 * f_re * mu * (pg25("mu", wall) / mu) ** 0.58 * u / d_h**2 * dx
    rho_in = pg25("rho", t_in)
    u_in = mass_flux / rho_in
    entrance = _k_infinity(aspect) * rho_in * u_in**2 / 2
    profile = [
        sum(face[s * STEPS_PER_SEGMENT : (s + 1) * STEPS_PER_SEGMENT])
        / STEPS_PER_SEGMENT
        - K0
        for s in range(PROFILE_SEGMENTS)
    ]
    return {
        "peak_c": max(face) - K0,
        "mean_c": sum(profile) / len(profile),
        "profile_c": profile,
        "outlet_c": t_b - K0,
        "pressure_drop_pa": friction + entrance,
        "diagnostics": {
            "max_wall_c": max(walls) - K0,
            "re_max": max(reynolds),
            "channels": d["channels"],
        },
    }
