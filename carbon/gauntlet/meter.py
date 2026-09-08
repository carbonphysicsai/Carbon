"""Deterministic fixture-policy accounting for B-E4 preflight diagnostics.

The unit in this module is a versioned semantic operation performed by one of
the fixed fixture drivers.  It is deliberately not CPU time, money, a B-07E
fixture resource quantity, or an official-result-dependent measurement.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import Enum

METER_SCHEMA_VERSION = "1.0"
METER_POLICY_ID = "be4_fixture_policy_work_unit_v1"
_METER_POLICY_BYTES = (
    b"carbon.be4.fixture-policy-work-unit.v1\x00"
    b"attempt=1;candidate_comparison=1;candidate_proposal=1;"
    b"corpus_item_inspection=1;policy_transition=1;prior_item_inspection=1;"
    b"rng_draw=1;scaffold_parameter_inspection=1;service_operation=1"
)
METER_POLICY_DIGEST = "sha256:" + hashlib.sha256(_METER_POLICY_BYTES).hexdigest()
_MAX_COUNT = (1 << 63) - 1
_RECEIPT_DOMAIN = b"carbon.be4.fixture-policy-work-receipt.v1\x00"


class PolicyWorkBudgetExceeded(ValueError):
    """A work event was rejected before it could cross the bound ceiling."""

    def __init__(self, kind: PolicyWorkKind) -> None:
        if type(kind) is not PolicyWorkKind:
            raise TypeError("budget exhaustion requires an exact work kind")
        self.kind = kind
        super().__init__(
            f"normalized policy-work ceiling would be exceeded by {kind.value}"
        )


class PolicyWorkKind(str, Enum):
    """Closed, equally weighted fixture-policy operation vocabulary."""

    ATTEMPT = "ATTEMPT"
    CANDIDATE_COMPARISON = "CANDIDATE_COMPARISON"
    CANDIDATE_PROPOSAL = "CANDIDATE_PROPOSAL"
    CORPUS_ITEM_INSPECTION = "CORPUS_ITEM_INSPECTION"
    POLICY_TRANSITION = "POLICY_TRANSITION"
    PRIOR_ITEM_INSPECTION = "PRIOR_ITEM_INSPECTION"
    RNG_DRAW = "RNG_DRAW"
    SCAFFOLD_PARAMETER_INSPECTION = "SCAFFOLD_PARAMETER_INSPECTION"
    SERVICE_OPERATION = "SERVICE_OPERATION"


@dataclass(frozen=True, slots=True)
class PolicyWorkCount:
    kind: PolicyWorkKind
    count: int

    def __post_init__(self) -> None:
        if (
            type(self) is not PolicyWorkCount
            or type(self.kind) is not PolicyWorkKind
            or type(self.count) is not int
            or not 0 <= self.count <= _MAX_COUNT
        ):
            raise TypeError("policy work counts require exact bounded values")


@dataclass(frozen=True, slots=True)
class NormalizedComputeReceipt:
    """Replayable work-unit total with no wall time or fixture-resource facts."""

    schema_version: str
    policy_id: str
    policy_digest: str
    counts: tuple[PolicyWorkCount, ...]
    total_work_units: int

    def __post_init__(self) -> None:
        if (
            type(self) is not NormalizedComputeReceipt
            or self.schema_version != METER_SCHEMA_VERSION
            or self.policy_id != METER_POLICY_ID
            or self.policy_digest != METER_POLICY_DIGEST
            or type(self.counts) is not tuple
            or any(type(item) is not PolicyWorkCount for item in self.counts)
            or tuple(item.kind for item in self.counts) != tuple(PolicyWorkKind)
            or type(self.total_work_units) is not int
            or not 0 <= self.total_work_units <= _MAX_COUNT
            or sum(item.count for item in self.counts) != self.total_work_units
        ):
            raise TypeError("normalized compute receipt is not canonical")

    @property
    def content_digest(self) -> str:
        """Bind the immutable counts for transcript replay, not qualification."""

        fields = (
            self.schema_version,
            self.policy_id,
            self.policy_digest,
            *(f"{item.kind.value}:{item.count}" for item in self.counts),
            f"TOTAL:{self.total_work_units}",
        )
        return (
            "sha256:"
            + hashlib.sha256(
                _RECEIPT_DOMAIN + b"\x00".join(item.encode("ascii") for item in fields)
            ).hexdigest()
        )


@dataclass(frozen=True, slots=True)
class WallTimeObservation:
    """Raw elapsed time kept separate from normalized fixture-policy compute."""

    elapsed_seconds: float

    def __post_init__(self) -> None:
        if (
            type(self) is not WallTimeObservation
            or type(self.elapsed_seconds) is not float
            or not math.isfinite(self.elapsed_seconds)
            or self.elapsed_seconds < 0.0
        ):
            raise TypeError("wall time must be an exact non-negative finite float")


class PolicyWorkMeter:
    """Mutable preflight-local counter with an optional fail-before-work cap."""

    __slots__ = ("__ceiling", "__counts")

    def __init__(self) -> None:
        if type(self) is not PolicyWorkMeter:
            raise TypeError("policy work meter subclasses are rejected")
        object.__setattr__(self, "_PolicyWorkMeter__counts", [0] * len(PolicyWorkKind))
        object.__setattr__(self, "_PolicyWorkMeter__ceiling", None)

    def bind_ceiling(self, maximum_work_units: int) -> None:
        """Bind one exact ceiling before the first metered operation.

        A bound meter cannot be repurposed for another budget.  Enforcement is
        performed before mutating a count, so a rejected event does not create
        an over-budget receipt.
        """

        if (
            type(maximum_work_units) is not int
            or not 0 <= maximum_work_units <= _MAX_COUNT
        ):
            raise TypeError("meter ceiling must be an exact non-negative int63")
        counts = object.__getattribute__(self, "_PolicyWorkMeter__counts")
        if any(counts):
            raise ValueError("meter ceiling must be bound before preflight work")
        current = object.__getattribute__(self, "_PolicyWorkMeter__ceiling")
        if current is not None and current != maximum_work_units:
            raise ValueError("meter ceiling cannot be rebound")
        object.__setattr__(self, "_PolicyWorkMeter__ceiling", maximum_work_units)

    def record(self, kind: PolicyWorkKind, count: int = 1) -> None:
        if (
            type(kind) is not PolicyWorkKind
            or type(count) is not int
            or count < 1
            or count > _MAX_COUNT
        ):
            raise TypeError("meter events require an exact kind and positive count")
        index = tuple(PolicyWorkKind).index(kind)
        counts = object.__getattribute__(self, "_PolicyWorkMeter__counts")
        updated = counts[index] + count
        if updated > _MAX_COUNT:
            raise OverflowError("policy work count exceeds int63")
        ceiling = object.__getattribute__(self, "_PolicyWorkMeter__ceiling")
        if ceiling is not None and sum(counts) + count > ceiling:
            raise PolicyWorkBudgetExceeded(kind)
        counts[index] = updated

    @property
    def bound_ceiling(self) -> int | None:
        return object.__getattribute__(self, "_PolicyWorkMeter__ceiling")

    def snapshot(self) -> NormalizedComputeReceipt:
        counts = object.__getattribute__(self, "_PolicyWorkMeter__counts")
        items = tuple(
            PolicyWorkCount(kind, counts[index])
            for index, kind in enumerate(PolicyWorkKind)
        )
        return NormalizedComputeReceipt(
            METER_SCHEMA_VERSION,
            METER_POLICY_ID,
            METER_POLICY_DIGEST,
            items,
            sum(item.count for item in items),
        )


__all__ = (
    "METER_POLICY_DIGEST",
    "METER_POLICY_ID",
    "METER_SCHEMA_VERSION",
    "NormalizedComputeReceipt",
    "PolicyWorkBudgetExceeded",
    "PolicyWorkCount",
    "PolicyWorkKind",
    "PolicyWorkMeter",
    "WallTimeObservation",
)
