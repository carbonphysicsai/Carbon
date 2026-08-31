"""Exact immutable nested models for the B-02B construction contract.

This module owns the closed value vocabulary shared by assembly, catalog,
training-policy, and resolved-plan modules.  It deliberately contains no
runtime lookup, execution, scientific qualification, or resource policy.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias, TypeVar

from carbon.authoring.canonical import encode_value
from carbon.authoring.errors import AuthoringValidationError
from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_exact_bool,
    validate_finite_float64,
    validate_int64,
    validate_tagged_sha256,
    validate_uint64,
    validate_version_token,
)
from carbon.authoring.refs import (
    ChallengeScope,
    GlobalScope,
    TopLevelObjectRef,
    reconstruct_top_level_ref,
    require_owner_ref,
)
from carbon.construction.errors import ConstructionValidationError
from carbon.registry import ChallengeKey

_T = TypeVar("_T")


def _invalid(code: str, message: str, field: str) -> ConstructionValidationError:
    return ConstructionValidationError(code, message, path=f"/{field}")


def _exact_self(value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise _invalid(
            "construction.subclass_rejected",
            "construction values must use their exact nominal type",
            "type",
        )


def _id(value: object, field: str) -> str:
    try:
        return validate_canonical_id(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.identifier_invalid",
            f"{field} must be an exact canonical identifier",
            field,
        ) from exc


def _version(value: object, field: str) -> str:
    try:
        return validate_version_token(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.version_invalid",
            f"{field} must be an exact bounded version token",
            field,
        ) from exc


def _digest(value: object, field: str = "content_digest") -> str:
    try:
        return validate_tagged_sha256(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.digest_invalid",
            f"{field} must be canonical tagged SHA-256",
            field,
        ) from exc


def _bool(value: object, field: str) -> bool:
    try:
        return validate_exact_bool(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.bool_invalid", f"{field} must be exact Boolean", field
        ) from exc


def _int64(value: object, field: str) -> int:
    try:
        return validate_int64(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.int64_invalid", f"{field} must be exact Int64", field
        ) from exc


def _uint64(value: object, field: str) -> int:
    try:
        return validate_uint64(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.uint64_invalid", f"{field} must be exact UInt64", field
        ) from exc


def _float64(value: object, field: str) -> float:
    try:
        checked = validate_finite_float64(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.float64_invalid",
            f"{field} must be exact finite Float64",
            field,
        ) from exc
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        raise _invalid(
            "construction.negative_zero",
            f"{field} must not use negative-zero bits",
            field,
        )
    return checked


def _enum(value: object, expected: type[_T], field: str) -> _T:
    if type(value) is not expected:
        raise _invalid(
            "construction.enum_type_invalid",
            f"{field} must use its exact closed enum type",
            field,
        )
    return value


def _tuple(
    value: object,
    field: str,
    copier: Callable[[object], _T],
    *,
    nonempty: bool = False,
    unique: bool = False,
) -> tuple[_T, ...]:
    if type(value) is not tuple:
        raise _invalid(
            "construction.tuple_type_invalid",
            f"{field} must be an exact built-in tuple",
            field,
        )
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS or (nonempty and not value):
        raise _invalid(
            "construction.tuple_size_invalid", f"{field} has invalid size", field
        )
    copied = tuple(copier(item) for item in value)
    if unique and len(set(copied)) != len(copied):
        raise _invalid(
            "construction.tuple_duplicate",
            f"{field} contains duplicate semantic members",
            field,
        )
    return copied


def _canonical_sort(value: tuple[_T, ...], field: str) -> tuple[_T, ...]:
    from carbon.construction.canonical import to_canonical_value

    try:
        return tuple(
            sorted(value, key=lambda item: encode_value(to_canonical_value(item)))
        )
    except ConstructionValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise _invalid(
            "construction.canonical_sort_failed",
            f"{field} cannot be represented as a canonical set tuple",
            field,
        ) from exc


def _set_tuple(
    value: object,
    field: str,
    copier: Callable[[object], _T],
    *,
    nonempty: bool = False,
) -> tuple[_T, ...]:
    return _canonical_sort(
        _tuple(value, field, copier, nonempty=nonempty, unique=True), field
    )


def _ids(value: object, field: str, *, nonempty: bool = False) -> tuple[str, ...]:
    return _set_tuple(value, field, lambda item: _id(item, field), nonempty=nonempty)


def _id_sequence(
    value: object, field: str, *, nonempty: bool = False
) -> tuple[str, ...]:
    return _tuple(
        value,
        field,
        lambda item: _id(item, field),
        nonempty=nonempty,
        unique=True,
    )


def _owner(value: object, kind: str) -> object:
    try:
        return require_owner_ref(value, kind)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.owner_ref_invalid",
            f"owner ref must have exact nominal kind {kind}",
            f"{kind}_ref",
        ) from exc


def _owner_set(
    value: object, field: str, kind: str, *, nonempty: bool = False
) -> tuple[object, ...]:
    return _set_tuple(value, field, lambda item: _owner(item, kind), nonempty=nonempty)


def _top_ref(value: object) -> TopLevelObjectRef:
    try:
        return reconstruct_top_level_ref(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.authoring_ref_invalid",
            "value must be an exact B-02A top-level ref",
            "authoring_ref",
        ) from exc


def _copy(value: object, expected: type[_T], field: str) -> _T:
    if type(value) is not expected:
        raise _invalid(
            "construction.nominal_type_invalid",
            f"{field} must have exact nominal type {expected.__name__}",
            field,
        )
    from carbon.construction.canonical import from_canonical_value, to_canonical_value

    return from_canonical_value(to_canonical_value(value), expected)


def _copy_union(value: object, allowed: tuple[type[object], ...], field: str) -> object:
    if type(value) not in allowed:
        raise _invalid(
            "construction.union_type_invalid",
            f"{field} must use one exact closed union variant",
            field,
        )
    return _copy(value, type(value), field)


def _copy_challenge(value: object) -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.challenge_key_invalid",
            "challenge_key must be an exact valid A3 ChallengeKey",
            "challenge_key",
        ) from exc


def validate_owner_ref_scope(
    value: object,
    *,
    expected_challenge_key: object,
    portable: bool = False,
) -> object:
    """Validate a copied owner ref against a construction object's Challenge."""

    key = _copy_challenge(expected_challenge_key)
    scope = getattr(value, "scope_binding", None)
    if type(scope) is ChallengeScope:
        if scope.challenge_key != key:
            raise _invalid(
                "construction.owner_ref_challenge_mismatch",
                "owner ref crosses Challenge versions",
                "scope_binding",
            )
    elif not portable or type(scope) is not GlobalScope:
        raise _invalid(
            "construction.owner_ref_scope_invalid",
            "owner ref has a forbidden scope for this field",
            "scope_binding",
        )
    return value


class SurfaceValueType(str, Enum):
    BOOL = "BOOL"
    INT64 = "INT64"
    UINT64 = "UINT64"
    FLOAT64 = "FLOAT64"
    CANONICAL_CHOICE = "CANONICAL_CHOICE"
    BACKBONE_SELECTOR = "BACKBONE_SELECTOR"
    COMPONENT_SELECTOR = "COMPONENT_SELECTOR"


