"""Shared names and refusals for the Graphite progress ledger (GRAPHITE-PROGRESS-01).

The ledger answers "does Graphite get better, and at what cost?" with one line per level per
batch. It lives OUTSIDE the repository (a host file); this package, its schema and its docs are
the repository's part. Nothing here estimates: a number with no cited source is the string
`UNMEASURED`, and a sealed source is refused, never read.

DEVELOPMENT only: it grades nothing, accepts nothing and claims no qualification.
"""

from __future__ import annotations

from pathlib import Path

LINE_SCHEMA = "carbon.graphite.progress-line.v1"
RUN_SCHEMA = "carbon.graphite.progress-run.v1"
UNMEASURED = "UNMEASURED"
USD_BASIS = (
    "controller-committed cost: pod reservation (pod charges are unresolved at the provider and "
    "stay at their reservation) plus the provider-reported model charge; totals only; a lower "
    "bound where a model charge was not recorded"
)
#: A path naming any of these is a sealed or private source and is refused, never read.
SEALED_MARKERS = (
    "sealed",
    "hidden",
    "private",
    "answer-key",
    "answer_key",
    "confirm-sheet",
)
REFUSAL_CLASSES = (
    "brief_gap",
    "envelope_too_tight",
    "correct_block",
    "infra",
    "UNCLASSIFIED",
)
TRIAGE_CLASSES = ("REAL_ESCAPE", "ORACLE_GAP", "FALSE_POSITIVE")


class ProgressError(ValueError):
    """A typed refusal; the first word is the code."""


def refuse_sealed(path):
    """Refuse a path that names sealed or private material (checked on every component)."""
    text = "/".join(Path(path).parts).lower()
    for marker in SEALED_MARKERS:
        if marker in text:
            raise ProgressError(f"sealed_source_refused: {marker}")
    return Path(path)


def metric(value, n, source):
    """One ledger number: `value` (or UNMEASURED), the sample size it rests on, and its source."""
    return {"value": value, "n": n, "source": source}


def unmeasured(reason, n=0):
    return {"value": UNMEASURED, "n": n, "source": reason}
