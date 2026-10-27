"""Single-design call timing for pool-graded versions (M4; Validator V8_RULINGS section 10 and 11).

The pool exam's speed gate times SINGLE-DESIGN calls: after the graded inference, the same inference container
(network none, the same resource profile) runs Carbon's fixed program over `SAMPLE` (20) sampled sealed rows, one
call each, after ONE warm-up call on a PUBLIC practice row that is excluded from the timing. Each call is timed by
this program with a monotonic clock around "pad the row into the graph's batch, run the graph, bring the answer
to the host"; a graph is tensor operations only and cannot reach the timer. Only the per-call seconds return, with
the receipt, as host-private evidence.

This is a NEW program version for pool versions only: it is derived, by anchored replacement (each anchor must occur
exactly once), from the adapter's own inference program, so the frozen `INFER_PROGRAM` and the programs derived from
it keep their bytes. Nothing else in the program changes: the same graph load, the same `forward`, the same
one-case-per-call padding the graded run uses, so what is timed is what is graded.

What the host holds and the container never gets:
- the per-grade seed (HMAC of the custody root, set id and submission id), which picks the rows: only the chosen
  indices cross, inside the host-private `control.json`;
- the indices point into the rows of the graded pack's `inputs.npz`, which the container already holds, so no row
  crosses the boundary that did not cross for the graded run;
- the warm-up row is public (a practice row) and is staged beside the inputs in its own file, digest-bound.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math

SIDE_FILE_SCHEMA = "carbon.lean-recipe.single-call.v1"
#: The domain tag of the per-grade sample seed (GPU_REBUILD_RULINGS section 8): HMAC-SHA256 under the pack's custody
#: copy key over this tag, the pool set id and the submission id.
SEED_DOMAIN = b"carbon.speed-sample/1"
SCHEMA = "carbon.development.bundle-inference.v3"
SCOPE = "SINGLE_DESIGN_CALLS_ONE_PUBLIC_WARMUP_EXCLUDED_MONOTONIC_CLOCK"
SAMPLE = 20
WARMUP_FILE = "warmup.npz"

_ANCHOR_CONTROL = (
    'per_case = control.get("per_case", True)\n'
    "if type(per_case) is not bool or (measure and per_case):\n"
    '    raise ValueError("bundle inference per-case control differs")\n'
)
_CONTROL = _ANCHOR_CONTROL + """single_call = control.get("single_call")
if single_call is not None:
    if (measure or type(single_call) is not dict
        or set(single_call) != {"indices", "warmup_digest"}
        or type(single_call["indices"]) is not list
        or not single_call["indices"]
        or len(set(single_call["indices"])) != len(single_call["indices"])
        or any(type(i) is not int or type(i) is bool or i < 0
               for i in single_call["indices"])
        or type(single_call["warmup_digest"]) is not str):
        raise ValueError("bundle inference single-call control differs")
"""
_ANCHOR_LOOP = (
    "if per_case:\n"
    "    # One case per call: the case is row 0 and the other batch rows are a fixed\n"
)
_LOOP = """if single_call is not None:
    # Pool versions' speed gate: single-design calls, timed here, never by the graph.
    if max(single_call["indices"]) >= len(input_array):
        raise ValueError("bundle inference single-call row differs")
    warm_inputs = input_tensor((work / "warmup.npz").read_bytes(),
                               single_call["warmup_digest"])
    if (warm_inputs.dtype != inputs.dtype or warm_inputs.ndim != inputs.ndim
        or warm_inputs.shape[1:] != inputs.shape[1:] or len(warm_inputs) < 1):
        raise ValueError("bundle inference warm-up row differs")
    warm_array = jnp.asarray(warm_inputs)
    # One warm-up call on a PUBLIC row (graph load and compile happen here): not timed.
    warm = forward(*parameter_arrays, jnp.pad(
        warm_array[0:1], [(0, batch - 1)] + [(0, 0)] * (warm_array.ndim - 1)))
    if len(warm) != 1:
        raise ValueError(arity)
    np.asarray(warm[0])
    call_s = []
    for index in single_call["indices"]:
        started = time.perf_counter()
        part = jnp.pad(input_array[index:index + 1],
                       [(0, batch - 1)] + [(0, 0)] * (input_array.ndim - 1))
        outputs = forward(*parameter_arrays, part)
        if len(outputs) != 1:
            raise ValueError(arity)
        piece = np.asarray(outputs[0][:1])
        call_s.append(time.perf_counter() - started)
        blocks.append(jnp.asarray(piece))
    outputs = [jnp.concatenate(blocks)]
