"""Cooling's public analytic prior as pure JAX ops (backbone-catalog lane, 2026-10-23).

A port of `carbon.cold_plate.analytic.predict` (the textbook one-dimensional microchannel model the repository already
publishes as Cooling's conventional baseline) into array operations on a batch, followed by Cooling's law-safe output
encoding (`carbon.cold_plate.output_encoding`, Cooling 1.3). `prior(x)` takes the (n, 9) inputs in the interface's order
and returns the (n, 32) encoded slots: slot 0 the raw peak excess, slots 1-30 the profile, slot 31 the raw pressure.

Only operations on the allowlist are used (add, mul, div, pow, exp, log, log1p, expm1, tanh, sqrt, erf, floor, max, select,
reduce_sum, reduce_max, split, concatenate). The bulk-temperature march is an unrolled Python loop over the cells (it is
sequential by nature); the tridiagonal conduction solve is parallel cyclic reduction (log2 levels of array operations);
everything else is vectorised over the cells.

Fidelity: the port follows the reference model line for line at a coarser march (see STEPS_PER_SEGMENT); the other differences
are floating-point order and `floor(30 / period + 1e-9)` for the channel count (the reference's `int(30 // period + 1e-9)`). It is a prior, never a
reference: the scored outputs are the learned model's, and the exam never uses this module.
"""

from __future__ import annotations

import jax.numpy as jnp
from jax import lax

PRIOR_ID = "cold_plate.analytic.v1"
INPUTS = (
    "channel_width_mm",
    "fin_width_mm",
    "channel_depth_mm",
    "flow_lpm_per_kw",
    "inlet_c",
    "heat_load_w",
    "hotspot_ratio",
    "hotspot_center_mm",
    "hotspot_width_mm",
)
INPUT_BOUNDS = (
    (0.2, 0.5),
    (0.2, 0.5),
    (1.0, 3.0),
    (1.25, 2.0),
    (30.0, 45.0),
    (500.0, 1500.0),
    (1.0, 3.0),
    (3.0, 27.0),
    (1.5, 3.5),
)
N_OUT = 32
#: Outputs whose decoded value is positive (slot 31: pressure = softplus(raw)); a learned model may work in log space on them.
POSITIVE_OUTPUTS = (31,)
FOOTPRINT_MM, BASE_MM, LID_MM, COPPER_K = 30.0, 1.0, 0.5, 391.0
K0 = 273.15
PROFILE_SEGMENTS = 30
#: The repository's model marches 20 cells per profile segment with 3 coupling passes (`carbon.cold_plate.analytic`). That unrolled
#: is ~16k graph nodes (about 2 MB); 10 cells per segment and 2 passes is ~6k nodes. The model, its closed forms and the
#: coupling are the same; the measured difference from the repository's output is at most 0.02 K on the peak, 0.07 K on the
#: profile and 1e-4 relative on the pressure (rung-7 style inputs, 24 TRAIN rows). Set STEPS_PER_SEGMENT = 20 and
#: COUPLING_PASSES = 3 to reproduce `analytic.predict` to rounding (`native(x, 20, 3)` does, for a check).
STEPS_PER_SEGMENT, COUPLING_PASSES = 10, 2
ULP_FACTOR, F32_EPS = 32, 2.0**-23
PG25 = {
    "rho": (471.83672241567854, 5.3710481851085525, -0.01615703005055183, 1.4345731910287373e-05),
    "cp": (2927.6100828735266, 4.2380574169872585, -0.002916907594152528),
    "kappa": (0.33130560354466126, -0.0005363884701318896, 5.322835865529474e-06, -6.495569444909945e-09),
    "mu": (
        11.809225533760118,
        -0.19835015412139706,
        0.0013929060738771873,
        -5.23132660955004e-06,
        1.1076921123177383e-08,
        -1.2533006110289745e-11,
        5.917954657407082e-15,
    ),
}


def _pg(name, t):
    value = 0.0
    for c in reversed(PG25[name]):
        value = value * t + c
    return value


def _nu_fully_developed(a):
    return 8.235 * (1 - 2.0421 * a + 3.0853 * a**2 - 2.4765 * a**3 + 1.0578 * a**4 - 0.1861 * a**5)


