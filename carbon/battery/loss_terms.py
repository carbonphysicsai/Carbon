"""Battery's Level-1 loss terms and the trainer's loss factory.

Standalone: numpy or `jax.numpy` comes in as `xp`, and the loss-expression
module comes in as `le`, because this file is also staged into the isolated
practice worker (`carbon.battery.level1_worker`), where it cannot import
Carbon. Nothing here reads anything but TRAIN outputs, TRAIN targets and the
output weights.

Terms (every one non-negative):
- the GA-D6 per-case terms, computed exactly as `training.case_loss` computes
  its objective menu;
- each output group's share of the squared error and of the target energy
  (`sq_error_<group>`, `target_energy_<group>`);
- per trajectory (normalized voltage, normalized temperature), the time terms:
  the squared error at each time and the time coordinate, both ways.
"""

from __future__ import annotations

CASE_TERMS = (
    "sq_error",
    "target_energy",
    "traj_ramp_early",
    "traj_ramp_late",
    "traj_d1",
    "traj_d2",
    "traj_spectral",
)
GROUPS = ("voltage", "temperature", "plating", "capacity")
COMPONENT_TERMS = tuple(f"sq_error_{g}" for g in GROUPS) + tuple(
    f"target_energy_{g}" for g in GROUPS
)
TIME_TERMS = ("err_sq_t", "time_t", "time_rev_t")
TRAJECTORIES = ("voltage", "temperature")
#: The Q6 label every Level-1 result carries until GPU identity is measured.
REBUILD_LABEL = "rebuild: CPU-verified only"


def case_terms(xp, zhat, zt, gw, trajectory, groups):
    """The per-case terms for outputs `zhat` against targets `zt`.

    `gw` weights the outputs; `trajectory(z)` returns the normalized voltage
    and temperature trajectories (cases x times); `groups` names each output
    group's columns as `(name, start, stop)`."""
    error = zhat - zt
    pairs = [a - b for a, b in zip(trajectory(zhat), trajectory(zt))]

    def summed(per_trajectory):
        total = 0.0
        for e in pairs:
            total = total + per_trajectory(e)
        return total

    def spectral(e):
        spectrum = xp.abs(xp.fft.rfft(e, axis=1)) ** 2
        k = xp.linspace(0.0, 1.0, spectrum.shape[1])
        return xp.mean(k * spectrum, axis=1) / e.shape[1]

    terms = {
        "sq_error": xp.sum(error**2 * gw[None, :], axis=1),
        "target_energy": xp.sum(zt**2 * gw[None, :], axis=1),
        "traj_ramp_early": summed(
            lambda e: xp.mean(xp.linspace(2.0, 0.0, e.shape[1]) * e**2, axis=1)
        ),
        "traj_ramp_late": summed(
            lambda e: xp.mean(xp.linspace(0.0, 2.0, e.shape[1]) * e**2, axis=1)
        ),
        "traj_d1": summed(lambda e: xp.mean(xp.diff(e, axis=1) ** 2, axis=1)),
        "traj_d2": summed(lambda e: xp.mean(xp.diff(e, n=2, axis=1) ** 2, axis=1)),
        "traj_spectral": summed(spectral),
    }
    for name, start, stop in groups:
        w = gw[None, start:stop]
        terms["sq_error_" + name] = xp.sum(error[:, start:stop] ** 2 * w, axis=1)
        terms["target_energy_" + name] = xp.sum(zt[:, start:stop] ** 2 * w, axis=1)
    return terms


def time_terms(xp, zhat, zt, trajectory):
    """Per trajectory, the time terms (cases x times)."""
    out = {}
    for name, a, b in zip(TRAJECTORIES, trajectory(zhat), trajectory(zt)):
        e = a - b
        n = e.shape[1]
        forward = xp.linspace(0.0, 1.0, n, dtype=e.dtype)[None, :]
        backward = xp.linspace(1.0, 0.0, n, dtype=e.dtype)[None, :]
        out[name] = {
            "err_sq_t": e**2,
            "time_t": xp.broadcast_to(forward, e.shape),
            "time_rev_t": xp.broadcast_to(backward, e.shape),
        }
    return out


def load(le, expression_bytes, operation_set_document):
    """Recompile a pinned expression from its canonical bytes against the
    operation set its document describes (the reconstruction rule)."""
    opset = le.OperationSet.from_document(operation_set_document)
    return le.from_bytes(expression_bytes, opset)


def jax_only(xp):
    """R2: a Level-1 loss is rebuilt with JAX against JAX, never with numpy."""
    if getattr(xp, "__name__", None) != "jax.numpy":
        raise TypeError("a Level-1 loss is rebuilt with jax.numpy only")


def factory(le, compiled):
    """The trainer's loss factory (`recipes.MLP`'s `loss`) for a compiled
    expression: `loss(xp, trajectory, groups) -> (zhat, zt, gw) -> loss`."""

    def loss(xp, trajectory, groups):
        jax_only(xp)
        timed = bool(compiled.operation_set.time_terms)

        def per_case(zhat, zt, gw):
            terms = case_terms(xp, zhat, zt, gw, trajectory, groups)
            trajectories = time_terms(xp, zhat, zt, trajectory) if timed else None
            return le.evaluate(compiled, terms, xp, trajectories)

        return per_case

    return loss
