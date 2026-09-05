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
from carbon.resource_policy.model import (
    BoundReconstructionReplicate,
    CompleteBuild,
    FrozenArtifactReuseWindow,
    IncompleteBuild,
    IncompleteReconstructionReplicate,
    NoBuildStarted,
    NoReuse,
    ReplicateNotApplicable,
    ResourceStopCause,
)
from carbon.resource_policy.refs import (
    FixtureResourceDecisionRef,
    ObservedResourceReceiptRef,
    StaticResourceAssessmentRef,
)
from carbon.scoring.model import ScorePackPin

from .enums import (
    MEASUREMENT_EVIDENCE_ROLE_CLAIMS,
    A5DestinationKind,
    DependenceShortcutKind,
    MeasurementClaimClass,
    MeasurementDefinitionKind,
    MeasurementEvidenceRole,
    MeasurementRole,
    ReconstructionEvidenceOutcome,
    ReconstructionEvidenceStage,
    ReconstructionStopKind,
    ScientificValueState,
    ScoreAggregationRole,
    ScoreDisclosureClass,
    ScoreEligibilityRole,
    ScoreRankingRole,
    ScoreScalarKind,
    ScoreUseRole,
    StratumApplicabilityStatus,
)
from .errors import MeasurementInputCode, MeasurementValidationError
from .refs import (
    MEASUREMENT_CANONICALIZATION_PROFILE,
    MEASUREMENT_SCHEMA_VERSION,
    MeasurementContractRef,
    MeasurementDefinitionRef,
    ReconstructionEvidencePolicyRef,
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

    @property
    def has_complete_score_authority(self) -> bool:
        resolved_states = (
            ScientificValueState.BOUND,
            ScientificValueState.NOT_APPLICABLE,
        )
        return all(
            getattr(self, name).state in resolved_states
            for name, _ in _UNCERTAINTY_COMPONENT_FIELDS
        ) and all(
            item.minimum_binding.state in resolved_states
            for item in self.stratum_minimum_bindings
        )


_RECONSTRUCTION_COMPONENT_FIELDS = (
    ("complete_base_minimum_binding", MeasurementDefinitionKind.COMPLETE_BASE_MINIMUM),
    (
        "build_completeness_criteria_binding",
        MeasurementDefinitionKind.BUILD_COMPLETENESS_CRITERIA,
    ),
    (
        "frozen_artifact_reuse_policy_binding",
        MeasurementDefinitionKind.FROZEN_ARTIFACT_REUSE_POLICY,
    ),
    ("nomination_criteria_binding", MeasurementDefinitionKind.NOMINATION_CRITERIA),
    ("promotion_criteria_binding", MeasurementDefinitionKind.PROMOTION_CRITERIA),
    (
        "case_coverage_requirement_binding",
        MeasurementDefinitionKind.CASE_COVERAGE_REQUIREMENT,
    ),
    (
        "stratum_coverage_requirement_binding",
        MeasurementDefinitionKind.STRATUM_COVERAGE_REQUIREMENT,
    ),
    (
        "evidence_extension_rule_binding",
        MeasurementDefinitionKind.EVIDENCE_EXTENSION_RULE,
    ),
    ("scientific_stopping_rule_binding", MeasurementDefinitionKind.STOPPING_RULE),
    ("stability_audit_rate_binding", MeasurementDefinitionKind.STABILITY_AUDIT_RATE),
    (
        "audit_selection_policy_binding",
        MeasurementDefinitionKind.AUDIT_SELECTION_POLICY,
    ),
    ("error_control_binding", MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL),
    ("power_requirement_binding", MeasurementDefinitionKind.POWER_REQUIREMENT),
    (
        "minimum_resolvable_improvement_binding",
        MeasurementDefinitionKind.MINIMUM_RESOLVABLE_IMPROVEMENT,
    ),
    (
        "sequential_stopping_rule_binding",
        MeasurementDefinitionKind.SEQUENTIAL_STOPPING_RULE,
    ),
)


@dataclass(frozen=True, slots=True)
class ReconstructionEvidencePolicy:
    """Challenge/family-bound authorship of scientific evidence sufficiency."""

    challenge_key: ChallengeKey
    policy_id: str
    policy_version: str
    construction_family_ref: MeasurementDefinitionRef
    complete_base_minimum_binding: UncertaintyComponentBinding
    build_completeness_criteria_binding: UncertaintyComponentBinding
    frozen_artifact_reuse_policy_binding: UncertaintyComponentBinding
    nomination_criteria_binding: UncertaintyComponentBinding
    promotion_criteria_binding: UncertaintyComponentBinding
    case_coverage_requirement_binding: UncertaintyComponentBinding
    stratum_coverage_requirement_binding: UncertaintyComponentBinding
    evidence_extension_rule_binding: UncertaintyComponentBinding
    scientific_stopping_rule_binding: UncertaintyComponentBinding
    stability_audit_rate_binding: UncertaintyComponentBinding
    audit_selection_policy_binding: UncertaintyComponentBinding
    error_control_binding: UncertaintyComponentBinding
    power_requirement_binding: UncertaintyComponentBinding
    minimum_resolvable_improvement_binding: UncertaintyComponentBinding
    sequential_stopping_rule_binding: UncertaintyComponentBinding
    fixture_origin: bool
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    RECORD_TYPE = "reconstruction_evidence_policy"

    def __post_init__(self) -> None:
        if type(self) is not ReconstructionEvidencePolicy:
            raise _invalid("/record_type", MeasurementInputCode.WRONG_TYPE)
        challenge_key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "policy_id", _identifier(self.policy_id, "/policy_id"))
        object.__setattr__(
            self,
            "policy_version",
            _version(self.policy_version, "/policy_version"),
        )
        object.__setattr__(
            self,
            "construction_family_ref",
            _definition(
                self.construction_family_ref,
                MeasurementDefinitionKind.CONSTRUCTION_FAMILY,
                challenge_key,
                "/construction_family_ref",
            ),
        )
        for name, expected_kind in _RECONSTRUCTION_COMPONENT_FIELDS:
            binding = _exact(
                getattr(self, name), UncertaintyComponentBinding, f"/{name}"
            )
            if binding.state is ScientificValueState.NOT_APPLICABLE:
                raise _invalid(f"/{name}/state")
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
                        f"/{name}/component_ref",
                        MeasurementInputCode.ROLE_CONFUSION,
                    )
        object.__setattr__(
            self, "fixture_origin", _boolean(self.fixture_origin, "/fixture_origin")
        )
        if (
            self.schema_version != MEASUREMENT_SCHEMA_VERSION
            or self.canonicalization_profile != MEASUREMENT_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")

    @property
    def has_complete_human_authority(self) -> bool:
        """Whether every mandatory human/qualification-owned component is bound."""

        return all(
            getattr(self, name).state is ScientificValueState.BOUND
            for name, _ in _RECONSTRUCTION_COMPONENT_FIELDS
        )


_BUILD_TYPES = (NoBuildStarted, IncompleteBuild, CompleteBuild)
_REUSE_TYPES = (NoReuse, FrozenArtifactReuseWindow)
_REPLICATE_TYPES = (
    ReplicateNotApplicable,
    IncompleteReconstructionReplicate,
    BoundReconstructionReplicate,
)


def _resource_challenge(value: object) -> ChallengeKey | None:
    identity = getattr(value, "build_identity", None)
    if identity is None:
        identity = getattr(value, "complete_build_identity", None)
    if identity is None:
        identity = getattr(value, "replicate_identity", None)
    return getattr(identity, "challenge_key", None)


@dataclass(frozen=True, slots=True)
class ReconstructionResourceFacts:
    """Exact B-02C facts; these fields grant no scientific authority."""

    build_completion: object
    frozen_artifact_reuse: object
    reconstruction_replicate: object
    resource_stop_cause: ResourceStopCause
    static_assessment_ref: StaticResourceAssessmentRef | None
    fixture_decision_ref: FixtureResourceDecisionRef | None
    observed_receipt_ref: ObservedResourceReceiptRef | None

    def __post_init__(self) -> None:
        if type(self.build_completion) not in _BUILD_TYPES:
            raise _invalid("/build_completion", MeasurementInputCode.WRONG_TYPE)
        if type(self.frozen_artifact_reuse) not in _REUSE_TYPES:
            raise _invalid("/frozen_artifact_reuse", MeasurementInputCode.WRONG_TYPE)
        if type(self.reconstruction_replicate) not in _REPLICATE_TYPES:
            raise _invalid("/reconstruction_replicate", MeasurementInputCode.WRONG_TYPE)
        _exact(self.resource_stop_cause, ResourceStopCause, "/resource_stop_cause")
        for name, expected in (
            ("static_assessment_ref", StaticResourceAssessmentRef),
            ("fixture_decision_ref", FixtureResourceDecisionRef),
            ("observed_receipt_ref", ObservedResourceReceiptRef),
        ):
            value = getattr(self, name)
            if value is not None:
                _exact(value, expected, f"/{name}")
        if type(self.frozen_artifact_reuse) is FrozenArtifactReuseWindow and (
            type(self.build_completion) is not CompleteBuild
            or self.frozen_artifact_reuse.complete_build_identity
            != self.build_completion.build_identity
        ):
            raise _invalid("/frozen_artifact_reuse")
        if (
            type(self.build_completion) is CompleteBuild
            and type(self.reconstruction_replicate) is BoundReconstructionReplicate
        ):
            build_identity = self.build_completion.build_identity
            replicate_identity = self.reconstruction_replicate.replicate_identity
            for name in (
                "construction_plan_ref",
                "policy_ref",
                "resource_class_ref",
            ):
                if getattr(build_identity, name) != getattr(replicate_identity, name):
                    raise _invalid(
                        f"/reconstruction_replicate/replicate_identity/{name}",
                        MeasurementInputCode.ROLE_CONFUSION,
                    )

    def validate_challenge(self, challenge_key: ChallengeKey) -> None:
        facts = (
            self.build_completion,
            self.frozen_artifact_reuse,
            self.reconstruction_replicate,
            self.static_assessment_ref,
            self.fixture_decision_ref,
            self.observed_receipt_ref,
        )
        for index, value in enumerate(facts):
            if value is None:
                continue
            fact_challenge = getattr(value, "challenge_key", None)
            if fact_challenge is None:
                fact_challenge = _resource_challenge(value)
            if fact_challenge is not None:
                _same_challenge(
                    fact_challenge, challenge_key, f"/resource_facts/{index}"
                )


_STAGE_EVIDENCE_FIELDS = (
    ("complete_base_evidence_ref", MeasurementDefinitionKind.COMPLETE_BASE_EVIDENCE),
    ("nomination_evidence_ref", MeasurementDefinitionKind.NOMINATION_EVIDENCE),
    ("extension_evidence_ref", MeasurementDefinitionKind.EXTENSION_EVIDENCE),
    ("promotion_evidence_ref", MeasurementDefinitionKind.PROMOTION_EVIDENCE),
)


@dataclass(frozen=True, slots=True)
class ReconstructionEvidenceInput:
    policy_ref: ReconstructionEvidencePolicyRef
    construction_family_ref: MeasurementDefinitionRef
    resource_facts: ReconstructionResourceFacts
    complete_base_evidence_ref: MeasurementDefinitionRef | None
    nomination_evidence_ref: MeasurementDefinitionRef | None
    extension_evidence_ref: MeasurementDefinitionRef | None
    promotion_evidence_ref: MeasurementDefinitionRef | None
    remaining_requirement_refs: tuple[MeasurementDefinitionRef, ...]
    stop_kind: ReconstructionStopKind
    reconstruction_failure_ref: MeasurementDefinitionRef | None = None

    def __post_init__(self) -> None:
        policy_ref = _exact(
            self.policy_ref, ReconstructionEvidencePolicyRef, "/policy_ref"
        )
        family_ref = _definition(
            self.construction_family_ref,
            MeasurementDefinitionKind.CONSTRUCTION_FAMILY,
            policy_ref.challenge_key,
            "/construction_family_ref",
        )
        object.__setattr__(self, "construction_family_ref", family_ref)
        resource_facts = _exact(
            self.resource_facts, ReconstructionResourceFacts, "/resource_facts"
        )
        resource_facts.validate_challenge(policy_ref.challenge_key)
        for name, kind in _STAGE_EVIDENCE_FIELDS:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _definition(value, kind, policy_ref.challenge_key, f"/{name}"),
                )
        if (
            self.nomination_evidence_ref is not None
            and self.complete_base_evidence_ref is None
        ):
            raise _invalid("/nomination_evidence_ref")
        if (
            self.extension_evidence_ref is not None
            and self.nomination_evidence_ref is None
        ):
            raise _invalid("/extension_evidence_ref")
        if (
            self.promotion_evidence_ref is not None
            and self.extension_evidence_ref is None
        ):
            raise _invalid("/promotion_evidence_ref")
        object.__setattr__(
            self,
            "remaining_requirement_refs",
            _definition_tuple(
                self.remaining_requirement_refs,
                MeasurementDefinitionKind.REMAINING_EVIDENCE_REQUIREMENT,
                policy_ref.challenge_key,
                "/remaining_requirement_refs",
            ),
        )
        _exact(self.stop_kind, ReconstructionStopKind, "/stop_kind")
        if self.stop_kind is ReconstructionStopKind.RECONSTRUCTION_EXECUTION_FAILURE:
            if self.reconstruction_failure_ref is None:
                raise _invalid("/reconstruction_failure_ref")
            object.__setattr__(
                self,
                "reconstruction_failure_ref",
                _definition(
                    self.reconstruction_failure_ref,
                    MeasurementDefinitionKind.RECONSTRUCTION_EXECUTION_FAILURE,
                    policy_ref.challenge_key,
                    "/reconstruction_failure_ref",
                ),
            )
        elif self.reconstruction_failure_ref is not None:
            raise _invalid("/reconstruction_failure_ref")