elif per_case:
    # One case per call: the case is row 0 and the other batch rows are a fixed
"""
_ANCHOR_SCHEMA = (
    '"schema": ("carbon.development.bundle-inference.v2" if measure\n'
    '               else "carbon.development.bundle-inference.v1"),\n'
)
_SCHEMA = (
    '"schema": ("carbon.development.bundle-inference.v3" if single_call is not None\n'
    '               else "carbon.development.bundle-inference.v2" if measure\n'
    '               else "carbon.development.bundle-inference.v1"),\n'
)
_ANCHOR_RECEIPT = "if measure:\n    export_end = time.perf_counter()\n"
_RECEIPT = (
    "if single_call is not None:\n"
    '    receipt["single_call"] = {\n'
    f'        "scope": "{SCOPE}",\n'
    '        "indices": single_call["indices"],\n'
    '        "warmup_digest": single_call["warmup_digest"],\n'
    '        "call_s": call_s,\n'
    "    }\n" + _ANCHOR_RECEIPT
)
_ANCHORS = (
    (_ANCHOR_CONTROL, _CONTROL),
    (_ANCHOR_LOOP, _LOOP),
    (_ANCHOR_SCHEMA, _SCHEMA),
    (_ANCHOR_RECEIPT, _RECEIPT),
)


class SingleCallRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def program(base_program: str) -> str:
    """The single-call program derived from an adapter's own inference program (never edited in place)."""
    result = base_program
    for old, new in _ANCHORS:
        if result.count(old) != 1:
            raise SingleCallRefused("single_call_program_anchor_moved")
        result = result.replace(old, new)
    return result


def sample_seed(key: bytes, set_id: str, submission_id: str) -> bytes:
    """The per-grade seed that picks the timed rows: custody's, never the miner's, never reused across grades."""
    if (
        type(key) is not bytes
        or len(key) < 32
        or type(set_id) is not str
        or not set_id
        or type(submission_id) is not str
        or not submission_id
    ):
        raise SingleCallRefused("single_call_seed_input_invalid")
    message = b"\x00".join(
        [SEED_DOMAIN, set_id.encode("utf-8"), submission_id.encode("utf-8")]
    )
    return hmac.new(key, message, hashlib.sha256).digest()


def delivered_indices(bank, delivered_inputs, seed: bytes) -> list:
    """The row indices, into the DELIVERED query (the validator copy order), of the `SAMPLE` pool rows timed.

    The draw is over the canonical bank's pool rows (`pool_exam.speed_sample`), so it is the same for every
    validator copy of one exam; each drawn row is then found in the delivered rows by exact value (pool rows are
    unique inputs). A row that is absent or ambiguous is a refusal, never a different row.
    """
    import numpy as np

    from carbon.scoring import pool_exam

    pool = [i for i, c in enumerate(bank["cohorts"]) if c == pool_exam.POOL_COHORT]
    if len(pool) < SAMPLE:
        raise SingleCallRefused("single_call_pool_smaller_than_the_sample")
    canonical = np.asarray(bank["inputs"])
    delivered = np.asarray(delivered_inputs)
    if delivered.ndim != 2 or delivered.shape[1:] != canonical.shape[1:]:
        raise SingleCallRefused("single_call_delivered_rows_differ")
    out = []
    for position in pool_exam.speed_sample(len(pool), seed=seed, count=SAMPLE):
        row = canonical[pool[position]]
        found = np.flatnonzero((delivered == row).all(axis=1))
        if len(found) != 1:
            raise SingleCallRefused("single_call_row_not_in_the_delivered_query")
        out.append(int(found[0]))
    return sorted(out)


