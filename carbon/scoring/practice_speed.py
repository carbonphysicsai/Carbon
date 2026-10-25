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
        "label": LABEL,
    }


def measure(runner) -> bool:
    """Whether a practice run asks for the timed cold query. Only a real
    isolated worker run is timed: a test runner stands in for the container, so
    its seconds would mean nothing."""
    return runner is None


def from_result(kind, result, *, designs):
    """The speed result from a reconstruction result that carried a timed query
    (`result.timed`), or None when the run was not timed."""
    timed = getattr(result, "timed", None)
    if timed is None:
        return None
    return from_receipt(kind, timed.receipt, designs=designs)


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
    return speed_block(kind, seconds=sum(parts), designs=designs)
