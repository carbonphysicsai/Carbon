"""F02's sealed-exam population (OWNER-F02-F08-EXAM-DRAW-01).

**Law:** the owner-approved TRAIN near-limit law S1 (OWNER-F02-TRAIN40-V2-01)
with fresh seeds: peak power a whole number of watts, uniform on 70-100 W,
and on-time uniform on 4.0-6.0 s in 0.1 s steps, the draw TRAIN40-v2 used
(`f02_rr08.py`). Each batch is drawn from its own custody-keyed generator.

**Disjointness:** a drawn action is never one of the development exam's eight
cold actions (they are code, not published inputs), never repeated within the
batch, and never a published case: the draw skips every published F02 key
(`confirmation_sources`, TRAIN included). The producer refuses a whole batch
that repeats a published case and never redraws a role, and 45 of the law's
651 lattice points are published, so the skip is part of the draw.

A DEVELOPMENT population; not qualified, and no LIVE or reward-bearing
evaluation may use it.
"""

from __future__ import annotations

from pathlib import Path

from .domain import INPUTS

POPULATION_VERSION = "carbon.f02.exam-near-limit-s1.v1"
REPOSITORY = Path(__file__).resolve().parents[2]
PEAK_W = (70, 100)
ON_TIME_DECISECONDS = (40, 60)
#: The development exam's eight cold actions (peak W, on-time s).
EXAM_ACTIONS = frozenset(
    {(80.0, 5.0), (110.0, 10.0), (140.0, 5.0), (140.0, 20.0)}
    | {(float(p), 5.0) for p in (84, 85, 86, 87)}
)


def admitted(case):
    """In the S1 law's lattice and not a development exam action."""
    if set(case) != set(INPUTS):
        return False
    peak, on_time = float(case["peak_w"]), float(case["on_time_s"])
    tenths = round(on_time * 10)
    return (
        peak == int(peak)
        and PEAK_W[0] <= peak <= PEAK_W[1]
        and abs(on_time * 10 - tenths) < 1e-9
        and ON_TIME_DECISECONDS[0] <= tenths <= ON_TIME_DECISECONDS[1]
        and (peak, round(tenths / 10, 1)) not in EXAM_ACTIONS
    )


def _published_key(case):
    """Whether `case` repeats a published F02 case (the family's overlap key)."""
    published, key = _published()
    return key(case) in published


_PUBLISHED = {}


def _published():
    """The published f02 keys and the overlap key function, validated before
    they are cached: a missing evidence root or an empty published set fails
    closed (never caches an empty set that would let every case through).
    The producer's own published-case refusal stays the authority."""
    if "set" not in _PUBLISHED:
        from carbon.challenge_validator.confirmation_sources import source_for

        if not (REPOSITORY / "docs" / "development" / "evidence").is_dir():
            raise RuntimeError("f02_published_evidence_missing")
        source = source_for("f02")
        published = source.published(REPOSITORY)
        if not published:
            raise RuntimeError("f02_published_set_empty")
        _PUBLISHED["set"] = (frozenset(published), source.key)
    return _PUBLISHED["set"]


def draw(rng, count, *, max_attempts=None):
    """`count` distinct admitted actions from `rng`, in draw order."""
    max_attempts = max_attempts or 100 * count
    cases, seen, attempts = [], set(), 0
    while len(cases) < count:
        if attempts >= max_attempts:
            raise RuntimeError(
                f"{attempts} draws admitted only {len(cases)} of {count} cases"
            )
        attempts += 1
        action = (
            float(rng.randint(*PEAK_W)),
            round(rng.randint(*ON_TIME_DECISECONDS) / 10, 1),
        )
        case = dict(zip(INPUTS, action, strict=True))
        if action in seen or not admitted(case) or _published_key(case):
            continue
        seen.add(action)
        cases.append(case)
    return cases, attempts
