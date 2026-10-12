"""MARGIN-SIZING-04's known-SD normal planning calculation, not a daemon rule.

The live library uses registered bounded evidence in ``core``. These functions
exist to make the public development simulation reproducible, including its
normal-known-SD caveat. They must not be used to grade an artifact.
"""

from __future__ import annotations

import math
import random
from statistics import NormalDist


def detectable_improvement(
    *, sd: float, cases: int, contenders: int, alpha: float, power: float
) -> float:
    if not (math.isfinite(sd) and sd > 0 and cases > 0 and contenders > 0):
        raise ValueError("positive known SD, case count and contender count required")
    if not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("alpha and power must be probabilities")
    normal = NormalDist()
    return (
        (-normal.inv_cdf(alpha / contenders) + normal.inv_cdf(power))
        * sd
        / math.sqrt(cases)
    )


def normal_mixture_crossed(
    *, total: float, cases: int, sd: float, prior_variance: float, alpha: float
) -> bool:
    """Exactly the M04 positive-side, normal-known-SD planning boundary."""
    if not (
        math.isfinite(total)
        and math.isfinite(sd)
        and math.isfinite(prior_variance)
        and sd > 0
        and prior_variance > 0
        and cases > 0
        and 0 < alpha < 1
    ):
        raise ValueError("valid normal planning inputs required")
    variance = cases * sd * sd
    return total >= math.sqrt(
        (variance + prior_variance)
        * math.log((variance + prior_variance) / (prior_variance * alpha * alpha))
    )


def m04_rounds_to_win(
    *,
    improvement: float,
    sd: float,
    cases_per_round: int,
    alpha_art: float,
    max_rounds: int,
    repetitions: int,
    seed: int,
) -> tuple[float, ...]:
    """Reproduce M04's deterministic simulation from its registered inputs."""
    if not (math.isfinite(improvement) and max_rounds > 0 and repetitions > 0):
        raise ValueError("valid planning simulation inputs required")
    rng = random.Random(seed)
    prior_variance = cases_per_round * sd * sd
    winners = [0] * max_rounds
    for _ in range(repetitions):
        total = 0.0
        for round_index in range(max_rounds):
            total += rng.gauss(
                improvement * cases_per_round, sd * math.sqrt(cases_per_round)
            )
            if normal_mixture_crossed(
                total=total,
                cases=(round_index + 1) * cases_per_round,
                sd=sd,
                prior_variance=prior_variance,
                alpha=alpha_art,
            ):
                for future in range(round_index, max_rounds):
                    winners[future] += 1
                break
    return tuple(count / repetitions for count in winners)
