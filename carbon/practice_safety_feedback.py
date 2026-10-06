"""Decision-value safety metrics shown beside the practice score (PRACTICE-SAFETY-01).

Owner decision A8, specified in
`.agent/tickets/PRACTICE-SAFETY-01_decision_value_feedback.md`: practice
feedback reports, next to the practice score, whether a model errs on the
unsafe side of a decision limit. The practice score measures average error,
so it cannot show the direction of an error at a limit.

The rules every metric follows here:
- **Feedback only.** A metric enters no score, gate, ranking, promotion,
  frontier event, reward, weight or settlement. Every metric and the document
  carry `"feedback_only": true`. Nothing outside the three practice research
  providers imports this module or a Challenge's `practice_safety` module.
- **Public practice material only.** Each Challenge computes on its committed
  PRACTICE references. The decision limits and bands are copied into the
  Challenge's module from their named source, and a test binds each copy to
  that source, so the metric code opens no study, contract or Track B file.
- **Allow-listed disclosure.** `document` refuses any field, label or value
  type its Challenge does not declare. Only aggregate counts, rates and signed
  means per constraint leave; never a per-case value, case id or per-case
  verdict.
- **Missing data is never clean.** A missing or invalid prediction on any
  practice case makes every metric `null` (UNMEASURED). A reference that
  fails validity, or that lies within its band of a limit, is UNRESOLVED and
  excluded. Both counts are reported (`unmeasured` counts cases, `unresolved`
  counts reference verdicts, one per case and constraint).
"""

from __future__ import annotations

import math
from statistics import fmean

SCHEMA = "carbon.practice-safety-feedback.v1"
#: The label on every metric compared exactly against its limit (cooling and
#: motor, Test Lead ruling 2026-10-05): read it as indicative.
NO_BAND = "no uncertainty band applied"
#: Battery B4 in practice-feedback v2, before Data Collection committed the
#: practice decision set. A stored v2 result keeps this meaning; battery v3
#: computes B4 instead and never emits it.
B4_BLOCKED = "BLOCKED: practice decision set not committed"
DIGITS = 6


class DisclosureRefused(ValueError):
    """A safety document carries something its allow-list does not name."""


#: Leaf kinds an allow-list may name.
COUNT = "count"  # a non-negative int
NUMBER = "number"  # a finite float or int, or None (no case to measure)
TRUE = "true"  # exactly True


def literal(*values):
    """A leaf that must be one of these fixed values (labels, names, None)."""
    return frozenset(values)


def rate(hits, of):
    """`hits / of`, rounded, or None when there is nothing to divide by."""
    return None if of == 0 else round(hits / of, DIGITS)


def signed_mean(values):
    """The rounded mean of `values`, or None when there are none (a rounded
    negative zero reads as 0.0)."""
    return None if not values else round(fmean(values), DIGITS) + 0.0


def _conforms(value, spec):
    if isinstance(spec, frozenset):
        return any(value is v or (type(value) is type(v) and value == v) for v in spec)
    if spec == COUNT:
        return type(value) is int and value >= 0
    if spec == NUMBER:
        return value is None or (type(value) in (int, float) and math.isfinite(value))
    if spec == TRUE:
        return value is True
    if isinstance(spec, dict):
        return (
            type(value) is dict
            and set(value) == set(spec)
            and all(_conforms(value[k], spec[k]) for k in spec)
        )
    if isinstance(spec, tuple):  # alternatives
        return any(_conforms(value, s) for s in spec)
    raise TypeError("unknown allow-list leaf")


def document(challenge, metrics, *, unmeasured, unresolved, material, allowed):
    """The allow-listed safety document, or DisclosureRefused.

    `allowed` maps each metric id to its declared shape. A metric is either
    that shape or None (UNMEASURED); anything else is refused, so a field
    added by mistake can never reach a participant.
    """
    out = {
        "schema": SCHEMA,
        "challenge": challenge,
        "feedback_only": True,
        "metrics": metrics,
        "unmeasured": unmeasured,
        "unresolved": unresolved,
        "material": material,
    }
    spec = {
        "schema": literal(SCHEMA),
        "challenge": literal(challenge),
        "feedback_only": TRUE,
        "metrics": {k: (v, literal(None)) for k, v in allowed.items()},
        "unmeasured": COUNT,
        "unresolved": COUNT,
        "material": {
            "path": literal(material["path"]),
            "sha256": literal(material["sha256"]),
        },
    }
    if not _conforms(out, spec):
        raise DisclosureRefused("practice safety document is not allow-listed")
    return out