def side_file(*, indices, warmup_digest, call_s, outputs_match, operation) -> dict:
    """The host-private evidence the receiver keeps beside the dual measurement."""
    return {
        "schema": SIDE_FILE_SCHEMA,
        "scope": SCOPE,
        "indices": list(indices),
        "warmup_digest": warmup_digest,
        "call_s": list(call_s),
        "outputs_match_graded": bool(outputs_match),
        "operation": operation,
    }


def read_side_file(raw) -> tuple:
    """``(per-call seconds, outputs_match_graded)`` of a retained side file, or a refusal."""
    try:
        document = json.loads(raw)
    except (TypeError, ValueError):
        raise SingleCallRefused("single_call_evidence_malformed") from None
    if (
        type(document) is not dict
        or set(document)
        != {
            "schema",
            "scope",
            "indices",
            "warmup_digest",
            "call_s",
            "outputs_match_graded",
            "operation",
        }
        or document["schema"] != SIDE_FILE_SCHEMA
        or document["scope"] != SCOPE
        or type(document["outputs_match_graded"]) is not bool
        or type(document["indices"]) is not list
        or len(document["indices"]) != SAMPLE
        or type(document["call_s"]) is not list
        or len(document["call_s"]) != SAMPLE
        or any(
            type(s) not in (int, float) or not math.isfinite(s) or s <= 0
            for s in document["call_s"]
        )
    ):
        raise SingleCallRefused("single_call_evidence_malformed")
    return list(document["call_s"]), document["outputs_match_graded"]


def control_block(indices, warmup_digest: str, *, rows: int) -> dict:
    """The host-private `single_call` control: the sampled row indices (into the graded `inputs.npz`) and the
    digest of the public warm-up file. Never the seed."""
    if (
        type(indices) not in (list, tuple)
        or len(indices) != SAMPLE
        or len(set(indices)) != SAMPLE
        or any(type(i) is not int or not 0 <= i < rows for i in indices)
        or type(warmup_digest) is not str
        or not warmup_digest.startswith("sha256:")
    ):
        raise SingleCallRefused("single_call_control_invalid")
    return {"indices": sorted(indices), "warmup_digest": warmup_digest}


def check_receipt_block(block, *, control: dict) -> list:
    """The per-call seconds of a receipt's `single_call` block, or a refusal: exactly the scope, the indices and
    warm-up digest the host sent, and `SAMPLE` positive finite seconds."""
    if (
        type(block) is not dict
        or set(block) != {"scope", "indices", "warmup_digest", "call_s"}
        or block["scope"] != SCOPE
        or block["indices"] != control["indices"]
        or block["warmup_digest"] != control["warmup_digest"]
        or type(block["call_s"]) is not list
        or len(block["call_s"]) != SAMPLE
        or any(
            type(s) not in (int, float) or not math.isfinite(s) or s <= 0
            for s in block["call_s"]
        )
    ):
        raise SingleCallRefused("single_call_receipt_differs")
    return list(block["call_s"])


def outputs_match_graded(single_outputs, graded_outputs, indices) -> bool:
    """Whether the timed calls answered exactly as the graded run did on the same rows: a graph that does
    different work when timed is the candidate's, never infrastructure."""
    if len(single_outputs) != len(indices):
        return False
    return all(
        single_outputs[position] == graded_outputs[index]
        for position, index in enumerate(indices)
    )


__all__ = [
    "SAMPLE",
    "SCHEMA",
    "SCOPE",
    "SEED_DOMAIN",
    "SIDE_FILE_SCHEMA",
    "WARMUP_FILE",
    "SingleCallRefused",
    "check_receipt_block",
    "control_block",
    "delivered_indices",
    "outputs_match_graded",
    "program",
    "read_side_file",
    "sample_seed",
    "side_file",
]
