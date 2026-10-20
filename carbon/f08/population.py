"""F08's sealed-exam population (OWNER-F02-F08-EXAM-DRAW-01).

**Law:** the approved TRAIN near-limit law N1r (TRAIN v2's near-limit
stratum, `docs/development/evidence/f08-near-limit-public-20261020`), with
fresh seeds. N1r placed registered-lattice geometries by a log-linear fit of
worst dynamic compliance to RR-PACKS-07's 40 solves (log thickness and the
other five inputs linear), half predicted safe over 0.125-0.150 mm/N and
half unsafe over 0.150-0.175 mm/N, spread evenly across each half.

N1r chose the candidate nearest each of 32 fixed targets; that rule has no
randomness, so a fresh seed would redraw the same geometries. Here each half
is cut into four equal strata of predicted compliance and each case is a
uniformly random lattice geometry from its stratum (case i from stratum
i mod 8): the same fit, band, split and spread, with the seed choosing the
geometry. Working decision (Data Collection, 2026-10-20), notified to the
Validator.

**The fit is pinned, not refit.** Its 32 RR-PACKS-07 N1 rows are not
committed (that stratum failed its one-third rule and is history); the eight
ladder rows are (`ladder-observed.json`, byte-identical to the run's). The
coefficients below are the fit's to the last bit, with the five source files'
SHA-256; a test pins that they place every committed N1r geometry on its
registered target.

**Disjointness:** the draw skips every published F08 geometry (TRAIN, pilot,
ladder, N1r; `confirmation_sources`). The producer refuses a whole batch that
repeats a published case and never redraws a role, and 50 published
geometries lie in the band, so the skip is part of the draw. A
prediction is placement only: it is not a reference and never a label.

A DEVELOPMENT population; not qualified, and no LIVE or reward-bearing
evaluation may use it.
"""

from __future__ import annotations

import bisect
import functools
import itertools
import json
import math
from pathlib import Path

from .domain import INPUTS, LIMIT_MM_PER_N

POPULATION_VERSION = "carbon.f08.exam-near-limit-n1r.v1"
REPOSITORY = Path(__file__).resolve().parents[2]
REGISTRATION = Path(
    "docs/development/challenge_pipeline/structures-readiness/registration.json"
)
#: log(worst dynamic mm/N) = c0 + c1 log(thickness) + c2 length + c3 width
#: + c4 rib height + c5 rib thickness + c6 relief length (RR-PACKS-07, 40 rows).
FIT = (
    -0.05780793352733087,
    -0.8889468901783588,
    0.016232538691098024,
    -0.0031040644409849757,
    -0.13859212067681917,
    -0.1631012212533035,
    0.0006389481443387523,
)
FIT_SOURCES_SHA256 = {
    "f08-rr07-n1-b0/observed.json": (
        "92e729c1cb41da1ceff9c9974e16721f42b4fc382da3702b85c089c9f781ddcd"
    ),
    "f08-rr07-n1-b1/observed.json": (
        "82e66876233b50efafe7a16ca42472b4e6352e8daaaee84029f2c2f9c8e6ffcf"
    ),
    "f08-rr07-n1-b2/observed.json": (
        "f45d3ec94c5335b04dde92219146f34f7e9ac102f4dd71d844fa8faff164b84b"
    ),
    "f08-rr07-n1-b3/observed.json": (
        "b075348f04f6ea393662b84a4ac372e7b7c01171810b6e73f5d9e653137b18a5"
    ),
    "f08-rr07-ladder/observed.json": (
        "26aef1d5f33a29e42c9f208b4b88220bffd488a2d68e9be73d0c93c9c13b03e9"
    ),
}
BAND = (0.125, 0.175)
STRATA = 8  # four safe, then four unsafe


def predicted(case):
    """The N1r fit's placement value for a geometry (mm/N); not a reference."""
    others = [case[name] for name in INPUTS if name != "thickness_mm"]
    features = [1.0, math.log(case["thickness_mm"]), *others]
    return math.exp(sum(c * x for c, x in zip(FIT, features, strict=True)))


def stratum(value):
    """The stratum index (0-7) of a predicted value inside the band, or None."""
    if not BAND[0] <= value < BAND[1]:
        return None
    return min(STRATA - 1, int((value - BAND[0]) / (BAND[1] - BAND[0]) * STRATA))


@functools.cache
def _registration():
    return json.loads((REPOSITORY / REGISTRATION).read_text(encoding="utf-8"))


def _grid():
    grammar = _registration()["grammar"]
    return {
        name: [
            grammar[name]["min"] + grammar[name]["step"] * i
            for i in range(
                round(
                    (grammar[name]["max"] - grammar[name]["min"])
                    / grammar[name]["step"]
                )
                + 1
            )
        ]
        for name in INPUTS
    }


def _on_lattice(case):
    from carbon.challenge_pipeline import structures_readiness as s

    try:
        s.action(_registration(), dict(case))
    except ValueError:
        return False
    return True


@functools.cache
def _strata():
    """Every valid lattice geometry in the band, by stratum, in lattice order."""
    grid = _grid()
    pools = [[] for _ in range(STRATA)]
    for combo in itertools.product(*(grid[name] for name in INPUTS)):
        case = {name: float(v) for name, v in zip(INPUTS, combo, strict=True)}
        index = stratum(predicted(case))
        if index is not None and _on_lattice(case):
            pools[index].append(case)
    return tuple(tuple(pool) for pool in pools)


def admitted(case):
    """A valid registered-lattice geometry predicted inside the band."""
    if type(case) is not dict or set(case) != set(INPUTS):
        return False
    grid = _grid()
    for name in INPUTS:
        values = grid[name]
        k = bisect.bisect_left(values, case[name])
        if k == len(values) or not math.isclose(values[k], case[name]):
            return False
    return stratum(predicted(case)) is not None and _on_lattice(case)


def _published_key(case):
    """Whether `case` repeats a published F08 geometry (the overlap key)."""
    published, key = _published()
    return key(case) in published


@functools.cache
def _published():
    from carbon.challenge_validator.confirmation_sources import source_for

    source = source_for("f08-ribbed-bracket")
    return source.published(REPOSITORY), source.key


def draw(rng, count, *, max_attempts=None):
    """`count` distinct geometries, case i uniformly from stratum i mod 8."""
    max_attempts = max_attempts or 100 * count
    pools = _strata()
    cases, seen, attempts = [], set(), 0
    while len(cases) < count:
        if attempts >= max_attempts:
            raise RuntimeError(
                f"{attempts} draws admitted only {len(cases)} of {count} cases"
            )
        attempts += 1
        case = rng.choice(pools[len(cases) % STRATA])
        key = tuple(case[name] for name in INPUTS)
        if key in seen or _published_key(case):
            continue
        seen.add(key)
        cases.append(dict(case))
    return cases, attempts


__all__ = [
    "BAND",
    "FIT",
    "LIMIT_MM_PER_N",
    "POPULATION_VERSION",
    "admitted",
    "draw",
    "predicted",
]