@dataclass(frozen=True, slots=True)
class ReconstructionEvidenceStatus:
    stage: ReconstructionEvidenceStage
    outcome: ReconstructionEvidenceOutcome
    remaining_requirement_refs: tuple[MeasurementDefinitionRef, ...]
    resource_receipt_ref: ObservedResourceReceiptRef | None


def assess_reconstruction_evidence(
    policy: ReconstructionEvidencePolicy,
    evidence: ReconstructionEvidenceInput,
) -> ReconstructionEvidenceStatus:
    """Classify fixture evidence without turning resource facts into science."""

    policy = _exact(policy, ReconstructionEvidencePolicy, "/policy")
    evidence = _exact(evidence, ReconstructionEvidenceInput, "/evidence")
    from .canonical import measurement_ref

    if evidence.policy_ref != measurement_ref(policy):
        raise _invalid("/policy_ref", MeasurementInputCode.DIGEST_MISMATCH)
    if evidence.construction_family_ref != policy.construction_family_ref:
        raise _invalid("/construction_family_ref", MeasurementInputCode.ROLE_CONFUSION)

    complete_build = type(evidence.resource_facts.build_completion) is CompleteBuild
    base_complete = complete_build and evidence.complete_base_evidence_ref is not None
    stage = ReconstructionEvidenceStage.BASE_REQUIRED
    if base_complete:
        stage = ReconstructionEvidenceStage.BASE_COMPLETE
        if evidence.nomination_evidence_ref is not None:
            stage = ReconstructionEvidenceStage.NOMINATED
            if (
                evidence.extension_evidence_ref is not None
                and type(evidence.resource_facts.reconstruction_replicate)
                is BoundReconstructionReplicate
            ):
                stage = ReconstructionEvidenceStage.EXTENDED
                if (
                    evidence.promotion_evidence_ref is not None
                    and not evidence.remaining_requirement_refs
                ):
                    stage = ReconstructionEvidenceStage.PROMOTION_ELIGIBLE

    status_args = (
        stage,
        evidence.remaining_requirement_refs,
        evidence.resource_facts.observed_receipt_ref,
    )
    if (
        evidence.resource_facts.resource_stop_cause
        is ResourceStopCause.INFRASTRUCTURE_FAILURE
    ):
        return ReconstructionEvidenceStatus(
            status_args[0],
            ReconstructionEvidenceOutcome.INFRASTRUCTURE_FAILURE,
            *status_args[1:],
        )
    if evidence.stop_kind is ReconstructionStopKind.RECONSTRUCTION_EXECUTION_FAILURE:
        return ReconstructionEvidenceStatus(
            status_args[0],
            ReconstructionEvidenceOutcome.RECONSTRUCTION_FAILURE,
            *status_args[1:],
        )
    if (
        evidence.stop_kind is ReconstructionStopKind.SCIENTIFIC_EVIDENCE_EXHAUSTED
        and base_complete
        and policy.has_complete_human_authority
    ):
        return ReconstructionEvidenceStatus(
            status_args[0],
            ReconstructionEvidenceOutcome.INDETERMINATE_INSUFFICIENT_EVIDENCE,
            *status_args[1:],
        )
    non_scientific_resource_stop = (
        evidence.resource_facts.resource_stop_cause
        is not ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING
    )
    if (
        not policy.has_complete_human_authority
        or not base_complete
        or evidence.stop_kind is ReconstructionStopKind.HEURISTIC_FUTILITY
        or non_scientific_resource_stop
        or evidence.remaining_requirement_refs
    ):
        return ReconstructionEvidenceStatus(
            status_args[0],
            ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED,
            *status_args[1:],
        )
    return ReconstructionEvidenceStatus(
        status_args[0],
        ReconstructionEvidenceOutcome.STAGE_ESTABLISHED,
        *status_args[1:],
    )


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


