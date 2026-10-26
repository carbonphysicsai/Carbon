"""The practice speed result: how long a model takes per exam design, against the
exam's speed gate (500 times faster than the reference solver).

The gate's numbers are registered in `carbon.challenge_registry.speed_gate` and
published; this module only measures against them. It reads no sealed or hidden
material. The seconds are measured on the miner's own machine, which is not the
validator class, so the result carries that label and is never a gate verdict:
the exam measures on the validator class.

What is timed is the cold query the practice already runs for a measured task
(`bundle-inference.v2`): graph load, JAX compile and one inference over every
practice design, preprocessing included. The receipt's export step (writing the
predictions file) is not model time and is left out.
"""

from __future__ import annotations

import math

from carbon.challenge_registry import speed_gate

SCHEMA = "carbon.practice.speed.v1"
LABEL = "on your machine; the exam measures on the validator class"
#: The Challenge kinds practice knows, to the speed gate's Challenge ids.
GATE_IDS = {
    "f02": "f02",
    "f08": "f08-ribbed-bracket",
    "cooling": "chip-cold-plate",
    "motor": "electric-motor-magnetics",
}
#: The receipt's timing parts that are the model's time (not the export).
MODEL_PARTS = ("preprocess", "inference", "postprocess")
#: What the batched figure is (Validator V8_RULINGS section 10): an average over one
#: batched query of the public practice rows, which a per-call fixed cost or a
#: recognised row can flatter. The exam times single-design calls instead.
FIGURE = "batched average over the public practice rows (not the exam's measure)"


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def speed_block(kind, *, seconds, designs):
    """The speed result for ``designs`` practice designs answered in ``seconds``
    of wall time, or None when either is not a positive finite number or the
    kind has no registered gate."""
    gate_id = GATE_IDS.get(kind)
    if gate_id is None or not _positive(seconds) or type(designs) is not int:
        return None
    if designs <= 0:
        return None
    per_design = seconds / designs
    ceiling = speed_gate.ceiling_seconds(gate_id)
    solver = speed_gate.SOLVER_SECONDS_PER_DESIGN[gate_id]
    return {
        "schema": SCHEMA,
        "seconds_per_design": per_design,
        "ceiling_seconds_per_design": ceiling,
        "solver_seconds_per_design": solver,
        "ratio_required": speed_gate.RATIO,
        "within_ceiling": per_design <= ceiling,
        "times_faster_than_solver": solver / per_design,
        "designs": designs,
        "scope": "cold query: model load, compile and one inference over all practice designs",
        "figure": FIGURE,
        "label": LABEL,
    }


def measure(runner) -> bool:
    """Whether a practice run asks for the timed cold query. Only a real
    isolated worker run is timed: a test runner stands in for the container, so
    its seconds would mean nothing."""
    return runner is None


NOT_MEASURED_NOTE = (
    "speed not measured: the timing run did not finish; "
    "the practice result itself is unaffected"
)


def not_measured(kind):
    """The speed result of a practice whose timing run failed or ran out of time.
    The timing run is best-effort and never fails the practice: the result returns
    as usual and says, in words, that its speed was not measured."""
    return {
        "schema": SCHEMA,
        "measured": False,
        "note": NOT_MEASURED_NOTE,
        "label": LABEL,
    }


def per_call_figures(kind, per_call):
    """The median and the largest single-design call over the timed practice
    rows, beside the batched average, and whether the median meets the speed
    gate's ceiling (the exam's gate compares a median of single-design calls).
    Nothing when the timing run reported none."""
    if (
        type(per_call) is not list
        or not per_call
        or not all(_positive(item) for item in per_call)
    ):
        return {}
    ordered = sorted(per_call)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )
    gate_id = GATE_IDS.get(kind)
    ceiling = speed_gate.ceiling_seconds(gate_id) if gate_id is not None else None
    return {
        "per_call_median_seconds": median,
        "per_call_max_seconds": ordered[-1],
        "per_call_rows": len(ordered),
        "per_call_within_ceiling": None if ceiling is None else median <= ceiling,
    }


def from_result(kind, result, *, designs, requested=False):
    """The speed result from a reconstruction result that carried a timed query
    (`result.timed`). None when the run was not timed; when timing was `requested`
    but the result carries none (the timing run failed or timed out), the named
    `not_measured` block instead."""
    timed = getattr(result, "timed", None)
    block = (
        from_receipt(kind, timed.receipt, designs=designs)
        if timed is not None
        else None
    )
    if block is None and requested:
        return not_measured(kind)
    return block


def from_receipt(kind, receipt, *, designs):
    """The speed result from a bundle-inference measurement receipt, or None
    when the receipt carries no measurement."""
    measured = receipt.get("measurement") if type(receipt) is dict else None
    timing = measured.get("timing_s") if type(measured) is dict else None
    if type(timing) is not dict:
        return None
    parts = [timing.get(name) for name in MODEL_PARTS]
    if not all(type(part) in (int, float) and math.isfinite(part) for part in parts):
        return None
    # A static-batch graph is timed on the first designs of the query (its
    # declared batch), not all of them: the result says how many.
    shape = measured.get("input_shape")
    timed_designs = (
        shape[0]
        if type(shape) is list
        and shape
        and type(shape[0]) is int
        and 0 < shape[0] <= designs
        else designs
    )
    block = speed_block(kind, seconds=sum(parts), designs=timed_designs)
    if block is not None:
        block.update(per_call_figures(kind, measured.get("per_call_s")))
    if block is not None and timed_designs < designs:
        block["designs_total"] = designs
        block["scope"] = (
            "cold query: model load, compile and one inference over the first "
            f"{timed_designs} practice designs"
        )
        block["label"] = f"measured on the first {timed_designs} designs; {LABEL}"
    return block
