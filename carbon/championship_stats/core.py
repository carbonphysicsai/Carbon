"""Pure paired-comparison primitives for a prospective championship daemon.

Positive differences mean lower contender accuracy error. The bounded mixture
is a one-sided e-process: for each positive bet lambda, Hoeffding's lemma makes
exp(lambda * sum(d - epsilon) - n * lambda**2 * width**2 / 8) a nonnegative
supermartingale when every conditional mean is at most epsilon and paired
differences are in the registered bounds. A fixed convex mixture is also an
e-process. The caller must ensure cases are fresh and conditionally valid; IDs
only prevent accidental duplicate accounting inside this state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace


def _finite(value: float, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _identity(value: str, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} identity required")
    return value


def _probability(value: float, name: str) -> float:
    value = _finite(value, name)
    if not 0 < value < 1:
        raise ValueError(f"{name} must be between zero and one")
    return value


@dataclass(frozen=True)
class PairedCase:
    case_id: str
    incumbent_error: float
    contender_error: float

    def __post_init__(self) -> None:
        _identity(self.case_id, "case")
        _finite(self.incumbent_error, "incumbent error")
        _finite(self.contender_error, "contender error")
        _finite(self.difference, "paired difference")

    @property
    def difference(self) -> float:
        return self.incumbent_error - self.contender_error


@dataclass(frozen=True)
class PairedRound:
    artifact_id: str
    incumbent_id: str
    round_id: str
    cases: tuple[PairedCase, ...]
    g_feas_passed: bool

    def __post_init__(self) -> None:
        for name in ("artifact_id", "incumbent_id", "round_id"):
            _identity(getattr(self, name), name)
        if self.artifact_id == self.incumbent_id:
            raise ValueError("contender and incumbent must be distinct artifacts")
        if type(self.g_feas_passed) is not bool:
            raise ValueError("G-FEAS must be a settled boolean")
        if not self.cases or type(self.cases) is not tuple:
            raise ValueError("nonempty paired case tuple required")
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate case in round")

    @property
    def differences(self) -> tuple[float, ...]:
        return tuple(case.difference for case in self.cases)


@dataclass(frozen=True)
class BoundedMixture:
    """Registered bounds, improvement margin and positive betting mixture."""

    lower: float
    upper: float
    epsilon: float
    bets: tuple[float, ...]
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        lower = _finite(self.lower, "lower bound")
        upper = _finite(self.upper, "upper bound")
        _finite(self.epsilon, "epsilon")
        if lower >= upper or not lower <= self.epsilon <= upper:
            raise ValueError("registered bounds must contain epsilon")
        if not self.bets or len(self.bets) != len(self.weights):
            raise ValueError("nonempty matched betting rates and weights required")
        if any(_finite(b, "bet") <= 0 for b in self.bets):
            raise ValueError("betting rates must be positive")
        if any(_finite(w, "weight") <= 0 for w in self.weights):
            raise ValueError("mixture weights must be positive")
        if not math.isclose(math.fsum(self.weights), 1.0, abs_tol=1e-12):
            raise ValueError("mixture weights must sum to one")

    def e_value(self, count: int, centered_sum: float) -> float:
        if type(count) is not int or count < 0:
            raise ValueError("nonnegative case count required")
        _finite(centered_sum, "centered sum")
        width = self.upper - self.lower
        logs = [
            math.log(weight)
            + bet * centered_sum
            - count * bet * bet * width * width / 8
            for bet, weight in zip(self.bets, self.weights, strict=True)
        ]
        high = max(logs)
        if high > 709:
            return math.inf
        return math.exp(high) * math.fsum(math.exp(x - high) for x in logs)


@dataclass(frozen=True)
class Evidence:
    """Immutable carry-forward state bound to an artifact and incumbent."""

    artifact_id: str
    incumbent_id: str
    mixture: BoundedMixture
    cases_per_round: int
    case_ids: frozenset[str] = frozenset()
    round_ids: frozenset[str] = frozenset()
    centered_sum: float = 0.0
    count: int = 0
    max_e_value: float = 1.0
    g_feas_passed: bool = True

    def __post_init__(self) -> None:
        _identity(self.artifact_id, "artifact")
        _identity(self.incumbent_id, "incumbent")
        if self.artifact_id == self.incumbent_id:
            raise ValueError("contender and incumbent must differ")
        if type(self.mixture) is not BoundedMixture:
            raise ValueError("registered bounded mixture required")
        if type(self.cases_per_round) is not int or self.cases_per_round <= 0:
            raise ValueError("registered positive N required")
        if type(self.count) is not int or self.count != len(self.case_ids):
            raise ValueError("case count must match accounted case identities")
        _finite(self.centered_sum, "centered sum")
        if self.max_e_value < 1 or math.isnan(self.max_e_value):
            raise ValueError("max e-value must be at least one")
        if type(self.g_feas_passed) is not bool:
            raise ValueError("settled G-FEAS boolean required")

    def update(self, round_: PairedRound) -> Evidence:
        if (round_.artifact_id, round_.incumbent_id) != (
            self.artifact_id,
            self.incumbent_id,
        ):
            raise ValueError("artifact or incumbent changed: start fresh evidence")
        if round_.round_id in self.round_ids:
            raise ValueError("round already accounted")
        if len(round_.cases) != self.cases_per_round:
            raise ValueError("round does not match registered N")
        new_ids = frozenset(case.case_id for case in round_.cases)
        if new_ids & self.case_ids:
            raise ValueError("case already accounted")
        differences = round_.differences
        if any(not self.mixture.lower <= d <= self.mixture.upper for d in differences):
            raise ValueError("paired difference exceeds registered bounds")
        count = self.count + len(differences)
        centered_sum = math.fsum(
            (self.centered_sum, *(d - self.mixture.epsilon for d in differences))
        )
        return replace(
            self,
            case_ids=self.case_ids | new_ids,
            round_ids=self.round_ids | {round_.round_id},
            centered_sum=centered_sum,
            count=count,
            max_e_value=max(
                self.max_e_value, self.mixture.e_value(count, centered_sum)
            ),
            g_feas_passed=self.g_feas_passed and round_.g_feas_passed,
        )

    @property
    def anytime_p_value(self) -> float:
        return 1 / self.max_e_value

    @property
    def mean_improvement(self) -> float | None:
        if self.count == 0:
            return None
        return self.centered_sum / self.count + self.mixture.epsilon


@dataclass(frozen=True)
class AlphaLedger:
    """Conservative artifact-keyed alpha investment with no wealth return."""

    day_id: str
    global_alpha: float
    allocations: tuple[tuple[str, str, float], ...] = ()

    def __post_init__(self) -> None:
        _identity(self.day_id, "day")
        _probability(self.global_alpha, "global daily alpha")
        for artifact, incumbent, allocation in self.allocations:
            _identity(artifact, "artifact")
            _identity(incumbent, "incumbent")
            _probability(allocation, "artifact alpha")
        if math.fsum(row[2] for row in self.allocations) > self.global_alpha + 1e-15:
            raise ValueError("daily alpha overspent")
        if len({row[:2] for row in self.allocations}) != len(self.allocations):
            raise ValueError("duplicate artifact/incumbent allocation")

    @property
    def remaining(self) -> float:
        return max(0.0, self.global_alpha - math.fsum(r[2] for r in self.allocations))

    def invest(self, artifact_id: str, incumbent_id: str, alpha: float) -> AlphaLedger:
        _identity(artifact_id, "artifact")
        _identity(incumbent_id, "incumbent")
        if artifact_id == incumbent_id:
            raise ValueError("artifact and incumbent must differ")
        alpha = _probability(alpha, "artifact alpha")
        if any(row[:2] == (artifact_id, incumbent_id) for row in self.allocations):
            raise ValueError("artifact/incumbent already allocated")
        if alpha > self.remaining + 1e-15:
            raise ValueError("daily global alpha exhausted")
        return replace(
            self, allocations=self.allocations + ((artifact_id, incumbent_id, alpha),)
        )

    def allocation(self, artifact_id: str, incumbent_id: str) -> float:
        for artifact, incumbent, alpha in self.allocations:
            if (artifact, incumbent) == (artifact_id, incumbent_id):
                return alpha
        raise ValueError("artifact/incumbent has no daily alpha allocation")


def holm(p_values: dict[str, float], alpha: float) -> frozenset[str]:
    """Holm step-down familywise rejections over the full registered family."""
    _probability(alpha, "family alpha")
    if not p_values:
        raise ValueError("nonempty contender family required")
    for artifact, p in p_values.items():
        _identity(artifact, "artifact")
        p = _finite(p, "p value")
        if not 0 <= p <= 1:
            raise ValueError("p value outside [0, 1]")
    ranked = sorted(p_values.items(), key=lambda row: (row[1], row[0]))
    rejected: set[str] = set()
    for index, (artifact, p) in enumerate(ranked):
        if p >= alpha / (len(ranked) - index):
            break  # equality is not a takeover
        rejected.add(artifact)
    return frozenset(rejected)


@dataclass(frozen=True)
class Contender:
    evidence: Evidence
    confirmed_noninferior: bool

    def __post_init__(self) -> None:
        if type(self.confirmed_noninferior) is not bool:
            raise ValueError("settled confirmation boolean required")


def select_winner(contenders: tuple[Contender, ...], ledger: AlphaLedger) -> str | None:
    """Choose a unique evidenced eligible winner; otherwise retain incumbent."""
    if not contenders:
        raise ValueError("nonempty registered contender family required")
    ids = [c.evidence.artifact_id for c in contenders]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate artifact in championship")
    if len({c.evidence.incumbent_id for c in contenders}) != 1:
        raise ValueError("all contenders must face the same incumbent")
    family_alpha = math.fsum(
        ledger.allocation(c.evidence.artifact_id, c.evidence.incumbent_id)
        for c in contenders
    )
    # Keep gated or unconfirmed artifacts in the multiplicity family.
    rejected = holm(
        {c.evidence.artifact_id: c.evidence.anytime_p_value for c in contenders},
        family_alpha,
    )
    eligible = [
        c.evidence
        for c in contenders
        if c.evidence.artifact_id in rejected
        and c.evidence.g_feas_passed
        and c.confirmed_noninferior
        and c.evidence.mean_improvement is not None
        and c.evidence.mean_improvement > c.evidence.mixture.epsilon
    ]
    if not eligible:
        return None
    maximum = max(c.mean_improvement for c in eligible)
    top = [c.artifact_id for c in eligible if c.mean_improvement == maximum]
    return top[0] if len(top) == 1 else None


def confirmation_lower_bound(
    differences: tuple[float, ...], *, lower: float, upper: float, alpha: float
) -> float:
    """One-sided Hoeffding lower bound on independent fresh paired differences."""
    _probability(alpha, "confirmation alpha")
    lower = _finite(lower, "lower bound")
    upper = _finite(upper, "upper bound")
    if lower >= upper or not differences:
        raise ValueError("nonempty confirmation cases and ordered bounds required")
    values = tuple(_finite(x, "paired difference") for x in differences)
    if any(not lower <= x <= upper for x in values):
        raise ValueError("confirmation difference exceeds registered bounds")
    return math.fsum(values) / len(values) - (upper - lower) * math.sqrt(
        math.log(1 / alpha) / (2 * len(values))
    )


def confirm_noninferiority(
    evidence: Evidence,
    confirmation: PairedRound,
    *,
    confirmation_cases: int,
    delta_c: float,
    lower: float,
    upper: float,
    alpha: float,
) -> bool:
    """Require disjoint fresh paired confirmation above -delta_c and G-FEAS."""
    delta_c = _finite(delta_c, "confirmation margin")
    if delta_c < 0:
        raise ValueError("nonnegative confirmation margin required")
    if type(confirmation_cases) is not int or confirmation_cases <= 0:
        raise ValueError("registered positive confirmation N required")
    if len(confirmation.cases) != confirmation_cases:
        raise ValueError("confirmation does not match registered N")
    if (confirmation.artifact_id, confirmation.incumbent_id) != (
        evidence.artifact_id,
        evidence.incumbent_id,
    ):
        raise ValueError("confirmation artifact or incumbent mismatch")
    if confirmation.round_id in evidence.round_ids or any(
        case.case_id in evidence.case_ids for case in confirmation.cases
    ):
        raise ValueError("confirmation must use fresh cases and round")
    if not evidence.g_feas_passed or not confirmation.g_feas_passed:
        return False
    return (
        confirmation_lower_bound(
            confirmation.differences, lower=lower, upper=upper, alpha=alpha
        )
        > -delta_c
    )