class InterfaceDirection(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class InputSource(str, Enum):
    TOP_LEVEL_BACKBONE = "TOP_LEVEL_BACKBONE"
    PARAMETER_KEY = "PARAMETER_KEY"


class ComponentRole(str, Enum):
    WARM_START = "WARM_START"
    PRECONDITIONER_ACTION = "PRECONDITIONER_ACTION"
    COARSE_CORRECTION = "COARSE_CORRECTION"
    RESIDUAL_CORRECTION = "RESIDUAL_CORRECTION"
    SUBDOMAIN_OPERATOR = "SUBDOMAIN_OPERATOR"
    NONLINEAR_INITIAL_GUESS = "NONLINEAR_INITIAL_GUESS"


class ComponentStatePolicy(str, Enum):
    STATELESS = "STATELESS"
    FIXED_STATE = "FIXED_STATE"
    TRAINABLE_STATE = "TRAINABLE_STATE"


StatePolicy = ComponentStatePolicy


class SideEffectPolicy(str, Enum):
    NONE = "NONE"


class TrainabilityBoundary(str, Enum):
    FIXED = "FIXED"
    TRAINABLE_REGISTERED_STATE = "TRAINABLE_REGISTERED_STATE"


class FallbackPolicy(str, Enum):
    FAIL_CLOSED = "FAIL_CLOSED"


class TrainingLeverKind(str, Enum):
    SAMPLING = "SAMPLING"
    CURRICULUM = "CURRICULUM"
    AUGMENTATION = "AUGMENTATION"


class PolicyState(str, Enum):
    BASE_NO_OVERRIDE = "BASE_NO_OVERRIDE"
    RESOLVED_OVERRIDES = "RESOLVED_OVERRIDES"


class GraphOrigin(str, Enum):
    FIXTURE_DERIVED = "FIXTURE_DERIVED"
    REGISTERED_GRAPH = "REGISTERED_GRAPH"


class UnknownOrInvalidPolicy(str, Enum):
    REJECT = "REJECT"


class AuthorityMarker(str, Enum):
    CONSTRUCTION_ONLY_NOT_QUALIFICATION = "CONSTRUCTION_ONLY_NOT_QUALIFICATION"


@dataclass(frozen=True, slots=True)
class CompilerIdentity:
    compiler_id: str
    compiler_version: str
    implementation_digest: str
    construction_schema_version: str
    canonicalization_profile: str

    def __post_init__(self) -> None:
        _exact_self(self, CompilerIdentity)
        object.__setattr__(self, "compiler_id", _id(self.compiler_id, "compiler_id"))
        object.__setattr__(
            self,
            "compiler_version",
            _version(self.compiler_version, "compiler_version"),
        )
        object.__setattr__(
            self,
            "implementation_digest",
            _digest(self.implementation_digest, "implementation_digest"),
        )
        if (
            _version(self.construction_schema_version, "construction_schema_version")
            != "1.0"
        ):
            raise _invalid(
                "construction.schema_version_unsupported",
                "compiler supports only construction schema version 1.0",
                "construction_schema_version",
            )
        if (
            type(self.canonicalization_profile) is not str
            or self.canonicalization_profile != "carbon_construction_canonical_v1"
        ):
            raise _invalid(
                "construction.canonicalization_profile_invalid",
                "compiler identity uses an unknown canonicalization profile",
                "canonicalization_profile",
            )


@dataclass(frozen=True, slots=True)
class ImplementationPin:
    implementation_id: str
    implementation_version: str
    content_digest: str

    def __post_init__(self) -> None:
        _exact_self(self, ImplementationPin)
        object.__setattr__(
            self, "implementation_id", _id(self.implementation_id, "implementation_id")
        )
        object.__setattr__(
            self,
            "implementation_version",
            _version(self.implementation_version, "implementation_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))


@dataclass(frozen=True, slots=True)
class EnvironmentPin:
    environment_id: str
    environment_version: str
    content_digest: str

    def __post_init__(self) -> None:
        _exact_self(self, EnvironmentPin)
        object.__setattr__(
            self, "environment_id", _id(self.environment_id, "environment_id")
        )
        object.__setattr__(
            self,
            "environment_version",
            _version(self.environment_version, "environment_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))


@dataclass(frozen=True, slots=True)
class DependencyPin:
    dependency_id: str
    dependency_version: str
    content_digest: str

    def __post_init__(self) -> None:
        _exact_self(self, DependencyPin)
        object.__setattr__(
            self, "dependency_id", _id(self.dependency_id, "dependency_id")
        )
        object.__setattr__(
            self,
            "dependency_version",
            _version(self.dependency_version, "dependency_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))


@dataclass(frozen=True, slots=True)
class InterfacePin:
    interface_id: str
    interface_version: str
    content_digest: str
    direction: InterfaceDirection

    def __post_init__(self) -> None:
        _exact_self(self, InterfacePin)
        object.__setattr__(self, "interface_id", _id(self.interface_id, "interface_id"))
        object.__setattr__(
            self,
            "interface_version",
            _version(self.interface_version, "interface_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        _enum(self.direction, InterfaceDirection, "direction")


@dataclass(frozen=True, slots=True)
class ConsumerTarget:
    consumer_id: str
    field_id: str

    def __post_init__(self) -> None:
        _exact_self(self, ConsumerTarget)
        object.__setattr__(self, "consumer_id", _id(self.consumer_id, "consumer_id"))
        object.__setattr__(self, "field_id", _id(self.field_id, "field_id"))


@dataclass(frozen=True, slots=True)
class SurfaceValue:
    value_type: SurfaceValueType
    value: bool | int | float | str

    def __post_init__(self) -> None:
        _exact_self(self, SurfaceValue)
        value_type = _enum(self.value_type, SurfaceValueType, "value_type")
        if value_type is SurfaceValueType.BOOL:
            value: bool | int | float | str = _bool(self.value, "value")
        elif value_type is SurfaceValueType.INT64:
            value = _int64(self.value, "value")
        elif value_type is SurfaceValueType.UINT64:
            value = _uint64(self.value, "value")
        elif value_type is SurfaceValueType.FLOAT64:
            value = _float64(self.value, "value")
        else:
            value = _id(self.value, "value")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class UnitNotApplicable:
    reason_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, UnitNotApplicable)
        object.__setattr__(
            self, "reason_ref", _owner(self.reason_ref, "applicability_reason")
        )


@dataclass(frozen=True, slots=True)
class BoundUnit:
    unit_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, BoundUnit)
        object.__setattr__(self, "unit_ref", _owner(self.unit_ref, "unit"))


UnitBinding: TypeAlias = UnitNotApplicable | BoundUnit


@dataclass(frozen=True, slots=True)
class BooleanDomain:
    allowed_values: tuple[bool, ...]

    def __post_init__(self) -> None:
        _exact_self(self, BooleanDomain)
        object.__setattr__(
            self,
            "allowed_values",
            _set_tuple(
                self.allowed_values,
                "allowed_values",
                lambda item: _bool(item, "allowed_values"),
                nonempty=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class Int64RangeDomain:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        _exact_self(self, Int64RangeDomain)
        minimum = _int64(self.minimum, "minimum")
        maximum = _int64(self.maximum, "maximum")
        if minimum > maximum:
            raise _invalid(
                "construction.range_invalid", "minimum exceeds maximum", "minimum"
            )
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)


@dataclass(frozen=True, slots=True)
class UInt64RangeDomain:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        _exact_self(self, UInt64RangeDomain)
        minimum = _uint64(self.minimum, "minimum")
        maximum = _uint64(self.maximum, "maximum")
        if minimum > maximum:
            raise _invalid(
                "construction.range_invalid", "minimum exceeds maximum", "minimum"
            )
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)


@dataclass(frozen=True, slots=True)
class Float64RangeDomain:
    minimum: float
    maximum: float
    lower_inclusive: bool
    upper_inclusive: bool

    def __post_init__(self) -> None:
        _exact_self(self, Float64RangeDomain)
        minimum = _float64(self.minimum, "minimum")
        maximum = _float64(self.maximum, "maximum")
        if minimum > maximum:
            raise _invalid(
                "construction.range_invalid", "minimum exceeds maximum", "minimum"
            )
        lower = _bool(self.lower_inclusive, "lower_inclusive")
        upper = _bool(self.upper_inclusive, "upper_inclusive")
        if minimum == maximum and (not lower or not upper):
            raise _invalid(
                "construction.range_empty", "Float64 range must not be empty", "minimum"
            )
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)
        object.__setattr__(self, "lower_inclusive", lower)
        object.__setattr__(self, "upper_inclusive", upper)


@dataclass(frozen=True, slots=True)
class ChoiceDomain:
    allowed_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _exact_self(self, ChoiceDomain)
        object.__setattr__(
            self,
            "allowed_ids",
            _ids(self.allowed_ids, "allowed_ids", nonempty=True),
        )


SurfaceDomain: TypeAlias = (
    BooleanDomain
    | Int64RangeDomain
    | UInt64RangeDomain
    | Float64RangeDomain
    | ChoiceDomain
)


@dataclass(frozen=True, slots=True)
class RequiredSurface:
    def __post_init__(self) -> None:
        _exact_self(self, RequiredSurface)


@dataclass(frozen=True, slots=True)
class ExplicitDefaultSurface:
    default_value: SurfaceValue

    def __post_init__(self) -> None:
        _exact_self(self, ExplicitDefaultSurface)
        object.__setattr__(
            self,
            "default_value",
            _copy(self.default_value, SurfaceValue, "default_value"),
        )


SurfaceRequirement: TypeAlias = RequiredSurface | ExplicitDefaultSurface


@dataclass(frozen=True, slots=True)
class AssemblySemanticOwner:
    local_target_id: str
    authority_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, AssemblySemanticOwner)
        object.__setattr__(
            self, "local_target_id", _id(self.local_target_id, "local_target_id")
        )
        object.__setattr__(
            self,
            "authority_ref",
            _owner(self.authority_ref, "scientific_authority"),
        )


@dataclass(frozen=True, slots=True)
class TrainingSupportSemanticOwner:
    semantic_clause_ref: object
    authority_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, TrainingSupportSemanticOwner)
        object.__setattr__(
            self,
            "semantic_clause_ref",
            _owner(self.semantic_clause_ref, "semantic_clause"),
        )
        object.__setattr__(
            self, "authority_ref", _owner(self.authority_ref, "policy_authority")
        )


SemanticOwnerBinding: TypeAlias = AssemblySemanticOwner | TrainingSupportSemanticOwner


@dataclass(frozen=True, slots=True)
class ActiveLifecycle:
    def __post_init__(self) -> None:
        _exact_self(self, ActiveLifecycle)


@dataclass(frozen=True, slots=True)
class RetiredLifecycle:
    reason_ref: object
    supersession_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, RetiredLifecycle)
        object.__setattr__(
            self, "reason_ref", _owner(self.reason_ref, "applicability_reason")
        )
        object.__setattr__(
            self,
            "supersession_ref",
            _owner(self.supersession_ref, "semantic_equivalence"),
        )


CatalogEntryLifecycle: TypeAlias = ActiveLifecycle | RetiredLifecycle


@dataclass(frozen=True, slots=True)
class AlwaysApplicable:
    applicability_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, AlwaysApplicable)
        object.__setattr__(
            self, "applicability_ref", _owner(self.applicability_ref, "applicability")
        )


@dataclass(frozen=True, slots=True)
class WhenSurfaceIn:
    applicability_ref: object
    selector_surface_id: str
    allowed_values: tuple[SurfaceValue, ...]
    not_applicable_reason_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, WhenSurfaceIn)
        object.__setattr__(
            self, "applicability_ref", _owner(self.applicability_ref, "applicability")
        )
        object.__setattr__(
            self,
            "selector_surface_id",
            _id(self.selector_surface_id, "selector_surface_id"),
        )
        object.__setattr__(
            self,
            "allowed_values",
            _set_tuple(
                self.allowed_values,
                "allowed_values",
                lambda item: _copy(item, SurfaceValue, "allowed_values"),
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "not_applicable_reason_ref",
            _owner(self.not_applicable_reason_ref, "applicability_reason"),
        )


ApplicabilityRule: TypeAlias = AlwaysApplicable | WhenSurfaceIn


@dataclass(frozen=True, slots=True)
class ValueCompatibilityCell:
    value: SurfaceValue

    def __post_init__(self) -> None:
        _exact_self(self, ValueCompatibilityCell)
        object.__setattr__(self, "value", _copy(self.value, SurfaceValue, "value"))


@dataclass(frozen=True, slots=True)
class NotApplicableCompatibilityCell:
    def __post_init__(self) -> None:
        _exact_self(self, NotApplicableCompatibilityCell)


CompatibilityCell: TypeAlias = ValueCompatibilityCell | NotApplicableCompatibilityCell


@dataclass(frozen=True, slots=True)
class CompatibilityRule:
    rule_id: str
    surface_ids: tuple[str, ...]
    allowed_rows: tuple[tuple[CompatibilityCell, ...], ...]
    semantic_clause_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, CompatibilityRule)
        rule_id = _id(self.rule_id, "rule_id")
        surface_ids = _id_sequence(self.surface_ids, "surface_ids", nonempty=True)

        def copy_row(value: object) -> tuple[CompatibilityCell, ...]:
            row = _tuple(
                value,
                "allowed_row",
                lambda item: _copy_union(
                    item,
                    (ValueCompatibilityCell, NotApplicableCompatibilityCell),
                    "compatibility_cell",
                ),
            )
            if len(row) != len(surface_ids):
                raise _invalid(
                    "construction.compatibility_arity_invalid",
                    "compatibility row arity must equal surface_ids arity",
                    "allowed_rows",
                )
            return row

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "surface_ids", surface_ids)
        object.__setattr__(
            self,
            "allowed_rows",
            _set_tuple(self.allowed_rows, "allowed_rows", copy_row, nonempty=True),
        )
        object.__setattr__(
            self,
            "semantic_clause_ref",
            _owner(self.semantic_clause_ref, "semantic_clause"),
        )


