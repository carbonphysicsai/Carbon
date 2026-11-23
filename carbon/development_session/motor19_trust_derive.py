"""Motor 1.9's trust `derive` (SELF_TRUST; owner MOTOR19-TRUST-REGISTRATION + MOTOR19-TRUST-FLOOR-0, 23 Nov 2026).

The jax-traceable map trust trainer v4 needs (`physical_graph_trainer_v4.TrustSpec.derive`): from the W = 241 native physics
columns of each case to the k = 5 derived scored outputs, in model-eval's order (5619): mean_torque_nm, ripple_pk_pk_nm,
back_emf_open_circuit, ke_ll_loaded, magnet_min_b_t. Written by exam-motor (reports/MOTOR_19_TRUST_DERIVE_20261123,
SHA256SUMS b16ff96c), reviewed by door-code (5648); placed here so it is staged into the trust build container
(`direct_graph_construction_worker.PHYSICAL_V2_TRUST_STAGED_MODULES`). jax is imported only when the map runs, so the
registration that names it stays importable where jax is not installed.

It equals the 1.9 grader's numpy derive (`carbon.scoring.motor19_dual_pack.pool_adapter().derive`) on rows that grader
accepts: mean = sum / len and ripple = max - min of the 60 torque columns; the k_e,ll ab waveform
d(lambda_A - lambda_B)/d theta with `carbon.motor.back_emf.derivative`'s stencil (central inside, one-sided second order
at both ends, no wrap, step = radians(15 / 60)); magnet_min_b_t = column 240. Two stated differences: (1) no validity
gate (selecting rows is the trainer's, not a differentiable map's); (2) the two EMF outputs are WAVEFORMS graded by their
shape error, and a Gaussian sigma needs one number per case: model-eval ruled 'rms' (5667), the RMS amplitude of the
waveform, the grade's own amplitude normalisation. So on the two EMF outputs trust covers the RMS AMPLITUDE, not the
graded shape.
"""

from __future__ import annotations

import math

ANGLE_STEPS = 60
PERIOD_DEG = 15.0
STEP_RAD = math.radians(PERIOD_DEG / ANGLE_STEPS)
WIDTH = 241
TORQUE = slice(0, 60)
LINKAGE_A = slice(60, 120)
LINKAGE_B = slice(120, 180)
MAGNET_COLUMN = 240
OUTPUTS = (
    "mean_torque_nm",
    "ripple_pk_pk_nm",
    "back_emf_open_circuit",
    "ke_ll_loaded",
    "magnet_min_b_t",
)
EMF_SCALARS = ("rms", "pk_pk")


def derivative(y):
    """d y / d theta_mech along the last axis (60 steps) of an (n, 60) array: `back_emf.derivative`'s stencil."""
    import jax.numpy as jnp

    step = STEP_RAD
    first = (-3.0 * y[:, 0] + 4.0 * y[:, 1] - y[:, 2]) / (2.0 * step)
    last = (3.0 * y[:, -1] - 4.0 * y[:, -2] + y[:, -3]) / (2.0 * step)
    inner = (y[:, 2:] - y[:, :-2]) / (2.0 * step)
    return jnp.concatenate([first[:, None], inner, last[:, None]], axis=1)


def make_derive(emf_scalar):
    """The derive for a stated scalar of the k_e,ll waveform ('rms' or 'pk_pk'); no default (a registration value)."""
    if emf_scalar not in EMF_SCALARS:
        raise ValueError("emf_scalar must be 'rms' or 'pk_pk'")

    def derive(rows, inputs):
        import jax.numpy as jnp

        del inputs  # none of the five derived outputs depends on the case's inputs
        rows = jnp.asarray(rows)
        torque = rows[:, TORQUE]
        mean = jnp.mean(torque, axis=1)
        ripple = jnp.max(torque, axis=1) - jnp.min(torque, axis=1)
        ke = derivative(rows[:, LINKAGE_A] - rows[:, LINKAGE_B])
        if emf_scalar == "rms":
            emf = jnp.sqrt(jnp.mean(ke * ke, axis=1))
        else:
            emf = jnp.max(ke, axis=1) - jnp.min(ke, axis=1)
        return jnp.stack([mean, ripple, emf, emf, rows[:, MAGNET_COLUMN]], axis=1)

    return derive


__all__ = ["EMF_SCALARS", "OUTPUTS", "WIDTH", "derivative", "make_derive"]
