"""Counts only: does a retained graph turn non-finite under per-case zero padding? (owed-4, 19 Nov 2026.)

Four owed re-runs fail the graded inference's output check (``bundle inference output contract differs``,
`bundle_construction_worker` INFER_PROGRAM), whose shape and dtype parts match by construction, leaving a non-finite
value. The graded pass runs each case alone as row 0 of the graph's batch, the other rows ZEROS (``per_case``). This
tool runs one retained state over PUBLIC inputs the same way it is graded, and two other ways, and prints the number of
rows with a non-finite output in each, nothing else:

- ``per_case_zero``: as graded (row 0 + zero rows);
- ``per_case_repeat``: row 0 + copies of the same row (no zeros in the batch);
- ``batched``: real rows together, a short last block padded with zeros (the timing query's way).

``per_case_zero`` > 0 with ``per_case_repeat`` and ``batched`` at 0 points at the zero padding (a graph that mixes the
rows of its batch); all three > 0 points at the model on those rows. It mirrors the inference program's own loading
(`physical_graph_state_v2.load` for a graph route v2 ensemble, with its per-member combination and decoder, else
`bundle_graph_state.load`; the x64 rule, `level4.interpret.rebuild`), and reads no exam input: give it PUBLIC inputs only
(the Challenge's public TRAIN inputs). It prints no prediction, value or input; the output shape and dtype it prints
are the public interface's. Run it in the inference image on a scratch copy, the invocation receipted by Validator-2:

    python scripts/dev/output_finite_counter.py --state state.npz --recipe recipe.json \\
        --allowlist allowlist.json --inputs public_train_inputs.npy [--rows 256] [--output-dtype float64]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _x64(doc, inputs, parameters, output_dtype=None):
    """The inference program's x64 rule: a 64-bit dtype in the graph, its inputs, its parameters or the interface's
    output dtype."""
    import numpy as np

    pending = [doc]
    while pending:
        value = pending.pop()
        if type(value) is dict:
            if value.get("dtype") in ("float64", "int64", "uint64", "complex128"):
                return True
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
    dtypes = [np.asarray(array).dtype for array in (inputs, *parameters)]
    if output_dtype is not None:
        dtypes.append(np.dtype(output_dtype))
    return any(dtype.itemsize >= 8 and dtype.kind in "fiuc" for dtype in dtypes)


def _bad(block):
    import numpy as np

    flat = np.asarray(block).reshape(len(block), -1)
    return int((~np.isfinite(flat)).any(axis=1).sum())


def count(
    state_bytes, recipe_bytes, allowlist_bytes, inputs, rows=None, output_dtype=None
):
    """``{mode: rows with a non-finite output}`` plus the run's public facts (see the module text)."""
    import numpy as np

    from carbon.development_session import bundle_graph_state, physical_graph_state_v2
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
    )
    from carbon.level4.allowlist import Allowlist

    recipe = ConstructionRecipe.from_bytes(recipe_bytes)
    allowed = Allowlist(allowlist_bytes)
    # A graph route v2 ensemble state (Motor 1.8 and the other v2 versions), read as its inference program does
    # (direct_graph_construction_worker.PHYSICAL_V2_INFER_PROGRAM); else a bundle state
    ensemble = None
    try:
        doc, members, mu, sd, combine = physical_graph_state_v2.load(
            state_bytes, recipe, allowed
        )
        ensemble = (members, mu, sd, combine)
        parameters = [p for member in members for p in member]
    except RecipeRefused:
        doc, parameters = bundle_graph_state.load(state_bytes, recipe, allowed)
    inputs = np.asarray(inputs)
    if rows is not None:
        inputs = inputs[:rows]
    if _x64(doc, inputs, parameters, output_dtype):
        os.environ["JAX_ENABLE_X64"] = "1"
        import jax

        jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp

    from carbon.level4.interpret import rebuild

    declared = doc["graphs"][doc["entry"]]["inputs"]
    batch = declared[-1]["shape"][0]
    if ensemble is None:
        forward = rebuild(doc, allowed)
        params = [jnp.asarray(p) for p in parameters]
    else:
        import jax

        members, mu, sd, combine = ensemble
        # Motor 1.8 compiles each member's forward (JIT_INFERENCE_VERSIONS); the same compiled call per member here
        member_forward = jax.jit(rebuild(doc, allowed))
        member_arrays = [[jnp.asarray(p) for p in member] for member in members]
        params = []

        def forward(*arguments):
            part = arguments[-1]
            total = None
            for weights, arrays in zip(combine, member_arrays):
                term = member_forward(*arrays, part)[0] * jnp.asarray(weights)
                total = term if total is None else total + term
            return [total * jnp.asarray(sd) + jnp.asarray(mu)]
    x = jnp.asarray(inputs, dtype=declared[-1]["dtype"])
    tail = [(0, 0)] * (x.ndim - 1)
    zero, repeat = [], []
    for index in range(len(x)):
        row = x[index : index + 1]
        zero.append(forward(*params, jnp.pad(row, [(0, batch - 1)] + tail))[0][:1])
        repeat.append(forward(*params, jnp.repeat(row, batch, axis=0))[0][:1])
    together = []
    for start in range(0, len(x), batch):
        part = x[start : start + batch]
        used = len(part)
        if used < batch:
            part = jnp.pad(part, [(0, batch - used)] + tail)
        together.append(forward(*params, part)[0][:used])
    zero, repeat, together = (
        np.asarray(jnp.concatenate(blocks)) for blocks in (zero, repeat, together)
    )
    return {
        "rows": len(x),
        "batch": int(batch),
        "output_shape": list(zero.shape),
        "output_dtype": str(zero.dtype),
        "non_finite_rows": {
            "per_case_zero": _bad(zero),
            "per_case_repeat": _bad(repeat),
            "batched": _bad(together),
        },
    }


def main(argv=None):
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument(
        "--inputs", type=Path, required=True, help="PUBLIC inputs (.npy) only"
    )
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument(
        "--output-dtype", default=None, help="the public interface's output dtype"
    )
    args = parser.parse_args(argv)
    if args.rows is not None and args.rows < 1:
        parser.error("--rows must be at least 1")
    inputs = np.load(args.inputs, allow_pickle=False)
    out = count(
        args.state.read_bytes(),
        args.recipe.read_bytes(),
        args.allowlist.read_bytes(),
        inputs,
        args.rows,
        args.output_dtype,
    )
    sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
