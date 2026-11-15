"""The speed gate's match tolerance for a vmap-64 version (owner, Sun 15 Nov 2026 ~11:1x CST via the Lead: "Just don't
make some barely fitting rule that causes things to fail and our system to be fragile."; CV-Motor-B ruling S2).

A vmap-64 version (`direct_graph_construction_worker.VMAP64_INFERENCE_VERSIONS`, Motor 1.8) grades every row in an
isolated lane of a multi-lane compiled call (at most 64 lanes, fewer for a large model), while the speed gate's timed calls stay per-case compiled calls: the two are
Carbon's own programs over the same row and agree to rounding, not bit for bit. Their comparison
(`lean_recipe_retention._single_call_raw`) is therefore a WIDE-MARGIN combined tolerance per value, over every value of
a row: ``|timed - graded| <= atol + rtol * |graded|``, both sides finite, the same shape.

- The VALUES are a host values row, outside ``carbon/`` (`REGISTRY`, ``"<challenge> <version>": {"rtol", "atol"}``),
  posted by CV-Motor-B. ``atol`` must be positive (a zero atol would make a value near zero need exact equality, the
  barely fitting case) and ``rtol`` non-negative. Unset (``null``, HUMAN_INPUT) or malformed, a vmap-64 version is
  refused: the receiver does not serve it (`require_served`), and a grade reads the row FIRST, before any exam read or
  inference (`lean_recipe_retention.regrade_retained_entry`), and stops with `UNREGISTERED`. Never exact, never a guess.
- A timed answer BEYOND the tolerance is CARBON's (two of our programs disagree), never the miner's: the single-call
  stage raises `DISAGREE` and writes no side file, so the scorer never receives a speed mismatch for a vmap-64 version.
- Both codes leave the evaluation's private grading by raising (`lean_recipe_retention._propagated_carbon_failures`), so
  the receiver's grader writes a FAILED marker through its give-back (`auto_grade.AutoGrader._fail`): the exam slot is
  released as FAILED_INFRA, never a candidate outcome and never a speed FAIL. `DISAGREE` is transient
  (`auto_retry.retryable`): one automatic re-grade for the task's life, and a second failure stays FAILED for the
  operator. `UNREGISTERED` is version-wide: the slot is returned, no automatic retry until the row is fixed.
- Every other version is untouched: `tolerance` is None and the stage compares exactly, as before.

This is a values contract only; it changes no score, no gate and no producer file.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "speed_match_tolerance.json"
)
SCHEMA = "carbon.validator.speed-match-tolerance.v1"
#: The tolerance is unset (HUMAN_INPUT) or malformed for a vmap-64 version: version-wide, never retried automatically.
UNREGISTERED = "speed_match_tolerance_unregistered"
#: A timed answer beyond the registered tolerance: Carbon's, FAILED_INFRA (transient: one automatic retry).
DISAGREE = "speed_outputs_disagree"


class SpeedMatchUnregistered(ValueError):
    def __init__(self, code=UNREGISTERED):
        self.code = code
        super().__init__(code)


def _vmap64(challenge_id, version) -> bool:
    from carbon.development_session.direct_graph_construction_worker import (
        VMAP64_INFERENCE_VERSIONS,
    )

    return (challenge_id, version) in VMAP64_INFERENCE_VERSIONS


def _value(value, *, positive=False):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or value < 0
        or (positive and value <= 0)
    ):
        raise SpeedMatchUnregistered()
    return float(value)


def tolerance(challenge_id, version, *, path=None):
    """``(rtol, atol)`` of a vmap-64 version, or None for every other version (exact, as before). A vmap-64 version
    with no registry, no row, a null value or a malformed row raises `SpeedMatchUnregistered` (fail closed).
    """
    if not _vmap64(challenge_id, version):
        return None
    try:
        document = json.loads(Path(REGISTRY if path is None else path).read_bytes())
    except (OSError, ValueError) as exc:
        raise SpeedMatchUnregistered() from exc
    if type(document) is not dict or document.get("schema") != SCHEMA:
        raise SpeedMatchUnregistered()
    rows = document.get("rows")
    row = rows.get(f"{challenge_id} {version}") if type(rows) is dict else None
    if type(row) is not dict or set(row) != {"rtol", "atol"}:
        raise SpeedMatchUnregistered()
    # a zero atol makes a value near zero need exact equality: the barely fitting rule the ruling rules out
    return _value(row["rtol"]), _value(row["atol"], positive=True)


def require_served(challenge_id, version, *, path=None) -> None:
    """The receiver's start check: a vmap-64 version is not served until its tolerance is registered."""
    tolerance(challenge_id, version, path=path)


def outputs_agree(single_outputs, graded_outputs, indices, registered) -> bool:
    """Whether every timed answer is within ``registered`` (``(rtol, atol)``) of the graded answer on the same row:
    ``|a - b| <= atol + rtol * |b|`` per value, ``b`` the graded value; a non-finite value on either side, a shape
    difference or a missing row never agrees."""
    import numpy as np

    rtol, atol = registered
    if type(indices) not in (list, tuple) or len(single_outputs) != len(indices):
        return False
    for position, index in enumerate(indices):
        try:
            a = np.asarray(single_outputs[position], dtype=np.float64)
            b = np.asarray(graded_outputs[index], dtype=np.float64)
        except (TypeError, ValueError, IndexError):
            return False
        if (
            a.shape != b.shape
            or not np.isfinite(a).all()
            or not np.isfinite(b).all()
            or not bool(np.all(np.abs(a - b) <= atol + rtol * np.abs(b)))
        ):
            return False
    return True


__all__ = [
    "DISAGREE",
    "REGISTRY",
    "SCHEMA",
    "UNREGISTERED",
    "SpeedMatchUnregistered",
    "outputs_agree",
    "require_served",
    "tolerance",
]
