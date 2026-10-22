"""Private-exam Ladder feedback: the one document a miner sees for a grade.

OWNER-GRADE-FEEDBACK-LADDER-01 (build spec LADDER_AND_CAP_BUILD_SPEC_20261020
section A). From one graded private-exam result per miner, Challenge and exam
version, the miner sees only a closed document:

- ``total``, rounded down to the step (v2, OWNER-FULL-EXAM-BANK-01: the total
  alone; v1 also showed A and D);
- ``status``: IMPROVED, NO_IMPROVEMENT, GATE_FAILED or NOT_SCORED;
- ``gate_names``, drawn only from the closed gate registry (the Challenge's
  registered hard gates);
- ``exam_version``, and the document's ``schema``.

The step is max(eta = 0.02, the Challenge's registered rebuild noise). Shown
values change only when a new total reaches the previous best shown total
plus the step within the same exam version; otherwise the previous shown
values repeat. A new exam version starts a fresh ladder. Nothing else from the
exam (per-case values, case ids, which cases failed, the picked design,
references, unrounded legs) can appear: the output is built field by field
from an allow-list, never by removing fields.

The ladder's state is the miner's **best** document (its last IMPROVED one),
kept apart from what each submission shows: NO_IMPROVEMENT and GATE_FAILED
repeat the best values; NOT_SCORED (indeterminate evidence, a diagnostic-only
result, infrastructure, an ineligible or invalid outcome) shows no total, A
or D at all, so a result that does not count reveals no grade (Validator,
2026-10-20; the cap releases its slot on that condition). ``next_best`` keeps
the state.

Values are rounded *down* to the step grid with exact decimal arithmetic, so a
shown value never exceeds what was earned and never depends on float error.
This module is pure: storing the best document and serving documents to the
miner belong to the serving lane.
"""

from __future__ import annotations

import math
from decimal import ROUND_FLOOR, Decimal

SCHEMA = "carbon.private-exam.ladder-feedback.v2"
SCHEMA_V1 = "carbon.private-exam.ladder-feedback.v1"
ETA = 0.02
FIELDS = frozenset({"schema", "exam_version", "status", "total", "gate_names"})
STATUSES = ("IMPROVED", "NO_IMPROVEMENT", "GATE_FAILED", "NOT_SCORED")
#: Scoring statuses that carry a total (development now; official later).
_SCORED = frozenset({"SCORED_DEVELOPMENT_CANDIDATE"})
_GATE_FAILED = frozenset({"MANDATORY_GATE_FAILED"})


class LadderFeedbackRefused(ValueError):
    """The graded result or the ladder state cannot produce safe feedback."""


def step(rebuild_noise=None):
    """max(eta, the registered rebuild noise); eta when none is registered."""
    if rebuild_noise is None:
        return ETA
    if (
        type(rebuild_noise) not in (int, float)
        or not math.isfinite(rebuild_noise)
        or rebuild_noise < 0
    ):
        raise LadderFeedbackRefused("rebuild_noise")
    return max(ETA, float(rebuild_noise))


def _floor(value, grid):
    """``value`` rounded down to a multiple of ``grid``, exactly."""
    if type(value) not in (int, float) or not math.isfinite(value):
        raise LadderFeedbackRefused("value")
    q = Decimal(repr(float(value))) / Decimal(repr(float(grid)))
    return float(q.to_integral_value(rounding=ROUND_FLOOR) * Decimal(repr(float(grid))))


def _document(exam_version, status, values, gate_names):
    document = {
        "schema": SCHEMA,
        "exam_version": exam_version,
        "status": status,
        "total": values.get("total"),
        "gate_names": list(gate_names),
    }
    if set(document) != FIELDS or status not in STATUSES:
        raise LadderFeedbackRefused("document_fields")
    return document


def next_best(best, document):
    """The ladder state after ``document``: it replaces ``best`` only when it
    improved, and a document for another exam version starts a fresh state."""
    if document["status"] == "IMPROVED":
        return document
    if best is not None and best["exam_version"] != document["exam_version"]:
        return None
    return best


def ladder_feedback(graded, *, best, exam_version, gate_registry, rebuild_noise):
    """The miner's feedback document for one graded result.

    ``graded`` is the ScoreEngine's row for the miner's model (``status``,
    ``score``, ``legs``, ``gates``); ``best`` the miner's best document for
    this Challenge (its last IMPROVED one, see ``next_best``), or None;
    ``gate_registry`` the Challenge's closed set of registered gate names;
    ``rebuild_noise`` its registered value, or None when none is registered.
    It has no default, so a caller that forgets it fails instead of silently
    showing values finer than the registered noise allows.
    """
    if type(exam_version) is not str or not exam_version:
        raise LadderFeedbackRefused("exam_version")
    registry = frozenset(gate_registry)
    if not registry or not all(type(name) is str and name for name in registry):
        raise LadderFeedbackRefused("gate_registry")
    if best is not None and (
        type(best) is not dict
        or set(best) != FIELDS
        or best["schema"] != SCHEMA
        or best["status"] != "IMPROVED"
    ):
        raise LadderFeedbackRefused("best")
    grid = step(rebuild_noise)
    # A new exam version starts a fresh ladder.
    if best is not None and best["exam_version"] != exam_version:
        best = None
    none = {"total": None}
    shown = {"total": best["total"]} if best is not None else none
    if type(graded) is not dict or type(graded.get("status")) is not str:
        raise LadderFeedbackRefused("graded")
    status = graded["status"]
    if status in _GATE_FAILED:
        gates = graded.get("gates")
        if type(gates) is not dict or not set(gates) <= registry:
            raise LadderFeedbackRefused("gate_registry")
        failed = sorted(name for name, verdict in gates.items() if verdict == "FAIL")
        if not failed:
            raise LadderFeedbackRefused("gate_failed_without_gate")
        return _document(exam_version, "GATE_FAILED", shown, failed)
    if status not in _SCORED:
        # A result that does not count reveals no grade.
        return _document(exam_version, "NOT_SCORED", none, ())
    total = graded.get("score")
    rounded = {"total": _floor(total, grid)}
    if shown["total"] is not None and not total >= shown["total"] + grid:
        return _document(exam_version, "NO_IMPROVEMENT", shown, ())
    return _document(exam_version, "IMPROVED", rounded, ())
