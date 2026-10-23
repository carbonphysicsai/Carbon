"""F02 (Burst Thermal) public textbook prior as pure JAX ops (backbone-catalog lane, 2026-10-23).

Validator-ruled admissible as `prior.f02.two-node-rc-v1`, including the constriction-resistance term (a coefficient-1 textbook
term implied by the public half-width source, disclosed, not fitted). A two-node RC network from the public layer table
(silicon surrogate, TIM surrogate, copper surrogate; convection h to 30 C; initial 40 C; the source covers the left half of the
silicon): C_s dT_s/dt = P - (T_s - T_c)/R_sc, C_c dT_c/dt = (T_s - T_c)/R_sc - (T_c - T_cool)/R_conv, with
R_sc = t_si/(2 k A) + t_tim/(k A) + t_cu/(2 k A) + R_con and R_con = 1/(4 k_si a) for a circular-equivalent source of half the
silicon area. The rectangular pulse's response is the closed form of the 2x2 linear system (its eigen-decomposition is computed
once at import into constants). Note and errors: codex-queue/reports/PRIORS_F08_F02_FOR_VALIDATOR_20261023.md.

`prior(x)` takes (n, 2) inputs (peak_w, on_time_s) and returns (n, 1): the top (silicon) temperature at the end of the pulse.
It is a prior, never the exam reference.
"""

from __future__ import annotations

import math

import jax.numpy as jnp
import numpy as np

PRIOR_ID = "prior.f02.two-node-rc-v1"
INPUTS = ("peak_w", "on_time_s")
INPUT_BOUNDS = ((80.0, 140.0), (5.0, 20.0))
N_OUT = 1
POSITIVE_OUTPUTS = ()
T_COOL, T_START = 30.0, 40.0


def _constants():
    a_si, t_si, k_si, rho_si, cp_si = 4e-4, 5e-4, 130.0, 2330.0, 700.0
    t_tim, k_tim = 2e-4, 5.0
    a_cu, t_cu, k_cu, rho_cu, cp_cu = 9e-4, 2e-3, 390.0, 8960.0, 385.0
    h = 2500.0
    c_s, c_c = rho_si * cp_si * a_si * t_si, rho_cu * cp_cu * a_cu * t_cu
    a_source = 0.5 * a_si
    r_con = 1.0 / (4 * k_si * math.sqrt(a_source / math.pi))
    r_sc = t_si / (2 * k_si * a_si) + t_tim / (k_tim * a_si) + t_cu / (2 * k_cu * a_cu) + r_con
    r_cv = 1.0 / (h * a_cu)
    m = np.array([[-1 / (c_s * r_sc), 1 / (c_s * r_sc)], [1 / (c_c * r_sc), -(1 / r_sc + 1 / r_cv) / c_c]])
    b, c = np.array([1 / c_s, 0.0]), np.array([0.0, T_COOL / (c_c * r_cv)])
    w, v = np.linalg.eig(m)
    vi = np.linalg.inv(v)
    inverse = np.linalg.inv(m)
    slope, offset = -inverse @ b, -inverse @ c  # steady state: T_ss = slope * P + offset
    return w.real, v.real, vi.real, slope, offset


_W, _V, _VI, _SLOPE, _OFFSET = (np.asarray(a, dtype=np.float64) for a in _constants())


def prior(x):
    """(n, 2) inputs (peak_w, on_time_s) -> (n, 1)."""
    x = jnp.asarray(x)
    power, on = x[:, 0], x[:, 1]
    ss0, ss1 = float(_SLOPE[0]) * power + float(_OFFSET[0]), float(_SLOPE[1]) * power + float(_OFFSET[1])
    d0, d1 = T_START - ss0, T_START - ss1
    out = ss0
    for j in range(2):
        out = out + float(_V[0, j]) * jnp.exp(float(_W[j]) * on) * (float(_VI[j, 0]) * d0 + float(_VI[j, 1]) * d1)
    return out[:, None]
