"""Immutable B-05 measurement, evidence, and uncertainty-policy records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_exact_bool,
    validate_version_token,
)
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.registry.model import ChallengeKey

from .enums import (
    MEASUREMENT_EVIDENCE_ROLE_CLAIMS,
    DependenceShortcutKind,
    MeasurementClaimClass,
    MeasurementDefinitionKind,
    MeasurementEvidenceRole,
    MeasurementRole,
    ScientificValueState,
    StratumApplicabilityStatus,
)
from .errors import MeasurementInputCode, MeasurementValidationError
from .refs import (
    MEASUREMENT_CANONICALIZATION_PROFILE,
    MEASUREMENT_SCHEMA_VERSION,
    MeasurementContractRef,
    MeasurementDefinitionRef,
    UncertaintyPolicyRef,
)

T = TypeVar("T")


def _invalid(
    path: str, code: MeasurementInputCode = MeasurementInputCode.INVALID_VALUE
):
    return MeasurementValidationError(code, path=path)


def _exact(value: object, expected: type[T], path: str) -> T:
    if type(value) is not expected:
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE) from None


def _identifier(value: object, path: str) -> str:
    try:
        return validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _boolean(value: object, path: str) -> bool:
    try:
        return validate_exact_bool(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE) from None


def _same_challenge(value: ChallengeKey, expected: ChallengeKey, path: str) -> None:
    if value != expected:
        raise _invalid(path, MeasurementInputCode.CROSS_CHALLENGE)


def _definition(
    value: object,
    kind: MeasurementDefinitionKind,
    challenge_key: ChallengeKey,
    path: str,
) -> MeasurementDefinitionRef:
    ref = _exact(value, MeasurementDefinitionRef, path)
    if ref.definition_kind is not kind:
        raise _invalid(path, MeasurementInputCode.ROLE_CONFUSION)
    _same_challenge(ref.challenge_key, challenge_key, path)
    return MeasurementDefinitionRef(
        ref.challenge_key,
        ref.definition_kind,
        ref.object_id,
        ref.object_version,
        ref.content_digest,
        ref.schema_version,
        ref.canonicalization_profile,
    )


def _definition_tuple(
    value: object,
    kind: MeasurementDefinitionKind,
    challenge_key: ChallengeKey,
    path: str,
    *,
    nonempty: bool = False,
) -> tuple[MeasurementDefinitionRef, ...]:
    if type(value) is not tuple:
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS or (nonempty and not value):
        raise _invalid(path)
    copied = tuple(
        _definition(item, kind, challenge_key, f"{path}/{index}")
        for index, item in enumerate(value)
    )
    if len(set(copied)) != len(copied):
        raise _invalid(path, MeasurementInputCode.DUPLICATE_IDENTITY)
    return tuple(sorted(copied, key=_definition_sort_key))


def _definition_sort_key(ref: MeasurementDefinitionRef) -> tuple[str, ...]:
    return (
        ref.definition_kind.value,
        ref.object_id,
        ref.object_version,
        ref.content_digest,
    )


@dataclass(frozen=True, slots=True)
class ScientificValueBinding:
    """Exact approved-value ref or an explicit unresolved/inapplicable state."""

    state: ScientificValueState
    value_ref: MeasurementDefinitionRef | None = None

    def __post_init__(self) -> None:
        _exact(self.state, ScientificValueState, "/state")
        if self.state is ScientificValueState.BOUND:
            if type(self.value_ref) is not MeasurementDefinitionRef:
                raise _invalid("/value_ref", MeasurementInputCode.WRONG_TYPE)
            if (
                self.value_ref.definition_kind
                is not MeasurementDefinitionKind.SCIENTIFIC_VALUE
            ):
                raise _invalid("/value_ref", MeasurementInputCode.ROLE_CONFUSION)
        elif self.state is ScientificValueState.NOT_APPLICABLE:
            if type(self.value_ref) is not MeasurementDefinitionRef:
                raise _invalid("/value_ref", MeasurementInputCode.WRONG_TYPE)
            if (
                self.value_ref.definition_kind
                is not MeasurementDefinitionKind.APPLICABILITY_REASON
            ):
                raise _invalid("/value_ref", MeasurementInputCode.ROLE_CONFUSION)
        elif self.value_ref is not None:
            raise _invalid("/value_ref")


@dataclass(frozen=True, slots=True)
class UncertaintyPolicyBinding:
    """Exact uncertainty-policy ref or explicit unresolved state."""

    state: ScientificValueState
    policy_ref: UncertaintyPolicyRef | None = None

    def __post_init__(self) -> None:
        _exact(self.state, ScientificValueState, "/state")
        if self.state is ScientificValueState.BOUND:
            _exact(self.policy_ref, UncertaintyPolicyRef, "/policy_ref")
        elif self.state in (
            ScientificValueState.HUMAN_INPUT,
            ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET,
        ):
            if self.policy_ref is not None:
                raise _invalid("/policy_ref")
        else:
            raise _invalid("/state")


@dataclass(frozen=True, slots=True)
class UncertaintyComponentBinding:
    """One exact approved policy component or an explicit unresolved state."""

    state: ScientificValueState
    component_ref: MeasurementDefinitionRef | None = None

    def __post_init__(self) -> None:
        _exact(self.state, ScientificValueState, "/state")
        if self.state is ScientificValueState.BOUND:
            _exact(self.component_ref, MeasurementDefinitionRef, "/component_ref")
        elif self.state is ScientificValueState.NOT_APPLICABLE:
            if (
                type(self.component_ref) is not MeasurementDefinitionRef
                or self.component_ref.definition_kind
                is not MeasurementDefinitionKind.APPLICABILITY_REASON
            ):
                raise _invalid("/component_ref", MeasurementInputCode.ROLE_CONFUSION)
        elif self.state in (
            ScientificValueState.HUMAN_INPUT,
            ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET,
        ):
            if self.component_ref is not None:
                raise _invalid("/component_ref")
        else:
            raise _invalid("/state")


@dataclass(frozen=True, slots=True)
class StratumEvidenceMinimumBinding:
    stratum_ref: MeasurementDefinitionRef
    minimum_binding: UncertaintyComponentBinding

    def __post_init__(self) -> None:
        if (
            type(self.stratum_ref) is not MeasurementDefinitionRef
            or self.stratum_ref.definition_kind is not MeasurementDefinitionKind.STRATUM
        ):
            raise _invalid("/stratum_ref", MeasurementInputCode.ROLE_CONFUSION)
        _exact(
            self.minimum_binding,
            UncertaintyComponentBinding,
            "/minimum_binding",
        )


@dataclass(frozen=True, slots=True)
class DependenceShortcutBinding:
    """Exact, scope-limited evidence binding for one qualified shortcut."""

    shortcut_id: str
    shortcut_version: str
    shortcut_kind: DependenceShortcutKind
    incumbent_evidence_ref: MeasurementDefinitionRef
    challenger_evidence_ref: MeasurementDefinitionRef
    case_scope_refs: tuple[MeasurementDefinitionRef, ...]
    stratum_scope_refs: tuple[MeasurementDefinitionRef, ...]
    assumption_ref: MeasurementDefinitionRef
    applicability_test_ref: MeasurementDefinitionRef
    dossier_qualification_ref: MeasurementDefinitionRef
    fixture_origin: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "shortcut_id", _identifier(self.shortcut_id, "/shortcut_id")
        )
        object.__setattr__(
            self,
            "shortcut_version",
            _version(self.shortcut_version, "/shortcut_version"),
        )
        _exact(self.shortcut_kind, DependenceShortcutKind, "/shortcut_kind")
        incumbent = _exact(
            self.incumbent_evidence_ref,
            MeasurementDefinitionRef,
            "/incumbent_evidence_ref",
        )
        challenge_key = incumbent.challenge_key
        fields = (
            (
                "incumbent_evidence_ref",
                MeasurementDefinitionKind.EVIDENCE_SET,
            ),
            (
                "challenger_evidence_ref",
                MeasurementDefinitionKind.EVIDENCE_SET,
            ),
            ("assumption_ref", MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION),
            ("applicability_test_ref", MeasurementDefinitionKind.APPLICABILITY_TEST),
            (
                "dossier_qualification_ref",
                MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
            ),
        )
        for name, kind in fields:
            object.__setattr__(
                self,
                name,
                _definition(getattr(self, name), kind, challenge_key, f"/{name}"),
            )
        if self.incumbent_evidence_ref == self.challenger_evidence_ref:
            raise _invalid(
                "/challenger_evidence_ref", MeasurementInputCode.DUPLICATE_IDENTITY
            )
        object.__setattr__(
            self,
            "case_scope_refs",
            _definition_tuple(
                self.case_scope_refs,
                MeasurementDefinitionKind.CASE_SCOPE,
                challenge_key,
                "/case_scope_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "stratum_scope_refs",
            _definition_tuple(
                self.stratum_scope_refs,
                MeasurementDefinitionKind.STRATUM,
                challenge_key,
                "/stratum_scope_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self, "fixture_origin", _boolean(self.fixture_origin, "/fixture_origin")
        )


_UNCERTAINTY_COMPONENT_FIELDS = (
    ("estimand_binding", MeasurementDefinitionKind.ESTIMAND),
    ("measurement_output_binding", MeasurementDefinitionKind.MEASUREMENT_OUTPUT),
    ("sampling_unit_binding", MeasurementDefinitionKind.SAMPLING_UNIT),
    ("resampling_unit_binding", MeasurementDefinitionKind.RESAMPLING_UNIT),
    ("independence_unit_binding", MeasurementDefinitionKind.INDEPENDENCE_UNIT),
    ("common_case_pairing_binding", MeasurementDefinitionKind.COMMON_CASE_PAIRING),
    (
        "reconstruction_case_interaction_binding",
        MeasurementDefinitionKind.RECONSTRUCTION_CASE_INTERACTION,
    ),
    (
        "reconstruction_stratum_interaction_binding",
        MeasurementDefinitionKind.RECONSTRUCTION_STRATUM_INTERACTION,
    ),
    (
        "joint_reference_uncertainty_binding",
        MeasurementDefinitionKind.JOINT_REFERENCE_UNCERTAINTY,
    ),
    (
        "reference_candidate_covariance_binding",
        MeasurementDefinitionKind.REFERENCE_CANDIDATE_COVARIANCE,
    ),
    (
        "representation_dependence_binding",
        MeasurementDefinitionKind.REPRESENTATION_DEPENDENCE,
    ),
    ("execution_dependence_binding", MeasurementDefinitionKind.EXECUTION_DEPENDENCE),
    ("censoring_accounting_binding", MeasurementDefinitionKind.CENSORING_ACCOUNTING),
    ("minimum_evidence_binding", MeasurementDefinitionKind.EVIDENCE_MINIMUM),
    ("stopping_rule_binding", MeasurementDefinitionKind.STOPPING_RULE),
    (
        "evidence_extension_rule_binding",
        MeasurementDefinitionKind.EVIDENCE_EXTENSION_RULE,
    ),
    (
        "interval_error_control_binding",
        MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL,
    ),
    ("multiplicity_policy_binding", MeasurementDefinitionKind.MULTIPLICITY_POLICY),
)


@dataclass(frozen=True, slots=True)
class UncertaintyPolicy:
    challenge_key: ChallengeKey
    policy_id: str
    policy_version: str
    measurement_contract_ref: MeasurementContractRef
    estimand_binding: UncertaintyComponentBinding
    measurement_output_binding: UncertaintyComponentBinding
    sampling_unit_binding: UncertaintyComponentBinding
    resampling_unit_binding: UncertaintyComponentBinding
    independence_unit_binding: UncertaintyComponentBinding
    common_case_pairing_binding: UncertaintyComponentBinding
    reconstruction_case_interaction_binding: UncertaintyComponentBinding
    reconstruction_stratum_interaction_binding: UncertaintyComponentBinding
    joint_reference_uncertainty_binding: UncertaintyComponentBinding
    reference_candidate_covariance_binding: UncertaintyComponentBinding
    representation_dependence_binding: UncertaintyComponentBinding
    execution_dependence_binding: UncertaintyComponentBinding
    censoring_accounting_binding: UncertaintyComponentBinding
    minimum_evidence_binding: UncertaintyComponentBinding
    stratum_minimum_bindings: tuple[StratumEvidenceMinimumBinding, ...]
    stopping_rule_binding: UncertaintyComponentBinding
    evidence_extension_rule_binding: UncertaintyComponentBinding
    interval_error_control_binding: UncertaintyComponentBinding
    multiplicity_policy_binding: UncertaintyComponentBinding
    dependence_shortcuts: tuple[DependenceShortcutBinding, ...]
    fixture_origin: bool
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    RECORD_TYPE = "uncertainty_policy"

    def __post_init__(self) -> None:
        if type(self) is not UncertaintyPolicy:
            raise _invalid("/record_type", MeasurementInputCode.WRONG_TYPE)
        challenge_key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "policy_id", _identifier(self.policy_id, "/policy_id"))
        object.__setattr__(
            self,
            "policy_version",
            _version(self.policy_version, "/policy_version"),
        )
        contract_ref = _exact(
            self.measurement_contract_ref,
            MeasurementContractRef,
            "/measurement_contract_ref",
        )
        _same_challenge(
            contract_ref.challenge_key, challenge_key, "/measurement_contract_ref"
        )
        for name, expected_kind in _UNCERTAINTY_COMPONENT_FIELDS:
            binding = _exact(
                getattr(self, name), UncertaintyComponentBinding, f"/{name}"
            )
            if binding.component_ref is not None:
                _same_challenge(
                    binding.component_ref.challenge_key,
                    challenge_key,
                    f"/{name}/component_ref",
                )
                if (
                    binding.state is ScientificValueState.BOUND
                    and binding.component_ref.definition_kind is not expected_kind
                ):
                    raise _invalid(
                        f"/{name}/component_ref", MeasurementInputCode.ROLE_CONFUSION
                    )
        if (
            type(self.stratum_minimum_bindings) is not tuple
            or not self.stratum_minimum_bindings
            or len(self.stratum_minimum_bindings) > MAX_CANONICAL_TUPLE_ITEMS
        ):
            raise _invalid("/stratum_minimum_bindings", MeasurementInputCode.WRONG_TYPE)
        minima = tuple(
            _exact(
                item, StratumEvidenceMinimumBinding, f"/stratum_minimum_bindings/{i}"
            )
            for i, item in enumerate(self.stratum_minimum_bindings)
        )
        if len({item.stratum_ref for item in minima}) != len(minima):
            raise _invalid(
                "/stratum_minimum_bindings", MeasurementInputCode.DUPLICATE_IDENTITY
            )
        for index, item in enumerate(minima):
            _same_challenge(
                item.stratum_ref.challenge_key,
                challenge_key,
                f"/stratum_minimum_bindings/{index}/stratum_ref",
            )
            component_ref = item.minimum_binding.component_ref
            if component_ref is not None:
                _same_challenge(
                    component_ref.challenge_key,
                    challenge_key,
                    f"/stratum_minimum_bindings/{index}/minimum_binding/component_ref",
                )
                if (
                    item.minimum_binding.state is ScientificValueState.BOUND
                    and component_ref.definition_kind
                    is not MeasurementDefinitionKind.STRATUM_EVIDENCE_MINIMUM
                ):
                    raise _invalid(
                        f"/stratum_minimum_bindings/{index}/minimum_binding/component_ref",
                        MeasurementInputCode.ROLE_CONFUSION,
                    )
        object.__setattr__(
            self,
            "stratum_minimum_bindings",
            tuple(
                sorted(minima, key=lambda item: _definition_sort_key(item.stratum_ref))
            ),
        )
        if (
            type(self.dependence_shortcuts) is not tuple
            or len(self.dependence_shortcuts) > MAX_CANONICAL_TUPLE_ITEMS
        ):
            raise _invalid("/dependence_shortcuts", MeasurementInputCode.WRONG_TYPE)
        shortcuts = tuple(
            _exact(item, DependenceShortcutBinding, f"/dependence_shortcuts/{i}")
            for i, item in enumerate(self.dependence_shortcuts)
        )
        shortcut_keys = tuple(
            (item.shortcut_id, item.shortcut_version) for item in shortcuts
        )
        if len(set(shortcut_keys)) != len(shortcut_keys):
            raise _invalid(
                "/dependence_shortcuts", MeasurementInputCode.DUPLICATE_IDENTITY
            )
        fixture_origin = _boolean(self.fixture_origin, "/fixture_origin")
        for index, item in enumerate(shortcuts):
            _same_challenge(
                item.incumbent_evidence_ref.challenge_key,
                challenge_key,
                f"/dependence_shortcuts/{index}/incumbent_evidence_ref",
            )
            if not fixture_origin and item.fixture_origin:
                raise _invalid(
                    f"/dependence_shortcuts/{index}/fixture_origin",
                    MeasurementInputCode.FIXTURE_REQUIRED,
                )
        object.__setattr__(
            self,
            "dependence_shortcuts",
            tuple(
                sorted(
                    shortcuts,
                    key=lambda item: (
                        item.shortcut_id,
                        item.shortcut_version,
                        item.shortcut_kind.value,
                    ),
                )
            ),
        )
        object.__setattr__(self, "fixture_origin", fixture_origin)
        if (
            self.schema_version != MEASUREMENT_SCHEMA_VERSION
            or self.canonicalization_profile != MEASUREMENT_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")


@dataclass(frozen=True, slots=True)
class StratumApplicabilityBinding:
    stratum_ref: MeasurementDefinitionRef
    status: StratumApplicabilityStatus
    evidence_or_reason_ref: MeasurementDefinitionRef | None = None

    def __post_init__(self) -> None:
        if type(self.stratum_ref) is not MeasurementDefinitionRef:
            raise _invalid("/stratum_ref", MeasurementInputCode.WRONG_TYPE)
        if self.stratum_ref.definition_kind is not MeasurementDefinitionKind.STRATUM:
            raise _invalid("/stratum_ref", MeasurementInputCode.ROLE_CONFUSION)
        _exact(self.status, StratumApplicabilityStatus, "/status")
        expected_kind = None
        if self.status is StratumApplicabilityStatus.APPLICABLE:
            expected_kind = MeasurementDefinitionKind.APPLICABILITY_EVIDENCE
        elif self.status is StratumApplicabilityStatus.NOT_APPLICABLE:
            expected_kind = MeasurementDefinitionKind.APPLICABILITY_REASON
        if expected_kind is None:
            if self.evidence_or_reason_ref is not None:
                raise _invalid("/evidence_or_reason_ref")
        elif (
            type(self.evidence_or_reason_ref) is not MeasurementDefinitionRef
            or self.evidence_or_reason_ref.definition_kind is not expected_kind
        ):
            raise _invalid(
                "/evidence_or_reason_ref", MeasurementInputCode.ROLE_CONFUSION
            )


def _strata(
    value: object, challenge_key: ChallengeKey, path: str
) -> tuple[StratumApplicabilityBinding, ...]:
    if type(value) is not tuple or not value or len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    copied: list[StratumApplicabilityBinding] = []
    seen: set[MeasurementDefinitionRef] = set()
    for index, item in enumerate(value):
        binding = _exact(item, StratumApplicabilityBinding, f"{path}/{index}")
        _same_challenge(
            binding.stratum_ref.challenge_key, challenge_key, f"{path}/{index}"
        )
        if binding.evidence_or_reason_ref is not None:
            _same_challenge(
                binding.evidence_or_reason_ref.challenge_key,
                challenge_key,
                f"{path}/{index}/evidence_or_reason_ref",
            )
        if binding.stratum_ref in seen:
            raise _invalid(path, MeasurementInputCode.DUPLICATE_IDENTITY)
        seen.add(binding.stratum_ref)
        copied.append(binding)
    return tuple(
        sorted(copied, key=lambda item: _definition_sort_key(item.stratum_ref))
    )


@dataclass(frozen=True, slots=True)
class MeasurementContract:
    challenge_key: ChallengeKey
    measurement_id: str
    measurement_version: str
    scientific_property_ref: MeasurementDefinitionRef
    observable_refs: tuple[MeasurementDefinitionRef, ...]
    coordinate_system_ref: MeasurementDefinitionRef
    unit_ref: MeasurementDefinitionRef
    numerical_operator_ref: MeasurementDefinitionRef
    discretization_ref: MeasurementDefinitionRef
    sampling_quadrature_ref: MeasurementDefinitionRef
    normalization_ref: MeasurementDefinitionRef
    aggregation_ref: MeasurementDefinitionRef
    precision_ref: MeasurementDefinitionRef
    reference_policy_ref: ReferencePolicyRef
    numerical_floor_binding: ScientificValueBinding
    applicability_policy_ref: MeasurementDefinitionRef
    uncertainty_policy_binding: UncertaintyPolicyBinding
    stratum_applicability: tuple[StratumApplicabilityBinding, ...]
    known_limitation_refs: tuple[MeasurementDefinitionRef, ...]
    implementation_refs: tuple[MeasurementDefinitionRef, ...]
    intended_role: MeasurementRole
    fixture_origin: bool
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    RECORD_TYPE = "measurement_contract"

    def __post_init__(self) -> None:
        if type(self) is not MeasurementContract:
            raise _invalid("/record_type", MeasurementInputCode.WRONG_TYPE)
        challenge_key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(
            self, "measurement_id", _identifier(self.measurement_id, "/measurement_id")
        )
        object.__setattr__(
            self,
            "measurement_version",
            _version(self.measurement_version, "/measurement_version"),
        )
        fields = (
            ("scientific_property_ref", MeasurementDefinitionKind.SCIENTIFIC_PROPERTY),
            ("coordinate_system_ref", MeasurementDefinitionKind.COORDINATE_SYSTEM),
            ("unit_ref", MeasurementDefinitionKind.UNIT),
            ("numerical_operator_ref", MeasurementDefinitionKind.NUMERICAL_OPERATOR),
            ("discretization_ref", MeasurementDefinitionKind.DISCRETIZATION),
            ("sampling_quadrature_ref", MeasurementDefinitionKind.SAMPLING_QUADRATURE),
            ("normalization_ref", MeasurementDefinitionKind.NORMALIZATION),
            ("aggregation_ref", MeasurementDefinitionKind.AGGREGATION),
            ("precision_ref", MeasurementDefinitionKind.PRECISION),
            (
                "applicability_policy_ref",
                MeasurementDefinitionKind.APPLICABILITY_POLICY,
            ),
        )
        for name, kind in fields:
            object.__setattr__(
                self,
                name,
                _definition(getattr(self, name), kind, challenge_key, f"/{name}"),
            )
        object.__setattr__(
            self,
            "observable_refs",
            _definition_tuple(
                self.observable_refs,
                MeasurementDefinitionKind.OBSERVABLE,
                challenge_key,
                "/observable_refs",
                nonempty=True,
            ),
        )
        reference = _exact(
            self.reference_policy_ref, ReferencePolicyRef, "/reference_policy_ref"
        )
        _same_challenge(reference.challenge_key, challenge_key, "/reference_policy_ref")
        object.__setattr__(
            self,
            "reference_policy_ref",
            ReferencePolicyRef(
                reference.challenge_key,
                reference.content_digest,
                reference.schema_version,
                reference.canonicalization_profile,
            ),
        )
        floor = _exact(
            self.numerical_floor_binding,
            ScientificValueBinding,
            "/numerical_floor_binding",
        )
        if floor.state is ScientificValueState.NOT_APPLICABLE:
            raise _invalid("/numerical_floor_binding/state")
        if floor.value_ref is not None:
            _same_challenge(
                floor.value_ref.challenge_key,
                challenge_key,
                "/numerical_floor_binding/value_ref",
            )
        uncertainty = _exact(
            self.uncertainty_policy_binding,
            UncertaintyPolicyBinding,
            "/uncertainty_policy_binding",
        )
        if uncertainty.policy_ref is not None:
            _same_challenge(
                uncertainty.policy_ref.challenge_key,
                challenge_key,
                "/uncertainty_policy_binding/policy_ref",
            )
        object.__setattr__(
            self,
            "stratum_applicability",
            _strata(
                self.stratum_applicability, challenge_key, "/stratum_applicability"
            ),
        )
        object.__setattr__(
            self,
            "known_limitation_refs",
            _definition_tuple(
                self.known_limitation_refs,
                MeasurementDefinitionKind.KNOWN_LIMITATION,
                challenge_key,
                "/known_limitation_refs",
            ),
        )
        object.__setattr__(
            self,
            "implementation_refs",
            _definition_tuple(
                self.implementation_refs,
                MeasurementDefinitionKind.IMPLEMENTATION,
                challenge_key,
                "/implementation_refs",
                nonempty=True,
            ),
        )
        _exact(self.intended_role, MeasurementRole, "/intended_role")
        object.__setattr__(
            self, "fixture_origin", _boolean(self.fixture_origin, "/fixture_origin")
        )
        if (
            self.schema_version != MEASUREMENT_SCHEMA_VERSION
            or self.canonicalization_profile != MEASUREMENT_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")


@dataclass(frozen=True, slots=True)
class MeasurementEvidenceItem:
    evidence_id: str
    source_ref: MeasurementDefinitionRef
    role: MeasurementEvidenceRole
    supported_claims: tuple[MeasurementClaimClass, ...]
    unsupported_claims: tuple[MeasurementClaimClass, ...]
    case_scope_refs: tuple[MeasurementDefinitionRef, ...]
    stratum_scope_refs: tuple[MeasurementDefinitionRef, ...]
    fixture_origin: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _identifier(self.evidence_id, "/evidence_id")
        )
        if (
            type(self.source_ref) is not MeasurementDefinitionRef
            or self.source_ref.definition_kind
            is not MeasurementDefinitionKind.EVIDENCE_SOURCE
        ):
            raise _invalid("/source_ref", MeasurementInputCode.ROLE_CONFUSION)
        _exact(self.role, MeasurementEvidenceRole, "/role")
        supported = _claim_tuple(
            self.supported_claims, "/supported_claims", nonempty=True
        )
        unsupported = _claim_tuple(
            self.unsupported_claims, "/unsupported_claims", nonempty=True
        )
        if set(supported) & set(unsupported) or set(supported) | set(
            unsupported
        ) != set(MeasurementClaimClass):
            raise _invalid(
                "/supported_claims", MeasurementInputCode.CLAIM_MATRIX_VIOLATION
            )
        if not set(supported) <= MEASUREMENT_EVIDENCE_ROLE_CLAIMS[self.role]:
            raise _invalid(
                "/supported_claims", MeasurementInputCode.CLAIM_MATRIX_VIOLATION
            )
        object.__setattr__(self, "supported_claims", supported)
        object.__setattr__(self, "unsupported_claims", unsupported)
        challenge_key = self.source_ref.challenge_key
        object.__setattr__(
            self,
            "case_scope_refs",
            _definition_tuple(
                self.case_scope_refs,
                MeasurementDefinitionKind.CASE_SCOPE,
                challenge_key,
                "/case_scope_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "stratum_scope_refs",
            _definition_tuple(
                self.stratum_scope_refs,
                MeasurementDefinitionKind.STRATUM,
                challenge_key,
                "/stratum_scope_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self, "fixture_origin", _boolean(self.fixture_origin, "/fixture_origin")
        )


def _claim_tuple(
    value: object, path: str, *, nonempty: bool
) -> tuple[MeasurementClaimClass, ...]:
    if (
        type(value) is not tuple
        or (nonempty and not value)
        or len(value) > len(MeasurementClaimClass)
    ):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    if any(type(item) is not MeasurementClaimClass for item in value):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    if len(set(value)) != len(value):
        raise _invalid(path, MeasurementInputCode.DUPLICATE_IDENTITY)
    return tuple(sorted(value, key=lambda item: item.value))


@dataclass(frozen=True, slots=True)
class MeasurementQualificationEvidence:
    challenge_key: ChallengeKey
    evidence_id: str
    evidence_version: str
    measurement_contract_ref: MeasurementContractRef
    evidence_items: tuple[MeasurementEvidenceItem, ...]
    fixture_origin: bool
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    RECORD_TYPE = "measurement_qualification_evidence"

    def __post_init__(self) -> None:
        if type(self) is not MeasurementQualificationEvidence:
            raise _invalid("/record_type", MeasurementInputCode.WRONG_TYPE)
        challenge_key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(
            self, "evidence_id", _identifier(self.evidence_id, "/evidence_id")
        )
        object.__setattr__(
            self,
            "evidence_version",
            _version(self.evidence_version, "/evidence_version"),
        )
        contract_ref = _exact(
            self.measurement_contract_ref,
            MeasurementContractRef,
            "/measurement_contract_ref",
        )
        _same_challenge(
            contract_ref.challenge_key, challenge_key, "/measurement_contract_ref"
        )
        if (
            type(self.evidence_items) is not tuple
            or not self.evidence_items
            or len(self.evidence_items) > MAX_CANONICAL_TUPLE_ITEMS
        ):
            raise _invalid("/evidence_items", MeasurementInputCode.WRONG_TYPE)
        items = tuple(
            _exact(item, MeasurementEvidenceItem, f"/evidence_items/{index}")
            for index, item in enumerate(self.evidence_items)
        )
        if len({item.evidence_id for item in items}) != len(items):
            raise _invalid("/evidence_items", MeasurementInputCode.DUPLICATE_IDENTITY)
        for index, item in enumerate(items):
            _same_challenge(
                item.source_ref.challenge_key,
                challenge_key,
                f"/evidence_items/{index}/source_ref",
            )
        fixture_origin = _boolean(self.fixture_origin, "/fixture_origin")
        if not fixture_origin and any(item.fixture_origin for item in items):
            raise _invalid("/evidence_items", MeasurementInputCode.FIXTURE_REQUIRED)
        object.__setattr__(
            self,
            "evidence_items",
            tuple(sorted(items, key=lambda item: item.evidence_id)),
        )
        object.__setattr__(self, "fixture_origin", fixture_origin)
        if (
            self.schema_version != MEASUREMENT_SCHEMA_VERSION
            or self.canonicalization_profile != MEASUREMENT_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")


MeasurementAuthoringObject = (
    MeasurementContract | MeasurementQualificationEvidence | UncertaintyPolicy
)


__all__ = (
    "DependenceShortcutBinding",
    "MeasurementAuthoringObject",
    "MeasurementContract",
    "MeasurementEvidenceItem",
    "MeasurementQualificationEvidence",
    "ScientificValueBinding",
    "StratumApplicabilityBinding",
    "StratumEvidenceMinimumBinding",
    "UncertaintyComponentBinding",
    "UncertaintyPolicy",
    "UncertaintyPolicyBinding",
)
