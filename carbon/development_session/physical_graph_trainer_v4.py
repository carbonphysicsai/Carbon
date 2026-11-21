"""Trainer v4: the two-phase trainer of a SELF-TRUST version (the name matches the grading-path rule `physical_graph_trainer_vN`) (SELF_TRUST DESIGN_v2 sections 7-8, H3d-2b).

A trust candidate's graph returns `W + k` columns: the W physics columns and k trust columns (log-sigma, one per trust output),
with the trust head sharing no parameter with the physics columns (`carbon.level4.trust_head`). This module trains it in TWO
phases so that the physics fit is exactly what it is today:

* PHASE 1: the version's pinned trainer (v2 or v3), UNCHANGED, runs on a W-VIEW of the model: `prepare` was called on the original
  document (the initializer check binds `graph.digest(doc)`), and here `Prepared.apply` is replaced by a slice of its first W
  columns, so the pinned trainer sees W outputs, W targets, a W-wide decoder and combination. The trust parameters reach no W
  output, so they receive exactly zero gradient. (Optimiser weight decay acts on every parameter regardless of gradient, so a
  result is deterministic, and phase 2 restarts the trust parameters from their initial values anyway.)
* PHASE 2: a new optax loop updates ONLY the trust parameters of the ONE trust member (member 0, door-code 04:34:35Z), restarted
  from their INITIAL values (optimiser weight decay would otherwise have drifted them in phase 1), on the HELD-OUT rows, the TRAIN
  rows phase 1 never used (`train_fraction` < 1), with a Gaussian negative log-likelihood of each trust output's residual
  `derive(ensemble prediction) - derive(truth)` under `sigma = floor + exp(log_sigma)`: the residual is the ENSEMBLE's (every
  member's W columns combined by `combine`, decoded), the prediction Carbon reports, never member 0's alone. The physics columns
  and every other parameter are frozen, so the W columns are byte-identical with and without the trust head.

NO SILENT IN-SAMPLE FALLBACK (V2 09:10:14Z): with no held-out row (`train_fraction` >= 1, or too few rows) phase 2 does not run and
the result carries the typed status `no_held_out_rows`; the trust parameters are whatever phase 1 returned (never an in-sample fit) and the trust read
reports nothing. Every science-adjacent value (the sigma floor per trust output, the phase-2 epochs and learning rate) is the
version's registration with NO default: a missing one refuses typed (`trust_value_is_human_input`).

Runs inside the isolated build worker with its staged modules only; it reads no participant Python and grants no judge authority.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

SCHEMA = "carbon.physical-graph-trainer.v4"
#: The member that owns the trust columns (the state records it too: `physical_graph_state_v3.TRUST_MEMBER`).
TRUST_MEMBER = 0
TRAINED = "trained"
NO_HELD_OUT_ROWS = "no_held_out_rows"


class TrustRefused(ValueError):
    """A typed refusal; `code` is stable and carries no content."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TrustSpec:
    """One version's registration of its trust training. Structural fields first, then the values that are the owner's."""

    #: W, the physics columns; `outputs` = k, the trust outputs (one log-sigma column each).
    width: int
    outputs: int
    #: jax-traceable `derive(native_rows) -> (n, k)`: the k derived scored outputs from the W native physics columns.
    derive: Callable[[Any], Any]
    #: Indices (graph parameter input order) of the trust head's parameters, from `trust_head.check`; all in member 0.
    trust_parameters: tuple
    #: HUMAN_INPUT (None refuses): per trust output a positive sigma floor in the derived output's unit, the phase-2 epochs over
    #: the held-out rows (a positive int) and the Adam learning rate (a positive float).
    sigma_floor: object = None
    epochs: object = None
    learning_rate: object = None