@dataclass(frozen=True, slots=True)
class TrainingRandomnessPurpose:
    purpose_id: str
    role_key_label: str

    def __post_init__(self) -> None:
        _exact_self(self, TrainingRandomnessPurpose)
        object.__setattr__(self, "purpose_id", _id(self.purpose_id, "purpose_id"))
        object.__setattr__(
            self, "role_key_label", _id(self.role_key_label, "role_key_label")
        )


@dataclass(frozen=True, slots=True)
class TrainingLeverNotApplicable:
    reason_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, TrainingLeverNotApplicable)
        object.__setattr__(
            self, "reason_ref", _owner(self.reason_ref, "applicability_reason")
        )


@dataclass(frozen=True, slots=True)
class BoundTrainingLever:
    kind: TrainingLeverKind
    executable_semantics_ref: object
    randomness_purposes: tuple[TrainingRandomnessPurpose, ...]

    def __post_init__(self) -> None:
        _exact_self(self, BoundTrainingLever)
        _enum(self.kind, TrainingLeverKind, "kind")
        object.__setattr__(
            self,
            "executable_semantics_ref",
            _owner(self.executable_semantics_ref, "semantic_clause"),
        )
        object.__setattr__(
            self,
            "randomness_purposes",
            _set_tuple(
                self.randomness_purposes,
                "randomness_purposes",
                lambda item: _copy(
                    item, TrainingRandomnessPurpose, "randomness_purposes"
                ),
            ),
        )


