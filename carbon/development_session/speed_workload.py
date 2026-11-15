"""The kit speed check's fixed public workload (owner pick 3, Sun 15 Nov 2026: "kit speed benchmark vs grade worker").

A miner's kit runs this workload on the miner's machine and prints its time next to Carbon's measured time for the SAME
workload on the grading worker (`speed_reference`), with the ratio and what it means against the published inference
wall. What is timed is what the grade times: the grade's own inference program (`bundle_construction_worker`'s
`INFER_PROGRAM`, as the practice's timed child runs it: one batched cold query, then one single-design call per row,
the design in row 0 and the rest of the batch the public zero filler), in the worker image, under the version's own
allowlist and worker resources, through the same carrier (`_infer_state`).

The workload is a FIXED PUBLIC GRAPH, not a model: a tanh multilayer perceptron at the newest Motor version's interface
widths whose parameters come from a fixed public seed. Nothing is trained or fitted and nothing is scored; it is a
timing load. It runs over that version's PUBLIC practice inputs (the first `BATCH` rows, so the static-batch graph
takes the batched cold query whole). It reads no bank, sealed, exam or hidden row, no seed and no key, and builds
nothing from TRAIN: the bytes are identical on every host, so the workload digest is exact.

One graph's operation mix: a graph with different operations can scale differently between two machines. The kit
says so beside the figure.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import statistics

import numpy as np

from .bundle_graph_state import freeze
from .construction_recipe import ConstructionRecipe

SCHEMA = "carbon.kit.speed-workload.v1"
RESULT_SCHEMA = "carbon.kit.speed-result.v1"
CHALLENGE = "electric-motor-magnetics"
VERSION = "1.8"
#: The graph's declared batch: the cold query takes the first BATCH public practice rows whole; each timed single-design
#: call pads one row into it.
BATCH = 128
WIDTH = 1024
HIDDEN_LAYERS = 3
#: The public seed of the parameters (a date, nothing else).
SEED = 20261115
OUTPUT_DTYPE = "float64"
#: Graph input and parameter dtypes.
INPUT_DTYPE = "float64"
PARAMETER_DTYPE = "float32"


def _sha(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _content_digest(arrays) -> str:
    """sha256 over each array's dtype, shape and little-endian C-order bytes."""
    body = hashlib.sha256()
    for array in arrays:
        array = np.ascontiguousarray(array)
        little = array.astype(array.dtype.newbyteorder("<"), copy=False)
        body.update(_canonical([little.dtype.str, list(little.shape)]))
        body.update(little.tobytes(order="C"))
    return "sha256:" + body.hexdigest()


def _named(part: str) -> str:
    """A fixed sentinel digest naming one part of this workload (it is no built bundle)."""
    return _sha((SCHEMA + "/" + part).encode())


def layer_shapes(n_in: int, n_out: int) -> list:
    """The (fan in, fan out) of each dense layer."""
    widths = [n_in, *([WIDTH] * HIDDEN_LAYERS), n_out]
    return list(itertools.pairwise(widths))


def parameters(n_in: int, n_out: int) -> list:
    """The fixed public parameters: per layer a weight (fan in x fan out, scaled 1/sqrt(fan in)) and a bias."""
    rng = np.random.default_rng(SEED)
    out = []
    for fan_in, fan_out in layer_shapes(n_in, n_out):
        weight = rng.standard_normal((fan_in, fan_out)) / math.sqrt(fan_in)
        out.append(weight.astype(PARAMETER_DTYPE))
        out.append((0.01 * rng.standard_normal((fan_out,))).astype(PARAMETER_DTYPE))
    return out


