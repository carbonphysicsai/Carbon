"""Counts only: why does a retained graph fail the graded output contract? (owed-4 / the 7 PARKED_CONTRACT replays.)

The graded inference refuses its output as ``bundle inference output contract differs`` (`bundle_construction_worker`
INFER_PROGRAM, and for a graph route v2 ensemble `direct_graph_construction_worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM`)
when ANY of three parts fails: the output SHAPE is not the served ``expected_output_shape``, its DTYPE is not the served
``expected_output_dtype`` (or not a real number), or a value is non-finite. The graded pass runs each case alone as row 0
of the graph's batch, the other rows ZEROS (``per_case``). This tool runs one retained state over PUBLIC inputs the way it
is graded, and two other ways, and prints which contract parts hold and the number of rows with a non-finite output in
each way, nothing else:

- ``per_case_zero``: as graded (row 0 + zero rows);
- ``per_case_repeat``: row 0 + copies of the same row (no zeros in the batch);
- ``batched``: real rows together, a short last block padded with zeros (the timing query's way).

``per_case_zero`` > 0 with ``per_case_repeat`` and ``batched`` at 0 points at the zero padding (a graph that mixes the
rows of its batch); all three > 0 points at the model on those rows; ``shape_matches`` / ``dtype_matches`` false points at
the served interface. It mirrors the live inference program exactly where a count depends on it (V2 parity, 19 Nov 2026):
the task's own retained ``control.json`` (bound to the state, recipe and allowlist by digest, as the program checks) gives
the served expected shape and dtype; the x64 rule is the program's (a 64-bit dtype in the graph, or `requires_x64` of the
inputs, the expected dtype and the FIRST member's parameters); the inputs go in uncast (``jnp.asarray(inputs)``); a v2
ensemble's members combine per output and its decoder applies in numpy after the per-case concatenation
(``np.asarray(out) * decoder_sd + decoder_mu``). It reads no exam input: give it PUBLIC inputs only (the Challenge's public
TRAIN inputs). It prints no prediction, value or input; the shape tail and dtype it prints are the public interface's.
Run it in the inference image on a scratch copy, the invocation receipted by Validator-2:

    python scripts/dev/output_finite_counter.py --state state.npz --recipe recipe.json \\
        --allowlist allowlist.json --control control.json --inputs public_train_inputs.npy [--rows 256]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def _x64(doc, inputs, parameters, output_dtype=None):
    """The inference program's x64 rule: a 64-bit dtype named in the graph, else `requires_x64` of the inputs, the served
    output dtype (the inputs' own when none is served) and the parameters (a v2 ensemble's FIRST member's, as live).
    """
    import numpy as np

    from carbon.development_session.construction_tensor_codec import requires_x64

    pending = [doc]
    while pending:
        value = pending.pop()
        if type(value) is dict:
            if value.get("dtype") in ("float64", "int64", "uint64", "complex128"):
                return True
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
    inputs = np.asarray(inputs)
    return requires_x64(
        inputs,
        output_dtype or inputs.dtype,
        *(np.asarray(parameter) for parameter in parameters),
    )


def _bad(block):
    import numpy as np

    flat = np.asarray(block).reshape(len(block), -1)
    return int((~np.isfinite(flat)).any(axis=1).sum())


def _bind(control, state_bytes, recipe, allowed):
    """The control must be this state's, recipe's and allowlist's (the program refuses otherwise); raises ValueError."""
    digest = "sha256:" + hashlib.sha256(state_bytes).hexdigest()
    if type(control) is not dict:
        raise ValueError("control document malformed")
    for name, actual in (
        ("recipe_digest", recipe.digest),
        ("state_digest", digest),
        ("allowlist_digest", allowed.digest),
    ):
        if control.get(name) != actual:
            raise ValueError("control does not bind this " + name.split("_")[0])
    shape = control.get("expected_output_shape")
    if type(shape) is not list or not shape or any(type(n) is not int for n in shape):
        raise ValueError("control expected_output_shape malformed")


def _contract(result, rows, control):
    """The graded output contract's shape and dtype parts (non-finite is counted apart), against the SERVED expectation:
    the expected shape with its row count replaced by the public rows run here."""
    import numpy as np

    expected = control["expected_output_shape"]
    dtype = control.get("expected_output_dtype")
    return {
        "shape_matches": list(result.shape) == [rows, *expected[1:]],
        "dtype_matches": (dtype is None or result.dtype == np.dtype(dtype))
        and result.dtype.kind in "fiu",
    }


def _graded(blocks, decoder=None):
    """One way's output as the program forms it: the blocks concatenated, then (a v2 ensemble) its decoder in numpy."""
    import numpy as np

    result = np.asarray(np.concatenate([np.asarray(block) for block in blocks]))
    if decoder is not None:
        mu, sd = decoder
        result = np.asarray(result) * sd + mu
    return result


def count(state_bytes, recipe_bytes, allowlist_bytes, control_bytes, inputs, rows=None):
    """``{mode: rows with a non-finite output}``, the contract's shape/dtype parts and the run's public facts."""
    import numpy as np

    from carbon.development_session import bundle_graph_state, physical_graph_state_v2
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
    )
    from carbon.level4.allowlist import Allowlist

    recipe = ConstructionRecipe.from_bytes(recipe_bytes)
    allowed = Allowlist(allowlist_bytes)
    control = json.loads(control_bytes)
    _bind(control, state_bytes, recipe, allowed)
    # A graph route v2 ensemble state (Motor 1.8 and the other v2 versions), read as its inference program does
    # (direct_graph_construction_worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM); else a bundle state
    ensemble = None
    try:
        doc, members, mu, sd, combine = physical_graph_state_v2.load(
            state_bytes, recipe, allowed
        )
        ensemble = (members, combine)
        decoder = (mu, sd)
        parameters = list(
            members[0]
        )  # live: the x64 rule and the binding read the first member
    except RecipeRefused:
        doc, parameters = bundle_graph_state.load(state_bytes, recipe, allowed)
        decoder = None
    inputs = np.asarray(inputs)
    if rows is not None:
        inputs = inputs[:rows]
    if _x64(doc, inputs, parameters, control.get("expected_output_dtype")):
        os.environ["JAX_ENABLE_X64"] = "1"
        import jax

        jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp

    from carbon.level4.interpret import rebuild

    declared = doc["graphs"][doc["entry"]]["inputs"]
    binding_matches = len(declared) == len(parameters) + 1 and (
        declared[-1]["name"] == control.get("input_name", "inputs/x")
    )
    batch = declared[-1]["shape"][0]
    if ensemble is None:
        forward = rebuild(doc, allowed)
        params = [jnp.asarray(p) for p in parameters]
    else:
        import jax

        members, combine = ensemble
        # Motor 1.8 compiles each member's forward (JIT_INFERENCE_VERSIONS); the same compiled call per member here
        member_forward = jax.jit(rebuild(doc, allowed))
        member_arrays = [[jnp.asarray(p) for p in member] for member in members]
        params = []

        def forward(*arguments):
            # each output: the members that train it, by the combination; the decoder applies after the concatenation
            part = arguments[-1]
            total = None
            for weights, arrays in zip(combine, member_arrays):
                term = member_forward(*arrays, part)[0] * jnp.asarray(weights)
                total = term if total is None else total + term
            return [total]

    x = jnp.asarray(inputs)  # uncast, as the program passes the inputs
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
        _graded(blocks, decoder) for blocks in (zero, repeat, together)
    )
    return {
        "rows": len(x),
        "batch": int(batch),
        "input_dtype": str(x.dtype),
        "output_shape": list(zero.shape),
        "output_dtype": str(zero.dtype),
        "expected_output_shape_tail": list(control["expected_output_shape"][1:]),
        "expected_output_dtype": control.get("expected_output_dtype"),
        "input_binding_matches": bool(binding_matches),
        **_contract(zero, len(x), control),
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
        "--control",
        type=Path,
        required=True,
        help="the task's retained inference control.json (served expected shape/dtype)",
    )
    parser.add_argument(
        "--inputs", type=Path, required=True, help="PUBLIC inputs (.npy) only"
    )
    parser.add_argument("--rows", type=int, default=None)
    args = parser.parse_args(argv)
    if args.rows is not None and args.rows < 1:
        parser.error("--rows must be at least 1")
    inputs = np.load(args.inputs, allow_pickle=False)
    out = count(
        args.state.read_bytes(),
        args.recipe.read_bytes(),
        args.allowlist.read_bytes(),
        args.control.read_bytes(),
        inputs,
        args.rows,
    )
    sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
