"""One fresh-batch championship round, prospectively separate from carry-forward.

The caller supplies sealed, shared accuracy-leg errors and the registered draw
blocks.  This module does not draw a batch, settle a gate, or change a king.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType

from .core import _finite, _identity, _probability


@dataclass(frozen=True)
class Rev5Rule:
    rule_digest: str
    contract_digest: str
    batch_id: str
    king_id: str
    drawn_cases: int
    max_contenders: int
    margin_rel: float
    alpha_round: float
    draw_unit: str

    def __post_init__(self) -> None:
        for name in ("rule_digest", "contract_digest", "batch_id", "king_id"):
            _identity(getattr(self, name), name)
        if type(self.drawn_cases) is not int or self.drawn_cases < 2:
            raise ValueError("registered drawn case count must be at least two")
        if type(self.max_contenders) is not int or self.max_contenders < 1:
            raise ValueError("registered positive contender limit required")
        if not 0 <= _finite(self.margin_rel, "posted margin") < 1:
            raise ValueError("posted relative margin must be in [0, 1)")
        _probability(self.alpha_round, "round alpha")
        if self.draw_unit not in {"case", "registered_block"}:
            raise ValueError("registered draw unit required")


@dataclass(frozen=True)
class Rev5Case:
    case_id: str
    block_id: str
    king_error: float
    contender_error: float

    def __post_init__(self) -> None:
        _identity(self.case_id, "case")
        _identity(self.block_id, "draw block")
        if _finite(self.king_error, "king error") < 0:
            raise ValueError("king error must be nonnegative")
        if _finite(self.contender_error, "contender error") < 0:
            raise ValueError("contender error must be nonnegative")


@dataclass(frozen=True)
class Rev5Contender:
    artifact_id: str
    cases: tuple[Rev5Case, ...]
    g_feas_passed: bool
    important_region_passed: bool

    def __post_init__(self) -> None:
        _identity(self.artifact_id, "artifact")
        if type(self.cases) is not tuple or not self.cases:
            raise ValueError("nonempty paired case tuple required")
        if (
            type(self.g_feas_passed) is not bool
            or type(self.important_region_passed) is not bool
        ):
            raise ValueError("settled G-FEAS and important-region guards required")


@dataclass(frozen=True)
class Rev5Outcome:
    artifact_id: str
    relative_improvement: float
    paired_improvement: float
    block_se: float
    block_count: int
    statistical_threshold: float
    qualified: bool


@dataclass(frozen=True)
class Rev5Result:
    winner_id: str
    king_id: str
    batch_id: str
    unique_cases: int
    outcomes: tuple[Rev5Outcome, ...]


def _beta_fraction(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta (Numerical Recipes)."""
    tiny = 1e-300
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 501):
        m2 = 2 * m
        aa = m * (b - m) * x / ((a + m2 - 1) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-14:
            return h
    raise ArithmeticError("incomplete beta did not converge")


def _regularized_beta(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    factor = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1) / (a + b + 2):
        return factor * _beta_fraction(a, b, x) / a
    return 1 - factor * _beta_fraction(b, a, 1 - x) / b


def _student_t_quantile(probability: float, degrees: int) -> float:
    """Positive one-sided Student t quantile, without an optional dependency."""
    _probability(probability, "t probability")
    if probability <= 0.5 or type(degrees) is not int or degrees < 1:
        raise ValueError("positive t quantile and positive degrees required")
    tail = 1 - probability
    lo, hi = 0.0, 1.0

    def survival(value: float) -> float:
        return 0.5 * _regularized_beta(
            degrees / 2, 0.5, degrees / (degrees + value * value)
        )

    while survival(hi) > tail:
        hi *= 2
    for _ in range(80):
        middle = (lo + hi) / 2
        if survival(middle) > tail:
            lo = middle
        else:
            hi = middle
    return (lo + hi) / 2


def select_rev5_winner(
    rule: Rev5Rule, contenders: tuple[Rev5Contender, ...]
) -> Rev5Result:
    """Select one winner from a single shared batch; a tie retains the king.

    ``drawn_cases`` counts the raw batch. Repeated hidden case identities must
    have identical paired values and are collapsed before the mean and SE.
    Every registered contender counts in the Bonferroni K, including gate failures.
    """
    if type(contenders) is not tuple or len(contenders) > rule.max_contenders:
        raise ValueError("contender family exceeds registered K")
    ids = [row.artifact_id for row in contenders]
    if len(ids) != len(set(ids)) or rule.king_id in ids:
        raise ValueError("distinct contender artifacts different from king required")
    if not contenders:
        return Rev5Result(rule.king_id, rule.king_id, rule.batch_id, 0, ())

    signature: tuple[tuple[str, str, float], ...] | None = None
    raw_ids: tuple[str, ...] | None = None
    outcomes: list[Rev5Outcome] = []
    unique_count = 0
    for contender in contenders:
        if len(contender.cases) != rule.drawn_cases:
            raise ValueError("contender does not have registered drawn batch size")
        unique: dict[str, Rev5Case] = {}
        for case in contender.cases:
            if type(case) is not Rev5Case:
                raise ValueError("registered paired case required")
            _finite(case.king_error - case.contender_error, "paired improvement")
            if rule.draw_unit == "case" and case.block_id != case.case_id:
                raise ValueError("case draw unit requires one block per case")
            previous = unique.setdefault(case.case_id, case)
            if previous != case:
                raise ValueError("conflicting values for duplicate case")
        current_signature = tuple(
            sorted(
                (case.case_id, case.block_id, case.king_error)
                for case in unique.values()
            )
        )
        current_raw_ids = tuple(sorted(case.case_id for case in contender.cases))
        if signature is None:
            signature = current_signature
            raw_ids = current_raw_ids
            unique_count = len(unique)
        elif current_signature != signature or current_raw_ids != raw_ids:
            raise ValueError("contenders must share the same sealed paired batch")
        king_mean = math.fsum(case.king_error for case in unique.values()) / len(unique)
        if king_mean <= 0:
            raise ValueError(
                "positive king mean error required for relative improvement"
            )
        difference = math.fsum(
            case.king_error - case.contender_error for case in unique.values()
        ) / len(unique)
        relative = difference / king_mean
        blocks: dict[str, list[float]] = {}
        for case in unique.values():
            blocks.setdefault(case.block_id, []).append(
                case.king_error - case.contender_error
            )
        if len(blocks) < 2:
            raise ValueError("at least two independent draw blocks required")
        block_means = [math.fsum(values) / len(values) for values in blocks.values()]
        block_mean = math.fsum(block_means) / len(block_means)
        se = math.sqrt(
            math.fsum((value - block_mean) ** 2 for value in block_means)
            / ((len(block_means) - 1) * len(block_means))
        )
        threshold = (
            _student_t_quantile(
                1 - rule.alpha_round / rule.max_contenders, len(block_means) - 1
            )
            * se
        )
        qualified = (
            contender.g_feas_passed
            and contender.important_region_passed
            and relative >= rule.margin_rel
            and block_mean > threshold
        )
        outcomes.append(
            Rev5Outcome(
                contender.artifact_id,
                relative,
                block_mean,
                se,
                len(block_means),
                threshold,
                qualified,
            )
        )
    eligible = [outcome for outcome in outcomes if outcome.qualified]
    best = max((row.relative_improvement for row in eligible), default=None)
    top = [row.artifact_id for row in eligible if row.relative_improvement == best]
    winner = top[0] if len(top) == 1 else rule.king_id
    return Rev5Result(
        winner, rule.king_id, rule.batch_id, unique_count, tuple(outcomes)
    )


BATTERY_REV5_TESTNET = MappingProxyType(
    {
        "drawn_cases": 4000,
        "max_contenders": 10,
        "margin_rel": 0.0225,
        "alpha_round": 0.01,
        "draw_unit": "case",
    }
)
