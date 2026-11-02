"""Gate G6: Carbon trains the graph (development only).

`prepare` turns a validated submission into what training needs, all built by
Carbon from the documents:

* `init(key) -> [params]`: the rebuilt init graph, or Carbon's initializers
  from the declared spec; never a module's own initialization;
* `apply(params, *inputs) -> outputs`: the rebuilt forward graph at its
  declared batch;
* `predict(params, *inputs)`: inference at any number of cases, padded into
  blocks of the declared batch (rows are independent, so every case's result
  is the one the declared graph computes);
* the Carbon key schedule (`keys`): the init key and the training key are
  Carbon's. An init graph never returns a key, so a submission cannot steer
  data order or any other randomness of training;
* `loss(pred, target, x, aux=()) -> scalar`, only for a submission carrying
  an admitted loss graph (`carbon.level4.loss`): the rebuilt per-case graph
  mapped over the batch by Carbon, then Carbon's mean (`per_case_mean`).
  None otherwise, and the Challenge's own loss trains.

The training loop itself is the Challenge's (its adapter's `train_graph`),
Carbon's own code: the registered optimizer menu, the Challenge's TRAIN data
and loss (or an admitted loss graph's), steps within the budget. Nothing here
chooses a value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import graph, initializers, interpret, validate
from . import loss as loss_slot

PARAMETER = validate.PARAMETER_PREFIX

#: `fold_in` data deriving the training key from the Carbon seed's key, so it
#: differs from the init key. An engineering constant, not a tuning value.
TRAIN_KEY_FOLD = 1


def keys(seed):
    """`(init_key, train_key)` for a Carbon seed."""
    import jax

    base = jax.random.PRNGKey(seed)
    return base, jax.random.fold_in(base, TRAIN_KEY_FOLD)


@dataclass(frozen=True)
class Prepared:
    init: Any
    apply: Any
    batch: int
    parameters: tuple
    #: The admitted loss graph, per case and mapped by Carbon, or None.
    loss: Any = None
    #: A jitted forward (`FORWARD_JIT`) only: `apply` mapped over cases (`jax.vmap`), each case its own zero-padded block.
    isolated_apply: Any = None

    def predict(self, params, *inputs, isolated=False):
        """Outputs for any number of cases, through the declared batch.

        `isolated` grades one case per call: the case is row 0 and the other
        rows are zeros, a fixed public constant, so no output can depend on
        another case. Judge-side inference sets it; training-time calls do not.
        A jitted forward runs the same per-case blocks mapped (`isolated_apply`),
        `ISOLATED_CHUNK` cases per call, so isolation is unchanged."""
        import jax.numpy as jnp

        n = inputs[0].shape[0]
        if isolated and self.isolated_apply is not None:
            outs = []
            for start in range(0, n, ISOLATED_CHUNK):
                stop = min(start + ISOLATED_CHUNK, n)
                blocks = []
                for x in inputs:
                    part = x[start:stop]
                    if stop - start < ISOLATED_CHUNK:  # whole zero cases, dropped below
                        part = jnp.pad(
                            part,
                            [(0, ISOLATED_CHUNK - (stop - start))]
                            + [(0, 0)] * (x.ndim - 1),
                        )
                    # (chunk, batch, ...): each case at row 0 of its own block, zero rows after
                    blocks.append(
                        jnp.pad(
                            part[:, None],
                            [(0, 0), (0, self.batch - 1)] + [(0, 0)] * (x.ndim - 1),
                        )
                    )
                out = self.isolated_apply(params, *blocks)
                outs.append([o[: stop - start, 0] for o in out])
            return [jnp.concatenate([b[k] for b in outs]) for k in range(len(outs[0]))]
        if isolated:
            blocks = []
            for i in range(n):
                chunk = [
                    jnp.pad(
                        x[i : i + 1], [(0, self.batch - 1)] + [(0, 0)] * (x.ndim - 1)
                    )
                    for x in inputs
                ]
                blocks.append([o[:1] for o in self.apply(params, *chunk)])
            return [
                jnp.concatenate([b[k] for b in blocks]) for k in range(len(blocks[0]))
            ]
        blocks = []
        for start in range(0, n, self.batch):
            stop = min(start + self.batch, n)
            chunk = []
            for x in inputs:
                part = x[start:stop]
                if stop - start < self.batch:
                    pad = [(0, self.batch - (stop - start))] + [(0, 0)] * (x.ndim - 1)
                    part = jnp.pad(part, pad)
                chunk.append(part)
            out = self.apply(params, *chunk)
            blocks.append([o[: stop - start] for o in out])
        return [jnp.concatenate([b[k] for b in blocks]) for k in range(len(blocks[0]))]


#: How a graph forward runs: op by op ("eager") or jitted ("jit": compiled once per input shape, so once per params state).
#: Practice, the trainer's train predictions and the judge's inference all call `Prepared.apply`, so a version runs jitted
#: everywhere or nowhere. Kept in this module (staged into every graph worker) so the workers stage nothing new.
FORWARD_EAGER = "eager"
FORWARD_JIT = "jit"
FORWARD_MODES = (FORWARD_EAGER, FORWARD_JIT)
#: Cases per mapped isolated call of a jitted forward (memory: this many blocks of the declared batch at once).
#: An engineering bound, not a scientific value; every chunk compiles to the same shape.
ISOLATED_CHUNK = 64
#: (challenge_id, version) pairs whose graph forward is jitted. A version opts in only by a Validator ruling; every live
#: (graded) version stays eager, so nothing graded is rescored. Empty until that ruling.
JIT_FORWARD_VERSIONS: frozenset = frozenset()


def forward_mode(challenge_id, version):
    """`FORWARD_JIT` for an opted-in version, else `FORWARD_EAGER` (the default, and every live version's)."""
    return (
        FORWARD_JIT
        if (challenge_id, version) in JIT_FORWARD_VERSIONS
        else FORWARD_EAGER
    )


def prepare(
    parsed, allowlist, *, verdict, kit=None, loss_override=None, forward=FORWARD_EAGER
):
    """G6's inputs from a verified (`submission.verify`) and validated
    (`validate.validate_submission`) submission.

    `kit` maps each `kit/` input name to Carbon's published array for it
    (OWNER-L4-CONSTANT-ACCOUNTING-02). `apply` binds those by name on every
    call, so `predict` (batched or isolated) never slices or pads them.

    `forward` is `forward_mode(challenge, version)`: "eager" (the default) runs
    the rebuilt graph op by op; "jit" wraps the SAME `apply` in `jax.jit`, compiled
    once per input shape (so once per params state), and every caller of `apply`
    (practice, train predictions, judge inference) gets it alike."""
    if verdict["status"] not in ("admitted", "blocked_human_input"):
        raise ValueError("prepare takes a validated submission")
    if forward not in FORWARD_MODES:
        raise ValueError("forward must be one of FORWARD_MODES")
    forward_run = forward
    forward = interpret.rebuild(parsed["forward"], allowlist)
    entry = parsed["forward"]["graphs"][parsed["forward"]["entry"]]
    order = [i["name"] for i in entry["inputs"]]
    kit_names = [n for n in order if n.startswith(validate.KIT_PREFIX)]
    if kit_names and (kit is None or not set(kit_names) <= set(kit)):
        raise graph.GraphRefused("kit_input_unbound", ",".join(kit_names))
    if "init" in parsed:
        rebuilt = interpret.rebuild(parsed["init"], allowlist)

        def init(key):
            return list(rebuilt(key))

    else:
        init = initializers.build(parsed["init_spec"], parsed["forward"])

    if not kit_names:

        def apply(params, *inputs):
            return forward(*params, *inputs)

    else:
        bound = {name: kit[name] for name in kit_names}

        def apply(params, *inputs):
            params, inputs = iter(params), iter(inputs)
            args = []
            for name in order:
                if name in bound:
                    args.append(bound[name])
                elif name.startswith(PARAMETER):
                    args.append(next(params))
                else:
                    args.append(next(inputs))
            return forward(*args)

    isolated_apply = None
    if forward_run == FORWARD_JIT:
        import jax

        n_inputs = (
            len(order)
            - len(kit_names)
            - sum(name.startswith(PARAMETER) for name in order)
        )
        isolated_apply = jax.jit(jax.vmap(apply, in_axes=(None,) + (0,) * n_inputs))
        apply = jax.jit(apply)
    loss = None
    if "loss" in parsed:
        # G4 admitted it (`validate_submission` with the Challenge's
        # `loss_override`); Carbon maps it per case and owns the mean.
        loss_graph = interpret.rebuild(parsed["loss"], allowlist)
        loss = (
            loss_slot.batch_loss(loss_graph)
            if loss_override == loss_slot.BATCH
            else loss_slot.per_case_mean(loss_graph)
        )
    return Prepared(
        init=init,
        apply=apply,
        batch=verdict["batch"],
        parameters=tuple(validate.parameters(parsed["forward"])),
        loss=loss,
        isolated_apply=isolated_apply,
    )


def train(adapter, recipe, prepared, *, seed):
    """The Challenge's Carbon training loop over a prepared graph."""
    return adapter.train_graph(recipe, prepared, seed=seed)
