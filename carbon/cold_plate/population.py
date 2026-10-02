# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The cold plate's DEVELOPMENT population: what a case may be, and how cases
are drawn.

**Membership.** A case is in the population when its nine inputs lie in
`domain.INPUT_BOUNDS` and the closed-form model (`analytic`) predicts, for it:
- a hottest wetted wall of at most `SCREEN["max_wall_c"]`, so the coolant
  stays inside the PG25 model, which ends at 100 C; and
- a Reynolds number of at most `SCREEN["re_max"]`, so the flow stays laminar.

The reference then checks its own fluid (`analysis`): a case the screen
admits but whose solved fluid passes 99 C is REFERENCE_INVALID, charged to
the reference, and counted. The screen is public code, so anyone can decide
membership exactly; it is versioned with the model it runs
(`POPULATION_VERSION`), because changing either changes the population.

**Sampling law.** Independent draws, uniform over the box, kept if they pass
the screen: P(x) is uniform on the admitted region. There is no separate
proposal or weighting; Q = P and w = 1.

**What this is not.** A provisional DEVELOPMENT population chosen under the
owner's 2026-10-01 delegation (OWNER-CHALLENGE-DESIGN-01). It is not a
qualified Challenge population, it claims nothing about which plates are
built, and no LIVE or reward-bearing evaluation may use it.
"""

from __future__ import annotations

import hashlib
import random

from . import analytic
from .domain import INPUT_BOUNDS, INPUTS, RE_LAMINAR_MAX

POPULATION_VERSION = "carbon.cold-plate.development-population.v1"
#: 4 K below the coolant model's 99 C ceiling: margin for the closed-form
#: model's error, which the pilot measures against the reference.
SCREEN = {"max_wall_c": 95.0, "re_max": RE_LAMINAR_MAX}


def screen(case):
    """(admitted, reasons, diagnostics) for one case's inputs."""
    result = analytic.predict(case)
    diagnostics = result["diagnostics"]
    reasons = []
    if diagnostics["max_wall_c"] > SCREEN["max_wall_c"]:
        reasons.append(
            f"closed-form hottest wall {diagnostics['max_wall_c']:.2f} C exceeds "
            f"{SCREEN['max_wall_c']:g} C"
        )
    if diagnostics["re_max"] > SCREEN["re_max"]:
        reasons.append(
            f"closed-form Re {diagnostics['re_max']:.0f} exceeds {SCREEN['re_max']:g}"
        )
    return not reasons, reasons, diagnostics


def admitted(case):
    return screen(case)[0]


def public_rng(label):
    """A deterministic generator for PUBLIC draws (pilots, public pools), seeded
    from a label anyone can read. Never for private evaluation cases."""
    seed = int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")
    return random.Random(seed)


def draw(rng, count, *, max_attempts=None):
    """`count` admitted cases, in draw order, and how many draws it took."""
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