@dataclass(frozen=True, slots=True)
class ScorePackInputBinding:
    """One exact qualified measurement-output ownership of one A5 input key."""

    measurement_contract_ref: MeasurementContractRef
    measurement_output_ref: MeasurementDefinitionRef
    input_key: str
    scalar_kind: ScoreScalarKind
    use_role: ScoreUseRole
    estimand_ref: MeasurementDefinitionRef
    case_scope_ref: MeasurementDefinitionRef
    stratum_ref: MeasurementDefinitionRef
    uncertainty_policy_ref: UncertaintyPolicyRef
    admissibility_policy_ref: MeasurementDefinitionRef
    admissibility_evidence_ref: MeasurementDefinitionRef
    aggregation_role: ScoreAggregationRole
    ranking_role: ScoreRankingRole
    disclosure_class: ScoreDisclosureClass
    eligibility_role: ScoreEligibilityRole
    disclosure_policy_ref: MeasurementDefinitionRef
    destination_kind: A5DestinationKind
    destination_id: str
    applicability_evidence_ref: MeasurementDefinitionRef
    qualification_ref: MeasurementDefinitionRef
    provenance_ref: MeasurementDefinitionRef
    fixture_origin: bool

    def __post_init__(self) -> None:
        contract_ref = _exact(
            self.measurement_contract_ref,
            MeasurementContractRef,
            "/measurement_contract_ref",
        )
        challenge_key = contract_ref.challenge_key
        for name, kind in (
            ("measurement_output_ref", MeasurementDefinitionKind.MEASUREMENT_OUTPUT),
            ("estimand_ref", MeasurementDefinitionKind.ESTIMAND),
            ("case_scope_ref", MeasurementDefinitionKind.CASE_SCOPE),
            ("stratum_ref", MeasurementDefinitionKind.STRATUM),
            (
                "admissibility_policy_ref",
                MeasurementDefinitionKind.SCORE_ADMISSIBILITY_POLICY,
            ),
            (
                "admissibility_evidence_ref",
                MeasurementDefinitionKind.SCORE_ADMISSIBILITY_EVIDENCE,
            ),
            (
                "disclosure_policy_ref",
                MeasurementDefinitionKind.SCORE_DISCLOSURE_POLICY,
            ),
            (
                "applicability_evidence_ref",
                MeasurementDefinitionKind.APPLICABILITY_EVIDENCE,
            ),
            ("qualification_ref", MeasurementDefinitionKind.DOSSIER_QUALIFICATION),
            ("provenance_ref", MeasurementDefinitionKind.EVIDENCE_SOURCE),
        ):
            object.__setattr__(
                self,
                name,
                _definition(getattr(self, name), kind, challenge_key, f"/{name}"),
            )
        uncertainty_ref = _exact(
            self.uncertainty_policy_ref,
            UncertaintyPolicyRef,
            "/uncertainty_policy_ref",
        )
        _same_challenge(
            uncertainty_ref.challenge_key, challenge_key, "/uncertainty_policy_ref"
        )
        object.__setattr__(self, "input_key", _identifier(self.input_key, "/input_key"))
        object.__setattr__(
            self, "destination_id", _identifier(self.destination_id, "/destination_id")
        )
        _exact(self.scalar_kind, ScoreScalarKind, "/scalar_kind")
        _exact(self.use_role, ScoreUseRole, "/use_role")
        _exact(self.aggregation_role, ScoreAggregationRole, "/aggregation_role")
        _exact(self.ranking_role, ScoreRankingRole, "/ranking_role")
        _exact(self.disclosure_class, ScoreDisclosureClass, "/disclosure_class")
        _exact(self.eligibility_role, ScoreEligibilityRole, "/eligibility_role")
        _exact(self.destination_kind, A5DestinationKind, "/destination_kind")
        expected = {
            ScoreUseRole.MANDATORY_GATE: (
                {ScoreAggregationRole.MANDATORY_ADMISSIBILITY},
                {ScoreRankingRole.ADMISSIBILITY_ONLY},
                {A5DestinationKind.MANDATORY_GATE},
                {ScoreEligibilityRole.MANDATORY_ADMISSIBILITY},
            ),
            ScoreUseRole.SOFT_COMPONENT: (
                {
                    ScoreAggregationRole.PHYSICS,
                    ScoreAggregationRole.ROBUSTNESS_MEAN,
                    ScoreAggregationRole.ROBUSTNESS_TAIL,
                    ScoreAggregationRole.ACCURACY,
                },
                {ScoreRankingRole.RANKING_INPUT},
                {
                    A5DestinationKind.PHYSICS_COMPONENT,
                    A5DestinationKind.ROBUSTNESS_MEAN,
                    A5DestinationKind.ROBUSTNESS_TAIL,
                    A5DestinationKind.ACCURACY_COMPONENT,
                },
                {ScoreEligibilityRole.ELIGIBLE_AFTER_MANDATORY_ADMISSIBILITY},
            ),
            ScoreUseRole.DIAGNOSTIC: (
                {ScoreAggregationRole.NONE},
                {ScoreRankingRole.NON_RANKING_DIAGNOSTIC},
                {A5DestinationKind.DIAGNOSTIC_GATE},
                {ScoreEligibilityRole.NON_SCORE_DIAGNOSTIC},
            ),
        }[self.use_role]
        if (
            self.aggregation_role not in expected[0]
            or self.ranking_role not in expected[1]
            or self.destination_kind not in expected[2]
            or self.eligibility_role not in expected[3]
        ):
            raise _invalid("/use_role", MeasurementInputCode.ROLE_CONFUSION)
        destination_aggregation = {
            A5DestinationKind.PHYSICS_COMPONENT: ScoreAggregationRole.PHYSICS,
            A5DestinationKind.ROBUSTNESS_MEAN: ScoreAggregationRole.ROBUSTNESS_MEAN,
            A5DestinationKind.ROBUSTNESS_TAIL: ScoreAggregationRole.ROBUSTNESS_TAIL,
            A5DestinationKind.ACCURACY_COMPONENT: ScoreAggregationRole.ACCURACY,
        }
        required_aggregation = destination_aggregation.get(self.destination_kind)
        if (
            required_aggregation is not None
            and self.aggregation_role is not required_aggregation
        ):
            raise _invalid("/aggregation_role", MeasurementInputCode.ROLE_CONFUSION)
        object.__setattr__(
            self, "fixture_origin", _boolean(self.fixture_origin, "/fixture_origin")
        )


