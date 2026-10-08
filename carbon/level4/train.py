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
  data order or any other randomness of training.

The training loop itself is the Challenge's (its adapter's `train_graph`),
Carbon's own code: the registered optimizer menu, the Challenge's TRAIN data
and loss, steps within the budget. Nothing here chooses a value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import initializers, interpret, validate

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

    def predict(self, params, *inputs):
        """Outputs for any number of cases, through the declared batch."""
        import jax.numpy as jnp

        n = inputs[0].shape[0]
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


def prepare(parsed, allowlist, *, verdict):
    """G6's inputs from a verified (`submission.verify`) and validated
    (`validate.validate_submission`) submission."""
    if verdict["status"] not in ("admitted", "blocked_human_input"):
        raise ValueError("prepare takes a validated submission")
    forward = interpret.rebuild(parsed["forward"], allowlist)
    if "init" in parsed:
        rebuilt = interpret.rebuild(parsed["init"], allowlist)

        def init(key):
            return list(rebuilt(key))

    else:
        init = initializers.build(parsed["init_spec"], parsed["forward"])

    def apply(params, *inputs):
        return forward(*params, *inputs)

    return Prepared(
        init=init,
        apply=apply,
        batch=verdict["batch"],
        parameters=tuple(validate.parameters(parsed["forward"])),
    )


def train(adapter, recipe, prepared, *, seed):
    """The Challenge's Carbon training loop over a prepared graph."""
    return adapter.train_graph(recipe, prepared, seed=seed)