def _f_re(a):
    return 24.0 * (1 - 1.3553 * a + 1.9467 * a**2 - 1.7012 * a**3 + 0.9564 * a**4 - 0.2537 * a**5)


def _k_infinity(a):
    return 0.6796 + 1.2197 * a + 3.3089 * a**2 - 9.5921 * a**3 + 8.9089 * a**4 - 2.9959 * a**5


def _columns(items):
    """Equal-length (n,) vectors as the columns of an (n, len) array (concatenate, which the allowlist has; `stack` it has not)."""
    return jnp.concatenate([item[:, None] for item in items], axis=1)


def _shift(x, by, fill):
    """x moved `by` places along axis 1 (positive: x[:, i - by] at i), `fill` where nothing arrives."""
    n, width = x.shape
    pad = jnp.full((n, abs(by)), fill, dtype=x.dtype)
    if by > 0:
        return jnp.concatenate([pad, x[:, : width - by]], axis=1)
    return jnp.concatenate([x[:, -by:], pad], axis=1)


def _solve_tridiagonal(off, diag, rhs):
    """Solve off*x[i-1] + diag[i]*x[i] + off*x[i+1] = rhs[i] (no neighbour past either end) by parallel cyclic reduction."""
    n, width = diag.shape
    index = jnp.arange(width)
    lower = jnp.where(index == 0, 0.0, 1.0).astype(diag.dtype)[None, :] * off
    upper = jnp.where(index == width - 1, 0.0, 1.0).astype(diag.dtype)[None, :] * off
    b, d = diag, rhs
    a, c = lower, upper
    stride = 1
    while stride < width:
        alpha = -a / _shift(b, stride, 1.0)
        gamma = -c / _shift(b, -stride, 1.0)
        b, d, a, c = (
            b + alpha * _shift(c, stride, 0.0) + gamma * _shift(a, -stride, 0.0),
            d + alpha * _shift(d, stride, 0.0) + gamma * _shift(d, -stride, 0.0),
            alpha * _shift(a, stride, 0.0),
            gamma * _shift(c, -stride, 0.0),
        )
        stride *= 2
    return d / b


