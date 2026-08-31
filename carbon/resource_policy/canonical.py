"""Closed B-02C resource-policy canonical adapters and document framing."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

from carbon.authoring.canonical import (
    CanonicalBytes,
    CanonicalFloat64,
    CanonicalInt64,
    CanonicalNominalRef,
    CanonicalRecord,
    CanonicalText,
    CanonicalTuple,
    CanonicalUInt64,
    CanonicalUnion,
    CanonicalValue,
    challenge_key_from_canonical,
    challenge_key_to_canonical,
    decode_value,
    encode_value,
    owner_ref_from_canonical,
    owner_ref_to_canonical,
    tagged_sha256,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import (
    MAX_CANONICAL_DOCUMENT_BYTES,
    validate_version_token,
)
from carbon.authoring.refs import is_owner_ref
from carbon.construction.canonical import (
    construction_ref_from_canonical,
    construction_ref_to_canonical,
)
from carbon.construction.canonical import (
    from_canonical_value as construction_from_canonical_value,
)
from carbon.construction.canonical import (
    to_canonical_value as construction_to_canonical_value,
)
from carbon.construction.errors import ConstructionError
from carbon.construction.model import (
    CompilerIdentity,
    EnvironmentPin,
    StaticResourceDimension,
    StaticResourceRequirement,
)
from carbon.construction.refs import (
    CONSTRUCTION_REF_TYPES,
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
    ResolvedConstructionPlanRef,
    is_construction_ref,
)
from carbon.registry import ChallengeKey

from . import model as m
from .errors import (
    ResourcePolicyCanonicalDecodingError,
    ResourcePolicyCanonicalEncodingError,
    ResourcePolicyInputCode,
    ResourcePolicyInputRejected,
    ResourcePolicyReferenceMismatchError,
)
from .refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_REF_TYPES,
    RESOURCE_POLICY_SCHEMA_VERSION,
    FixtureResourceDecisionRef,
    ObservedResourceReceiptRef,
    ResearchResourcePolicyRef,
    ResourceCancellationRecordRef,
    ResourceClassRef,
    StaticResourceAssessmentRef,
    _make_resource_policy_ref,
    is_resource_policy_ref,
    resource_policy_ref_from_canonical,
    resource_policy_ref_to_canonical,
    verify_resource_policy_ref,
)

RESOURCE_POLICY_DOCUMENT_HEADER = b"carbon.resource_policy.canonical.v1\x00"
RESOURCE_POLICY_OBJECT_KINDS = (
    "resource_class",
    "research_resource_policy",
    "static_resource_assessment",
    "fixture_resource_availability",
    "fixture_resource_decision",
    "resource_enforcement_event",
    "resource_enforcement_result",
    "resource_cancellation_record",
    "observed_resource_receipt",
)


@dataclass(frozen=True, slots=True)
class DecodedResourcePolicyDocument:
    """One validated B-02C frame and its exact canonical record."""

    object_kind: str
    schema_version: str
    record: CanonicalRecord

    def __post_init__(self) -> None:
        if type(self) is not DecodedResourcePolicyDocument:
            raise ResourcePolicyCanonicalDecodingError(path="/type")


class _Schema(NamedTuple):
    record_type: str
    fields: tuple[tuple[str, object], ...]
    union_tag: str | None = None


_TEXT = "TEXT"
_BOOL = "BOOL"
_UINT64 = "UINT64"
_CHALLENGE_KEY = "CHALLENGE_KEY"


def _enum(enum_type: type) -> tuple[str, type]:
    return ("ENUM", enum_type)


def _model(model_type: type) -> tuple[str, type]:
    return ("MODEL", model_type)


def _union(*model_types: type) -> tuple[str, tuple[type, ...]]:
    return ("UNION", model_types)


def _tuple_of(
    descriptor: object, *, set_like: bool = False
) -> tuple[str, object, bool]:
    return ("TUPLE", descriptor, set_like)


def _owner(kind: str) -> tuple[str, str]:
    return ("OWNER", kind)


def _construction(expected_type: type) -> tuple[str, type]:
    return ("CONSTRUCTION", expected_type)


def _resource_ref(expected_type: type) -> tuple[str, type]:
    return ("RESOURCE_REF", expected_type)


def _tagged(tag: str, descriptor: object) -> tuple[str, str, object]:
    return ("TAGGED", tag, descriptor)


def _closed_union(
    *variants: tuple[type, str, object],
) -> tuple[str, tuple[tuple[type, str, object], ...]]:
    return ("CLOSED_UNION", variants)


def _schema(
    record_type: str,
    *fields: tuple[str, object],
    tag: str | None = None,
) -> _Schema:
    return _Schema(record_type, fields, tag)


_SCHEMAS: MappingProxyType[type, _Schema] = MappingProxyType(
    {
        m.FixtureResourceProvenance: _schema(
            "fixture_resource_provenance",
            ("fixture_registration_ref", _owner("fixture_registration")),
            (
                "source_provenance_refs",
                _tuple_of(_owner("provenance"), set_like=True),
            ),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
        m.FixturePracticeResourceContext: _schema(
            "fixture_practice_resource_context",
            ("challenge_key", _CHALLENGE_KEY),
            ("context_id", _TEXT),
            ("fixture_registration_ref", _owner("fixture_registration")),
            ("internal_service_scope_ref", _owner("internal_service_scope")),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
            tag="FIXTURE_PRACTICE",
        ),
        m.FixtureOfficialShapedResourceContext: _schema(
            "fixture_official_shaped_resource_context",
            ("challenge_key", _CHALLENGE_KEY),
            ("context_id", _TEXT),
            ("fixture_registration_ref", _owner("fixture_registration")),
            ("internal_service_scope_ref", _owner("internal_service_scope")),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
            tag="FIXTURE_OFFICIAL_SHAPED",
        ),
        m.DeclaredResourceCeiling: _schema(
            "declared_resource_ceiling",
            ("dimension_id", _TEXT),
            ("unit_ref", _owner("unit")),
            ("maximum_quantity", _UINT64),
        ),
        m.ResourceObservationMetric: _schema(
            "resource_observation_metric",
            ("metric_id", _TEXT),
            ("unit_ref", _owner("unit")),
            ("observation_role", _enum(m.ResourceObservationRole)),
        ),
        m.ObservedResourceQuantity: _schema(
            "observed_resource_quantity",
            ("metric_id", _TEXT),
            ("unit_ref", _owner("unit")),
            ("quantity", _UINT64),
            ("observation_role", _enum(m.ResourceObservationRole)),
        ),
        m.ObservedMetricObserved: _schema(
            "observed_metric_observed",
            ("observed_quantity", _model(m.ObservedResourceQuantity)),
            tag="OBSERVED",
        ),
        m.ObservedMetricUnavailable: _schema(
            "observed_metric_unavailable",
            ("reason", _enum(m.ObservationUnavailableReason)),
            tag="UNAVAILABLE",
        ),
        m.OperationalRequirementRequired: _schema(
            "operational_requirement_required",
            tag="REQUIRED",
        ),
        m.OperationalRequirementNotApplicable: _schema(
            "operational_requirement_not_applicable",
            ("reason_ref", _owner("applicability_reason")),
            tag="NOT_APPLICABLE",
        ),
        m.OperationalReadinessRequirements: _schema(
            "operational_readiness_requirements",
            (
                "validator_capacity",
                _union(
                    m.OperationalRequirementRequired,
                    m.OperationalRequirementNotApplicable,
                ),
            ),
            (
                "reconstruction_funding",
                _union(
                    m.OperationalRequirementRequired,
                    m.OperationalRequirementNotApplicable,
                ),
            ),
            (
                "queue_availability",
                _union(
                    m.OperationalRequirementRequired,
                    m.OperationalRequirementNotApplicable,
                ),
            ),
            (
                "evidence_budget_availability",
                _union(
                    m.OperationalRequirementRequired,
                    m.OperationalRequirementNotApplicable,
                ),
            ),
        ),
        m.RuntimeResourceLimit: _schema(
            "runtime_resource_limit",
            ("limit_id", _TEXT),
            ("metric_id", _TEXT),
            ("unit_ref", _owner("unit")),
            ("maximum_quantity", _UINT64),
            ("enforcement_point", _enum(m.EnforcementPoint)),
            ("enforcement_mode", _enum(m.EnforcementMode)),
        ),
        m.ResourceEnforcementObservation: _schema(
            "resource_enforcement_observation",
            ("metric_quantity", _model(m.ObservedResourceQuantity)),
            ("observation_kind", _enum(m.EnforcementObservationKind)),
        ),
        m.ResourcePolicyIssue: _schema(
            "resource_policy_issue",
            ("code", _enum(m.ResourcePolicyIssueCode)),
            ("message", _TEXT),
            ("path", _TEXT),
        ),
    }
)

_SCHEMAS = MappingProxyType(
    {
        **dict(_SCHEMAS),
        m.ResourceClass: _schema(
            "resource_class",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("object_id", _TEXT),
            ("object_version", _TEXT),
            ("execution_environment_pin", _construction(EnvironmentPin)),
            (
                "required_plan_environment_pins",
                _tuple_of(_construction(EnvironmentPin), set_like=True),
            ),
            (
                "supported_dimensions",
                _tuple_of(_construction(StaticResourceDimension), set_like=True),
            ),
            (
                "observation_metrics",
                _tuple_of(_model(m.ResourceObservationMetric), set_like=True),
            ),
            ("provenance", _model(m.FixtureResourceProvenance)),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
        m.ResourceClassPolicyBinding: _schema(
            "resource_class_policy_binding",
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            (
                "ceilings",
                _tuple_of(_model(m.DeclaredResourceCeiling), set_like=True),
            ),
            ("supported_impact_tags", _tuple_of(_TEXT, set_like=True)),
            (
                "runtime_limits",
                _tuple_of(_model(m.RuntimeResourceLimit), set_like=True),
            ),
            (
                "readiness_requirements",
                _model(m.OperationalReadinessRequirements),
            ),
        ),
        m.ResearchResourcePolicy: _schema(
            "research_resource_policy",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("object_id", _TEXT),
            ("object_version", _TEXT),
            (
                "candidate_assembly_ref",
                _construction(CandidateAssemblyContractRef),
            ),
            ("parameter_catalog_ref", _construction(ParameterCatalogRef)),
            ("compiler_identity", _construction(CompilerIdentity)),
            (
                "authority_context",
                _union(
                    m.FixturePracticeResourceContext,
                    m.FixtureOfficialShapedResourceContext,
                ),
            ),
            (
                "class_bindings",
                _tuple_of(_model(m.ResourceClassPolicyBinding), set_like=True),
            ),
            ("policy_authority_ref", _owner("policy_authority")),
            ("provenance", _model(m.FixtureResourceProvenance)),
            ("unknown_or_invalid_policy", _enum(m.UnknownOrInvalidPolicy)),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
        m.StaticResourceAssessment: _schema(
            "static_resource_assessment",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            (
                "expected_active_policy_ref",
                _resource_ref(ResearchResourcePolicyRef),
            ),
            (
                "expected_active_resource_class_ref",
                _resource_ref(ResourceClassRef),
            ),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            (
                "authority_context",
                _union(
                    m.FixturePracticeResourceContext,
                    m.FixtureOfficialShapedResourceContext,
                ),
            ),
            (
                "static_resource_requirements",
                _tuple_of(_construction(StaticResourceRequirement)),
            ),
            ("resource_impact_tags", _tuple_of(_TEXT, set_like=True)),
            ("outcome", _enum(m.StaticAssessmentOutcome)),
            ("issues", _tuple_of(_model(m.ResourcePolicyIssue))),
            ("epistemic_layer", _enum(m.ResourceEpistemicLayer)),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
        m.NoAvailabilityInput: _schema(
            "fixture_availability_input_none",
            tag="NO_AVAILABILITY_INPUT",
        ),
        m.FixtureResourceAvailability: _schema(
            "fixture_resource_availability",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            (
                "authority_context",
                _union(
                    m.FixturePracticeResourceContext,
                    m.FixtureOfficialShapedResourceContext,
                ),
            ),
            ("validator_capacity", _enum(m.FixtureAvailabilityState)),
            ("reconstruction_funding", _enum(m.FixtureAvailabilityState)),
            ("queue_availability", _enum(m.FixtureAvailabilityState)),
            (
                "evidence_budget_availability",
                _enum(m.FixtureAvailabilityState),
            ),
            ("fixture_registration_ref", _owner("fixture_registration")),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
        m.FixtureResourceDecision: _schema(
            "fixture_resource_decision",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("assessment_ref", _resource_ref(StaticResourceAssessmentRef)),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            (
                "authority_context",
                _union(
                    m.FixturePracticeResourceContext,
                    m.FixtureOfficialShapedResourceContext,
                ),
            ),
            (
                "availability_input",
                _closed_union(
                    (
                        m.NoAvailabilityInput,
                        "NO_AVAILABILITY_INPUT",
                        _model(m.NoAvailabilityInput),
                    ),
                    (
                        m.FixtureResourceAvailability,
                        "PROVIDED",
                        _model(m.FixtureResourceAvailability),
                    ),
                ),
            ),
            ("outcome", _enum(m.FixtureDecisionOutcome)),
            (
                "deferral_causes",
                _tuple_of(_enum(m.ResourceDeferralCause), set_like=True),
            ),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
        m.NoIssue: _schema(
            "resource_enforcement_issue_none",
            tag="NO_ISSUE",
        ),
        m.ResourceEnforcementEvent: _schema(
            "resource_enforcement_event",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            ("assessment_ref", _resource_ref(StaticResourceAssessmentRef)),
            ("decision_ref", _resource_ref(FixtureResourceDecisionRef)),
            (
                "authority_context",
                _union(
                    m.FixturePracticeResourceContext,
                    m.FixtureOfficialShapedResourceContext,
                ),
            ),
            ("limit_id", _TEXT),
            ("enforcement_point", _enum(m.EnforcementPoint)),
            ("enforcement_mode", _enum(m.EnforcementMode)),
            ("maximum_quantity", _UINT64),
            ("observation", _model(m.ResourceEnforcementObservation)),
            ("action", _enum(m.ResourceEnforcementAction)),
            ("outcome", _enum(m.ResourceEnforcementOutcome)),
            (
                "issue",
                _closed_union(
                    (m.NoIssue, "NO_ISSUE", _model(m.NoIssue)),
                    (m.ResourcePolicyIssue, "ISSUE", _model(m.ResourcePolicyIssue)),
                ),
            ),
        ),
        m.ResourceEnforcementResult: _schema(
            "resource_enforcement_result",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            ("assessment_ref", _resource_ref(StaticResourceAssessmentRef)),
            ("decision_ref", _resource_ref(FixtureResourceDecisionRef)),
            (
                "authority_context",
                _union(
                    m.FixturePracticeResourceContext,
                    m.FixtureOfficialShapedResourceContext,
                ),
            ),
            ("event", _model(m.ResourceEnforcementEvent)),
            ("outcome", _enum(m.ResourceEnforcementOutcome)),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
        m.PolicyEnforcerActor: _schema(
            "cancellation_actor_policy_enforcer",
            ("policy_authority_ref", _owner("policy_authority")),
            tag="POLICY_ENFORCER",
        ),
        m.FixtureRequesterActor: _schema(
            "cancellation_actor_fixture_requester",
            ("fixture_registration_ref", _owner("fixture_registration")),
            tag="FIXTURE_REQUESTER",
        ),
        m.InfrastructureActor: _schema(
            "cancellation_actor_infrastructure",
            ("infrastructure_failure_ref", _owner("infrastructure_failure")),
            tag="INFRASTRUCTURE",
        ),
        m.NoEnforcementPoint: _schema(
            "stop_point_none",
            tag="NO_ENFORCEMENT_POINT",
        ),
        m.AtEnforcementPoint: _schema(
            "stop_point_at",
            ("enforcement_point", _enum(m.EnforcementPoint)),
            tag="AT",
        ),
        m.NoEnforcementEvent: _schema(
            "enforcement_event_binding_none",
            tag="NO_ENFORCEMENT_EVENT",
        ),
        m.ResourceCancellationRecord: _schema(
            "resource_cancellation_record",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            ("assessment_ref", _resource_ref(StaticResourceAssessmentRef)),
            (
                "fixture_decision_ref",
                _resource_ref(FixtureResourceDecisionRef),
            ),
            (
                "authority_context",
                _union(
                    m.FixturePracticeResourceContext,
                    m.FixtureOfficialShapedResourceContext,
                ),
            ),
            (
                "stop_point",
                _union(m.NoEnforcementPoint, m.AtEnforcementPoint),
            ),
            (
                "actor",
                _union(
                    m.PolicyEnforcerActor,
                    m.FixtureRequesterActor,
                    m.InfrastructureActor,
                ),
            ),
            ("reason", _enum(m.CancellationReason)),
            (
                "enforcement_event_binding",
                _closed_union(
                    (
                        m.NoEnforcementEvent,
                        "NO_ENFORCEMENT_EVENT",
                        _model(m.NoEnforcementEvent),
                    ),
                    (
                        m.ResourceEnforcementEvent,
                        "ENFORCEMENT_EVENT",
                        _model(m.ResourceEnforcementEvent),
                    ),
                ),
            ),
            ("work_started", _BOOL),
            (
                "observed_resource_quantities_so_far",
                _tuple_of(_model(m.ObservedResourceQuantity), set_like=True),
            ),
            ("resulting_state", _enum(m.CancellationResultingState)),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
    }
)

_SCHEMAS = MappingProxyType(
    {
        **dict(_SCHEMAS),
        m.IncompleteBuildIdentity: _schema(
            "incomplete_build_identity",
            ("challenge_key", _CHALLENGE_KEY),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            ("execution_environment_pin", _construction(EnvironmentPin)),
            ("build_attempt_id", _TEXT),
            ("build_attempt_digest", _TEXT),
        ),
        m.CompleteBuildIdentity: _schema(
            "complete_build_identity",
            ("challenge_key", _CHALLENGE_KEY),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            ("execution_environment_pin", _construction(EnvironmentPin)),
            ("build_attempt_id", _TEXT),
            ("complete_build_digest", _TEXT),
        ),
        m.NoBuildStarted: _schema(
            "build_completion_none",
            tag="NO_BUILD_STARTED",
        ),
        m.IncompleteBuild: _schema(
            "build_completion_incomplete",
            ("build_identity", _model(m.IncompleteBuildIdentity)),
            tag="INCOMPLETE",
        ),
        m.CompleteBuild: _schema(
            "build_completion_complete",
            ("build_identity", _model(m.CompleteBuildIdentity)),
            tag="COMPLETE",
        ),
        m.NoReuse: _schema(
            "artifact_reuse_none",
            tag="NO_REUSE",
        ),
        m.FrozenArtifactReuseWindow: _schema(
            "frozen_artifact_reuse_window",
            ("window_id", _TEXT),
            ("complete_build_identity", _model(m.CompleteBuildIdentity)),
            ("reuse_policy_ref", _owner("restriction")),
            ("maximum_declared_uses", _UINT64),
            ("observed_use_ordinal", _UINT64),
        ),
        m.ReconstructionReplicateIdentity: _schema(
            "reconstruction_replicate_identity",
            ("challenge_key", _CHALLENGE_KEY),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            ("replicate_id", _TEXT),
            ("replicate_digest", _TEXT),
        ),
        m.IncompleteReconstructionReplicateIdentity: _schema(
            "incomplete_reconstruction_replicate_identity",
            ("challenge_key", _CHALLENGE_KEY),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            ("replicate_attempt_id", _TEXT),
            ("replicate_attempt_digest", _TEXT),
        ),
        m.ReplicateNotApplicable: _schema(
            "reconstruction_replicate_not_applicable",
            ("reason", _enum(m.ReplicateNotApplicableReason)),
            tag="NOT_APPLICABLE",
        ),
        m.IncompleteReconstructionReplicate: _schema(
            "reconstruction_replicate_incomplete",
            (
                "replicate_identity",
                _model(m.IncompleteReconstructionReplicateIdentity),
            ),
            tag="INCOMPLETE",
        ),
        m.BoundReconstructionReplicate: _schema(
            "reconstruction_replicate_bound",
            (
                "replicate_identity",
                _model(m.ReconstructionReplicateIdentity),
            ),
            tag="BOUND",
        ),
        m.NoResourceStop: _schema(
            "resource_stop_binding_none",
            tag="NO_RESOURCE_STOP",
        ),
        m.ObservedResourceReceipt: _schema(
            "observed_resource_receipt",
            ("object_kind", _TEXT),
            ("schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
            ("challenge_key", _CHALLENGE_KEY),
            ("policy_ref", _resource_ref(ResearchResourcePolicyRef)),
            ("resource_class_ref", _resource_ref(ResourceClassRef)),
            (
                "construction_plan_ref",
                _construction(ResolvedConstructionPlanRef),
            ),
            ("assessment_ref", _resource_ref(StaticResourceAssessmentRef)),
            (
                "fixture_decision_ref",
                _resource_ref(FixtureResourceDecisionRef),
            ),
            (
                "authority_context",
                _union(
                    m.FixturePracticeResourceContext,
                    m.FixtureOfficialShapedResourceContext,
                ),
            ),
            (
                "build_completion",
                _union(m.NoBuildStarted, m.IncompleteBuild, m.CompleteBuild),
            ),
            (
                "frozen_artifact_reuse",
                _closed_union(
                    (m.NoReuse, "NO_REUSE", _model(m.NoReuse)),
                    (
                        m.FrozenArtifactReuseWindow,
                        "REUSE",
                        _model(m.FrozenArtifactReuseWindow),
                    ),
                ),
            ),
            (
                "reconstruction_replicate",
                _union(
                    m.ReplicateNotApplicable,
                    m.IncompleteReconstructionReplicate,
                    m.BoundReconstructionReplicate,
                ),
            ),
            (
                "observed_consumption_quantities",
                _tuple_of(_model(m.ObservedResourceQuantity), set_like=True),
            ),
            (
                "observed_latency",
                _union(m.ObservedMetricObserved, m.ObservedMetricUnavailable),
            ),
            (
                "observed_cost",
                _union(m.ObservedMetricObserved, m.ObservedMetricUnavailable),
            ),
            ("evidence_stage_label", _enum(m.DeclaredResourceEvidenceStage)),
            ("stop_cause", _enum(m.ResourceStopCause)),
            (
                "stop_record_binding",
                _closed_union(
                    (
                        m.NoResourceStop,
                        "NO_RESOURCE_STOP",
                        _model(m.NoResourceStop),
                    ),
                    (
                        ResourceCancellationRecordRef,
                        "RESOURCE_STOP",
                        _resource_ref(ResourceCancellationRecordRef),
                    ),
                ),
            ),
            (
                "enforcement_event_binding",
                _closed_union(
                    (
                        m.NoEnforcementEvent,
                        "NO_ENFORCEMENT_EVENT",
                        _model(m.NoEnforcementEvent),
                    ),
                    (
                        m.ResourceEnforcementEvent,
                        "ENFORCEMENT_EVENT",
                        _model(m.ResourceEnforcementEvent),
                    ),
                ),
            ),
            ("work_started", _BOOL),
            ("epistemic_layer", _enum(m.ResourceEpistemicLayer)),
            ("authority_marker", _enum(m.ResourcePolicyAuthorityMarker)),
        ),
    }
)


_ENUM_TYPES = (
    m.ResourcePolicyAuthorityMarker,
    m.ResourceEpistemicLayer,
    m.UnknownOrInvalidPolicy,
    m.ResourceObservationRole,
    m.ObservationUnavailableReason,
    m.EnforcementPoint,
    m.EnforcementMode,
    m.EnforcementObservationKind,
    m.ResourcePolicyIssueCode,
    m.StaticAssessmentOutcome,
    m.FixtureAvailabilityState,
    m.FixtureDecisionOutcome,
    m.ResourceDeferralCause,
    m.ResourceEnforcementAction,
    m.ResourceEnforcementOutcome,
    m.CancellationReason,
    m.CancellationResultingState,
    m.ReplicateNotApplicableReason,
    m.DeclaredResourceEvidenceStage,
    m.ResourceStopCause,
)

_CANONICAL_VALUE_TYPES = (
    bool,
    CanonicalInt64,
    CanonicalUInt64,
    CanonicalFloat64,
    CanonicalText,
    CanonicalBytes,
    CanonicalTuple,
    CanonicalRecord,
    CanonicalUnion,
    CanonicalNominalRef,
)

_CONSTRUCTION_MODEL_TYPES = (
    CompilerIdentity,
    EnvironmentPin,
    StaticResourceDimension,
    StaticResourceRequirement,
)


def _encoding_error(path: str = "") -> ResourcePolicyCanonicalEncodingError:
    return ResourcePolicyCanonicalEncodingError(path=path)


def _decoding_error(
    path: str = "", *, trailing: bool = False
) -> ResourcePolicyCanonicalDecodingError:
    return ResourcePolicyCanonicalDecodingError(trailing=trailing, path=path)


def _canonical_text(value: object, path: str = "") -> CanonicalText:
    if type(value) is not str:
        raise _encoding_error(path)
    try:
        return CanonicalText(value)
    except AuthoringError as exc:
        raise _encoding_error(path) from exc


def _encode_field(descriptor: object, value: object, owner: object) -> CanonicalValue:
    if descriptor == _TEXT:
        return _canonical_text(value)
    if descriptor == _BOOL:
        if type(value) is not bool:
            raise _encoding_error()
        return value
    if descriptor == _UINT64:
        if type(value) is not int:
            raise _encoding_error()
        try:
            return CanonicalUInt64(value)
        except AuthoringError as exc:
            raise _encoding_error() from exc
    if descriptor == _CHALLENGE_KEY:
        try:
            return challenge_key_to_canonical(value)
        except AuthoringError as exc:
            raise _encoding_error("/challenge_key") from exc
    if type(descriptor) is not tuple or not descriptor:
        raise _encoding_error()
    kind = descriptor[0]
    if kind == "ENUM":
        enum_type = descriptor[1]
        if type(value) is not enum_type:
            raise _encoding_error()
        return _canonical_text(value.value)
    if kind == "MODEL":
        if type(value) is not descriptor[1]:
            raise _encoding_error()
        return _model_to_canonical(value)
    if kind == "UNION":
        if type(value) not in descriptor[1]:
            raise _encoding_error()
        return _model_to_canonical(value)
    if kind == "OWNER":
        if not is_owner_ref(value):
            raise _encoding_error()
        try:
            canonical = owner_ref_to_canonical(value)
        except AuthoringError as exc:
            raise _encoding_error() from exc
        if canonical.ref_type != descriptor[1]:
            raise _encoding_error()
        return canonical
    if kind == "CONSTRUCTION":
        expected_type = descriptor[1]
        if type(value) is not expected_type:
            raise _encoding_error()
        try:
            return construction_to_canonical_value(value)
        except (AuthoringError, ConstructionError) as exc:
            raise _encoding_error() from exc
    if kind == "RESOURCE_REF":
        expected_type = descriptor[1]
        if type(value) is not expected_type:
            raise _encoding_error()
        return resource_policy_ref_to_canonical(value)
    if kind == "TUPLE":
        if type(value) is not tuple:
            raise _encoding_error()
        item_descriptor, set_like = descriptor[1], descriptor[2]
        return CanonicalTuple(
            tuple(_encode_field(item_descriptor, item, owner) for item in value),
            set_like=set_like,
        )
    if kind == "TAGGED":
        return CanonicalUnion(
            descriptor[1],
            _encode_field(descriptor[2], value, owner),
        )
    if kind == "CLOSED_UNION":
        matches = tuple(item for item in descriptor[1] if type(value) is item[0])
        if len(matches) != 1:
            raise _encoding_error()
        _, tag, inner = matches[0]
        encoded = _encode_field(inner, value, owner)
        if type(encoded) is CanonicalUnion:
            if encoded.tag != tag:
                raise _encoding_error()
            return encoded
        return CanonicalUnion(tag, encoded)
    raise _encoding_error()


def _model_to_canonical(value: object) -> CanonicalRecord | CanonicalUnion:
    schema = _SCHEMAS.get(type(value))
    if schema is None:
        raise _encoding_error("/type")
    try:
        record = CanonicalRecord(
            schema.record_type,
            tuple(
                (
                    name,
                    _encode_field(
                        descriptor,
                        object.__getattribute__(value, name),
                        value,
                    ),
                )
                for name, descriptor in schema.fields
            ),
        )
        if schema.union_tag is not None:
            return CanonicalUnion(schema.union_tag, record)
        return record
    except ResourcePolicyInputRejected:
        raise
    except (
        AuthoringError,
        ConstructionError,
        AttributeError,
        TypeError,
        ValueError,
    ) as exc:
        raise _encoding_error() from exc


def to_canonical_value(value: object) -> CanonicalValue:
    """Adapt one exact closed B-02C/upstream value to the shared vocabulary."""

    if type(value) in _CANONICAL_VALUE_TYPES:
        return value
    if type(value) is str:
        return _canonical_text(value)
    if type(value) is tuple:
        return CanonicalTuple(tuple(to_canonical_value(item) for item in value))
    if type(value) in _ENUM_TYPES:
        return _canonical_text(value.value)
    if type(value) is ChallengeKey:
        try:
            return challenge_key_to_canonical(value)
        except AuthoringError as exc:
            raise _encoding_error("/challenge_key") from exc
    if is_owner_ref(value):
        try:
            return owner_ref_to_canonical(value)
        except AuthoringError as exc:
            raise _encoding_error() from exc
    if is_construction_ref(value):
        try:
            return construction_ref_to_canonical(value)
        except ConstructionError as exc:
            raise _encoding_error() from exc
    if is_resource_policy_ref(value):
        return resource_policy_ref_to_canonical(value)
    if type(value) in _CONSTRUCTION_MODEL_TYPES:
        try:
            return construction_to_canonical_value(value)
        except (AuthoringError, ConstructionError) as exc:
            raise _encoding_error() from exc
    if type(value) in _SCHEMAS:
        return _model_to_canonical(value)
    raise _encoding_error("/type")


def canonical_sort_key(value: object) -> bytes:
    """Return the complete canonical member bytes used by every set-like tuple."""

    try:
        return encode_value(to_canonical_value(value))
    except ResourcePolicyInputRejected:
        raise
    except (AuthoringError, ConstructionError, TypeError, ValueError) as exc:
        raise _encoding_error() from exc


def _require_text(value: object) -> str:
    if type(value) is not CanonicalText:
        raise _decoding_error()
    return value.value


def _decode_field(descriptor: object, value: object) -> object:
    if descriptor == _TEXT:
        return _require_text(value)
    if descriptor == _BOOL:
        if type(value) is not bool:
            raise _decoding_error()
        return value
    if descriptor == _UINT64:
        if type(value) is not CanonicalUInt64:
            raise _decoding_error()
        return value.value
    if descriptor == _CHALLENGE_KEY:
        try:
            return challenge_key_from_canonical(value)
        except AuthoringError as exc:
            raise _decoding_error("/challenge_key") from exc
    if type(descriptor) is not tuple or not descriptor:
        raise _decoding_error()
    kind = descriptor[0]
    if kind == "ENUM":
        text = _require_text(value)
        try:
            return descriptor[1](text)
        except (TypeError, ValueError) as exc:
            raise _decoding_error() from exc
    if kind == "MODEL":
        return _from_canonical_model(value, descriptor[1])
    if kind == "UNION":
        return _from_canonical_union(value, descriptor[1])
    if kind == "OWNER":
        try:
            return owner_ref_from_canonical(value, expected_kind=descriptor[1])
        except AuthoringError as exc:
            raise _decoding_error() from exc
    if kind == "CONSTRUCTION":
        expected_type = descriptor[1]
        try:
            if expected_type in CONSTRUCTION_REF_TYPES:
                return construction_ref_from_canonical(
                    value, expected_type=expected_type
                )
            return construction_from_canonical_value(value, expected_type)
        except (AuthoringError, ConstructionError) as exc:
            raise _decoding_error() from exc
    if kind == "RESOURCE_REF":
        try:
            return resource_policy_ref_from_canonical(
                value, expected_type=descriptor[1]
            )
        except ResourcePolicyInputRejected as exc:
            raise _decoding_error() from exc
    if kind == "TUPLE":
        if type(value) is not CanonicalTuple:
            raise _decoding_error()
        return tuple(_decode_field(descriptor[1], item) for item in value.items)
    if kind == "TAGGED":
        if type(value) is not CanonicalUnion or value.tag != descriptor[1]:
            raise _decoding_error()
        return _decode_field(descriptor[2], value.payload)
    if kind == "CLOSED_UNION":
        if type(value) is not CanonicalUnion:
            raise _decoding_error()
        matches = tuple(item for item in descriptor[1] if item[1] == value.tag)
        if len(matches) != 1:
            raise _decoding_error()
        expected_type, tag, inner = matches[0]
        target = value.payload
        if (
            type(inner) is tuple
            and inner
            and inner[0] == "MODEL"
            and _SCHEMAS[expected_type].union_tag == tag
        ):
            target = value
        result = _decode_field(inner, target)
        if type(result) is not expected_type:
            raise _decoding_error()
        return result
    raise _decoding_error()


def _record_for_schema(value: object, schema: _Schema) -> CanonicalRecord:
    if schema.union_tag is None:
        if type(value) is not CanonicalRecord:
            raise _decoding_error()
        record = value
    else:
        if (
            type(value) is not CanonicalUnion
            or value.tag != schema.union_tag
            or type(value.payload) is not CanonicalRecord
        ):
            raise _decoding_error()
        record = value.payload
    if record.record_type != schema.record_type:
        raise _decoding_error()
    if set(record.field_map()) != {name for name, _ in schema.fields}:
        raise _decoding_error()
    return record


def _from_canonical_model(value: object, expected_type: type) -> object:
    schema = _SCHEMAS.get(expected_type)
    if schema is None:
        raise _decoding_error("/type")
    record = _record_for_schema(value, schema)
    fields = record.field_map()
    kwargs = {
        name: _decode_field(descriptor, fields[name])
        for name, descriptor in schema.fields
    }
    try:
        result = expected_type(**kwargs)
    except (
        AuthoringError,
        ConstructionError,
        ResourcePolicyInputRejected,
        TypeError,
        ValueError,
    ) as exc:
        raise _decoding_error() from exc
    if type(result) is not expected_type:
        raise _decoding_error("/type")
    return result


def _from_canonical_union(value: object, allowed_types: tuple[type, ...]) -> object:
    if type(value) is not CanonicalUnion:
        raise _decoding_error()
    matches = tuple(
        model_type
        for model_type in allowed_types
        if _SCHEMAS[model_type].union_tag == value.tag
    )
    if len(matches) != 1:
        raise _decoding_error()
    return _from_canonical_model(value, matches[0])


def from_canonical_value(value: object, expected_type: type) -> object:
    """Reconstruct one exact registered value and reject nominal substitution."""

    if type(expected_type) is not type:
        raise TypeError("expected_type must be an exact class")
    if expected_type in RESOURCE_POLICY_REF_TYPES:
        result = resource_policy_ref_from_canonical(value, expected_type=expected_type)
    elif expected_type in CONSTRUCTION_REF_TYPES:
        try:
            result = construction_ref_from_canonical(value, expected_type=expected_type)
        except ConstructionError as exc:
            raise _decoding_error() from exc
    elif expected_type is ChallengeKey:
        try:
            result = challenge_key_from_canonical(value)
        except AuthoringError as exc:
            raise _decoding_error("/challenge_key") from exc
    elif expected_type in _ENUM_TYPES:
        try:
            result = expected_type(_require_text(value))
        except (TypeError, ValueError) as exc:
            raise _decoding_error() from exc
    elif expected_type in _CONSTRUCTION_MODEL_TYPES:
        try:
            result = construction_from_canonical_value(value, expected_type)
        except (AuthoringError, ConstructionError) as exc:
            raise _decoding_error() from exc
    else:
        result = _from_canonical_model(value, expected_type)
    try:
        if not hmac.compare_digest(
            encode_value(to_canonical_value(result)), encode_value(value)
        ):
            raise _decoding_error()
    except ResourcePolicyInputRejected:
        raise
    except (AuthoringError, ConstructionError, TypeError, ValueError) as exc:
        raise _decoding_error() from exc
    return result


def encode_model(value: object) -> bytes:
    """Encode one nested registered model/reference without document framing."""

    try:
        canonical = to_canonical_value(value)
        if type(value) in _SCHEMAS:
            owned = _from_canonical_model(canonical, type(value))
            canonical = _model_to_canonical(owned)
        return encode_value(canonical)
    except ResourcePolicyInputRejected:
        raise
    except (AuthoringError, ConstructionError, TypeError, ValueError) as exc:
        raise _encoding_error() from exc


def decode_model(payload: object, expected_type: type) -> object:
    """Decode one nested value with exact-type and trailing-byte rejection."""

    if type(payload) is not bytes:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.WRONG_TYPE, path="/canonical_bytes"
        )
    try:
        canonical = decode_value(payload)
    except AuthoringError as exc:
        raise _decoding_error(
            "/canonical_bytes", trailing="trailing" in exc.code
        ) from exc
    return from_canonical_value(canonical, expected_type)


def _required_document_text(record: CanonicalRecord, field: str) -> str:
    value = record.field_map().get(field)
    if type(value) is not CanonicalText:
        raise _encoding_error(f"/{field}")
    return value.value


def resource_policy_document(
    object_kind: object,
    schema_version: object,
    record: CanonicalRecord,
) -> bytes:
    """Frame one exact closed B-02C record with domain separation."""

    if type(object_kind) is not str or object_kind not in RESOURCE_POLICY_OBJECT_KINDS:
        raise _encoding_error("/object_kind")
    try:
        schema = validate_version_token(schema_version, "schema_version")
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _encoding_error("/schema_version") from exc
    if schema != RESOURCE_POLICY_SCHEMA_VERSION:
        raise _encoding_error("/schema_version")
    if type(record) is not CanonicalRecord or record.record_type != object_kind:
        raise _encoding_error("/object_kind")
    if _required_document_text(record, "object_kind") != object_kind:
        raise _encoding_error("/object_kind")
    if _required_document_text(record, "schema_version") != schema:
        raise _encoding_error("/schema_version")
    if (
        _required_document_text(record, "canonicalization_profile")
        != RESOURCE_POLICY_CANONICALIZATION_PROFILE
    ):
        raise _encoding_error("/canonicalization_profile")
    try:
        document = RESOURCE_POLICY_DOCUMENT_HEADER + encode_value(record)
    except AuthoringError as exc:
        raise _encoding_error("/canonical_bytes") from exc
    if len(document) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _encoding_error("/canonical_bytes")
    return document


def decode_document(
    payload: object,
    *,
    expected_object_kind: object | None = None,
    expected_schema_version: object | None = None,
    allowed_record_fields: tuple[str, ...] | None = None,
) -> DecodedResourcePolicyDocument:
    """Decode an exact B-02C frame and reject all schema ambiguity."""

    if type(payload) is not bytes:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.WRONG_TYPE, path="/canonical_bytes"
        )
    if len(payload) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _decoding_error("/canonical_bytes")
    if not payload.startswith(RESOURCE_POLICY_DOCUMENT_HEADER):
        raise _decoding_error("/canonical_bytes")
    try:
        value = decode_value(payload[len(RESOURCE_POLICY_DOCUMENT_HEADER) :])
    except AuthoringError as exc:
        raise _decoding_error(
            "/canonical_bytes", trailing="trailing" in exc.code
        ) from exc
    if type(value) is not CanonicalRecord:
        raise _decoding_error("/canonical_bytes")
    fields = value.field_map()
    kind_value = fields.get("object_kind")
    schema_value = fields.get("schema_version")
    profile_value = fields.get("canonicalization_profile")
    if (
        type(kind_value) is not CanonicalText
        or kind_value.value not in RESOURCE_POLICY_OBJECT_KINDS
        or value.record_type != kind_value.value
    ):
        raise _decoding_error("/object_kind")
    if (
        type(schema_value) is not CanonicalText
        or schema_value.value != RESOURCE_POLICY_SCHEMA_VERSION
    ):
        raise _decoding_error("/schema_version")
    if (
        type(profile_value) is not CanonicalText
        or profile_value.value != RESOURCE_POLICY_CANONICALIZATION_PROFILE
    ):
        raise _decoding_error("/canonicalization_profile")
    if expected_object_kind is not None and (
        type(expected_object_kind) is not str
        or kind_value.value != expected_object_kind
    ):
        raise _decoding_error("/object_kind")
    if expected_schema_version is not None and (
        type(expected_schema_version) is not str
        or schema_value.value != expected_schema_version
    ):
        raise _decoding_error("/schema_version")
    if allowed_record_fields is not None:
        if type(allowed_record_fields) is not tuple or any(
            type(name) is not str for name in allowed_record_fields
        ):
            raise TypeError("allowed_record_fields must be an exact tuple of strings")
        if set(fields) != set(allowed_record_fields):
            raise _decoding_error("/canonical_bytes")
    return DecodedResourcePolicyDocument(
        kind_value.value,
        schema_value.value,
        value,
    )


encode_resource_policy_document = resource_policy_document
decode_resource_policy_document = decode_document


def resource_policy_content_digest(payload: object) -> str:
    """Hash exact B-02C bytes with the shared tagged SHA-256 grammar."""

    if type(payload) is not bytes:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.WRONG_TYPE, path="/canonical_bytes"
        )
    try:
        return tagged_sha256(payload)
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _encoding_error("/canonical_bytes") from exc


content_digest = resource_policy_content_digest


def verify_document_digest(payload: object, expected_digest: object) -> bytes:
    """Validate a document and constant-time verify its exact tagged digest."""

    decode_document(payload)
    if type(expected_digest) is not str or not hmac.compare_digest(
        resource_policy_content_digest(payload), expected_digest
    ):
        raise ResourcePolicyReferenceMismatchError(path="/content_digest")
    return bytes(payload)


_DOCUMENT_TYPES = MappingProxyType(
    {
        m.ResourceClass: "resource_class",
        m.ResearchResourcePolicy: "research_resource_policy",
        m.StaticResourceAssessment: "static_resource_assessment",
        m.FixtureResourceAvailability: "fixture_resource_availability",
        m.FixtureResourceDecision: "fixture_resource_decision",
        m.ResourceEnforcementEvent: "resource_enforcement_event",
        m.ResourceEnforcementResult: "resource_enforcement_result",
        m.ResourceCancellationRecord: "resource_cancellation_record",
        m.ObservedResourceReceipt: "observed_resource_receipt",
    }
)

_REF_TYPES_BY_DOCUMENT_TYPE = MappingProxyType(
    {
        m.ResourceClass: ResourceClassRef,
        m.ResearchResourcePolicy: ResearchResourcePolicyRef,
        m.StaticResourceAssessment: StaticResourceAssessmentRef,
        m.FixtureResourceDecision: FixtureResourceDecisionRef,
        m.ResourceCancellationRecord: ResourceCancellationRecordRef,
        m.ObservedResourceReceipt: ObservedResourceReceiptRef,
    }
)


def _owned_document_value(value: object, expected_type: type) -> object:
    if type(value) is not expected_type or expected_type not in _DOCUMENT_TYPES:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.WRONG_TYPE, path="/type"
        )
    try:
        canonical = _model_to_canonical(value)
        if type(canonical) is not CanonicalRecord:
            raise _encoding_error("/type")
        result = _from_canonical_model(canonical, expected_type)
    except ResourcePolicyInputRejected as exc:
        if type(exc) is ResourcePolicyCanonicalEncodingError:
            raise
        raise _encoding_error() from exc
    if type(result) is not expected_type:
        raise _encoding_error("/type")
    return result


def _encode_document_value(value: object, expected_type: type) -> bytes:
    owned = _owned_document_value(value, expected_type)
    canonical = _model_to_canonical(owned)
    if type(canonical) is not CanonicalRecord:
        raise _encoding_error("/type")
    return resource_policy_document(
        _DOCUMENT_TYPES[expected_type],
        object.__getattribute__(owned, "schema_version"),
        canonical,
    )


def _decode_document_value(
    payload: object,
    expected_type: type,
    *,
    expected_ref: object | None = None,
) -> object:
    object_kind = _DOCUMENT_TYPES.get(expected_type)
    if object_kind is None:
        raise TypeError("expected_type must be an exact B-02C document class")
    schema = _SCHEMAS[expected_type]
    decoded = decode_document(
        payload,
        expected_object_kind=object_kind,
        expected_schema_version=RESOURCE_POLICY_SCHEMA_VERSION,
        allowed_record_fields=tuple(name for name, _ in schema.fields),
    )
    result = from_canonical_value(decoded.record, expected_type)
    if type(result) is not expected_type:
        raise _decoding_error("/type")
    try:
        reencoded = _encode_document_value(result, expected_type)
    except ResourcePolicyInputRejected as exc:
        raise _decoding_error("/canonical_bytes") from exc
    if type(payload) is not bytes or not hmac.compare_digest(reencoded, payload):
        raise _decoding_error("/canonical_bytes")
    if expected_ref is not None:
        _verify_document_value_ref(expected_ref, result)
    return result


def _document_value_to_ref(value: object, expected_type: type) -> object:
    if expected_type not in _REF_TYPES_BY_DOCUMENT_TYPE:
        raise TypeError("expected_type does not have a B-02C nominal ref")
    owned = _owned_document_value(value, expected_type)
    payload = _encode_document_value(owned, expected_type)
    kwargs: dict[str, object] = {
        "canonical_bytes": payload,
        "challenge_key": object.__getattribute__(owned, "challenge_key"),
    }
    ref_type = _REF_TYPES_BY_DOCUMENT_TYPE[expected_type]
    if ref_type in (ResourceClassRef, ResearchResourcePolicyRef):
        kwargs["object_id"] = object.__getattribute__(owned, "object_id")
        kwargs["object_version"] = object.__getattribute__(owned, "object_version")
    return _make_resource_policy_ref(ref_type, **kwargs)


def _verify_document_value_ref(expected: object, value: object) -> object:
    value_type = type(value)
    ref_type = _REF_TYPES_BY_DOCUMENT_TYPE.get(value_type)
    if ref_type is None or type(expected) is not ref_type:
        raise ResourcePolicyReferenceMismatchError(path="/ref")
    owned = _owned_document_value(value, value_type)
    kwargs: dict[str, object] = {
        "canonical_bytes": _encode_document_value(owned, value_type),
        "challenge_key": object.__getattribute__(owned, "challenge_key"),
    }
    if ref_type in (ResourceClassRef, ResearchResourcePolicyRef):
        kwargs["object_id"] = object.__getattribute__(owned, "object_id")
        kwargs["object_version"] = object.__getattribute__(owned, "object_version")
    return verify_resource_policy_ref(expected, **kwargs)


def encode_resource_class(value: object) -> bytes:
    return _encode_document_value(value, m.ResourceClass)


def decode_resource_class(
    payload: object, *, expected_ref: object | None = None
) -> m.ResourceClass:
    result = _decode_document_value(payload, m.ResourceClass, expected_ref=expected_ref)
    assert type(result) is m.ResourceClass
    return result


def resource_class_to_ref(value: object) -> ResourceClassRef:
    result = _document_value_to_ref(value, m.ResourceClass)
    assert type(result) is ResourceClassRef
    return result


def verify_resource_class_ref(expected: object, *, value: object) -> ResourceClassRef:
    result = _verify_document_value_ref(expected, value)
    assert type(result) is ResourceClassRef
    return result


def encode_research_resource_policy(value: object) -> bytes:
    return _encode_document_value(value, m.ResearchResourcePolicy)


def _validate_policy_bundle(value: object, class_bundle: object) -> None:
    # Late import deliberately keeps the canonical registry acyclic.
    from .service import validate_research_resource_policy_bundle

    validate_research_resource_policy_bundle(value, class_bundle=class_bundle)


def decode_research_resource_policy(
    payload: object,
    *,
    class_bundle: object,
    expected_ref: object | None = None,
) -> m.ResearchResourcePolicy:
    result = _decode_document_value(payload, m.ResearchResourcePolicy)
    assert type(result) is m.ResearchResourcePolicy
    _validate_policy_bundle(result, class_bundle)
    if expected_ref is not None:
        _verify_document_value_ref(expected_ref, result)
    return result


def research_resource_policy_to_ref(
    value: object, *, class_bundle: object
) -> ResearchResourcePolicyRef:
    if type(value) is not m.ResearchResourcePolicy:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.WRONG_TYPE, path="/type"
        )
    _validate_policy_bundle(value, class_bundle)
    result = _document_value_to_ref(value, m.ResearchResourcePolicy)
    assert type(result) is ResearchResourcePolicyRef
    return result


def verify_research_resource_policy_ref(
    expected: object, *, value: object, class_bundle: object
) -> ResearchResourcePolicyRef:
    if type(value) is not m.ResearchResourcePolicy:
        raise ResourcePolicyReferenceMismatchError(path="/ref")
    _validate_policy_bundle(value, class_bundle)
    result = _verify_document_value_ref(expected, value)
    assert type(result) is ResearchResourcePolicyRef
    return result


def encode_static_resource_assessment(value: object) -> bytes:
    return _encode_document_value(value, m.StaticResourceAssessment)


def decode_static_resource_assessment(
    payload: object, *, expected_ref: object | None = None
) -> m.StaticResourceAssessment:
    result = _decode_document_value(
        payload, m.StaticResourceAssessment, expected_ref=expected_ref
    )
    assert type(result) is m.StaticResourceAssessment
    return result


def static_resource_assessment_to_ref(
    value: object,
) -> StaticResourceAssessmentRef:
    result = _document_value_to_ref(value, m.StaticResourceAssessment)
    assert type(result) is StaticResourceAssessmentRef
    return result


def verify_static_resource_assessment_ref(
    expected: object, *, value: object
) -> StaticResourceAssessmentRef:
    result = _verify_document_value_ref(expected, value)
    assert type(result) is StaticResourceAssessmentRef
    return result


def encode_fixture_resource_availability(value: object) -> bytes:
    return _encode_document_value(value, m.FixtureResourceAvailability)


def decode_fixture_resource_availability(
    payload: object,
) -> m.FixtureResourceAvailability:
    result = _decode_document_value(payload, m.FixtureResourceAvailability)
    assert type(result) is m.FixtureResourceAvailability
    return result


def encode_fixture_resource_decision(value: object) -> bytes:
    return _encode_document_value(value, m.FixtureResourceDecision)


def decode_fixture_resource_decision(
    payload: object, *, expected_ref: object | None = None
) -> m.FixtureResourceDecision:
    result = _decode_document_value(
        payload, m.FixtureResourceDecision, expected_ref=expected_ref
    )
    assert type(result) is m.FixtureResourceDecision
    return result


def fixture_resource_decision_to_ref(value: object) -> FixtureResourceDecisionRef:
    result = _document_value_to_ref(value, m.FixtureResourceDecision)
    assert type(result) is FixtureResourceDecisionRef
    return result


def verify_fixture_resource_decision_ref(
    expected: object, *, value: object
) -> FixtureResourceDecisionRef:
    result = _verify_document_value_ref(expected, value)
    assert type(result) is FixtureResourceDecisionRef
    return result


def encode_resource_enforcement_event(value: object) -> bytes:
    return _encode_document_value(value, m.ResourceEnforcementEvent)


def decode_resource_enforcement_event(
    payload: object,
) -> m.ResourceEnforcementEvent:
    result = _decode_document_value(payload, m.ResourceEnforcementEvent)
    assert type(result) is m.ResourceEnforcementEvent
    return result


def encode_resource_enforcement_result(value: object) -> bytes:
    return _encode_document_value(value, m.ResourceEnforcementResult)


def decode_resource_enforcement_result(
    payload: object,
) -> m.ResourceEnforcementResult:
    result = _decode_document_value(payload, m.ResourceEnforcementResult)
    assert type(result) is m.ResourceEnforcementResult
    return result


def encode_resource_cancellation_record(value: object) -> bytes:
    return _encode_document_value(value, m.ResourceCancellationRecord)


def decode_resource_cancellation_record(
    payload: object, *, expected_ref: object | None = None
) -> m.ResourceCancellationRecord:
    result = _decode_document_value(
        payload, m.ResourceCancellationRecord, expected_ref=expected_ref
    )
    assert type(result) is m.ResourceCancellationRecord
    return result


def resource_cancellation_record_to_ref(
    value: object,
) -> ResourceCancellationRecordRef:
    result = _document_value_to_ref(value, m.ResourceCancellationRecord)
    assert type(result) is ResourceCancellationRecordRef
    return result


def verify_resource_cancellation_record_ref(
    expected: object, *, value: object
) -> ResourceCancellationRecordRef:
    result = _verify_document_value_ref(expected, value)
    assert type(result) is ResourceCancellationRecordRef
    return result


def encode_observed_resource_receipt(value: object) -> bytes:
    return _encode_document_value(value, m.ObservedResourceReceipt)


def decode_observed_resource_receipt(
    payload: object, *, expected_ref: object | None = None
) -> m.ObservedResourceReceipt:
    result = _decode_document_value(
        payload, m.ObservedResourceReceipt, expected_ref=expected_ref
    )
    assert type(result) is m.ObservedResourceReceipt
    return result


def _observed_resource_receipt_to_ref(value: object) -> ObservedResourceReceiptRef:
    """Issue a receipt ref for the semantic service boundary only."""

    result = _document_value_to_ref(value, m.ObservedResourceReceipt)
    assert type(result) is ObservedResourceReceiptRef
    return result


def _verify_observed_resource_receipt_ref(
    expected: object, *, value: object
) -> ObservedResourceReceiptRef:
    """Structurally verify a receipt ref inside the semantic service boundary."""

    result = _verify_document_value_ref(expected, value)
    assert type(result) is ObservedResourceReceiptRef
    return result


# Descriptive canonical-byte aliases parallel B-02B's public spellings.
resource_class_canonical_bytes = encode_resource_class
research_resource_policy_canonical_bytes = encode_research_resource_policy
static_resource_assessment_canonical_bytes = encode_static_resource_assessment
fixture_resource_decision_canonical_bytes = encode_fixture_resource_decision
resource_cancellation_record_canonical_bytes = encode_resource_cancellation_record
observed_resource_receipt_canonical_bytes = encode_observed_resource_receipt


MODEL_CANONICAL_FIELD_REGISTRY_V1 = MappingProxyType(
    {
        schema.record_type: tuple(name for name, _ in schema.fields)
        for schema in _SCHEMAS.values()
    }
)


__all__ = [
    "MODEL_CANONICAL_FIELD_REGISTRY_V1",
    "RESOURCE_POLICY_DOCUMENT_HEADER",
    "RESOURCE_POLICY_OBJECT_KINDS",
    "DecodedResourcePolicyDocument",
    "canonical_sort_key",
    "content_digest",
    "decode_document",
    "decode_fixture_resource_availability",
    "decode_fixture_resource_decision",
    "decode_model",
    "decode_observed_resource_receipt",
    "decode_research_resource_policy",
    "decode_resource_cancellation_record",
    "decode_resource_class",
    "decode_resource_enforcement_event",
    "decode_resource_enforcement_result",
    "decode_resource_policy_document",
    "decode_static_resource_assessment",
    "encode_fixture_resource_availability",
    "encode_fixture_resource_decision",
    "encode_model",
    "encode_observed_resource_receipt",
    "encode_research_resource_policy",
    "encode_resource_cancellation_record",
    "encode_resource_class",
    "encode_resource_enforcement_event",
    "encode_resource_enforcement_result",
    "encode_resource_policy_document",
    "encode_static_resource_assessment",
    "fixture_resource_decision_canonical_bytes",
    "fixture_resource_decision_to_ref",
    "from_canonical_value",
    "observed_resource_receipt_canonical_bytes",
    "research_resource_policy_canonical_bytes",
    "research_resource_policy_to_ref",
    "resource_cancellation_record_canonical_bytes",
    "resource_cancellation_record_to_ref",
    "resource_class_canonical_bytes",
    "resource_class_to_ref",
    "resource_policy_content_digest",
    "resource_policy_document",
    "static_resource_assessment_canonical_bytes",
    "static_resource_assessment_to_ref",
    "to_canonical_value",
    "verify_document_digest",
    "verify_fixture_resource_decision_ref",
    "verify_research_resource_policy_ref",
    "verify_resource_cancellation_record_ref",
    "verify_resource_class_ref",
    "verify_static_resource_assessment_ref",
]
