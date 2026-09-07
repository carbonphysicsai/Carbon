"""Nominal, content-addressed values for B-07C fixture-only practice."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum

from carbon.authoring.primitives import validate_canonical_id, validate_version_token
from carbon.measurement.refs import MeasurementContractRef
from carbon.registry import ChallengeKey
from carbon.research.records import PrivateIdentityRef, ResearchFailureCategory
from carbon.research.refs import (
    CompilerEnvironmentRef,
    PracticePackRef,
    PracticeScopeStatementRef,
)


class PracticeAuthority(str, Enum):
    MOCK_ONLY = "MOCK_ONLY"


class PracticePopulationRelationship(str, Enum):
    SYNTHETIC_FIXTURE_ONLY = "SYNTHETIC_FIXTURE_ONLY"
    HUMAN_INPUT_REQUIRED = "HUMAN_INPUT_REQUIRED"


class PracticeOmission(str, Enum):
    RESOLUTION = "RESOLUTION"
    SAMPLE_COUNT = "SAMPLE_COUNT"
    TRAINING_DURATION = "TRAINING_DURATION"
    REFERENCE_DEPTH = "REFERENCE_DEPTH"
    REGIME_BREADTH = "REGIME_BREADTH"
    STRESS_BREADTH = "STRESS_BREADTH"
    AUDIT_STRATA = "AUDIT_STRATA"
    ROLLOUT_HORIZON = "ROLLOUT_HORIZON"


class PracticeUncertaintyRule(str, Enum):
    OBSERVED_RANGE_ONLY = "OBSERVED_RANGE_ONLY"


class PracticeDisclosureRule(str, Enum):
    AGGREGATE_ONLY = "AGGREGATE_ONLY"


class MockReferenceCapability(str, Enum):
    SYNTHETIC_MOCK_ONLY = "SYNTHETIC_MOCK_ONLY"


class MockFixtureBehavior(str, Enum):
    COMPLETE = "COMPLETE"
    REFERENCE_FAILURE = "REFERENCE_FAILURE"
    MEASUREMENT_FAILURE = "MEASUREMENT_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    RESOURCE_KILL = "RESOURCE_KILL"


class PracticeAggregateKind(str, Enum):
    RECONSTRUCTION = "RECONSTRUCTION"
    SINGLE_PRACTICE = "SINGLE_PRACTICE"
    PAIRED_DIFFERENCE = "PAIRED_DIFFERENCE"
    RESOURCE_CALIBRATION = "RESOURCE_CALIBRATION"


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(b"carbon.practice.v1\x00" + encoded).hexdigest()


def _key(value: object) -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise TypeError("practice values require an exact ChallengeKey")
    return ChallengeKey(value.challenge_id, value.version)


def _strings(values: object, *, nonempty: bool = False) -> tuple[str, ...]:
    if type(values) is not tuple or (nonempty and not values):
        raise TypeError("practice text collections require an exact tuple")
    for value in values:
        if type(value) is not str or not value or len(value.encode("utf-8")) > 512:
            raise ValueError("practice text is invalid or exceeds its bound")
    if len(values) > 64:
        raise ValueError("practice text collection exceeds its bound")
    return values


@dataclass(frozen=True, slots=True)
class PracticeScopeStatement:
    challenge_key: ChallengeKey
    scope_id: str
    version: str
    population_relationship: PracticePopulationRelationship
    omissions: tuple[PracticeOmission, ...]
    limitations: tuple[str, ...]
    authority: PracticeAuthority = PracticeAuthority.MOCK_ONLY

    def __post_init__(self) -> None:
        if type(self) is not PracticeScopeStatement:
            raise TypeError("practice scope subclasses are rejected")
        object.__setattr__(self, "challenge_key", _key(self.challenge_key))
        validate_canonical_id(self.scope_id, "scope_id")
        validate_version_token(self.version, "version")
        if type(self.population_relationship) is not PracticePopulationRelationship:
            raise TypeError("population relationship must use its exact enum")
        if (
            type(self.omissions) is not tuple
            or not self.omissions
            or any(type(item) is not PracticeOmission for item in self.omissions)
            or len(set(self.omissions)) != len(self.omissions)
        ):
            raise ValueError("practice omissions require unique exact categories")
        object.__setattr__(
            self, "limitations", _strings(self.limitations, nonempty=True)
        )
        if self.authority is not PracticeAuthority.MOCK_ONLY:
            raise ValueError("B-07C scope authority is MOCK_ONLY")

    def to_ref(self) -> PracticeScopeStatementRef:
        payload = {
            "challenge": [self.challenge_key.challenge_id, self.challenge_key.version],
            "scope_id": self.scope_id,
            "version": self.version,
            "population_relationship": self.population_relationship.value,
            "omissions": [item.value for item in self.omissions],
            "limitations": list(self.limitations),
            "authority": self.authority.value,
        }
        return PracticeScopeStatementRef(
            self.challenge_key, content_digest=_digest(payload)
        )


@dataclass(frozen=True, slots=True)
class PracticeMeasurementPack:
    challenge_key: ChallengeKey
    pack_id: str
    version: str
    measurement_contract_ref: MeasurementContractRef
    measurement_implementation_ref: PrivateIdentityRef
    non_authoritative_configuration_ref: PrivateIdentityRef
    rights_authorization_ref: PrivateIdentityRef
    uncertainty_rule: PracticeUncertaintyRule
    disclosure_rule: PracticeDisclosureRule
    limitations: tuple[str, ...]
    authority: PracticeAuthority = PracticeAuthority.MOCK_ONLY

    def __post_init__(self) -> None:
        if type(self) is not PracticeMeasurementPack:
            raise TypeError("measurement pack subclasses are rejected")
        object.__setattr__(self, "challenge_key", _key(self.challenge_key))
        validate_canonical_id(self.pack_id, "pack_id")
        validate_version_token(self.version, "version")
        if (
            type(self.measurement_contract_ref) is not MeasurementContractRef
            or self.measurement_contract_ref.challenge_key != self.challenge_key
        ):
            raise ValueError("practice measurement identity has a Challenge mismatch")
        expected = (
            (self.measurement_implementation_ref, "measurement_implementation"),
            (
                self.non_authoritative_configuration_ref,
                "practice_measurement_configuration",
            ),
            (self.rights_authorization_ref, "practice_measurement_rights"),
        )
        if any(
            type(item) is not PrivateIdentityRef or item.ref_type != kind
            for item, kind in expected
        ):
            raise ValueError("practice measurement authority bindings are invalid")
        if type(self.uncertainty_rule) is not PracticeUncertaintyRule:
            raise TypeError("uncertainty rule must use its exact enum")
        if type(self.disclosure_rule) is not PracticeDisclosureRule:
            raise TypeError("disclosure rule must use its exact enum")
        object.__setattr__(
            self, "limitations", _strings(self.limitations, nonempty=True)
        )
        if self.authority is not PracticeAuthority.MOCK_ONLY:
            raise ValueError("practice measurement authority is MOCK_ONLY")

    def to_private_ref(self) -> PrivateIdentityRef:
        return PrivateIdentityRef(
            "practice_measurement_pack",
            _digest(
                {
                    "challenge": [
                        self.challenge_key.challenge_id,
                        self.challenge_key.version,
                    ],
                    "pack_id": self.pack_id,
                    "version": self.version,
                    "measurement": self.measurement_contract_ref.content_digest,
                    "implementation": self.measurement_implementation_ref.content_digest,
                    "configuration": self.non_authoritative_configuration_ref.content_digest,
                    "rights": self.rights_authorization_ref.content_digest,
                    "uncertainty": self.uncertainty_rule.value,
                    "disclosure": self.disclosure_rule.value,
                    "limitations": list(self.limitations),
                    "authority": self.authority.value,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class MockPracticePack:
    challenge_key: ChallengeKey
    pack_id: str
    version: str
    practice_scope_ref: PracticeScopeStatementRef
    measurement_pack: PracticeMeasurementPack
    compiler_environment_ref: CompilerEnvironmentRef
    generator_implementation_ref: PrivateIdentityRef
    reference_implementation_ref: PrivateIdentityRef
    reference_capability: MockReferenceCapability
    training_case_count: int
    evaluation_case_count: int
    fixture_behavior: MockFixtureBehavior
    limitations: tuple[str, ...]
    authority: PracticeAuthority = PracticeAuthority.MOCK_ONLY

    def __post_init__(self) -> None:
        if type(self) is not MockPracticePack:
            raise TypeError("mock pack subclasses are rejected")
        object.__setattr__(self, "challenge_key", _key(self.challenge_key))
        validate_canonical_id(self.pack_id, "pack_id")
        validate_version_token(self.version, "version")
        for ref in (self.practice_scope_ref, self.compiler_environment_ref):
            if ref.challenge_key != self.challenge_key:
                raise ValueError("mock pack reference has a Challenge mismatch")
        if (
            type(self.measurement_pack) is not PracticeMeasurementPack
            or self.measurement_pack.challenge_key != self.challenge_key
        ):
            raise ValueError("mock pack measurement binding is invalid")
        if (
            type(self.generator_implementation_ref) is not PrivateIdentityRef
            or self.generator_implementation_ref.ref_type != "mock_generator"
            or type(self.reference_implementation_ref) is not PrivateIdentityRef
            or self.reference_implementation_ref.ref_type != "mock_reference"
        ):
            raise ValueError("mock-only generator/reference bindings are required")
        if self.reference_capability is not MockReferenceCapability.SYNTHETIC_MOCK_ONLY:
            raise ValueError("official reference capability is forbidden")
        if (
            type(self.training_case_count) is not int
            or type(self.evaluation_case_count) is not int
            or not 1 <= self.training_case_count <= 4096
            or not 2 <= self.evaluation_case_count <= 4096
        ):
            raise ValueError("mock case counts are outside fixture bounds")
        if type(self.fixture_behavior) is not MockFixtureBehavior:
            raise TypeError("fixture behavior must use its exact enum")
        object.__setattr__(
            self, "limitations", _strings(self.limitations, nonempty=True)
        )
        if self.authority is not PracticeAuthority.MOCK_ONLY:
            raise ValueError("mock pack authority is MOCK_ONLY")

    def to_ref(self) -> PracticePackRef:
        payload = {
            "challenge": [self.challenge_key.challenge_id, self.challenge_key.version],
            "pack_id": self.pack_id,
            "version": self.version,
            "scope": self.practice_scope_ref.content_digest,
            "measurement_pack": self.measurement_pack.to_private_ref().content_digest,
            "compiler_environment": self.compiler_environment_ref.content_digest,
            "generator": self.generator_implementation_ref.content_digest,
            "reference": self.reference_implementation_ref.content_digest,
            "reference_capability": self.reference_capability.value,
            "training_case_count": self.training_case_count,
            "evaluation_case_count": self.evaluation_case_count,
            "fixture_behavior": self.fixture_behavior.value,
            "limitations": list(self.limitations),
            "authority": self.authority.value,
        }
        return PracticePackRef(self.challenge_key, content_digest=_digest(payload))


@dataclass(frozen=True, slots=True)
class PracticeAggregate:
    kind: PracticeAggregateKind
    mock_pack_ref: PracticePackRef
    measurement_pack_ref: PrivateIdentityRef
    resolved_plan_digests: tuple[str, ...]
    case_count: int
    aggregate_value: float | None
    observed_range: tuple[float, ...] | None
    common_cases: bool
    scientific_failure_category: ResearchFailureCategory | None
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self) is not PracticeAggregate:
            raise TypeError("practice aggregate subclasses are rejected")
        if type(self.kind) is not PracticeAggregateKind:
            raise TypeError("aggregate kind must use its exact enum")
        if type(self.mock_pack_ref) is not PracticePackRef:
            raise TypeError("aggregate requires an exact mock pack ref")
        if (
            type(self.measurement_pack_ref) is not PrivateIdentityRef
            or self.measurement_pack_ref.ref_type != "practice_measurement_pack"
        ):
            raise TypeError("aggregate requires an exact measurement pack identity")
        if (
            type(self.resolved_plan_digests) is not tuple
            or not self.resolved_plan_digests
        ):
            raise ValueError("aggregate requires resolved plan identities")
        if type(self.case_count) is not int or not 0 <= self.case_count <= 4096:
            raise ValueError("aggregate case count is outside its bound")
        if self.aggregate_value is not None and (
            type(self.aggregate_value) is not float
            or not math.isfinite(self.aggregate_value)
        ):
            raise ValueError("aggregate value must be finite or absent")
        if self.observed_range is not None and (
            type(self.observed_range) is not tuple
            or len(self.observed_range) != 2
            or any(
                type(item) is not float or not math.isfinite(item)
                for item in self.observed_range
            )
            or self.observed_range[0] > self.observed_range[1]
        ):
            raise ValueError("observed range must be finite and ordered")
        if type(self.common_cases) is not bool:
            raise TypeError("common_cases must be exact bool")
        if (
            self.scientific_failure_category is not None
            and type(self.scientific_failure_category) is not ResearchFailureCategory
        ):
            raise TypeError("scientific failure category must use its exact enum")
        if self.kind is PracticeAggregateKind.PAIRED_DIFFERENCE:
            if len(self.resolved_plan_digests) != 2 or not self.common_cases:
                raise ValueError("paired aggregate requires two plans and common cases")
        elif self.common_cases:
            raise ValueError("only a paired aggregate can claim common cases")
        if self.kind in (
            PracticeAggregateKind.RECONSTRUCTION,
            PracticeAggregateKind.RESOURCE_CALIBRATION,
        ) and (self.case_count != 0 or self.observed_range is not None):
            raise ValueError("non-measurement aggregates cannot claim measured cases")
        if self.kind is PracticeAggregateKind.RESOURCE_CALIBRATION and (
            self.aggregate_value is not None
            or self.scientific_failure_category is not None
        ):
            raise ValueError("resource calibration carries resource facts only")
        if self.scientific_failure_category is not None and (
            self.case_count != 0
            or self.aggregate_value is not None
            or self.observed_range is not None
        ):
            raise ValueError("scientific failure cannot carry measured evidence")
        object.__setattr__(
            self, "limitations", _strings(self.limitations, nonempty=True)
        )

    def to_private_ref(self) -> PrivateIdentityRef:
        return PrivateIdentityRef(
            "practice_aggregate",
            _digest(
                {
                    "kind": self.kind.value,
                    "mock_pack": self.mock_pack_ref.content_digest,
                    "measurement_pack": self.measurement_pack_ref.content_digest,
                    "plans": list(self.resolved_plan_digests),
                    "case_count": self.case_count,
                    "aggregate_value": self.aggregate_value,
                    "observed_range": self.observed_range,
                    "common_cases": self.common_cases,
                    "failure": (
                        None
                        if self.scientific_failure_category is None
                        else self.scientific_failure_category.value
                    ),
                    "limitations": list(self.limitations),
                }
            ),
        )


__all__ = (
    "MockFixtureBehavior",
    "MockPracticePack",
    "MockReferenceCapability",
    "PracticeAggregate",
    "PracticeAggregateKind",
    "PracticeAuthority",
    "PracticeDisclosureRule",
    "PracticeMeasurementPack",
    "PracticeOmission",
    "PracticePopulationRelationship",
    "PracticeScopeStatement",
    "PracticeUncertaintyRule",
)
