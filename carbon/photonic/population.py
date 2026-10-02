"""The photonic coupler's DEVELOPMENT population and its public sampling law.

**Membership.** A case is in the population when its two inputs lie in
`domain.INPUT_BOUNDS`: the exam-design campaign's coupler family, all of
which the reference covers (its gap ladder starts at the smallest gap and
ends where the bends do).

**Sampling law.** Independent draws, uniform over the box: P(x) is uniform,
with no separate proposal or weighting (Q = P, w = 1).

**What this is not.** A provisional DEVELOPMENT population under the owner's
2026-10-01 delegation (OWNER-CHALLENGE-DESIGN-01). It is not a qualified
Challenge population, claims nothing about which couplers are built, and no
LIVE or reward-bearing evaluation may use it.
"""

from __future__ import annotations

import hashlib
import random

from .domain import INPUT_BOUNDS, INPUTS

POPULATION_VERSION = "carbon.photonic-coupler.development-population.v1"


def public_rng(label):
    """A deterministic generator for PUBLIC draws (pilots, public pools), seeded
    from a label anyone can read. Never for private evaluation cases."""
    seed = int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")
    return random.Random(seed)


def draw(rng, count):
    """`count` cases, uniform over the box, in draw order."""
    return [
        {name: rng.uniform(*INPUT_BOUNDS[name]) for name in INPUTS}
        for _ in range(count)
    ]
