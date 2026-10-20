"""F02's sealed-exam population (OWNER-F02-F08-EXAM-DRAW-01).

**Law:** the owner-approved TRAIN near-limit law S1 (OWNER-F02-TRAIN40-V2-01)
with fresh seeds: peak power a whole number of watts, uniform on 70-100 W,
and on-time uniform on 4.0-6.0 s in 0.1 s steps, the draw TRAIN40-v2 used
(`f02_rr08.py`). Each batch is drawn from its own custody-keyed generator.

**Disjointness:** a drawn action is never one of the development exam's eight
cold actions (they are code, not published inputs) or repeated within the
batch. Every published case, TRAIN included, is excluded by the family's
overlap check (`confirmation_sources`), so a drawn case that repeats one is
refused and redrawn there.

A DEVELOPMENT population; not qualified, and no LIVE or reward-bearing
evaluation may use it.
"""

from __future__ import annotations

from .domain import INPUTS

POPULATION_VERSION = "carbon.f02.exam-near-limit-s1.v1"
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
        if action in seen or not admitted(case):
            continue
        seen.add(action)
        cases.append(case)
    return cases, attempts
