"""The motor's DEVELOPMENT population: uniform over the buildable box.

**Membership:** the eight inputs lie in `domain.INPUT_BOUNDS` and the
geometry is buildable (`domain.validity`: about 91 % of the box). There is no
physics screen: the reference has no applicability edge inside the box that
a closed-form model must predict, and a case whose solve fails is typed
REFERENCE_INVALID or REFERENCE_SOLVER_FAILED, charged to the reference.

**Sampling law:** independent uniform draws, kept if buildable. Q = P, w = 1.

A provisional DEVELOPMENT population under OWNER-CHALLENGE-DESIGN-01; not a
qualified one, and no LIVE or reward-bearing evaluation may use it.
"""

from __future__ import annotations

import hashlib
import random

from .domain import INPUT_BOUNDS, INPUTS, validity

POPULATION_VERSION = "carbon.motor.development-population.v1"


def admitted(case):
    return not validity(case)


def public_rng(label):
    """A deterministic generator for PUBLIC draws only."""
    seed = int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")
    return random.Random(seed)


def draw(rng, count, *, max_attempts=None):
    max_attempts = max_attempts or 100 * count
    cases, attempts = [], 0
    while len(cases) < count:
        if attempts >= max_attempts:
            raise RuntimeError(
                f"{attempts} draws admitted only {len(cases)} of {count} cases"
            )
        attempts += 1
        case = {name: rng.uniform(*INPUT_BOUNDS[name]) for name in INPUTS}
        if admitted(case):
            cases.append(case)
    return cases, attempts
