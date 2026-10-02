"""Pure bounded-linear DEVELOPMENT targets. Inputs are not an authority root."""

import math
from dataclasses import dataclass, replace
from decimal import (
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    InvalidOperation,
    localcontext,
)
from enum import Enum

Q12 = 10**12
DAY_MS = 86400000
ARITHMETIC = Context(prec=80, rounding=ROUND_HALF_EVEN)


class RewardFailure(ValueError):
    pass


def tick(value):
    if type(value) is not int or not 0 <= value < 2**63:
        raise RewardFailure("INVALID_TIME")
    return value


def units(value):
    if type(value) is not int or not 0 <= value <= Q12:
        raise RewardFailure("INVALID_ALLOCATION")
    return value


def decimal(value):
    if type(value) is not str or not 1 <= len(value) <= 100:
        raise RewardFailure("INVALID_DECIMAL")
    try:
        result = Decimal(value)
    except InvalidOperation:
        result = None
    if (
        result is None
        or not result.is_finite()
        or abs(result.as_tuple().exponent) > 1000
    ):
        raise RewardFailure("INVALID_DECIMAL")
    return result


def scientific(value):
    """Preserve A5's exact binary64 comparator; reject alternative hex encodings."""
    if type(value) is not str or len(value) > 32:
        raise RewardFailure("INVALID_SCORE")
    try:
        result = float.fromhex(value)
    except ValueError:
        result = math.nan
    if not math.isfinite(result) or not 0 <= result <= 1 or result.hex() != value:
        raise RewardFailure("INVALID_SCORE")
    if result == 0 and math.copysign(1, result) != 1:
        raise RewardFailure("INVALID_SCORE")
    return result


def score_decimal(value):
    return Decimal(str(scientific(value)))


@dataclass(frozen=True)
class Holder:
    hotkey: str
    coldkey: str
    registered_at: int

    def __post_init__(self):
        for value in (self.hotkey, self.coldkey):
            if (
                type(value) is not str
                or not 1 <= len(value) <= 128
                or not value.isascii()
            ):
                raise RewardFailure("INVALID_HOLDER")
        tick(self.registered_at)


@dataclass(frozen=True)
class DevelopmentTerms:
    """Synthetic/fixture terms only; ledger registration resolves baseline proof."""

    context_id: str
    baseline_ref: str
    baseline_hex: str
    upper: str
    opens_ms: int
    admits_until_ms: int
    funded_until_ms: int
    allocation: tuple[tuple[int, int], ...]

    def __post_init__(self):
        if any(
            type(value) is not str or len(value) != 64
            for value in (self.context_id, self.baseline_ref)
        ):
            raise RewardFailure("INVALID_CONTEXT")
        if not 0 <= score_decimal(self.baseline_hex) < decimal(self.upper) <= 1:
            raise RewardFailure("INVALID_RANGE")
        for value in (self.opens_ms, self.admits_until_ms, self.funded_until_ms):
            tick(value)
        if not self.opens_ms < self.admits_until_ms <= self.funded_until_ms:
            raise RewardFailure("INVALID_WINDOWS")
        if type(self.allocation) is not tuple or not 1 <= len(self.allocation) <= 1024:
            raise RewardFailure("INVALID_SCHEDULE")
        previous = -1
        for point in self.allocation:
            if type(point) is not tuple or len(point) != 2:
                raise RewardFailure("INVALID_SCHEDULE")
            when, amount = point
            tick(when)
            units(amount)
            if not self.opens_ms <= when < self.funded_until_ms or when <= previous:
                raise RewardFailure("INVALID_SCHEDULE")
            previous = when
        if self.allocation[0][0] != self.opens_ms:
            raise RewardFailure("INVALID_SCHEDULE")

    def allocated(self, now):
        tick(now)
        amount = 0
        if self.opens_ms <= now < self.funded_until_ms:
            for when, value in self.allocation:
                if when > now:
                    break
                amount = value
        return amount


@dataclass(frozen=True)
class Record:
    """Pure fixture input; journal adapter supplies accepted provenance."""

    event: str
    artifact: str
    score_hex: str
    holder: Holder
    receipt_order: int

    def __post_init__(self):
        scientific(self.score_hex)
        tick(self.receipt_order)
        if type(self.holder) is not Holder or any(
            type(v) is not str or len(v) != 64 for v in (self.event, self.artifact)
        ):
            raise RewardFailure("INVALID_RECORD")


@dataclass(frozen=True)
class State:
    terms: DevelopmentTerms
    record_hex: str
    holder: Holder | None
    event: str | None
    gain_at_anchor: str
    anchor_ms: int

    def __post_init__(self):
        if type(self.terms) is not DevelopmentTerms:
            raise RewardFailure("INVALID_STATE")
        tick(self.anchor_ms)
        with localcontext(ARITHMETIC):
            gain = score_decimal(self.record_hex) - score_decimal(
                self.terms.baseline_hex
            )
            if not 0 <= decimal(self.gain_at_anchor) <= gain or score_decimal(
                self.record_hex
            ) > decimal(self.terms.upper):
                raise RewardFailure("INVALID_STATE")
        if not self.terms.opens_ms <= self.anchor_ms <= self.terms.admits_until_ms:
            raise RewardFailure("INVALID_STATE")
        if self.holder is None:
            if (
                self.event is not None
                or self.record_hex != self.terms.baseline_hex
                or decimal(self.gain_at_anchor) != 0
            ):
                raise RewardFailure("INVALID_STATE")
        elif (
            type(self.holder) is not Holder
            or type(self.event) is not str
            or len(self.event) != 64
        ):
            raise RewardFailure("INVALID_STATE")