def graph_document(n_in: int, n_out: int, allowlist_version: str) -> dict:
    """The Level 4 forward graph of the workload: float64 rows in, cast to float32, dense + tanh per hidden layer, a
    dense output layer, cast back to float64. Only allowlisted ops (`convert_element_type`, `dot_general`,
    `broadcast_in_dim`, `add`, `tanh`) with the parameters JAX's lowering records for them.
    """
    layers = layer_shapes(n_in, n_out)
    inputs = []
    value = 0
    for index, (fan_in, fan_out) in enumerate(layers):
        inputs.append(
            {
                "value": value,
                "name": f"params/{2 * index}",
                "dtype": PARAMETER_DTYPE,
                "shape": [fan_in, fan_out],
            }
        )
        inputs.append(
            {
                "value": value + 1,
                "name": f"params/{2 * index + 1}",
                "dtype": PARAMETER_DTYPE,
                "shape": [fan_out],
            }
        )
        value += 2
    x = value
    inputs.append(
        {"value": x, "name": "inputs/x", "dtype": INPUT_DTYPE, "shape": [BATCH, n_in]}
    )
    nodes = []
    counter = [x]

    def node(op, args, dtype, shape, params):
        counter[0] += 1
        nodes.append(
            {
                "op": op,
                "in": list(args),
                "out": [{"value": counter[0], "dtype": dtype, "shape": list(shape)}],
                "params": params,
            }
        )
        return counter[0]

    def convert(source, dtype, shape):
        return node(
            "convert_element_type",
            [source],
            dtype,
            shape,
            {"new_dtype": dtype, "sharding": None, "weak_type": False},
        )

    h = convert(x, PARAMETER_DTYPE, [BATCH, n_in])
    for index, (_fan_in, fan_out) in enumerate(layers):
        weight, bias = 2 * index, 2 * index + 1
        shape = [BATCH, fan_out]
        product = node(
            "dot_general",
            [h, weight],
            PARAMETER_DTYPE,
            shape,
            {
                "dimension_numbers": [[[1], [0]], [[], []]],
                "out_sharding": None,
                "precision": None,
                "preferred_element_type": PARAMETER_DTYPE,
            },
        )
        row = node(
            "broadcast_in_dim",
            [bias],
            PARAMETER_DTYPE,
            [1, fan_out],
            {"broadcast_dimensions": [1], "shape": [1, fan_out], "sharding": None},
        )
        h = node("add", [product, row], PARAMETER_DTYPE, shape, {})
        if index < len(layers) - 1:
            h = node("tanh", [h], PARAMETER_DTYPE, shape, {"accuracy": None})
    out = convert(h, OUTPUT_DTYPE, [BATCH, n_out])
    return {
        "schema": "carbon.development.level4-graph.v0",
        "allowlist": allowlist_version,
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": inputs,
                "constants": [],
                "nodes": nodes,
                "outputs": [out],
            }
        },
    }


def recipe(kit: dict) -> ConstructionRecipe:
    """The workload's recipe, bound to the version's public construction kit. Its source names no real bundle (fixed
    sentinel digests): the inference program checks only the binding and the frozen state's header against it.
    """
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": {
                "id": kit["id"],
                "version": kit["version"],
                "train_digest": kit["train_digest"],
                "interface_digest": kit["interface_digest"],
                "construction_limits_digest": kit["construction_limits_digest"],
            },
            "source": {
                "kind": "bundle",
                "bundle_ref": {
                    "schema": "carbon.library-bundle-ref.v1",
                    "bundle_digest": _named("bundle"),
                    "language": "python",
                    "runtime_profile_id": "python-cpu-py311",
                    "environment_digest": _named("environment"),
                },
            },
            "procedure": {
                "entrypoint": {"module": "speed_workload", "name": "fixed"},
                "configuration": {},
                "train_use": {},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": kit["interface_digest"],
            },
        }
    )


def material():
    """The newest Motor version's public construction material (`physical_material.bundle_material`)."""
    from carbon.challenge_kit import physical_material

    return physical_material.bundle_material(CHALLENGE, VERSION)


def build(public=None) -> dict:
    """The workload, from the version's public material: its recipe, frozen state, inputs, the binding the inference
    program checks, and the workload digest (graph, parameters, inputs, allowlist, timed program).
    """
    from carbon.level4.allowlist import Allowlist

    from .bundle_construction_worker import INFER_PROGRAM, _tensors, timed_program

    public = material() if public is None else public
    kit = public["construction_kit"]
    if (kit["id"], kit["version"]) != (CHALLENGE, VERSION):
        raise ValueError("speed workload material differs")
    practice = np.asarray(public["practice_inputs"])
    width = tuple(public["expected_output_shape"])[1:]
    if practice.ndim != 2 or len(practice) < BATCH or len(width) != 1:
        raise ValueError("speed workload material differs")
    inputs = np.ascontiguousarray(practice[:BATCH], dtype=INPUT_DTYPE)
    n_in, n_out = int(inputs.shape[1]), int(width[0])
    allowlist_bytes = public["allowlist_bytes"]
    allowed = Allowlist(allowlist_bytes)
    the_recipe = recipe(kit)
    doc = graph_document(n_in, n_out, allowed.version)
    arrays = parameters(n_in, n_out)
    state = freeze(the_recipe, doc, arrays, allowed)
    state_digest = _sha(state)
    _tensors(inputs=inputs)  # the carrier's own input check, before anything runs
    # Content digests (raw little-endian bytes and shapes), not the .npz container's bytes, so two hosts with
    # different NumPy builds still name the same workload.
    identity = {
        "schema": SCHEMA,
        "challenge": {"id": CHALLENGE, "version": VERSION},
        "graph_digest": _sha(_canonical(doc)),
        "parameters_digest": _content_digest(arrays),
        "inputs_digest": _content_digest([inputs]),
        "allowlist_digest": allowed.digest,
        "program_digest": _sha(timed_program(INFER_PROGRAM).encode()),
        "batch": BATCH,
    }
    return {
        "recipe": the_recipe,
        "binding": {
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
            "train_digest": kit["train_digest"],
            "interface_digest": kit["interface_digest"],
            "construction_limits_digest": kit["construction_limits_digest"],
        },
        "state": state,
        "state_digest": state_digest,
        "inputs": inputs,
        "expected_output_shape": (BATCH, n_out),
        "allowlist_bytes": allowlist_bytes,
        "limits_document": public["construction_limits_document"],
        "identity": identity,
        "workload_digest": _sha(_canonical(identity)),
    }