def native(x, steps_per_segment=STEPS_PER_SEGMENT, passes=COUPLING_PASSES):
    """(peak_c (n,), profile_c (n, 30), pressure_drop_pa (n,)) of the analytic model for (n, 9) inputs."""
    x = jnp.asarray(x)
    dt = x.dtype
    wc_mm, wf_mm, hc_mm, lpm, inlet, load, ratio, centre, width = (x[:, i] for i in range(9))
    w_c, w_f, h_c = wc_mm * 1e-3, wf_mm * 1e-3, hc_mm * 1e-3
    length, t_base = FOOTPRINT_MM * 1e-3, BASE_MM * 1e-3
    k_s = COPPER_K
    period = w_c + w_f
    aspect = jnp.minimum(w_c, h_c) / jnp.maximum(w_c, h_c)
    d_h = 2 * w_c * h_c / (w_c + h_c)
    area = w_c * h_c
    t_in = K0 + inlet
    channels = jnp.floor(FOOTPRINT_MM / (wc_mm + wf_mm) + 1e-9)
    flow = load / 1000.0 * lpm / 60000.0
    mass_flow = _pg("rho", t_in) * flow
    m_dot = mass_flow / channels
    mass_flux = m_dot / area
    fin_height = h_c + w_c / 2
    nu_fd, f_re = _nu_fully_developed(aspect), _f_re(aspect)
    k_area = k_s * (t_base * period + w_f * h_c + LID_MM * 1e-3 * period)

    steps = PROFILE_SEGMENTS * steps_per_segment
    dx = length / steps
    xs = (jnp.arange(steps, dtype=dt) + 0.5) * dx  # metres
    # hotspot map (domain.hotspot_shape / heat_flux)
    root = width * jnp.sqrt(2.0)
    mean_g = (
        width * jnp.sqrt(jnp.pi / 2.0) / FOOTPRINT_MM * (lax.erf((FOOTPRINT_MM - centre) / root) + lax.erf(centre / root))
    )
    amplitude = (ratio - 1.0) / (1.0 - ratio * mean_g)
    mean_shape = 1.0 + amplitude * mean_g
    g = jnp.exp(-0.5 * ((xs[None, :] * 1e3 - centre[:, None]) / width[:, None]) ** 2)
    side = FOOTPRINT_MM * 1e-3
    flux = (load / side**2 / mean_shape)[:, None] * (1.0 + amplitude[:, None] * g)  # (n, steps)
    applied = flux * period[:, None]
    absorbed = applied
    col = lambda a, i: a[:, i]  # noqa: E731

    for _ in range(passes):
        # the bulk temperature entering each cell: a sequential march
        tbs, t_b = [], t_in[:, None]
        heat = absorbed * dx / m_dot[:, None]
        steps_b = [heat[:, i : i + 1] for i in range(steps)]  # slices, not `split`: the public interpreter has no split
        for step_b in steps_b:
            tbs.append(t_b)
            t_b = t_b + step_b / _pg("cp", t_b)
        tb = jnp.concatenate(tbs, axis=1)
        cp, mu, k_f = _pg("cp", tb), _pg("mu", tb), _pg("kappa", tb)
        bulk = tb + absorbed * dx / 2 / (m_dot[:, None] * cp)
        re = (mass_flux * d_h)[:, None] / mu
        x_star = xs[None, :] / (d_h[:, None] * re * mu * cp / k_f)
        nu = (nu_fd[:, None] ** 3 + (1.302 * x_star ** (-1 / 3)) ** 3) ** (1 / 3)
        h = nu * k_f / d_h[:, None]
        m = jnp.sqrt(2 * h / (k_s * w_f[:, None]))
        mh = m * fin_height[:, None]
        eta = jnp.tanh(mh) / mh
        conductance = h * (w_c[:, None] + 2 * eta * fin_height[:, None])
        # theta from k_area theta'' - G theta = -q' (zero-flux ends): a symmetric tridiagonal system, solved by parallel cyclic
        # reduction (log2(steps) levels of array operations; the Thomas algorithm it replaces is sequential, which unrolled costs
        # thousands of graph nodes).
        off = (k_area / dx**2)[:, None]
        edge = ((jnp.arange(steps) == 0) | (jnp.arange(steps) == steps - 1)).astype(dt)
        diag = -2 * off - conductance + off * edge[None, :]
        theta = _solve_tridiagonal(off, diag, -applied)
        absorbed = conductance * theta
    walls = bulk + theta
    face = walls + (t_base / k_s) * (flux + absorbed / period[:, None]) / 2
    mu_b = _pg("mu", bulk)
    u = mass_flux[:, None] / _pg("rho", bulk)
    friction = jnp.sum(
        2 * f_re[:, None] * mu_b * (_pg("mu", walls) / mu_b) ** 0.58 * u / d_h[:, None] ** 2 * dx, axis=1
    )
    rho_in = _pg("rho", t_in)
    u_in = mass_flux / rho_in
    entrance = _k_infinity(aspect) * rho_in * u_in**2 / 2
    profile = jnp.mean(face.reshape(face.shape[0], PROFILE_SEGMENTS, steps_per_segment), axis=2) - K0
    return jnp.max(face, axis=1) - K0, profile, friction + entrance


def _inverse_softplus(y):
    big = y > 20.0
    small_arg = jnp.where(big, 1.0, y)
    big_arg = jnp.where(big, y, 25.0)
    return jnp.where(big, big_arg + jnp.log1p(-jnp.exp(-big_arg)), jnp.log(jnp.expm1(small_arg)))


def encode(peak, profile, pressure):
    """The (n, 32) encoded slots (`output_encoding.encode_targets`) of a native prediction."""
    profile_max = jnp.max(profile, axis=1)
    floor = ULP_FACTOR * F32_EPS * jnp.maximum(1.0, jnp.abs(profile_max))
    excess = jnp.maximum(peak - profile_max, floor)
    return jnp.concatenate(
        [_inverse_softplus(excess)[:, None], profile, _inverse_softplus(pressure)[:, None]], axis=1
    )


def decode_positive(raw):
    """The positive quantity a raw slot holds (softplus)."""
    return jnp.maximum(raw, 0.0) + jnp.log1p(jnp.exp(-jnp.abs(raw)))


def encode_positive(value):
    """The raw slot value of a positive decoded value (inverse softplus)."""
    return _inverse_softplus(value)


def prior(x):
    """The prior in the interface's output encoding: (n, 9) inputs -> (n, 32)."""
    return encode(*native(x))
