"""Shared fixture-only toy semantics for B-07C, B-07F, and B-E4.

The values in this module are deterministic engineering fixtures.  They are
not a physical population, an official reference, or qualification evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

FIXTURE_TRAINING_OBSERVATIONS = ((1, 1), (2, 4))
FIXTURE_HELDOUT_OBSERVATIONS = ((3, 9), (4, 16))
FIXTURE_TRANSFER_OBSERVATIONS = ((5, 25), (6, 36))

FIXTURE_SAMPLING_SURFACE_ID = "fixture_sampling_level"
FIXTURE_CURRICULUM_SURFACE_ID = "fixture_curriculum_emphasis"
FIXTURE_FEATURE_SURFACE_ID = "fixture_feature_degree"
_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)


@dataclass(frozen=True, slots=True)
class FixtureModelConfiguration:
    """Closed three-family configuration for the synthetic toy fit."""

    sampling_level: int
    curriculum_emphasis: int = 1
    feature_degree: int = 1

    def __post_init__(self) -> None:
        if type(self) is not FixtureModelConfiguration or any(
            type(value) is not int or value not in (1, 2)
            for value in (
                self.sampling_level,
                self.curriculum_emphasis,
                self.feature_degree,
            )
        ):
            raise ArithmeticError


@dataclass(frozen=True, slots=True)
class FixtureObservationSet:
    """Evaluator-held observations shared exactly by B-07C and B-07F.

    This fixture-data carrier is neither an agent-facing disclosure nor an
    execution authorization.  Its digest lets a campaign bind one toy task
    without persisting evaluator-held values in the provider transcript.
    """

    task_id: str
    training_observations: tuple[tuple[int, int], ...]
    heldout_observations: tuple[tuple[int, int], ...]
    transfer_observations: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        groups = (
            self.training_observations,
            self.heldout_observations,
            self.transfer_observations,
        )
        if (
            type(self) is not FixtureObservationSet
            or type(self.task_id) is not str
            or _TASK_ID.fullmatch(self.task_id) is None
            or any(
                type(group) is not tuple
                or not group
                or any(
                    type(item) is not tuple
                    or len(item) != 2
                    or type(item[0]) is not int
                    or type(item[1]) is not int
                    for item in group
                )
                for group in groups
            )
        ):
            raise TypeError("fixture observation set is invalid")

    @property
    def content_digest(self) -> str:
        return _digest(
            {
                "heldout": self.heldout_observations,
                "task_id": self.task_id,
                "training": self.training_observations,
                "transfer": self.transfer_observations,
            }
        )


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


LEGACY_FIXTURE_OBSERVATION_SET = FixtureObservationSet(
    "legacy-toy-physics-v1",
    FIXTURE_TRAINING_OBSERVATIONS,
    FIXTURE_HELDOUT_OBSERVATIONS,
    FIXTURE_TRANSFER_OBSERVATIONS,
)


def construct_fixture_model(
    observations: tuple[tuple[int, int], ...],
    level: int,
    seed: bytes,
    *,
    curriculum_emphasis: int = 1,
    feature_degree: int = 1,
) -> tuple[float, str]:
    """Fit one coefficient through three closed, independently causal levers.

    The keyword defaults deliberately preserve the original B-07C/B-07F
    linear, uniformly weighted sampling behavior.  All values remain bounded
    fixture mechanics; none selects evaluator cases or measurement policy.
    """

    if type(observations) is not tuple or type(seed) is not bytes or not seed:
        raise ArithmeticError
    configuration = FixtureModelConfiguration(
        level, curriculum_emphasis, feature_degree
    )
    ordered = observations if seed[0] % 2 == 0 else tuple(reversed(observations))
    # Level two gives the later item in the seed-bound curriculum first
    # priority before the sampling budget is applied.  This makes curriculum
    # a real construction choice even when sampling_level is one, while the
    # level-one/default path remains byte-for-byte compatible with B-07C/B-07F.
    if configuration.curriculum_emphasis == 2:
        ordered = tuple(reversed(ordered))
    selected = ordered[: configuration.sampling_level]
    if len(selected) != configuration.sampling_level or any(
        type(item) is not tuple
        or len(item) != 2
        or type(item[0]) is not int
        or type(item[1]) is not int
        for item in selected
    ):
        raise ArithmeticError
    weighted = tuple(
        (
            1 + (configuration.curriculum_emphasis - 1) * index,
            x**configuration.feature_degree,
            y,
        )
        for index, (x, y) in enumerate(selected)
    )
    denominator = sum(weight * feature * feature for weight, feature, _ in weighted)
    if denominator <= 0:
        raise ArithmeticError
    coefficient = float(
        sum(weight * feature * y for weight, feature, y in weighted) / denominator
    )
    if not math.isfinite(coefficient):
        raise ArithmeticError
    payload: dict[str, object] = {
        "coefficient": coefficient.hex(),
        "level": configuration.sampling_level,
    }
    # Preserve the exact legacy artifact identity for the legacy semantics.
    if configuration.curriculum_emphasis != 1 or configuration.feature_degree != 1:
        payload.update(
            {
                "curriculum_emphasis": configuration.curriculum_emphasis,
                "feature_degree": configuration.feature_degree,
            }
        )
    return coefficient, _digest(payload)


def evaluate_fixture_reference(
    coefficient: float,
    observations: tuple[tuple[int, int], ...],
    *,
    feature_degree: int = 1,
) -> float:
    """Return deterministic held-out mean squared error for the toy fixture."""

    if (
        type(coefficient) is not float
        or type(observations) is not tuple
        or not observations
        or type(feature_degree) is not int
        or feature_degree not in (1, 2)
        or any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not int
            or type(item[1]) is not int
            for item in observations
        )
    ):
        raise ArithmeticError
    value = float(
        sum((coefficient * (x**feature_degree) - y) ** 2 for x, y in observations)
        / len(observations)
    )
    if not math.isfinite(value) or value < 0.0:
        raise ArithmeticError
    return value