def inference_wall_seconds(public=None) -> int:
    """The published per-pass inference wall of the version (`inference_wall_seconds_max`)."""
    public = material() if public is None else public
    policy = public["construction_limits_document"]["reconstruction_resource_policy"]
    wall = policy["inference_wall_seconds_max"]
    if type(wall) is not int or wall <= 0:
        raise ValueError("speed workload wall differs")
    return wall


def summarize(receipt: dict, *, workload_digest: str, image_id: str) -> dict:
    """The speed result from the timed inference receipt: the per-call median and largest of the single-design calls,
    the cold query (graph load, JAX compile and one batched call), and the start-up it implies (cold query less one
    call). Refused (ValueError) when the receipt carries no per-call figure."""
    measured = receipt.get("measurement") if type(receipt) is dict else None
    timing = measured.get("timing_s") if type(measured) is dict else None
    per_call = measured.get("per_call_s") if type(measured) is dict else None
    if (
        type(timing) is not dict
        or type(per_call) is not list
        or not per_call
        or not all(
            type(s) in (int, float) and math.isfinite(s) and s > 0 for s in per_call
        )
    ):
        raise ValueError("speed workload timing missing")
    cold = sum(
        float(timing[name]) for name in ("preprocess", "inference", "postprocess")
    )
    median = statistics.median(per_call)
    return {
        "schema": RESULT_SCHEMA,
        "workload_digest": workload_digest,
        "image_id": image_id,
        "per_call_median_seconds": median,
        "per_call_max_seconds": max(per_call),
        "per_call_rows": len(per_call),
        "cold_query_seconds": cold,
        "startup_seconds": max(cold - median, 0.0),
    }


#: The ledger owner of a speed run (its own campaign; never a miner's practice ledger).
OWNER = "speed-check"


def open_ledger(root):
    """A speed run's own campaign ledger at `root` (absolute), frozen once as an uncontrolled development campaign."""
    from .research_ledger import (
        DEVELOPMENT_CEILINGS,
        DEVELOPMENT_ELAPSED_SECONDS,
        VERSION,
        CampaignLedger,
    )

    ledger = CampaignLedger(root)
    with ledger.db() as db:
        frozen = db.execute("SELECT 1 FROM campaign WHERE id=1").fetchone()
    if frozen is None:
        ledger.freeze(
            {
                "schema": VERSION,
                "ceilings": DEVELOPMENT_CEILINGS,
                "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
                "campaign_id": "kit-speed-check",
                "implementation": "candidate",
                "objective": "speed-check-only",
                "sampling": "none",
                "control": "speed-check-only",
                "selection": "speed-check-only",
                "replica_policy": "none",
                "provider": "none",
                "owner": OWNER,
            }
        )
    return ledger


def measure(
    ledger,
    *,
    owner: str,
    identity: str,
    inference_image,
    public=None,
    runner=None,
) -> dict:
    """Run the workload once in the worker image (the grade's timed inference program, through the carrier) and return
    its speed result. `identity` must be new per run: the ledger replays a repeated identity instead of running it.
    """
    from .bundle_construction_worker import (
        TIMING_WALL_SECONDS_MAX,
        _infer_state,
        rebuild_wall_kwargs,
    )

    work = build(public)
    wall = min(
        work["limits_document"]["reconstruction_resource_policy"][
            "inference_wall_seconds_max"
        ],
        TIMING_WALL_SECONDS_MAX,
    )
    result = _infer_state(
        ledger,
        owner=owner,
        identity=identity,
        inference_image=inference_image,
        recipe=work["recipe"],
        binding=work["binding"],
        state=work["state"],
        state_digest=work["state_digest"],
        inputs=work["inputs"],
        expected_output_shape=work["expected_output_shape"],
        allowlist_bytes=work["allowlist_bytes"],
        expected_output_dtype=OUTPUT_DTYPE,
        measure_query=True,
        seconds=wall,
        practice_timing=True,
        runner=runner,
        **rebuild_wall_kwargs(work["limits_document"]),
    )
    return summarize(
        result.receipt,
        workload_digest=work["workload_digest"],
        image_id=inference_image.image_id,
    )