_SCORE_POLICY_AUTHORITY_FIELDS = (
    ("threshold_authority_binding", MeasurementDefinitionKind.SCORE_THRESHOLD_POLICY),
    ("transform_authority_binding", MeasurementDefinitionKind.SCORE_TRANSFORM_POLICY),
    ("weight_authority_binding", MeasurementDefinitionKind.SCORE_WEIGHT_POLICY),
)


@dataclass(frozen=True, slots=True)
class ScorePackAuthoringContract:
    """Content-addressed B-05 binding to one exact fixture A5 Score Pack."""

    challenge_key: ChallengeKey
    contract_id: str
    contract_version: str
    score_pack_pin: ScorePackPin
    input_bindings: tuple[ScorePackInputBinding, ...]
    threshold_authority_binding: UncertaintyComponentBinding
    transform_authority_binding: UncertaintyComponentBinding
    weight_authority_binding: UncertaintyComponentBinding
    fixture_origin: bool
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    RECORD_TYPE = "score_pack_authoring_contract"

    def __post_init__(self) -> None:
        if type(self) is not ScorePackAuthoringContract:
            raise _invalid("/record_type", MeasurementInputCode.WRONG_TYPE)
        challenge_key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(
            self, "contract_id", _identifier(self.contract_id, "/contract_id")
        )
        object.__setattr__(
            self,
            "contract_version",
            _version(self.contract_version, "/contract_version"),
        )
        pin = _exact(self.score_pack_pin, ScorePackPin, "/score_pack_pin")
        _same_challenge(
            pin.challenge_key, challenge_key, "/score_pack_pin/challenge_key"
        )
        if type(self.input_bindings) is not tuple or not self.input_bindings:
            raise _invalid("/input_bindings", MeasurementInputCode.WRONG_TYPE)
        if len(self.input_bindings) > MAX_CANONICAL_TUPLE_ITEMS:
            raise _invalid("/input_bindings")
        bindings = tuple(
            _exact(item, ScorePackInputBinding, f"/input_bindings/{index}")
            for index, item in enumerate(self.input_bindings)
        )
        for index, binding in enumerate(bindings):
            _same_challenge(
                binding.measurement_contract_ref.challenge_key,
                challenge_key,
                f"/input_bindings/{index}/measurement_contract_ref",
            )
            if binding.fixture_origin != pin.fixture_origin:
                raise _invalid(
                    f"/input_bindings/{index}/fixture_origin",
                    MeasurementInputCode.FIXTURE_REQUIRED,
                )
        if len({item.input_key for item in bindings}) != len(bindings):
            raise _invalid("/input_bindings", MeasurementInputCode.DUPLICATE_IDENTITY)
        destinations = tuple(
            (item.destination_kind, item.destination_id) for item in bindings
        )
        if len(set(destinations)) != len(destinations):
            raise _invalid("/input_bindings", MeasurementInputCode.DUPLICATE_IDENTITY)
        object.__setattr__(
            self,
            "input_bindings",
            tuple(sorted(bindings, key=lambda item: item.input_key)),
        )
        for name, expected_kind in _SCORE_POLICY_AUTHORITY_FIELDS:
            binding = _exact(
                getattr(self, name), UncertaintyComponentBinding, f"/{name}"
            )
            if binding.state is ScientificValueState.NOT_APPLICABLE:
                raise _invalid(f"/{name}/state")
            if binding.component_ref is not None:
                _same_challenge(
                    binding.component_ref.challenge_key,
                    challenge_key,
                    f"/{name}/component_ref",
                )
                if binding.component_ref.definition_kind is not expected_kind:
                    raise _invalid(
                        f"/{name}/component_ref",
                        MeasurementInputCode.ROLE_CONFUSION,
                    )
        fixture_origin = _boolean(self.fixture_origin, "/fixture_origin")
        if fixture_origin != pin.fixture_origin:
            raise _invalid("/fixture_origin", MeasurementInputCode.FIXTURE_REQUIRED)
        object.__setattr__(self, "fixture_origin", fixture_origin)
        if (
            self.schema_version != MEASUREMENT_SCHEMA_VERSION
            or self.canonicalization_profile != MEASUREMENT_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")

    @property
    def has_complete_score_policy_authority(self) -> bool:
        """Whether threshold, transform, and weight authority is exact."""

        return all(
            getattr(self, name).state is ScientificValueState.BOUND
            for name, _ in _SCORE_POLICY_AUTHORITY_FIELDS
        )


MeasurementAuthoringObject = (
    MeasurementContract
    | MeasurementQualificationEvidence
    | UncertaintyPolicy
    | ReconstructionEvidencePolicy
    | ScorePackAuthoringContract
)


__all__ = (
    "DependenceShortcutBinding",
    "MeasurementAuthoringObject",
    "MeasurementContract",
    "MeasurementEvidenceItem",
    "MeasurementQualificationEvidence",
    "ReconstructionEvidenceInput",
    "ReconstructionEvidencePolicy",
    "ReconstructionEvidenceStatus",
    "ReconstructionResourceFacts",
    "ScientificValueBinding",
    "ScorePackAuthoringContract",
    "ScorePackInputBinding",
    "StratumApplicabilityBinding",
    "StratumEvidenceMinimumBinding",
    "UncertaintyComponentBinding",
    "UncertaintyPolicy",
    "UncertaintyPolicyBinding",
    "assess_reconstruction_evidence",
)