def _positive(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def check(spec: TrustSpec) -> None:
    """Refuse unless `spec` is complete: the structure sound and every value of the owner's present and in its domain."""
    if (
        not isinstance(spec, TrustSpec)
        or type(spec.width) is not int
        or spec.width < 1
        or type(spec.outputs) is not int
        or spec.outputs < 1
        or not callable(spec.derive)
        or type(spec.trust_parameters) is not tuple
        or not spec.trust_parameters
        or any(type(i) is not int or i < 0 for i in spec.trust_parameters)
        or len(set(spec.trust_parameters)) != len(spec.trust_parameters)
    ):
        raise TrustRefused("trust_spec_malformed")
    if spec.sigma_floor is None or spec.epochs is None or spec.learning_rate is None:
        raise TrustRefused("trust_value_is_human_input")
    if (
        type(spec.sigma_floor) is not tuple
        or len(spec.sigma_floor) != spec.outputs
        or not all(_positive(v) for v in spec.sigma_floor)
        or type(spec.epochs) is not int
        or spec.epochs < 1
        or not _positive(spec.learning_rate)
    ):
        raise TrustRefused("trust_value_out_of_domain")


def held_out_rows(count: int, selected: np.ndarray) -> np.ndarray:
    """The TRAIN rows the base trainer did NOT select, in TRAIN order (empty at `train_fraction` 1)."""
    return np.setdiff1d(np.arange(count), np.asarray(selected))


def w_view(prepared, width: int):
    """`prepared` seen through its first `width` output columns: the pinned trainer then sees a W-wide model. `apply` runs the
    forward at the declared batch and returns the list of outputs; only the first output's trailing columns are cut.
    """
    apply = prepared.apply

    def narrow(params, *inputs):
        outputs = apply(params, *inputs)
        return [outputs[0][..., :width], *outputs[1:]]

    return dataclasses.replace(prepared, apply=narrow, isolated_apply=None)


def trust_nll(residual, log_sigma, floor):
    """Gaussian negative log-likelihood per case, summed over the trust outputs: `0.5 (r / s)^2 + log s`, `s = floor + exp(log_sigma)`
    (the floor keeps s positive and bounded below; it is the version's registered value, never a default here).
    """
    import jax.numpy as jnp

    sigma = jnp.asarray(floor) + jnp.exp(log_sigma)
    return jnp.sum(0.5 * (residual / sigma) ** 2 + jnp.log(sigma), axis=-1)


def _chunks(held: np.ndarray, batch: int):
    """Fixed-order chunks of `batch` held-out rows; the last is padded with its first row and masked (the forward runs at the
    declared batch only), so every held-out row counts exactly once per epoch."""
    for start in range(0, len(held), batch):
        part = held[start : start + batch]
        used = len(part)
        if used < batch:
            part = np.concatenate([part, np.full(batch - used, part[0])])
        yield part, used


def combined_residual(
    prepared, members, combine, inputs, targets, mu, sd, held, spec: TrustSpec
):
    """The residual the trust read judges: the held-out rows' ENSEMBLE prediction (every member's first W columns weighted by
    `combine`, then decoded by `mu`, `sd`) through the trust outputs' derive, less the derived truth. Fixed (no gradient), computed
    once; `(len(held), k)` in the held-out rows' order. With one member it is that member's own residual (door-code 09:57:05Z: the
    prediction Carbon reports is the ensemble's, so sigma is calibrated to the ensemble's residual, never member 0's alone).
    """
    import jax.numpy as jnp

    width = spec.width
    combine_j, mu_j, sd_j = jnp.asarray(combine), jnp.asarray(mu), jnp.asarray(sd)
    held_rows = jnp.asarray(held)
    x_held, y_held = jnp.asarray(inputs)[held_rows], jnp.asarray(targets)[held_rows]
    total = None
    for weights, member in zip(combine_j, members):
        params = [jnp.asarray(p) for p in member]
        # the way Carbon GRADES: one case per call, the case at row 0 and zero rows after (door-code 10:10:41Z: a graph whose
        # output depends on its batch-mates is allowed to build, which is why grading is isolated; the residual must be the
        # reported prediction's, not a batched one's)
        term = prepared.predict(params, x_held, isolated=True)[0][..., :width] * weights
        total = term if total is None else total + term
    residual = spec.derive(total * sd_j + mu_j) - spec.derive(y_held)
    return np.asarray(residual)


def _initial_trust_parameters(prepared, seed, indices, like):
    """The trust parameters at their INITIAL values, drawn exactly as the pinned trainer draws member 0's (`keys(seed)` folded with
    the member index): phase 1 gives them zero gradient but optimiser weight decay would still have drifted them, and phase 2 must
    not start from a value that depends on the physics schedule (door-code 09:57:05Z).
    """
    import jax

    from carbon.level4.train import keys

    init_key, _train_key = (jax.random.fold_in(k, TRUST_MEMBER) for k in keys(seed))
    fresh = prepared.init(init_key)
    return [np.asarray(fresh[i]).astype(like[i].dtype) for i in indices]


def train_trust_head(
    prepared, member, residual, inputs, held, spec: TrustSpec, *, start
):
    """PHASE 2: member 0's parameters with ONLY `spec.trust_parameters` updated, from `start` (their initial values), on the held-out
    rows; every other parameter is returned bit for bit. `residual` is the fixed ensemble residual of `combined_residual`; the
    forward of member 0 supplies only the k log-sigma columns."""
    import jax
    import jax.numpy as jnp
    import optax

    width = spec.width
    frozen = [jnp.asarray(p) for p in member]
    indices = list(spec.trust_parameters)
    if any(i >= len(frozen) for i in indices):
        raise TrustRefused("trust_spec_malformed")
    floor = jnp.asarray(spec.sigma_floor)
    x_all, r_all = jnp.asarray(inputs), jnp.asarray(residual)

    def merged(trust_values):
        full = list(frozen)
        for index, value in zip(indices, trust_values):
            full[index] = value
        return full

    def chunk_loss(trust_values, x, r, mask):
        outputs = prepared.apply(merged(trust_values), x)[0]
        per_case = trust_nll(r, outputs[..., width:], floor)
        return jnp.sum(per_case * mask) / jnp.sum(mask)

    step = jax.jit(jax.value_and_grad(chunk_loss))
    optimiser = optax.adam(float(spec.learning_rate))
    trust_values = [jnp.asarray(v) for v in start]
    state = optimiser.init(trust_values)
    batch = prepared.batch
    plan = []
    for number, (rows, used) in enumerate(_chunks(held, batch)):
        r = r_all[number * batch : number * batch + used]
        if used < batch:
            r = jnp.concatenate([r, jnp.zeros((batch - used,) + r.shape[1:], r.dtype)])
        plan.append(
            (
                jnp.asarray(rows),
                r,
                jnp.asarray(np.arange(batch) < used, dtype=r_all.dtype),
            )
        )
    for _epoch in range(spec.epochs):
        for rows, r, mask in plan:
            _loss, grads = step(trust_values, x_all[rows], r, mask)
            updates, state = optimiser.update(grads, state, trust_values)
            trust_values = optax.apply_updates(trust_values, updates)
    out = [np.asarray(p) for p in member]
    for index, value in zip(indices, trust_values):
        value = np.asarray(value)
        if not np.isfinite(value).all():
            raise TrustRefused("trust_nonfinite_state")
        out[index] = value.astype(out[index].dtype)
    return out


def train(prepared, inputs, targets, settings, *, seed, base_trainer, spec: TrustSpec):
    """Both phases. `base_trainer` is the version's pinned trainer module (`physical_graph_trainer_v2` / `_v3`: its `train` and
    `selected_rows`), run unchanged on the W-view. Returns the base trainer's result with member 0's trust parameters trained
    and a `trust` block: `{"status": "trained" | "no_held_out_rows", "held_out_rows": n}`. A batch loss graph is refused (V2
    09:10:14Z: the trainer feeds W columns, a loss graph on the trust interface would take W + k).
    """
    check(spec)
    if prepared.loss is not None:
        raise TrustRefused("trust_loss_graph_not_offered")
    result = base_trainer.train(
        w_view(prepared, spec.width), inputs, targets, settings, seed=seed
    )
    selected = base_trainer.selected_rows(len(inputs), settings["train_fraction"], seed)
    held = held_out_rows(len(inputs), selected)
    if len(held) == 0:
        return {**result, "trust": {"status": NO_HELD_OUT_ROWS, "held_out_rows": 0}}
    members = [list(member) for member in result["members"]]
    residual = combined_residual(
        prepared,
        members,
        result["combine"],
        inputs,
        targets,
        result["mu"],
        result["sd"],
        held,
        spec,
    )
    start = _initial_trust_parameters(
        prepared, seed, list(spec.trust_parameters), members[TRUST_MEMBER]
    )
    members[TRUST_MEMBER] = train_trust_head(
        prepared, members[TRUST_MEMBER], residual, inputs, held, spec, start=start
    )
    return {
        **result,
        "members": members,
        "trust": {"status": TRAINED, "held_out_rows": len(held)},
    }