TrainingLeverBinding: TypeAlias = TrainingLeverNotApplicable | BoundTrainingLever


@dataclass(frozen=True, slots=True)
class ComponentSelectionNotApplicable:
    reason_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, ComponentSelectionNotApplicable)
        object.__setattr__(
            self, "reason_ref", _owner(self.reason_ref, "applicability_reason")
        )


@dataclass(frozen=True, slots=True)
class BoundComponentSelection:
    slot_id: str
    role: ComponentRole

    def __post_init__(self) -> None:
        _exact_self(self, BoundComponentSelection)
        object.__setattr__(self, "slot_id", _id(self.slot_id, "slot_id"))
        _enum(self.role, ComponentRole, "role")


ComponentSelectionBinding: TypeAlias = (
    ComponentSelectionNotApplicable | BoundComponentSelection
)


@dataclass(frozen=True, slots=True)
class StaticResourceDimension:
    dimension_id: str
    unit_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, StaticResourceDimension)
        object.__setattr__(self, "dimension_id", _id(self.dimension_id, "dimension_id"))
        object.__setattr__(self, "unit_ref", _owner(self.unit_ref, "unit"))


@dataclass(frozen=True, slots=True)
class ResourceLookupCase:
    selector_value: SurfaceValue
    quantity: int

    def __post_init__(self) -> None:
        _exact_self(self, ResourceLookupCase)
        object.__setattr__(
            self,
            "selector_value",
            _copy(self.selector_value, SurfaceValue, "selector_value"),
        )
        object.__setattr__(self, "quantity", _uint64(self.quantity, "quantity"))


@dataclass(frozen=True, slots=True)
class FixedResourceContribution:
    dimension_id: str
    unit_ref: object
    quantity: int
    impact_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        _exact_self(self, FixedResourceContribution)
        object.__setattr__(self, "dimension_id", _id(self.dimension_id, "dimension_id"))
        object.__setattr__(self, "unit_ref", _owner(self.unit_ref, "unit"))
        object.__setattr__(self, "quantity", _uint64(self.quantity, "quantity"))
        object.__setattr__(self, "impact_tags", _ids(self.impact_tags, "impact_tags"))


@dataclass(frozen=True, slots=True)
class DiscreteLookupResourceContribution:
    dimension_id: str
    unit_ref: object
    selector_surface_id: str
    cases: tuple[ResourceLookupCase, ...]
    impact_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        _exact_self(self, DiscreteLookupResourceContribution)
        object.__setattr__(self, "dimension_id", _id(self.dimension_id, "dimension_id"))
        object.__setattr__(self, "unit_ref", _owner(self.unit_ref, "unit"))
        object.__setattr__(
            self,
            "selector_surface_id",
            _id(self.selector_surface_id, "selector_surface_id"),
        )
        cases = _set_tuple(
            self.cases,
            "cases",
            lambda item: _copy(item, ResourceLookupCase, "cases"),
            nonempty=True,
        )
        if len({case.selector_value for case in cases}) != len(cases):
            raise _invalid(
                "construction.resource_lookup_duplicate",
                "resource lookup cases have duplicate selector values",
                "cases",
            )
        object.__setattr__(self, "cases", cases)
        object.__setattr__(self, "impact_tags", _ids(self.impact_tags, "impact_tags"))


StaticResourceContribution: TypeAlias = (
    FixedResourceContribution | DiscreteLookupResourceContribution
)


@dataclass(frozen=True, slots=True)
class StaticResourceRequirement:
    dimension_id: str
    unit_ref: object
    quantity: int
    contributing_source_ids: tuple[str, ...]
    impact_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        _exact_self(self, StaticResourceRequirement)
        object.__setattr__(self, "dimension_id", _id(self.dimension_id, "dimension_id"))
        object.__setattr__(self, "unit_ref", _owner(self.unit_ref, "unit"))
        object.__setattr__(self, "quantity", _uint64(self.quantity, "quantity"))
        object.__setattr__(
            self,
            "contributing_source_ids",
            _ids(
                self.contributing_source_ids,
                "contributing_source_ids",
                nonempty=True,
            ),
        )
        object.__setattr__(self, "impact_tags", _ids(self.impact_tags, "impact_tags"))


