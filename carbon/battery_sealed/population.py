"""Battery's sealed-exam population (Validator, VALIDATOR_BATTERY_SEALED_RULINGS_20261022 §4, §7).

**Law:** fresh uniform draws over the hull of the 2.0 material's 420-grid
region (EV4's development grid: 12 conditions x 35 candidates): ambient
5-34 C, initial state of charge 0.12-0.48, first-stage rate 0.5-2.0 C and
second-stage rate 0.2-1.0 C, each rounded to 4 decimals. The hull is read
from the EV4 contract by a test, never restated as a new value. Placement is
never a label: the plating-onset label is the pinned v2 reader's, and the
exam QA enforces the straddle.

**Disjointness:** a drawn case is never repeated within the batch and never a
published Battery case (the 420 grid, practice, the B15 probes, the plating
studies, every EV4/PDD record): the draw skips every published key
(`confirmation_sources`), and the producer refuses a whole batch that repeats
one. A missing or empty evidence set fails closed.

A DEVELOPMENT population; not qualified, and no LIVE or reward-bearing
evaluation may use it.
"""

from __future__ import annotations

from pathlib import Path

from .domain import INPUTS

POPULATION_VERSION = "carbon.battery.sealed-exam-grid-hull.v1"
REPOSITORY = Path(__file__).resolve().parents[2]
#: The 420 grid's hull (a test pins these to the EV4 contract's min/max).
HULL = {
    "c1": (0.5, 2.0),
    "c2": (0.2, 1.0),
    "t_amb_c": (5.0, 34.0),
    "soc0": (0.12, 0.48),
}
PLACES = 4


def admitted(case):
    """Inside the hull and rounded to the law's 4 decimals."""
    if set(case) != set(INPUTS):
        return False
    for name in INPUTS:
        value = float(case[name])
        low, high = HULL[name]
        if not low <= value <= high or round(value, PLACES) != value:
            return False
    return True


def _published_key(case):
    """Whether `case` repeats a published Battery case (the family's overlap key)."""
    published, key = _published()
    return key(case) in published


_PUBLISHED = {}


def _published():
    """The published keys and the overlap key function, validated before they
    are cached: a missing evidence root or an empty published set fails
    closed (it would otherwise let every case through)."""
    if "set" not in _PUBLISHED:
        from carbon.challenge_validator.confirmation_sources import source_for

        if not (REPOSITORY / "docs" / "development" / "evidence").is_dir():
            raise RuntimeError("battery_sealed_published_evidence_missing")
        source = source_for("battery-sealed-exam")
        published = source.published(REPOSITORY)
        if not published:
            raise RuntimeError("battery_sealed_published_set_empty")
        _PUBLISHED["set"] = (frozenset(published), source.key)
    return _PUBLISHED["set"]


def draw(rng, count, *, max_attempts=None):
    """`count` distinct admitted cases from `rng`, in draw order."""
    max_attempts = max_attempts or 100 * count
    cases, seen, attempts = [], set(), 0
    while len(cases) < count:
        if attempts >= max_attempts:
            raise RuntimeError(
                f"{attempts} draws admitted only {len(cases)} of {count} cases"
            )
        attempts += 1
        case = {
            name: round(rng.uniform(*HULL[name]), PLACES) for name in INPUTS
        }
        key = tuple(case[name] for name in INPUTS)
        if key in seen or not admitted(case) or _published_key(case):
            continue
        seen.add(key)
        cases.append(case)
    return cases, attempts