def opening(terms):
    return State(terms, terms.baseline_hex, None, None, "0", terms.opens_ms)


def decay(gain, elapsed_ms):
    tick(elapsed_ms)
    with localcontext(ARITHMETIC):
        return gain * (Decimal(2) ** (-Decimal(elapsed_ms) / DAY_MS))


def advance_batch(state, records, activation_ms):
    """Select one best accepted improvement; ties keep the incumbent.

    The ledger supplies an authoritative closed batch and immutable activation.
    This pure function neither authenticates nor accepts scientific evidence.
    """
    tick(activation_ms)
    if (
        activation_ms < state.anchor_ms
        or not state.terms.opens_ms <= activation_ms <= state.terms.admits_until_ms
    ):
        raise RewardFailure("STALE_ACTIVATION")
    if type(records) is not tuple or len(records) > 10000:
        raise RewardFailure("INVALID_BATCH")
    for record in records:
        if type(record) is not Record or score_decimal(record.score_hex) > decimal(
            state.terms.upper
        ):
            raise RewardFailure("INVALID_RECORD")
    if len({r.event for r in records}) != len(records) or len(
        {r.receipt_order for r in records}
    ) != len(records):
        raise RewardFailure("DUPLICATE_BATCH")
    if not records:
        return state
    winner = min(records, key=lambda r: (-scientific(r.score_hex), r.receipt_order))
    # Current A5/fixture comparison is exact binary64, with no invented tolerance.
    if scientific(winner.score_hex) <= scientific(state.record_hex):
        return state
    with localcontext(ARITHMETIC):
        gain = score_decimal(winner.score_hex) - score_decimal(state.record_hex)
        checkpoint = (
            decay(decimal(state.gain_at_anchor), activation_ms - state.anchor_ms) + gain
        )
    return replace(
        state,
        record_hex=winner.score_hex,
        holder=winner.holder,
        event=winner.event,
        gain_at_anchor=str(checkpoint),
        anchor_ms=activation_ms,
    )


def fraction(state, now):
    tick(now)
    if now < state.anchor_ms:
        raise RewardFailure("STALE_TIME")
    with localcontext(ARITHMETIC):
        headroom = decimal(state.terms.upper) - score_decimal(state.terms.baseline_hex)
        value = decay(decimal(state.gain_at_anchor), now - state.anchor_ms) / headroom
        if not 0 <= value <= 1:
            raise RewardFailure("INVALID_CREDIT_STATE")
        return int((value * Q12).to_integral_value(rounding=ROUND_FLOOR))


class WinnerStatus(str, Enum):
    USABLE = "USABLE"
    MISSING = "MISSING"
    DISQUALIFIED = "DISQUALIFIED"
    CONTESTED = "CONTESTED"


@dataclass(frozen=True)
class ChallengeTarget:
    context_id: str
    allocated: int
    earned: int
    unearned: int
    holder: Holder | None


@dataclass(frozen=True)
class CompleteTargets:
    challenges: tuple[ChallengeTarget, ...]
    winners: tuple[tuple[Holder, int], ...]
    burn: int


def targets(states, now, statuses):
    """One complete allocation: no earned-subset normalization or loser floors."""
    tick(now)
    if len(states) > 64 or len({s.terms.context_id for s in states}) != len(states):
        raise RewardFailure("INVALID_CHALLENGES")
    if set(statuses) != {s.terms.context_id for s in states}:
        raise RewardFailure("MISSING_WINNER_STATUS")
    rows, winners, allocated = [], {}, 0
    for state in sorted(states, key=lambda s: s.terms.context_id):
        status = statuses[state.terms.context_id]
        if type(status) is not WinnerStatus:
            raise RewardFailure("INVALID_WINNER_STATUS")
        amount = state.terms.allocated(now)
        earned = (
            amount * fraction(state, now) // Q12
            if state.holder and status is WinnerStatus.USABLE
            else 0
        )
        allocated += amount
        if earned:
            winners[state.holder] = winners.get(state.holder, 0) + earned
        rows.append(
            ChallengeTarget(
                state.terms.context_id, amount, earned, amount - earned, state.holder
            )
        )
    if allocated > Q12:
        raise RewardFailure("OVERALLOCATED")
    if len({holder.hotkey for holder in winners}) != len(winners):
        raise RewardFailure("CONFLICTING_HOTKEY_IDENTITY")
    ordered = tuple(
        sorted(
            winners.items(),
            key=lambda pair: (pair[0].hotkey, pair[0].coldkey, pair[0].registered_at),
        )
    )
    return CompleteTargets(tuple(rows), ordered, Q12 - sum(winners.values()))
