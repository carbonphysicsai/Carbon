"""Producer-side per-candidate settlement for solved-panel exports
(EVIDENCE-PRODUCER-STAGES-01).

`reference_resolution` consumes explicit producer verdicts and never infers
one from a near-limit point estimate. This module computes those verdicts
from the solved rungs, under the named method
`two-rungs-same-side-change-below-band.v1`:

- a candidate gets a verdict only when the reference assessment (bands
  applied) leaves it unresolved;
- every in-band limit must settle. Its ladder is the standard value followed
  by the registered rungs present on the row (`<rung>.<quantity>`);
- `mode="finest_two"`: the two finest rungs lie on one side of the limit and
  differ by less than the band (battery, motor; Test Lead ruling (a));
- `mode="all"`: every rung lies on one side and the ladder's spread is below
  the band (f02, whose mesh and time rungs are not ordered by fineness; this
  is the registry's all-rungs-agree rule plus the method's change test);
- a limit without a refined rung, or that does not settle, leaves the
  candidate without a verdict (it stays UNRESOLVED).

It reads values only; it never changes a limit, band or candidate.
"""

from __future__ import annotations

from carbon.design_search import power, reference_resolution, tasks

MODES = ("finest_two", "all")


def rule(rule_id):
    """The export-level rule naming this method."""
    body = {"id": rule_id, "method": reference_resolution.REFINEMENT_METHOD}
    reference_resolution.validate_rule(body)
    return body


def _settles(limit, ladder, mode):
    used = ladder[-2:] if mode == "finest_two" else ladder
    if len(used) < 2:
        return None
    sides = {tasks._verdict(limit, value, False) for value in used}
    if len(sides) != 1 or max(used) - min(used) >= limit["band"]:
        return None
    return sides.pop()


def verdicts(task, rows, rungs, mode):
    """[{candidate, feasible}] for the band-unresolved candidates that settle."""
    if mode not in MODES:
        raise ValueError(f"unknown settlement mode {mode!r}")
    panel = power._panel(rows, task)
    truth = tasks.assess(task, panel, reference=True)
    out = []
    for candidate in task["candidates"]:
        if truth[candidate]["feasible"] is not None:
            continue
        feasible = True
        for condition in (c["id"] for c in task["conditions"]):
            values = panel[(candidate, condition)]
            for limit in task["limits"]:
                quantity = limit["quantity"]
                side = tasks._verdict(limit, values[quantity], True)
                if side is None:
                    ladder = [values[quantity]] + [
                        values[f"{r}.{quantity}"]
                        for r in rungs
                        if f"{r}.{quantity}" in values
                    ]
                    side = _settles(limit, ladder, mode)
                if side is None:
                    feasible = None
                    break
                feasible = feasible and side
            if feasible is None:
                break
        if feasible is not None:
            out.append({"candidate": candidate, "feasible": feasible})
    return out