@dataclass(frozen=True, slots=True)
class FixtureProvenance:
    fixture_registration_ref: object
    source_provenance_refs: tuple[object, ...]
    origin_evidence_refs: tuple[object, ...]

    def __post_init__(self) -> None:
        _exact_self(self, FixtureProvenance)
        object.__setattr__(
            self,
            "fixture_registration_ref",
            _owner(self.fixture_registration_ref, "fixture_registration"),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_set(
                self.source_provenance_refs,
                "source_provenance_refs",
                "provenance",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "origin_evidence_refs",
            _owner_set(
                self.origin_evidence_refs,
                "origin_evidence_refs",
                "authoring_origin_evidence",
                nonempty=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class RegisteredProvenance:
    authoring_registration_ref: object
    source_provenance_refs: tuple[object, ...]
    origin_evidence_refs: tuple[object, ...]

    def __post_init__(self) -> None:
        _exact_self(self, RegisteredProvenance)
        object.__setattr__(
            self,
            "authoring_registration_ref",
            _owner(self.authoring_registration_ref, "authoring_registration"),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_set(
                self.source_provenance_refs,
                "source_provenance_refs",
                "provenance",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "origin_evidence_refs",
            _owner_set(
                self.origin_evidence_refs,
                "origin_evidence_refs",
                "authoring_origin_evidence",
                nonempty=True,
            ),
        )


ConstructionProvenance: TypeAlias = FixtureProvenance | RegisteredProvenance


_AUTHORING_BINDING_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class AuthoringOriginBinding:
    graph_origin: GraphOrigin
    graph_fingerprint: str
    root_ref: TopLevelObjectRef
    dependency_refs: tuple[TopLevelObjectRef, ...]
    origin_evidence_refs: tuple[object, ...]
    composition_audit_ref: object

    def __init__(
        self,
        *,
        graph_origin: GraphOrigin,
        graph_fingerprint: str,
        root_ref: TopLevelObjectRef,
        dependency_refs: tuple[TopLevelObjectRef, ...],
        origin_evidence_refs: tuple[object, ...],
        composition_audit_ref: object,
        _token: object = None,
    ) -> None:
        if _token is not _AUTHORING_BINDING_TOKEN:
            raise _invalid(
                "construction.authoring_origin_capability_required",
                "authoring binding requires a capability or verified decoder",
                "authoring_origin_binding",
            )
        exact_origin = _enum(graph_origin, GraphOrigin, "graph_origin")
        exact_fingerprint = _digest(graph_fingerprint, "graph_fingerprint")
        root = _top_ref(root_ref)
        dependencies = _set_tuple(
            dependency_refs,
            "dependency_refs",
            _top_ref,
        )
        if root in dependencies:
            raise _invalid(
                "construction.authoring_origin_duplicate_root",
                "root_ref must not be repeated in dependency_refs",
                "dependency_refs",
            )
        evidence = _owner_set(
            origin_evidence_refs,
            "origin_evidence_refs",
            "authoring_origin_evidence",
            nonempty=True,
        )
        audit = _owner(composition_audit_ref, "origin_composition_audit")
        object.__setattr__(self, "graph_origin", exact_origin)
        object.__setattr__(self, "graph_fingerprint", exact_fingerprint)
        object.__setattr__(self, "root_ref", root)
        object.__setattr__(self, "dependency_refs", dependencies)
        object.__setattr__(
            self,
            "origin_evidence_refs",
            evidence,
        )
        object.__setattr__(
            self,
            "composition_audit_ref",
            audit,
        )

    @classmethod
    def from_capability(
        cls,
        origin: object,
    ) -> AuthoringOriginBinding:
        """Derive the inert binding only from exact capability-issued origin data."""

        from carbon.authoring.loading import AuthoringGraphOrigin, GraphOriginTag

        if type(origin) is not AuthoringGraphOrigin:
            raise _invalid(
                "construction.authoring_origin_capability_invalid",
                "origin must be an exact capability-issued AuthoringGraphOrigin",
                "origin",
            )
        raw_origin = object.__getattribute__(origin, "graph_origin")
        if raw_origin is GraphOriginTag.DRAFT_OR_UNRESOLVED:
            raise _invalid(
                "construction.authoring_origin_unresolved",
                "draft or unresolved authoring origin cannot enter a plan",
                "graph_origin",
            )
        from carbon.authoring.graph import scientific_authoring_graph_fingerprint

        try:
            graph_fingerprint = scientific_authoring_graph_fingerprint(origin)
        except (TypeError, ValueError) as exc:
            raise _invalid(
                "construction.authoring_origin_fingerprint_invalid",
                "authoring graph fingerprint could not be derived exactly",
                "graph_fingerprint",
            ) from exc
        graph_origin = GraphOrigin(raw_origin.value)
        return cls(
            graph_origin=graph_origin,
            graph_fingerprint=graph_fingerprint,
            root_ref=object.__getattribute__(origin, "root_ref"),
            dependency_refs=object.__getattribute__(origin, "dependency_refs"),
            origin_evidence_refs=object.__getattribute__(
                origin, "origin_evidence_refs"
            ),
            composition_audit_ref=object.__getattribute__(
                origin, "composition_audit_ref"
            ),
            _token=_AUTHORING_BINDING_TOKEN,
        )

    @classmethod
    def _from_canonical(
        cls,
        *,
        graph_origin: GraphOrigin,
        graph_fingerprint: str,
        root_ref: TopLevelObjectRef,
        dependency_refs: tuple[TopLevelObjectRef, ...],
        origin_evidence_refs: tuple[object, ...],
        composition_audit_ref: object,
    ) -> AuthoringOriginBinding:
        """Reconstruct a digest-verified binding for the closed codec only."""

        return cls(
            graph_origin=graph_origin,
            graph_fingerprint=graph_fingerprint,
            root_ref=root_ref,
            dependency_refs=dependency_refs,
            origin_evidence_refs=origin_evidence_refs,
            composition_audit_ref=composition_audit_ref,
            _token=_AUTHORING_BINDING_TOKEN,
        )


def _dependency_pins(
    value: object, field: str = "dependency_pins"
) -> tuple[DependencyPin, ...]:
    return _set_tuple(
        value,
        field,
        lambda item: _copy(item, DependencyPin, field),
    )


def _resource_contributions(
    value: object, field: str = "static_resource_contributions"
) -> tuple[StaticResourceContribution, ...]:
    return _set_tuple(
        value,
        field,
        lambda item: _copy_union(
            item,
            (FixedResourceContribution, DiscreteLookupResourceContribution),
            field,
        ),
    )


@dataclass(frozen=True, slots=True)
class BackboneOption:
    selector_token: str
    backbone_id: str
    backbone_version: str
    content_digest: str
    implementation_pin: ImplementationPin
    environment_pin: EnvironmentPin
    dependency_pins: tuple[DependencyPin, ...]
    input_interface_pin: InterfacePin
    output_interface_pin: InterfacePin
    applicability_ref: object
    assumption_refs: tuple[object, ...]
    limitation_refs: tuple[object, ...]
    static_resource_contributions: tuple[StaticResourceContribution, ...]
    resource_impact_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        _exact_self(self, BackboneOption)
        object.__setattr__(
            self, "selector_token", _id(self.selector_token, "selector_token")
        )
        object.__setattr__(self, "backbone_id", _id(self.backbone_id, "backbone_id"))
        object.__setattr__(
            self,
            "backbone_version",
            _version(self.backbone_version, "backbone_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(
            self,
            "implementation_pin",
            _copy(self.implementation_pin, ImplementationPin, "implementation_pin"),
        )
        object.__setattr__(
            self,
            "environment_pin",
            _copy(self.environment_pin, EnvironmentPin, "environment_pin"),
        )
        object.__setattr__(
            self, "dependency_pins", _dependency_pins(self.dependency_pins)
        )
        input_pin = _copy(self.input_interface_pin, InterfacePin, "input_interface_pin")
        output_pin = _copy(
            self.output_interface_pin, InterfacePin, "output_interface_pin"
        )
        if input_pin.direction is not InterfaceDirection.INPUT:
            raise _invalid(
                "construction.interface_direction_invalid",
                "input_interface_pin must have INPUT direction",
                "input_interface_pin",
            )
        if output_pin.direction is not InterfaceDirection.OUTPUT:
            raise _invalid(
                "construction.interface_direction_invalid",
                "output_interface_pin must have OUTPUT direction",
                "output_interface_pin",
            )
        object.__setattr__(self, "input_interface_pin", input_pin)
        object.__setattr__(self, "output_interface_pin", output_pin)
        object.__setattr__(
            self, "applicability_ref", _owner(self.applicability_ref, "applicability")
        )
        object.__setattr__(
            self,
            "assumption_refs",
            _owner_set(self.assumption_refs, "assumption_refs", "semantic_clause"),
        )
        object.__setattr__(
            self,
            "limitation_refs",
            _owner_set(self.limitation_refs, "limitation_refs", "restriction"),
        )
        object.__setattr__(
            self,
            "static_resource_contributions",
            _resource_contributions(self.static_resource_contributions),
        )
        object.__setattr__(
            self,
            "resource_impact_tags",
            _ids(self.resource_impact_tags, "resource_impact_tags"),
        )


@dataclass(frozen=True, slots=True)
class BackboneSurfaceContract:
    surface_id: str
    consumer_target: ConsumerTarget
    options: tuple[BackboneOption, ...]

    def __post_init__(self) -> None:
        _exact_self(self, BackboneSurfaceContract)
        surface_id = _id(self.surface_id, "surface_id")
        if surface_id != "strategy_backbone":
            raise _invalid(
                "construction.backbone_surface_invalid",
                "backbone surface id must be strategy_backbone",
                "surface_id",
            )
        options = _set_tuple(
            self.options,
            "options",
            lambda item: _copy(item, BackboneOption, "options"),
            nonempty=True,
        )
        if len({option.selector_token for option in options}) != len(options):
            raise _invalid(
                "construction.selector_duplicate",
                "backbone selector tokens must be unique",
                "options",
            )
        object.__setattr__(self, "surface_id", surface_id)
        object.__setattr__(
            self,
            "consumer_target",
            _copy(self.consumer_target, ConsumerTarget, "consumer_target"),
        )
        object.__setattr__(self, "options", options)


@dataclass(frozen=True, slots=True)
class RegisteredComponentOption:
    selector_token: str
    component_id: str
    component_version: str
    content_digest: str
    role: ComponentRole
    consumer_target: ConsumerTarget
    input_interface_pin: InterfacePin
    output_interface_pin: InterfacePin
    state_policy: ComponentStatePolicy
    side_effect_policy: SideEffectPolicy
    trainability_boundary: TrainabilityBoundary
    implementation_pin: ImplementationPin
    environment_pin: EnvironmentPin
    dependency_pins: tuple[DependencyPin, ...]
    applicability_ref: object
    assumption_refs: tuple[object, ...]
    limitation_refs: tuple[object, ...]
    static_resource_contributions: tuple[StaticResourceContribution, ...]
    resource_impact_tags: tuple[str, ...]
    public_falsification_refs: tuple[object, ...]

    def __post_init__(self) -> None:
        _exact_self(self, RegisteredComponentOption)
        object.__setattr__(
            self, "selector_token", _id(self.selector_token, "selector_token")
        )
        object.__setattr__(self, "component_id", _id(self.component_id, "component_id"))
        object.__setattr__(
            self,
            "component_version",
            _version(self.component_version, "component_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        _enum(self.role, ComponentRole, "role")
        object.__setattr__(
            self,
            "consumer_target",
            _copy(self.consumer_target, ConsumerTarget, "consumer_target"),
        )
        input_pin = _copy(self.input_interface_pin, InterfacePin, "input_interface_pin")
        output_pin = _copy(
            self.output_interface_pin, InterfacePin, "output_interface_pin"
        )
        if input_pin.direction is not InterfaceDirection.INPUT:
            raise _invalid(
                "construction.interface_direction_invalid",
                "input_interface_pin must have INPUT direction",
                "input_interface_pin",
            )
        if output_pin.direction is not InterfaceDirection.OUTPUT:
            raise _invalid(
                "construction.interface_direction_invalid",
                "output_interface_pin must have OUTPUT direction",
                "output_interface_pin",
            )
        object.__setattr__(self, "input_interface_pin", input_pin)
        object.__setattr__(self, "output_interface_pin", output_pin)
        _enum(self.state_policy, ComponentStatePolicy, "state_policy")
        _enum(self.side_effect_policy, SideEffectPolicy, "side_effect_policy")
        _enum(self.trainability_boundary, TrainabilityBoundary, "trainability_boundary")
        object.__setattr__(
            self,
            "implementation_pin",
            _copy(self.implementation_pin, ImplementationPin, "implementation_pin"),
        )
        object.__setattr__(
            self,
            "environment_pin",
            _copy(self.environment_pin, EnvironmentPin, "environment_pin"),
        )
        object.__setattr__(
            self, "dependency_pins", _dependency_pins(self.dependency_pins)
        )
        object.__setattr__(
            self, "applicability_ref", _owner(self.applicability_ref, "applicability")
        )
        object.__setattr__(
            self,
            "assumption_refs",
            _owner_set(self.assumption_refs, "assumption_refs", "semantic_clause"),
        )
        object.__setattr__(
            self,
            "limitation_refs",
            _owner_set(self.limitation_refs, "limitation_refs", "restriction"),
        )
        object.__setattr__(
            self,
            "static_resource_contributions",
            _resource_contributions(self.static_resource_contributions),
        )
        object.__setattr__(
            self,
            "resource_impact_tags",
            _ids(self.resource_impact_tags, "resource_impact_tags"),
        )
        object.__setattr__(
            self,
            "public_falsification_refs",
            _owner_set(
                self.public_falsification_refs,
                "public_falsification_refs",
                "audit_evidence",
            ),
        )


@dataclass(frozen=True, slots=True)
class ComponentSlotContract:
    slot_id: str
    selector_surface_id: str
    role: ComponentRole
    consumer_target: ConsumerTarget
    input_interface_pin: InterfacePin
    output_interface_pin: InterfacePin
    state_policy: ComponentStatePolicy
    side_effect_policy: SideEffectPolicy
    trainability_boundary: TrainabilityBoundary
    applicability_ref: object
    options: tuple[RegisteredComponentOption, ...]
    fallback_policy: FallbackPolicy

    def __post_init__(self) -> None:
        _exact_self(self, ComponentSlotContract)
        object.__setattr__(self, "slot_id", _id(self.slot_id, "slot_id"))
        object.__setattr__(
            self,
            "selector_surface_id",
            _id(self.selector_surface_id, "selector_surface_id"),
        )
        role = _enum(self.role, ComponentRole, "role")
        consumer = _copy(self.consumer_target, ConsumerTarget, "consumer_target")
        input_pin = _copy(self.input_interface_pin, InterfacePin, "input_interface_pin")
        output_pin = _copy(
            self.output_interface_pin, InterfacePin, "output_interface_pin"
        )
        state = _enum(self.state_policy, ComponentStatePolicy, "state_policy")
        side_effects = _enum(
            self.side_effect_policy, SideEffectPolicy, "side_effect_policy"
        )
        trainability = _enum(
            self.trainability_boundary,
            TrainabilityBoundary,
            "trainability_boundary",
        )
        if (
            input_pin.direction is not InterfaceDirection.INPUT
            or output_pin.direction is not InterfaceDirection.OUTPUT
        ):
            raise _invalid(
                "construction.interface_direction_invalid",
                "slot interface pins have wrong directions",
                "interface_pin",
            )
        options = _set_tuple(
            self.options,
            "options",
            lambda item: _copy(item, RegisteredComponentOption, "options"),
            nonempty=True,
        )
        if len({option.selector_token for option in options}) != len(options):
            raise _invalid(
                "construction.selector_duplicate",
                "component selector tokens must be unique within a slot",
                "options",
            )
        for option in options:
            if (
                option.role is not role
                or option.consumer_target != consumer
                or option.input_interface_pin != input_pin
                or option.output_interface_pin != output_pin
                or option.state_policy is not state
                or option.side_effect_policy is not side_effects
                or option.trainability_boundary is not trainability
            ):
                raise _invalid(
                    "construction.component_slot_mismatch",
                    "component option semantics differ from the owning slot",
                    "options",
                )
        object.__setattr__(self, "consumer_target", consumer)
        object.__setattr__(self, "input_interface_pin", input_pin)
        object.__setattr__(self, "output_interface_pin", output_pin)
        object.__setattr__(
            self, "applicability_ref", _owner(self.applicability_ref, "applicability")
        )
        object.__setattr__(self, "options", options)
        _enum(self.fallback_policy, FallbackPolicy, "fallback_policy")


@dataclass(frozen=True, slots=True)
class ParameterCatalogEntry:
    surface_id: str
    input_source: InputSource
    consumer_target: ConsumerTarget
    value_type: SurfaceValueType
    unit_binding: UnitBinding
    domain: SurfaceDomain
    dependency_surface_ids: tuple[str, ...]
    applicability: ApplicabilityRule
    requirement: SurfaceRequirement
    compatibility_rule_ids: tuple[str, ...]
    static_resource_contributions: tuple[StaticResourceContribution, ...]
    resource_impact_tags: tuple[str, ...]
    public_outcome_family_tags: tuple[str, ...]
    semantic_owner_binding: SemanticOwnerBinding
    lifecycle: CatalogEntryLifecycle
    training_lever_binding: TrainingLeverBinding
    component_slot_binding: ComponentSelectionBinding

    def __post_init__(self) -> None:
        _exact_self(self, ParameterCatalogEntry)
        surface_id = _id(self.surface_id, "surface_id")
        _enum(self.input_source, InputSource, "input_source")
        _enum(self.value_type, SurfaceValueType, "value_type")
        object.__setattr__(self, "surface_id", surface_id)
        object.__setattr__(
            self,
            "consumer_target",
            _copy(self.consumer_target, ConsumerTarget, "consumer_target"),
        )
        object.__setattr__(
            self,
            "unit_binding",
            _copy_union(
                self.unit_binding, (UnitNotApplicable, BoundUnit), "unit_binding"
            ),
        )
        object.__setattr__(
            self,
            "domain",
            _copy_union(
                self.domain,
                (
                    BooleanDomain,
                    Int64RangeDomain,
                    UInt64RangeDomain,
                    Float64RangeDomain,
                    ChoiceDomain,
                ),
                "domain",
            ),
        )
        dependencies = _ids(self.dependency_surface_ids, "dependency_surface_ids")
        if surface_id in dependencies:
            raise _invalid(
                "construction.self_dependency",
                "catalog entry cannot depend on itself",
                "dependency_surface_ids",
            )
        object.__setattr__(self, "dependency_surface_ids", dependencies)
        object.__setattr__(
            self,
            "applicability",
            _copy_union(
                self.applicability,
                (AlwaysApplicable, WhenSurfaceIn),
                "applicability",
            ),
        )
        object.__setattr__(
            self,
            "requirement",
            _copy_union(
                self.requirement,
                (RequiredSurface, ExplicitDefaultSurface),
                "requirement",
            ),
        )
        object.__setattr__(
            self,
            "compatibility_rule_ids",
            _ids(self.compatibility_rule_ids, "compatibility_rule_ids"),
        )
        object.__setattr__(
            self,
            "static_resource_contributions",
            _resource_contributions(self.static_resource_contributions),
        )
        object.__setattr__(
            self,
            "resource_impact_tags",
            _ids(self.resource_impact_tags, "resource_impact_tags"),
        )
        object.__setattr__(
            self,
            "public_outcome_family_tags",
            _ids(self.public_outcome_family_tags, "public_outcome_family_tags"),
        )
        object.__setattr__(
            self,
            "semantic_owner_binding",
            _copy_union(
                self.semantic_owner_binding,
                (AssemblySemanticOwner, TrainingSupportSemanticOwner),
                "semantic_owner_binding",
            ),
        )
        object.__setattr__(
            self,
            "lifecycle",
            _copy_union(
                self.lifecycle, (ActiveLifecycle, RetiredLifecycle), "lifecycle"
            ),
        )
        object.__setattr__(
            self,
            "training_lever_binding",
            _copy_union(
                self.training_lever_binding,
                (TrainingLeverNotApplicable, BoundTrainingLever),
                "training_lever_binding",
            ),
        )
        object.__setattr__(
            self,
            "component_slot_binding",
            _copy_union(
                self.component_slot_binding,
                (ComponentSelectionNotApplicable, BoundComponentSelection),
                "component_slot_binding",
            ),
        )


@dataclass(frozen=True, slots=True)
class SelectedSurface:
    surface_id: str
    consumer_target: ConsumerTarget
    value: SurfaceValue

    def __post_init__(self) -> None:
        _exact_self(self, SelectedSurface)
        object.__setattr__(self, "surface_id", _id(self.surface_id, "surface_id"))
        object.__setattr__(
            self,
            "consumer_target",
            _copy(self.consumer_target, ConsumerTarget, "consumer_target"),
        )
        object.__setattr__(self, "value", _copy(self.value, SurfaceValue, "value"))


@dataclass(frozen=True, slots=True)
class DefaultedSurface:
    surface_id: str
    consumer_target: ConsumerTarget
    value: SurfaceValue

    def __post_init__(self) -> None:
        _exact_self(self, DefaultedSurface)
        object.__setattr__(self, "surface_id", _id(self.surface_id, "surface_id"))
        object.__setattr__(
            self,
            "consumer_target",
            _copy(self.consumer_target, ConsumerTarget, "consumer_target"),
        )
        object.__setattr__(self, "value", _copy(self.value, SurfaceValue, "value"))


@dataclass(frozen=True, slots=True)
class NotApplicableSurface:
    surface_id: str
    consumer_target: ConsumerTarget
    reason_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, NotApplicableSurface)
        object.__setattr__(self, "surface_id", _id(self.surface_id, "surface_id"))
        object.__setattr__(
            self,
            "consumer_target",
            _copy(self.consumer_target, ConsumerTarget, "consumer_target"),
        )
        object.__setattr__(
            self, "reason_ref", _owner(self.reason_ref, "applicability_reason")
        )


ResolvedSurface: TypeAlias = SelectedSurface | DefaultedSurface | NotApplicableSurface


@dataclass(frozen=True, slots=True)
class ResolvedBackboneBinding:
    surface_id: str
    selector_token: str
    backbone_id: str
    backbone_version: str
    content_digest: str
    implementation_pin: ImplementationPin
    environment_pin: EnvironmentPin
    dependency_pins: tuple[DependencyPin, ...]
    input_interface_pin: InterfacePin
    output_interface_pin: InterfacePin
    applicability_ref: object
    assumption_refs: tuple[object, ...]
    limitation_refs: tuple[object, ...]

    def __post_init__(self) -> None:
        _exact_self(self, ResolvedBackboneBinding)
        object.__setattr__(self, "surface_id", _id(self.surface_id, "surface_id"))
        object.__setattr__(
            self, "selector_token", _id(self.selector_token, "selector_token")
        )
        object.__setattr__(self, "backbone_id", _id(self.backbone_id, "backbone_id"))
        object.__setattr__(
            self,
            "backbone_version",
            _version(self.backbone_version, "backbone_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(
            self,
            "implementation_pin",
            _copy(self.implementation_pin, ImplementationPin, "implementation_pin"),
        )
        object.__setattr__(
            self,
            "environment_pin",
            _copy(self.environment_pin, EnvironmentPin, "environment_pin"),
        )
        object.__setattr__(
            self, "dependency_pins", _dependency_pins(self.dependency_pins)
        )
        input_pin = _copy(self.input_interface_pin, InterfacePin, "input_interface_pin")
        output_pin = _copy(
            self.output_interface_pin, InterfacePin, "output_interface_pin"
        )
        if (
            input_pin.direction is not InterfaceDirection.INPUT
            or output_pin.direction is not InterfaceDirection.OUTPUT
        ):
            raise _invalid(
                "construction.interface_direction_invalid",
                "resolved backbone interface pins have wrong directions",
                "interface_pin",
            )
        object.__setattr__(self, "input_interface_pin", input_pin)
        object.__setattr__(self, "output_interface_pin", output_pin)
        object.__setattr__(
            self, "applicability_ref", _owner(self.applicability_ref, "applicability")
        )
        object.__setattr__(
            self,
            "assumption_refs",
            _owner_set(self.assumption_refs, "assumption_refs", "semantic_clause"),
        )
        object.__setattr__(
            self,
            "limitation_refs",
            _owner_set(self.limitation_refs, "limitation_refs", "restriction"),
        )


@dataclass(frozen=True, slots=True)
class ResolvedComponentBinding:
    slot_id: str
    selector_surface_id: str
    selector_token: str
    component_id: str
    component_version: str
    content_digest: str
    role: ComponentRole
    consumer_target: ConsumerTarget
    input_interface_pin: InterfacePin
    output_interface_pin: InterfacePin
    state_policy: ComponentStatePolicy
    side_effect_policy: SideEffectPolicy
    trainability_boundary: TrainabilityBoundary
    implementation_pin: ImplementationPin
    environment_pin: EnvironmentPin
    dependency_pins: tuple[DependencyPin, ...]
    applicability_ref: object
    assumption_refs: tuple[object, ...]
    limitation_refs: tuple[object, ...]
    public_falsification_refs: tuple[object, ...]

    def __post_init__(self) -> None:
        _exact_self(self, ResolvedComponentBinding)
        object.__setattr__(self, "slot_id", _id(self.slot_id, "slot_id"))
        object.__setattr__(
            self,
            "selector_surface_id",
            _id(self.selector_surface_id, "selector_surface_id"),
        )
        object.__setattr__(
            self, "selector_token", _id(self.selector_token, "selector_token")
        )
        object.__setattr__(self, "component_id", _id(self.component_id, "component_id"))
        object.__setattr__(
            self,
            "component_version",
            _version(self.component_version, "component_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        _enum(self.role, ComponentRole, "role")
        object.__setattr__(
            self,
            "consumer_target",
            _copy(self.consumer_target, ConsumerTarget, "consumer_target"),
        )
        input_pin = _copy(self.input_interface_pin, InterfacePin, "input_interface_pin")
        output_pin = _copy(
            self.output_interface_pin, InterfacePin, "output_interface_pin"
        )
        if (
            input_pin.direction is not InterfaceDirection.INPUT
            or output_pin.direction is not InterfaceDirection.OUTPUT
        ):
            raise _invalid(
                "construction.interface_direction_invalid",
                "resolved component interface pins have wrong directions",
                "interface_pin",
            )
        object.__setattr__(self, "input_interface_pin", input_pin)
        object.__setattr__(self, "output_interface_pin", output_pin)
        _enum(self.state_policy, ComponentStatePolicy, "state_policy")
        _enum(self.side_effect_policy, SideEffectPolicy, "side_effect_policy")
        _enum(self.trainability_boundary, TrainabilityBoundary, "trainability_boundary")
        object.__setattr__(
            self,
            "implementation_pin",
            _copy(self.implementation_pin, ImplementationPin, "implementation_pin"),
        )
        object.__setattr__(
            self,
            "environment_pin",
            _copy(self.environment_pin, EnvironmentPin, "environment_pin"),
        )
        object.__setattr__(
            self, "dependency_pins", _dependency_pins(self.dependency_pins)
        )
        object.__setattr__(
            self, "applicability_ref", _owner(self.applicability_ref, "applicability")
        )
        object.__setattr__(
            self,
            "assumption_refs",
            _owner_set(self.assumption_refs, "assumption_refs", "semantic_clause"),
        )
        object.__setattr__(
            self,
            "limitation_refs",
            _owner_set(self.limitation_refs, "limitation_refs", "restriction"),
        )
        object.__setattr__(
            self,
            "public_falsification_refs",
            _owner_set(
                self.public_falsification_refs,
                "public_falsification_refs",
                "audit_evidence",
            ),
        )


@dataclass(frozen=True, slots=True)
class ResolvedTrainingBinding:
    surface_id: str
    kind: TrainingLeverKind
    resolved_value: SurfaceValue
    executable_semantics_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, ResolvedTrainingBinding)
        object.__setattr__(self, "surface_id", _id(self.surface_id, "surface_id"))
        _enum(self.kind, TrainingLeverKind, "kind")
        object.__setattr__(
            self,
            "resolved_value",
            _copy(self.resolved_value, SurfaceValue, "resolved_value"),
        )
        object.__setattr__(
            self,
            "executable_semantics_ref",
            _owner(self.executable_semantics_ref, "semantic_clause"),
        )


# Literal-name aliases make the Python API readable alongside the contract's
# displayed union vocabulary without creating wrapper/subclass identities.
UnitBound = BoundUnit
TrainingLeverBound = BoundTrainingLever
ComponentSelectionBound = BoundComponentSelection
FixedStaticResourceContribution = FixedResourceContribution
DiscreteLookupStaticResourceContribution = DiscreteLookupResourceContribution


__all__ = [
    "ActiveLifecycle",
    "AlwaysApplicable",
    "ApplicabilityRule",
    "AssemblySemanticOwner",
    "AuthoringOriginBinding",
    "AuthorityMarker",
    "BackboneOption",
    "BackboneSurfaceContract",
    "BooleanDomain",
    "BoundComponentSelection",
    "BoundTrainingLever",
    "BoundUnit",
    "CatalogEntryLifecycle",
    "ChoiceDomain",
    "CompatibilityCell",
    "CompatibilityRule",
    "CompilerIdentity",
    "ComponentRole",
    "ComponentSelectionBinding",
    "ComponentSelectionBound",
    "ComponentSelectionNotApplicable",
    "ComponentSlotContract",
    "ComponentStatePolicy",
    "ConstructionProvenance",
    "ConsumerTarget",
    "DefaultedSurface",
    "DependencyPin",
    "DiscreteLookupResourceContribution",
    "DiscreteLookupStaticResourceContribution",
    "EnvironmentPin",
    "ExplicitDefaultSurface",
    "FallbackPolicy",
    "FixedResourceContribution",
    "FixedStaticResourceContribution",
    "FixtureProvenance",
    "Float64RangeDomain",
    "GraphOrigin",
    "ImplementationPin",
    "InputSource",
    "Int64RangeDomain",
    "InterfaceDirection",
    "InterfacePin",
    "NotApplicableCompatibilityCell",
    "NotApplicableSurface",
    "ParameterCatalogEntry",
    "PolicyState",
    "RegisteredComponentOption",
    "RegisteredProvenance",
    "RequiredSurface",
    "ResolvedBackboneBinding",
    "ResolvedComponentBinding",
    "ResolvedSurface",
    "ResolvedTrainingBinding",
    "ResourceLookupCase",
    "RetiredLifecycle",
    "SelectedSurface",
    "SemanticOwnerBinding",
    "SideEffectPolicy",
    "StatePolicy",
    "StaticResourceContribution",
    "StaticResourceDimension",
    "StaticResourceRequirement",
    "SurfaceDomain",
    "SurfaceRequirement",
    "SurfaceValue",
    "SurfaceValueType",
    "TrainabilityBoundary",
    "TrainingLeverBinding",
    "TrainingLeverBound",
    "TrainingLeverKind",
    "TrainingLeverNotApplicable",
    "TrainingRandomnessPurpose",
    "TrainingSupportSemanticOwner",
    "UInt64RangeDomain",
    "UnitBinding",
    "UnitBound",
    "UnitNotApplicable",
    "UnknownOrInvalidPolicy",
    "ValueCompatibilityCell",
    "WhenSurfaceIn",
    "validate_owner_ref_scope",
]
