"""Gate G7: Carbon grades the trained graph (development only).

* **Inference** runs the trained graph through `Prepared.predict`, at the
  declared batch, padded, so every case's output is the declared graph's.
* **Finite outputs.** Each case with a non-finite output is named. It is not
  repaired, and it is not a refusal of the submission: the Challenge's own
  exam gates type it (mandatory gate failure is never compensated by score).
* **Inference cost** is measured from the compiled forward graph (FLOPs,
  bytes accessed, XLA temp memory), per call and per case. It is recorded
  only; whether and how it is capped or scored is the Challenge's exam rule,
  `HUMAN_INPUT` until an owner sets it.
* **The exam** is the Challenge's code, unchanged, through the adapter's
  `grade_graph`.
"""

from __future__ import annotations

from .allowlist import HUMAN_INPUT

#: The inference-cost rule (D6). None is chosen here.
INFERENCE_COST_RULE = HUMAN_INPUT


def inference_cost(prepared, params, inputs):
    """The compiled forward graph's cost at its declared batch."""
    import jax

    def forward(p, *xs):
        return prepared.apply(p, *xs)

    shaped = [
        jax.ShapeDtypeStruct((prepared.batch, *x.shape[1:]), x.dtype) for x in inputs
    ]
    params_shape = [jax.ShapeDtypeStruct(p.shape, p.dtype) for p in params]
    compiled = jax.jit(forward).lower(params_shape, *shaped).compile()
    cost = compiled.cost_analysis() or {}
    if isinstance(cost, list):
        cost = cost[0] if cost else {}
    memory = compiled.memory_analysis()
    flops = float(cost.get("flops", 0.0))
    return {
        "batch": prepared.batch,
        "flops_per_call": flops,
        "flops_per_case": flops / prepared.batch,
        "bytes_accessed_per_call": float(cost.get("bytes accessed", 0.0)),
        "temp_bytes": int(memory.temp_size_in_bytes),
        "rule": INFERENCE_COST_RULE,
    }


def nonfinite_cases(outputs, case_ids):
    """Case ids whose outputs hold any NaN or infinity."""
    import numpy as np

    bad = np.zeros(len(case_ids), dtype=bool)
    for out in outputs:
        values = np.asarray(out)
        bad |= ~np.isfinite(values.reshape(values.shape[0], -1)).all(axis=1)
    return [c for c, b in zip(case_ids, bad) if b]


def grade(adapter, recipe, prepared, params, *, seed):
    """G7 for one trained graph: the Challenge's exam verdict, the cases
    with non-finite outputs and the measured inference cost."""
    exam = adapter.grade_graph(recipe, prepared, params, seed=seed)
    return {
        "exam": exam["summary"],
        "nonfinite_cases": nonfinite_cases(exam["outputs"], exam["case_ids"]),
        "inference_cost": inference_cost(prepared, params, exam["inputs"]),
    }
