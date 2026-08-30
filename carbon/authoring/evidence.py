"""Case dispositions, censoring, and evidence-role separation for B-02A."""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from enum import Enum
from typing import Protocol

from carbon.registry.model import ChallengeKey

from .cases import (
    CaseProjectionAuthority,
    PublicCaseIdentityProjection,
    projection_matches_case,
)
from .model import (
    ApplicabilityBinding,
    CaseState,
    CensoringReason,
    DisclosureContract,
    EvidenceRole,
    PopulationRole,
    canonical_set_tuple,
    copied_challenge_key,
    exact,
    exact_enum,
    exact_tuple,
    owner,
    owner_tuple,
)
from .primitives import (
    AUTHORING_SCHEMA_VERSION,
    DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
    validate_tagged_sha256,
    validate_version_token,
)
from .refs import (
    CanonicalChallengeCaseRef,
    InstanceDistributionContractRef,
    SamplingPlanRef,
)
from .sampling import (
    ReplacementPolicy,
    ReplacementPolicyKind,
    ReplacementTrigger,
    ReplacementTriggerKind,
)


def _require_challenge(value: object, challenge_key: ChallengeKey, field: str) -> None:
    if getattr(value, "challenge_key", None) != challenge_key:
        raise ValueError(f"{field} Challenge mismatch")


def _owner_pin_equal(left: object, right: object) -> bool:
    return all(
        getattr(left, field, None) == getattr(right, field, None)
        for field in (
            "scope_binding",
            "object_id",
            "object_version",
            "content_digest",
        )
    )


def _exact_echo_value(observed: object, expected: object) -> bool:
    """Compare authority echoes without nominal or tuple-member coercion."""

    if type(observed) is not type(expected):
        return False
    if type(expected) is tuple:
        return len(observed) == len(expected) and all(
            _exact_echo_value(left, right)
            for left, right in zip(observed, expected, strict=True)
        )
    if type(expected) is ApplicabilityBinding:
        return observed.tag is expected.tag and _exact_echo_value(
            observed.value, expected.value
        )
    return observed == expected


def _scope_population_refs(scope: EvidenceScopeBinding) -> tuple[object, ...]:
    refs: list[object] = []
    for binding in (
        scope.query_population_binding,
        scope.observation_population_binding,
    ):
        if binding.is_bound:
            refs.append(binding.value)
    return tuple(refs)


@dataclass(frozen=True, slots=True)
class EvidenceScopeBinding:
    evidence_campaign_binding: ApplicabilityBinding[object]
    query_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    observation_population_binding: ApplicabilityBinding[
        InstanceDistributionContractRef
    ]
    intended_estimand_or_reporting_ref: object
    measurement_applicability_binding: ApplicabilityBinding[object]

    def __post_init__(self) -> None:
        campaign = exact(
            self.evidence_campaign_binding,
            ApplicabilityBinding,
            "evidence_campaign_binding",
        )
        if campaign.is_bound:
            owner(campaign.value, "evidence_campaign", "evidence_campaign_binding")
        for name, role in (
            ("query_population_binding", PopulationRole.QUERY),
            ("observation_population_binding", PopulationRole.OBSERVATION),
        ):
            binding = exact(getattr(self, name), ApplicabilityBinding, name)
            if binding.is_bound:
                ref = exact(
                    binding.value, InstanceDistributionContractRef, f"{name} value"
                )
                if ref.expected_population_role != role.value:
                    raise ValueError(f"{name} has the wrong role")
        owner(
            self.intended_estimand_or_reporting_ref,
            "intended_estimand_or_reporting",
            "intended_estimand_or_reporting_ref",
        )
        measurement = exact(
            self.measurement_applicability_binding,
            ApplicabilityBinding,
            "measurement_applicability_binding",
        )
        if measurement.is_bound:
            owner(
                measurement.value,
                "measurement_applicability",
                "measurement_applicability_binding",
            )


class CensoringTriggerKind(str, Enum):
    REFERENCE = "REFERENCE"
    OBSERVATION = "OBSERVATION"
    MEASUREMENT = "MEASUREMENT"
    EXPERIMENT = "EXPERIMENT"
    EVIDENCE_ACQUISITION_INFRASTRUCTURE = "EVIDENCE_ACQUISITION_INFRASTRUCTURE"


_CENSORING_REASON_TRIGGER_KIND = {
    CensoringReason.REFERENCE_UNAVAILABLE: (
        CensoringTriggerKind.REFERENCE,
        "reference_unavailable",
    ),
    CensoringReason.REFERENCE_DISPUTED: (
        CensoringTriggerKind.REFERENCE,
        "reference_disputed",
    ),
    CensoringReason.REFERENCE_NUMERICAL_FAILURE: (
        CensoringTriggerKind.REFERENCE,
        "reference_numerical_failure",
    ),
    CensoringReason.REFERENCE_RESOURCE_LIMIT: (
        CensoringTriggerKind.REFERENCE,
        "reference_resource_limit",
    ),
    CensoringReason.REFERENCE_TIMEOUT: (
        CensoringTriggerKind.REFERENCE,
        "reference_timeout",
    ),
    CensoringReason.OBSERVATION_MISSING: (
        CensoringTriggerKind.OBSERVATION,
        "observation_missing",
    ),
    CensoringReason.OBSERVATION_TIMEOUT: (
        CensoringTriggerKind.OBSERVATION,
        "observation_timeout",
    ),
    CensoringReason.MEASUREMENT_UNAVAILABLE: (
        CensoringTriggerKind.MEASUREMENT,
        "measurement_unavailable",
    ),
    CensoringReason.MEASUREMENT_RESOURCE_LIMIT: (
        CensoringTriggerKind.MEASUREMENT,
        "measurement_resource_limit",
    ),
    CensoringReason.MEASUREMENT_TIMEOUT: (
        CensoringTriggerKind.MEASUREMENT,
        "measurement_timeout",
    ),
    CensoringReason.EXPERIMENT_CORRUPTED: (
        CensoringTriggerKind.EXPERIMENT,
        "experiment_corrupted",
    ),
    CensoringReason.EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER: (
        CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE,
        None,
    ),
}

_CENSORING_TRIGGER_OWNER_KINDS = {
    kind
    for trigger_kind, kind in _CENSORING_REASON_TRIGGER_KIND.values()
    if trigger_kind is not CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE
}


@dataclass(frozen=True, slots=True)
class InfrastructureCensoringTrigger:
    acquisition_operation_ref: object
    infrastructure_failure_ref: object

    def __post_init__(self) -> None:
        owner(
            self.acquisition_operation_ref,
            "evidence_acquisition_operation",
            "acquisition_operation_ref",
        )
        owner(
            self.infrastructure_failure_ref,
            "infrastructure_failure",
            "infrastructure_failure_ref",
        )


@dataclass(frozen=True, slots=True)
class CensoringTrigger:
    kind: CensoringTriggerKind
    payload: object

    def __post_init__(self) -> None:
        exact_enum(self.kind, CensoringTriggerKind, "censoring trigger kind")
        if self.kind is CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE:
            exact(
                self.payload, InfrastructureCensoringTrigger, "infrastructure trigger"
            )
            return
        payload_kind = getattr(self.payload, "ref_kind", None)
        if payload_kind not in _CENSORING_TRIGGER_OWNER_KINDS:
            raise TypeError("censoring trigger payload lacks an exact reason subtype")
        admissible_family = {
            reason_kind
            for reason_kind, owner_kind in _CENSORING_REASON_TRIGGER_KIND.values()
            if owner_kind == payload_kind
        }
        if admissible_family != {self.kind}:
            raise ValueError("censoring trigger subtype belongs to a different family")
        owner(self.payload, payload_kind, "censoring trigger payload")


class ReplacementDecisionKind(str, Enum):
    PROHIBITED = "PROHIBITED"
    PERMITTED = "PERMITTED"
    REQUIRED_BY_POLICY = "REQUIRED_BY_POLICY"


class ReplacementPolicyBindingKind(str, Enum):
    PLAN_NEVER = "PLAN_NEVER"
    REGISTERED_POLICY = "REGISTERED_POLICY"


@dataclass(frozen=True, slots=True)
class ReplacementPolicyBinding:
    kind: ReplacementPolicyBindingKind
    policy_ref: object | None

    def __post_init__(self) -> None:
        exact_enum(
            self.kind, ReplacementPolicyBindingKind, "replacement policy binding"
        )
        if self.kind is ReplacementPolicyBindingKind.PLAN_NEVER:
            if self.policy_ref is not None:
                raise ValueError("PLAN_NEVER cannot carry policy ref")
        else:
            owner(self.policy_ref, "replacement_policy", "policy_ref")


@dataclass(frozen=True, slots=True, repr=False)
class ReplacementDecision:
    sampling_plan_ref: SamplingPlanRef
    policy_binding: ReplacementPolicyBinding
    decision: ReplacementDecisionKind
    trigger_binding: ApplicabilityBinding[ReplacementTrigger]
    lineage_binding: ApplicabilityBinding[object]
    accounting_evidence_ref: object

    def __post_init__(self) -> None:
        exact(self.sampling_plan_ref, SamplingPlanRef, "sampling_plan_ref")
        exact(self.policy_binding, ReplacementPolicyBinding, "policy_binding")
        exact_enum(self.decision, ReplacementDecisionKind, "replacement decision")
        trigger = exact(self.trigger_binding, ApplicabilityBinding, "trigger_binding")
        if trigger.is_bound:
            exact(trigger.value, ReplacementTrigger, "replacement trigger")
        lineage = exact(self.lineage_binding, ApplicabilityBinding, "lineage_binding")
        if lineage.is_bound:
            owner(
                lineage.value,
                "protected_replacement_lineage",
                "lineage_binding",
            )
        owner(
            self.accounting_evidence_ref,
            "replacement_accounting",
            "accounting_evidence_ref",
        )
        if self.policy_binding.kind is ReplacementPolicyBindingKind.PLAN_NEVER:
            if self.decision is not ReplacementDecisionKind.PROHIBITED:
                raise ValueError("PLAN_NEVER requires PROHIBITED decision")
            trigger.require_not_applicable("PLAN_NEVER trigger_binding")
            lineage.require_not_applicable("PLAN_NEVER lineage_binding")
        elif (
            self.decision is not ReplacementDecisionKind.PROHIBITED
            and not trigger.is_bound
        ):
            raise ValueError("permitted/requisite replacement requires exact trigger")


def validate_replacement_decision(
    decision: ReplacementDecision,
    *,
    plan_ref: SamplingPlanRef,
    policy: ReplacementPolicy,
    executed: bool,
) -> None:
    exact(decision, ReplacementDecision, "decision")
    exact(plan_ref, SamplingPlanRef, "plan_ref")
    exact(policy, ReplacementPolicy, "policy")
    if decision.sampling_plan_ref != plan_ref:
        raise ValueError("replacement decision plan mismatch")
    if decision.decision is ReplacementDecisionKind.PROHIBITED:
        decision.trigger_binding.require_not_applicable("prohibited trigger_binding")
        decision.lineage_binding.require_not_applicable("prohibited lineage_binding")
    elif executed:
        if not decision.lineage_binding.is_bound:
            raise ValueError("executed replacement requires distinct protected lineage")
    else:
        decision.lineage_binding.require_not_applicable(
            "unexecuted replacement lineage_binding"
        )
    if policy.kind is ReplacementPolicyKind.NEVER:
        if decision.policy_binding.kind is not ReplacementPolicyBindingKind.PLAN_NEVER:
            raise ValueError("NEVER plan requires PLAN_NEVER binding")
    else:
        if (
            decision.policy_binding.kind
            is not ReplacementPolicyBindingKind.REGISTERED_POLICY
        ):
            raise ValueError("registered plan requires registered policy binding")
        if decision.policy_binding.policy_ref != policy.payload.policy_ref:
            raise ValueError("registered replacement policy ref mismatch")
        if (
            decision.trigger_binding.is_bound
            and decision.trigger_binding.value not in policy.payload.triggers
        ):
            raise ValueError("replacement trigger is not registered")


@dataclass(frozen=True, slots=True)
class CensoringRecordRef:
    record_type: str
    schema_version: str
    canonicalization_profile: str
    content_digest: str

    def __post_init__(self) -> None:
        if type(self.record_type) is not str or self.record_type != "censoring_record":
            raise ValueError("record_type must be censoring_record")
        _validate_derived_header(self.schema_version, self.canonicalization_profile)
        validate_tagged_sha256(self.content_digest, "content_digest")


@dataclass(frozen=True, slots=True)
class ValidCasePayload:
    applicability_evidence_ref: object
    membership_evidence_ref: object

    def __post_init__(self) -> None:
        owner(
            self.applicability_evidence_ref,
            "applicability_evidence",
            "applicability_evidence_ref",
        )
        owner(
            self.membership_evidence_ref,
            "membership_evidence",
            "membership_evidence_ref",
        )


@dataclass(frozen=True, slots=True)
class ExcludedCasePayload:
    exclusion_contract_ref: object
    assessment_ref: object
    prospective_screening_design_ref: object
    inclusion_probability_accounting_ref: object

    def __post_init__(self) -> None:
        for name, kind in (
            ("exclusion_contract_ref", "exclusion_contract"),
            ("assessment_ref", "exclusion_assessment"),
            ("prospective_screening_design_ref", "screening_design"),
            (
                "inclusion_probability_accounting_ref",
                "inclusion_probability_accounting",
            ),
        ):
            owner(getattr(self, name), kind, name)


@dataclass(frozen=True, slots=True)
class GenerationFailurePayload:
    source_ref: object
    failure_evidence_ref: object
    distribution_conformance_ref: object
    accounting_ref: object

    def __post_init__(self) -> None:
        for name, kind in (
            ("source_ref", "case_source"),
            ("failure_evidence_ref", "generation_failure"),
            ("distribution_conformance_ref", "distribution_conformance"),
            ("accounting_ref", "generation_failure_accounting"),
        ):
            owner(getattr(self, name), kind, name)


@dataclass(frozen=True, slots=True)
class CaseStatePayload:
    state: CaseState
    payload: (
        ValidCasePayload
        | CensoringRecordRef
        | ExcludedCasePayload
        | GenerationFailurePayload
    )

    def __post_init__(self) -> None:
        exact_enum(self.state, CaseState, "case payload state")
        expected = {
            CaseState.VALID: ValidCasePayload,
            CaseState.CENSORED: CensoringRecordRef,
            CaseState.EXCLUDED: ExcludedCasePayload,
            CaseState.GENERATION_FAILURE: GenerationFailurePayload,
        }[self.state]
        exact(self.payload, expected, "case state payload")


def _validate_derived_header(
    schema_version: object, canonicalization_profile: object
) -> None:
    validate_version_token(schema_version, "schema_version")
    if schema_version != AUTHORING_SCHEMA_VERSION:
        raise ValueError("unsupported derived-evidence schema_version")
    if (
        type(canonicalization_profile) is not str
        or canonicalization_profile != DERIVED_EVIDENCE_CANONICALIZATION_PROFILE
    ):
        raise ValueError("wrong derived-evidence canonicalization profile")


@dataclass(frozen=True, slots=True, repr=False)
class CensoringRecord:
    schema_version: str
    canonicalization_profile: str
    intended_evidence_unit_ref: object
    evidence_scope: EvidenceScopeBinding
    censoring_reason: CensoringReason
    trigger_failure_binding: CensoringTrigger
    actor_authority_ref: object
    population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    evidence_campaign_binding: ApplicabilityBinding[object]
    query_observation_provenance: tuple[object, ...]
    replacement_decision: ReplacementDecision
    accounting_binding: object
    missingness_adjustment_binding: ApplicabilityBinding[object]
    audit_evidence_refs: tuple[object, ...]
    downstream_use_restrictions: tuple[object, ...]

    def __post_init__(self) -> None:
        _validate_derived_header(self.schema_version, self.canonicalization_profile)
        owner(
            self.intended_evidence_unit_ref,
            "protected_intended_evidence_unit",
            "intended_evidence_unit_ref",
        )
        exact(self.evidence_scope, EvidenceScopeBinding, "evidence_scope")
        exact_enum(self.censoring_reason, CensoringReason, "censoring_reason")
        trigger = exact(
            self.trigger_failure_binding, CensoringTrigger, "trigger_failure_binding"
        )
        expected_kind, expected_payload_kind = _CENSORING_REASON_TRIGGER_KIND[
            self.censoring_reason
        ]
        if trigger.kind is not expected_kind:
            raise ValueError("censoring reason/trigger family mismatch")
        if (
            expected_payload_kind is not None
            and getattr(trigger.payload, "ref_kind", None) != expected_payload_kind
        ):
            raise ValueError("censoring reason/trigger subtype mismatch")
        owner(self.actor_authority_ref, "censoring_authority", "actor_authority_ref")
        exact(self.population_ref, InstanceDistributionContractRef, "population_ref")
        exact(self.sampling_plan_ref, SamplingPlanRef, "sampling_plan_ref")
        _require_challenge(
            self.population_ref, self.sampling_plan_ref.challenge_key, "population_ref"
        )
        for ref in _scope_population_refs(self.evidence_scope):
            _require_challenge(
                ref, self.sampling_plan_ref.challenge_key, "evidence_scope"
            )
        exact(
            self.evidence_campaign_binding,
            ApplicabilityBinding,
            "evidence_campaign_binding",
        )
        if (
            self.evidence_campaign_binding
            != self.evidence_scope.evidence_campaign_binding
        ):
            raise ValueError("censoring campaign binding must equal evidence scope")
        object.__setattr__(
            self,
            "query_observation_provenance",
            owner_tuple(
                self.query_observation_provenance,
                "query_observation_provenance",
                "query_observation_provenance",
            ),
        )
        exact(self.replacement_decision, ReplacementDecision, "replacement_decision")
        if self.replacement_decision.sampling_plan_ref != self.sampling_plan_ref:
            raise ValueError("replacement decision plan mismatch")
        if self.replacement_decision.trigger_binding.is_bound:
            replacement_trigger = self.replacement_decision.trigger_binding.value
            if (
                replacement_trigger.kind is not ReplacementTriggerKind.CENSORED
                or replacement_trigger.payload is not self.censoring_reason
            ):
                raise ValueError(
                    "replacement trigger reason differs from censoring reason"
                )
        owner(self.accounting_binding, "censoring_accounting", "accounting_binding")
        missingness = exact(
            self.missingness_adjustment_binding,
            ApplicabilityBinding,
            "missingness_adjustment_binding",
        )
        if missingness.is_bound:
            owner(
                missingness.value,
                "missingness_adjustment",
                "missingness_adjustment_binding",
            )
        object.__setattr__(
            self,
            "audit_evidence_refs",
            owner_tuple(
                self.audit_evidence_refs,
                "audit_evidence",
                "audit_evidence_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "downstream_use_restrictions",
            owner_tuple(
                self.downstream_use_restrictions,
                "restriction",
                "downstream_use_restrictions",
                nonempty=True,
            ),
        )

    def to_canonical_record(self):
        return _derived_to_record(self, "censoring_record")

    def canonical_bytes(self) -> bytes:
        return _derived_canonical_bytes(self, "censoring_record")

    def to_ref(self) -> CensoringRecordRef:
        from .canonical import tagged_sha256

        return CensoringRecordRef(
            "censoring_record",
            self.schema_version,
            self.canonicalization_profile,
            tagged_sha256(self.canonical_bytes()),
        )


def validate_censoring_against_plan(record: CensoringRecord, plan: object) -> None:
    """Validate exact plan/population applicability without owning its policy.

    Reference and infrastructure trigger eligibility remains external policy;
    this B-02A helper only closes objective binding and provenance seams.
    """

    from .sampling import SamplingPlan

    censoring = exact(record, CensoringRecord, "censoring record")
    sampling_plan = exact(plan, SamplingPlan, "sampling plan")
    if censoring.sampling_plan_ref != sampling_plan.to_ref():
        raise ValueError("censoring record does not bind the governing SamplingPlan")
    population_refs = {
        sampling_plan.primary_population_ref,
        sampling_plan.selection_population_ref,
    }
    for binding in (
        sampling_plan.target_population_binding,
        sampling_plan.official_proposal_binding,
        sampling_plan.evidence_weight_binding,
        sampling_plan.query_population_binding,
        sampling_plan.observation_population_binding,
    ):
        if binding.is_bound:
            population_refs.add(
                exact(
                    binding.value,
                    InstanceDistributionContractRef,
                    "SamplingPlan population binding",
                )
            )
    if censoring.population_ref not in population_refs:
        raise ValueError("censoring population is outside the governing SamplingPlan")
    if (
        censoring.evidence_scope.evidence_campaign_binding
        != sampling_plan.evidence_campaign_binding
        or censoring.evidence_scope.query_population_binding
        != sampling_plan.query_population_binding
        or censoring.evidence_scope.observation_population_binding
        != sampling_plan.observation_population_binding
        or censoring.evidence_scope.intended_estimand_or_reporting_ref
        != sampling_plan.intended_estimand_or_reporting_ref
    ):
        raise ValueError("censoring evidence scope differs from the SamplingPlan")
    query_or_observation_bound = (
        censoring.evidence_scope.query_population_binding.is_bound
        or censoring.evidence_scope.observation_population_binding.is_bound
    )
    if query_or_observation_bound and not censoring.query_observation_provenance:
        raise ValueError(
            "bound query/observation scope requires acquisition provenance"
        )
    if not query_or_observation_bound and censoring.query_observation_provenance:
        raise ValueError(
            "query/observation provenance requires a bound query or observation scope"
        )
    observation_reasons = {
        CensoringReason.OBSERVATION_MISSING,
        CensoringReason.OBSERVATION_TIMEOUT,
    }
    measurement_reasons = {
        CensoringReason.MEASUREMENT_UNAVAILABLE,
        CensoringReason.MEASUREMENT_RESOURCE_LIMIT,
        CensoringReason.MEASUREMENT_TIMEOUT,
    }
    if censoring.censoring_reason in observation_reasons:
        observation = sampling_plan.observation_population_binding
        if not observation.is_bound:
            raise ValueError(
                "observation censoring requires a bound observation population"
            )
        if censoring.population_ref != observation.value:
            raise ValueError(
                "observation censoring must bind the observation population"
            )
        if not censoring.query_observation_provenance:
            raise ValueError(
                "observation censoring requires query/observation provenance"
            )
    if (
        censoring.censoring_reason in measurement_reasons
        and not censoring.evidence_scope.measurement_applicability_binding.is_bound
    ):
        raise ValueError(
            "measurement censoring requires bound measurement applicability"
        )
    if (
        censoring.censoring_reason is CensoringReason.EXPERIMENT_CORRUPTED
        and not censoring.evidence_scope.evidence_campaign_binding.is_bound
    ):
        raise ValueError("experiment censoring requires a bound evidence campaign")


@dataclass(frozen=True, slots=True)
class CanonicalCaseDispositionRef:
    record_type: str
    schema_version: str
    canonicalization_profile: str
    content_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.record_type) is not str
            or self.record_type != "canonical_case_disposition"
        ):
            raise ValueError("record_type must be canonical_case_disposition")
        _validate_derived_header(self.schema_version, self.canonicalization_profile)
        validate_tagged_sha256(self.content_digest, "content_digest")


@dataclass(frozen=True, slots=True, repr=False)
class CanonicalCaseDisposition:
    schema_version: str
    canonicalization_profile: str
    intended_evidence_unit_ref: object
    sampling_plan_ref: SamplingPlanRef
    primary_population_ref: InstanceDistributionContractRef
    evidence_scope: EvidenceScopeBinding
    case_state: CaseState
    case_ref_binding: ApplicabilityBinding[CanonicalChallengeCaseRef]
    attempt_commitment_binding: ApplicabilityBinding[object]
    state_payload: CaseStatePayload
    actor_policy_authority_ref: object
    replacement_decision: ReplacementDecision
    audit_evidence_refs: tuple[object, ...]
    downstream_use_restrictions: tuple[object, ...]
    disclosure_contract: DisclosureContract

    def __post_init__(self) -> None:
        _validate_derived_header(self.schema_version, self.canonicalization_profile)
        owner(
            self.intended_evidence_unit_ref,
            "protected_intended_evidence_unit",
            "intended_evidence_unit_ref",
        )
        exact(self.sampling_plan_ref, SamplingPlanRef, "sampling_plan_ref")
        exact(
            self.primary_population_ref,
            InstanceDistributionContractRef,
            "primary_population_ref",
        )
        _require_challenge(
            self.primary_population_ref,
            self.sampling_plan_ref.challenge_key,
            "primary_population_ref",
        )
        exact(self.evidence_scope, EvidenceScopeBinding, "evidence_scope")
        exact_enum(self.case_state, CaseState, "case_state")
        case_binding = exact(
            self.case_ref_binding, ApplicabilityBinding, "case_ref_binding"
        )
        if case_binding.is_bound:
            case_ref = exact(
                case_binding.value, CanonicalChallengeCaseRef, "case_ref_binding value"
            )
            _require_challenge(
                case_ref, self.sampling_plan_ref.challenge_key, "case_ref_binding"
            )
        for ref in _scope_population_refs(self.evidence_scope):
            _require_challenge(
                ref, self.sampling_plan_ref.challenge_key, "evidence_scope"
            )
        attempt = exact(
            self.attempt_commitment_binding,
            ApplicabilityBinding,
            "attempt_commitment_binding",
        )
        if attempt.is_bound:
            owner(
                attempt.value,
                "protected_attempt_commitment",
                "attempt_commitment_binding",
            )
        payload = exact(self.state_payload, CaseStatePayload, "state_payload")
        if payload.state is not self.case_state:
            raise ValueError("case state and payload tag differ")
        if self.case_state in {CaseState.VALID, CaseState.CENSORED}:
            if not case_binding.is_bound or attempt.is_bound:
                raise ValueError(
                    "valid/censored state requires case and no attempt-only ref"
                )
        elif self.case_state is CaseState.GENERATION_FAILURE:
            if case_binding.is_bound or not attempt.is_bound:
                raise ValueError("generation failure requires attempt and no case")
        elif case_binding.is_bound == attempt.is_bound:
            raise ValueError("excluded state requires exactly one case/attempt binding")
        owner(
            self.actor_policy_authority_ref,
            "policy_authority",
            "actor_policy_authority_ref",
        )
        exact(self.replacement_decision, ReplacementDecision, "replacement_decision")
        if self.replacement_decision.sampling_plan_ref != self.sampling_plan_ref:
            raise ValueError("replacement decision plan mismatch")
        decision = self.replacement_decision
        trigger = decision.trigger_binding
        lineage = decision.lineage_binding
        if decision.decision is ReplacementDecisionKind.PROHIBITED:
            trigger.require_not_applicable("prohibited disposition trigger")
            lineage.require_not_applicable("prohibited disposition lineage")
        if self.case_state is CaseState.VALID:
            trigger.require_not_applicable("valid disposition trigger")
            lineage.require_not_applicable("valid disposition lineage")
        elif trigger.is_bound:
            replacement_trigger = exact(
                trigger.value,
                ReplacementTrigger,
                "disposition replacement trigger",
            )
            expected_trigger_kind = {
                CaseState.CENSORED: ReplacementTriggerKind.CENSORED,
                CaseState.EXCLUDED: ReplacementTriggerKind.EXCLUDED,
                CaseState.GENERATION_FAILURE: ReplacementTriggerKind.GENERATION_FAILURE,
            }[self.case_state]
            if replacement_trigger.kind is not expected_trigger_kind:
                raise ValueError("replacement trigger does not match case state")
            if self.case_state is CaseState.EXCLUDED and not _owner_pin_equal(
                replacement_trigger.payload,
                payload.payload.exclusion_contract_ref,
            ):
                raise ValueError("excluded replacement trigger contract mismatch")
            if (
                self.case_state is CaseState.GENERATION_FAILURE
                and not _owner_pin_equal(
                    replacement_trigger.payload,
                    payload.payload.failure_evidence_ref,
                )
            ):
                raise ValueError("generation replacement trigger reason mismatch")
        object.__setattr__(
            self,
            "audit_evidence_refs",
            owner_tuple(
                self.audit_evidence_refs,
                "audit_evidence",
                "audit_evidence_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "downstream_use_restrictions",
            owner_tuple(
                self.downstream_use_restrictions,
                "restriction",
                "downstream_use_restrictions",
                nonempty=True,
            ),
        )
        exact(self.disclosure_contract, DisclosureContract, "disclosure_contract")

    def to_canonical_record(self):
        return _derived_to_record(self, "canonical_case_disposition")

    def canonical_bytes(self) -> bytes:
        return _derived_canonical_bytes(self, "canonical_case_disposition")

    def to_ref(self) -> CanonicalCaseDispositionRef:
        from .canonical import tagged_sha256

        return CanonicalCaseDispositionRef(
            "canonical_case_disposition",
            self.schema_version,
            self.canonicalization_profile,
            tagged_sha256(self.canonical_bytes()),
        )


@dataclass(frozen=True, slots=True)
class EvidenceRoleBinding:
    role: EvidenceRole
    hybrid_role_ref: object | None = None

    def __post_init__(self) -> None:
        exact_enum(self.role, EvidenceRole, "evidence role")
        if self.role is EvidenceRole.REGISTERED_HYBRID:
            owner(self.hybrid_role_ref, "hybrid_evidence_role", "hybrid_role_ref")
        elif self.hybrid_role_ref is not None:
            raise ValueError("non-hybrid evidence role cannot carry hybrid ref")


@dataclass(frozen=True, slots=True, repr=False)
class CaseEvidenceBinding:
    authoritative_case_ref: CanonicalChallengeCaseRef
    public_projection_binding: ApplicabilityBinding[PublicCaseIdentityProjection]
    evidence_role: EvidenceRoleBinding
    evidence_campaign_ref: object
    role_population_ref: InstanceDistributionContractRef
    evidence_artifact_ref: object
    claim_scope_ref: object
    applicability_refs: tuple[object, ...]
    query_observation_provenance: tuple[object, ...]
    policy_qualification_binding: ApplicabilityBinding[object]
    provenance_refs: tuple[object, ...]
    disclosure_contract: DisclosureContract
    downstream_use_restrictions: tuple[object, ...]
    _projection_authority: InitVar[CaseProjectionAuthority | None] = None

    def __post_init__(
        self, _projection_authority: CaseProjectionAuthority | None
    ) -> None:
        exact(
            self.authoritative_case_ref,
            CanonicalChallengeCaseRef,
            "authoritative_case_ref",
        )
        projection = exact(
            self.public_projection_binding,
            ApplicabilityBinding,
            "public_projection_binding",
        )
        if projection.is_bound:
            value = exact(
                projection.value,
                PublicCaseIdentityProjection,
                "public projection",
            )
            if value.challenge_key != self.authoritative_case_ref.challenge_key:
                raise ValueError("public projection Challenge mismatch")
            authority = exact(
                _projection_authority,
                CaseProjectionAuthority,
                "projection authority",
            )
            projection_matches_case(
                value,
                self.authoritative_case_ref,
                authority,
            )
        elif _projection_authority is not None:
            raise ValueError("projection authority supplied without public projection")
        exact(self.evidence_role, EvidenceRoleBinding, "evidence_role")
        owner(self.evidence_campaign_ref, "evidence_campaign", "evidence_campaign_ref")
        role_population = exact(
            self.role_population_ref,
            InstanceDistributionContractRef,
            "role_population_ref",
        )
        _require_challenge(
            role_population,
            self.authoritative_case_ref.challenge_key,
            "role_population_ref",
        )
        if (
            role_population.expected_population_role
            != PopulationRole.EVIDENCE_CAMPAIGN.value
        ):
            raise ValueError("evidence binding requires EVIDENCE_CAMPAIGN population")
        owner(self.evidence_artifact_ref, "evidence_artifact", "evidence_artifact_ref")
        owner(self.claim_scope_ref, "claim_scope", "claim_scope_ref")
        object.__setattr__(
            self,
            "applicability_refs",
            owner_tuple(
                self.applicability_refs,
                "applicability",
                "applicability_refs",
                nonempty=True,
            ),
        )
        # Query/observation provenance is scoped to the same exact Challenge;
        # the owner refs themselves remain opaque and are not reinterpreted.
        object.__setattr__(
            self,
            "query_observation_provenance",
            owner_tuple(
                self.query_observation_provenance,
                "query_observation_provenance",
                "query_observation_provenance",
            ),
        )
        qualification = exact(
            self.policy_qualification_binding,
            ApplicabilityBinding,
            "policy_qualification_binding",
        )
        if qualification.is_bound:
            owner(
                qualification.value,
                "reference_qualification_policy",
                "policy_qualification_binding",
            )
        object.__setattr__(
            self,
            "provenance_refs",
            owner_tuple(
                self.provenance_refs,
                "provenance",
                "provenance_refs",
                nonempty=True,
            ),
        )
        exact(self.disclosure_contract, DisclosureContract, "disclosure_contract")
        object.__setattr__(
            self,
            "downstream_use_restrictions",
            owner_tuple(
                self.downstream_use_restrictions,
                "restriction",
                "downstream_use_restrictions",
                nonempty=True,
            ),
        )

    @property
    def is_mms(self) -> bool:
        return (
            self.evidence_role.role is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
        )


def reject_evidence_role_relabel(
    binding: CaseEvidenceBinding, requested_role: EvidenceRoleBinding
) -> None:
    exact(binding, CaseEvidenceBinding, "binding")
    exact(requested_role, EvidenceRoleBinding, "requested_role")
    if requested_role != binding.evidence_role:
        raise ValueError("evidence role cannot be relabeled or inherit authority")


def validate_case_evidence_binding(
    binding: CaseEvidenceBinding,
    *,
    case: object,
    role_population: object,
    physical_system: object,
    candidate_output: object,
) -> None:
    """Validate the loaded case/evidence graph without transferring authority."""

    from .cases import (
        CanonicalChallengeCase,
        CaseSourceKind,
        ManufacturedSolutionCaseSource,
    )
    from .model import AllowedConsumerKind
    from .physical import CandidateOutputContract, PhysicalSystemSpec
    from .populations import InstanceDistributionContract

    exact(binding, CaseEvidenceBinding, "binding")
    loaded_case = exact(case, CanonicalChallengeCase, "case")
    population = exact(
        role_population,
        InstanceDistributionContract,
        "role_population",
    )
    physical = exact(physical_system, PhysicalSystemSpec, "physical_system")
    candidate = exact(candidate_output, CandidateOutputContract, "candidate_output")
    if loaded_case.to_ref() != binding.authoritative_case_ref:
        raise ValueError("evidence binding authoritative case mismatch")
    if population.to_ref() != binding.role_population_ref:
        raise ValueError("evidence binding role population mismatch")
    case_population_refs = {loaded_case.primary_population_ref}
    case_population_refs.update(
        item.population_ref for item in loaded_case.related_population_bindings
    )
    if binding.role_population_ref not in case_population_refs:
        raise ValueError("evidence population is not bound by the canonical case")
    if (
        loaded_case.physical_system_ref != physical.to_ref()
        or loaded_case.candidate_output_ref != candidate.to_ref()
        or population.physical_system_ref != physical.to_ref()
        or population.candidate_output_ref != candidate.to_ref()
        or candidate.physical_system_ref != physical.to_ref()
    ):
        raise ValueError("evidence binding physical/candidate graph mismatch")
    if (
        binding.claim_scope_ref != physical.claim_scope_ref
        or population.owning_claim_scope_ref != physical.claim_scope_ref
    ):
        raise ValueError("evidence binding claim scope mismatch")
    if (
        not loaded_case.evidence_campaign_binding.is_bound
        or loaded_case.evidence_campaign_binding.value != binding.evidence_campaign_ref
    ):
        raise ValueError("evidence binding campaign differs from canonical case")
    if not any(
        consumer.kind is AllowedConsumerKind.CASE_EVIDENCE
        and consumer.payload is binding.evidence_role.role
        for consumer in population.allowed_consumers
    ):
        raise ValueError("population does not admit this evidence role")
    if binding.is_mms:
        if loaded_case.case_source.kind is not CaseSourceKind.MANUFACTURED_SOLUTION:
            raise ValueError("MMS evidence requires an MMS canonical case")
        source = exact(
            loaded_case.case_source.payload,
            ManufacturedSolutionCaseSource,
            "MMS case source",
        )
        if source.verification_campaign_ref != binding.evidence_campaign_ref:
            raise ValueError("MMS source campaign differs from evidence binding")


@dataclass(frozen=True, slots=True, repr=False)
class CaseEvidenceBindingAuthorization:
    """Exact authority echo permitting consumption of one authored binding.

    A raw :class:`CaseEvidenceBinding` remains only an authored claim.  This
    receipt is a trusted in-process composition result; it is neither a B-04
    qualification policy nor a signature, credential, or durable proof.
    """

    authority_ref: object
    authoritative_case_ref: CanonicalChallengeCaseRef
    public_projection_binding: ApplicabilityBinding[PublicCaseIdentityProjection]
    evidence_role: EvidenceRoleBinding
    evidence_campaign_ref: object
    role_population_ref: InstanceDistributionContractRef
    evidence_artifact_ref: object
    claim_scope_ref: object
    applicability_refs: tuple[object, ...]
    query_observation_provenance: tuple[object, ...]
    policy_qualification_binding: ApplicabilityBinding[object]
    provenance_refs: tuple[object, ...]
    disclosure_contract: DisclosureContract
    downstream_use_restrictions: tuple[object, ...]


class CaseEvidenceBindingRegistryAuthority(Protocol):
    """External B-04/history-owned verifier for one exact evidence binding."""

    def authorize_case_evidence_binding(
        self,
        *,
        authority_ref: object,
        binding: CaseEvidenceBinding,
    ) -> CaseEvidenceBindingAuthorization:
        """Return the exact registered binding currently held by the authority."""
        ...


class CaseEvidenceBindingAuthority:
    """Internal fail-closed adapter around the separately owned registry."""

    __slots__ = ("_authority", "authority_ref")

    def __init__(
        self,
        *,
        authority_ref: object,
        authority: CaseEvidenceBindingRegistryAuthority,
    ) -> None:
        owner(authority_ref, "evidence_binding_authority", "authority_ref")
        if callable(authority):
            raise TypeError("evidence binding authority must not be a raw callable")
        verifier = getattr(authority, "authorize_case_evidence_binding", None)
        if not callable(verifier):
            raise TypeError(
                "evidence binding authority must provide "
                "authorize_case_evidence_binding"
            )
        self.authority_ref = authority_ref
        self._authority = authority

    def authorize(
        self,
        binding: CaseEvidenceBinding,
        *,
        case: object,
        role_population: object,
        physical_system: object,
        candidate_output: object,
    ) -> CaseEvidenceBindingAuthorization:
        """Authorize exact consumption only after the loaded graph validates."""

        exact(binding, CaseEvidenceBinding, "binding")
        validate_case_evidence_binding(
            binding,
            case=case,
            role_population=role_population,
            physical_system=physical_system,
            candidate_output=candidate_output,
        )
        result = self._authority.authorize_case_evidence_binding(
            authority_ref=self.authority_ref,
            binding=binding,
        )
        echo = exact(
            result,
            CaseEvidenceBindingAuthorization,
            "case evidence authorization",
        )
        expected = {
            "authority_ref": self.authority_ref,
            "authoritative_case_ref": binding.authoritative_case_ref,
            "public_projection_binding": binding.public_projection_binding,
            "evidence_role": binding.evidence_role,
            "evidence_campaign_ref": binding.evidence_campaign_ref,
            "role_population_ref": binding.role_population_ref,
            "evidence_artifact_ref": binding.evidence_artifact_ref,
            "claim_scope_ref": binding.claim_scope_ref,
            "applicability_refs": binding.applicability_refs,
            "query_observation_provenance": (binding.query_observation_provenance),
            "policy_qualification_binding": (binding.policy_qualification_binding),
            "provenance_refs": binding.provenance_refs,
            "disclosure_contract": binding.disclosure_contract,
            "downstream_use_restrictions": (binding.downstream_use_restrictions),
        }
        for name, value in expected.items():
            if not _exact_echo_value(getattr(echo, name), value):
                raise ValueError(f"case evidence authorization {name} mismatch")
        return echo


def _issue_case_evidence_binding_authority(
    *,
    authority_ref: object,
    authority: CaseEvidenceBindingRegistryAuthority,
) -> CaseEvidenceBindingAuthority:
    """Package-internal adapter for trusted B-04/history composition."""

    return CaseEvidenceBindingAuthority(
        authority_ref=authority_ref,
        authority=authority,
    )


@dataclass(frozen=True, slots=True)
class RealizedValidEvidenceRecordRef:
    record_type: str
    schema_version: str
    canonicalization_profile: str
    content_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.record_type) is not str
            or self.record_type != "realized_valid_evidence_record"
        ):
            raise ValueError("record_type must be realized_valid_evidence_record")
        _validate_derived_header(self.schema_version, self.canonicalization_profile)
        validate_tagged_sha256(self.content_digest, "content_digest")


_REALIZED_CAPABILITY = object()
_ACCOUNTING_CAPABILITY = object()
_REALIZED_LOAD_AUTHORITY_CAPABILITY = object()


@dataclass(frozen=True, slots=True, init=False, repr=False)
class EvidenceAccountingCapability:
    sampling_plan_ref: SamplingPlanRef
    complete_unit_manifest_ref: object
    intended_evidence_unit_refs: tuple[object, ...]
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    target_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    official_proposal_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    evidence_weight_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    intended_estimand_or_reporting_ref: object
    accounting_evidence_ref: object
    denominator_policy_ref: object
    censoring_policy_ref: object
    missingness_adjustment_binding: ApplicabilityBinding[object]
    sensitivity_analysis_binding: ApplicabilityBinding[object]
    construction_authority_ref: object
    construction_audit_refs: tuple[object, ...]

    def __init__(self, *, _capability: object, **fields: object) -> None:
        if _capability is not _ACCOUNTING_CAPABILITY:
            raise PermissionError("accounting capability requires controlled issuance")
        expected = _ACCOUNTING_CAPABILITY_FIELDS
        if set(fields) != set(expected):
            raise TypeError("accounting capability fields are closed and complete")
        for name in expected:
            object.__setattr__(self, name, fields[name])
        exact(self.sampling_plan_ref, SamplingPlanRef, "sampling_plan_ref")
        owner(
            self.complete_unit_manifest_ref,
            "protected_unit_manifest",
            "complete_unit_manifest_ref",
        )
        object.__setattr__(
            self,
            "intended_evidence_unit_refs",
            owner_tuple(
                self.intended_evidence_unit_refs,
                "protected_intended_evidence_unit",
                "intended_evidence_unit_refs",
                nonempty=True,
            ),
        )
        for name in ("primary_population_ref", "selection_population_ref"):
            ref = exact(getattr(self, name), InstanceDistributionContractRef, name)
            _require_challenge(ref, self.sampling_plan_ref.challenge_key, name)
        for name, role in (
            ("target_population_binding", PopulationRole.TARGET_WORKLOAD_P),
            ("official_proposal_binding", PopulationRole.OFFICIAL_PROPOSAL_Q),
            ("evidence_weight_binding", PopulationRole.EVIDENCE_WEIGHT_W),
        ):
            binding = exact(getattr(self, name), ApplicabilityBinding, name)
            if binding.is_bound:
                ref = exact(binding.value, InstanceDistributionContractRef, name)
                if ref.expected_population_role != role.value:
                    raise ValueError(f"{name} role mismatch")
                _require_challenge(ref, self.sampling_plan_ref.challenge_key, name)
        owner(
            self.intended_estimand_or_reporting_ref,
            "intended_estimand_or_reporting",
            "intended_estimand_or_reporting_ref",
        )
        for name, kind in (
            ("accounting_evidence_ref", "realized_evidence_accounting"),
            ("denominator_policy_ref", "denominator_policy"),
            ("censoring_policy_ref", "censoring_policy"),
        ):
            owner(getattr(self, name), kind, name)
        for name, kind in (
            ("missingness_adjustment_binding", "missingness_adjustment"),
            ("sensitivity_analysis_binding", "sensitivity_analysis"),
        ):
            binding = exact(getattr(self, name), ApplicabilityBinding, name)
            if binding.is_bound:
                owner(binding.value, kind, name)
        owner(
            self.construction_authority_ref,
            "accounting_authority",
            "construction_authority_ref",
        )
        object.__setattr__(
            self,
            "construction_audit_refs",
            owner_tuple(
                self.construction_audit_refs,
                "audit_evidence",
                "construction_audit_refs",
                nonempty=True,
            ),
        )


_ACCOUNTING_CAPABILITY_FIELDS = (
    "sampling_plan_ref",
    "complete_unit_manifest_ref",
    "intended_evidence_unit_refs",
    "primary_population_ref",
    "selection_population_ref",
    "target_population_binding",
    "official_proposal_binding",
    "evidence_weight_binding",
    "intended_estimand_or_reporting_ref",
    "accounting_evidence_ref",
    "denominator_policy_ref",
    "censoring_policy_ref",
    "missingness_adjustment_binding",
    "sensitivity_analysis_binding",
    "construction_authority_ref",
    "construction_audit_refs",
)


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceAccountingVerificationEcho:
    """Exact external-accounting echo for a complete intended-unit manifest."""

    sampling_plan_ref: SamplingPlanRef
    complete_unit_manifest_ref: object
    intended_evidence_unit_refs: tuple[object, ...]
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    target_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    official_proposal_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    evidence_weight_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    intended_estimand_or_reporting_ref: object
    accounting_evidence_ref: object
    denominator_policy_ref: object
    censoring_policy_ref: object
    missingness_adjustment_binding: ApplicabilityBinding[object]
    sensitivity_analysis_binding: ApplicabilityBinding[object]
    construction_authority_ref: object
    construction_audit_refs: tuple[object, ...]


class EvidenceAccountingRegistryAuthority(Protocol):
    """External statistics/history authority for complete evidence accounting."""

    def verify_evidence_accounting(
        self,
        *,
        candidate: EvidenceAccountingCapability,
    ) -> EvidenceAccountingVerificationEcho:
        """Return exact current accounting state, not a Boolean approval."""
        ...


def _require_accounting_verification_echo(
    result: object,
    candidate: EvidenceAccountingCapability,
) -> EvidenceAccountingVerificationEcho:
    echo = exact(
        result,
        EvidenceAccountingVerificationEcho,
        "evidence accounting verification",
    )
    for name in _ACCOUNTING_CAPABILITY_FIELDS:
        expected = getattr(candidate, name)
        observed = getattr(echo, name)
        if not _exact_echo_value(observed, expected):
            raise ValueError(f"evidence accounting verification {name} mismatch")
    return echo


_FINALIZED_ACCOUNTING_CAPABILITY = object()


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceAccountingFinalizationEcho:
    """Exact final composition echoed by the external accounting authority."""

    authority_ref: object
    accounting_verification: EvidenceAccountingVerificationEcho
    capability: EvidenceAccountingCapability
    disposition_refs: tuple[CanonicalCaseDispositionRef, ...]
    dispositions: tuple[CanonicalCaseDisposition, ...]
    censoring_record_refs: tuple[CensoringRecordRef, ...]
    censoring_records: tuple[CensoringRecord, ...]


class EvidenceAccountingFinalizationAuthority(Protocol):
    """External authority for the exact final evidence composition."""

    def finalize_evidence_accounting(
        self,
        *,
        authority_ref: object,
        capability: EvidenceAccountingCapability,
        disposition_refs: tuple[CanonicalCaseDispositionRef, ...],
        dispositions: tuple[CanonicalCaseDisposition, ...],
        censoring_record_refs: tuple[CensoringRecordRef, ...],
        censoring_records: tuple[CensoringRecord, ...],
    ) -> EvidenceAccountingFinalizationEcho:
        """Return exact loaded records and refs for one complete composition."""
        ...


@dataclass(frozen=True, slots=True, init=False, repr=False)
class FinalizedEvidenceAccountingCapability:
    """Internal capability pinned to one externally echoed final composition."""

    capability: EvidenceAccountingCapability
    disposition_refs: tuple[CanonicalCaseDispositionRef, ...]
    dispositions: tuple[CanonicalCaseDisposition, ...]
    censoring_record_refs: tuple[CensoringRecordRef, ...]
    censoring_records: tuple[CensoringRecord, ...]

    def __init__(
        self,
        *,
        _capability: object,
        capability: EvidenceAccountingCapability,
        disposition_refs: tuple[CanonicalCaseDispositionRef, ...],
        dispositions: tuple[CanonicalCaseDisposition, ...],
        censoring_record_refs: tuple[CensoringRecordRef, ...],
        censoring_records: tuple[CensoringRecord, ...],
    ) -> None:
        if _capability is not _FINALIZED_ACCOUNTING_CAPABILITY:
            raise PermissionError(
                "finalized accounting capability requires controlled issuance"
            )
        object.__setattr__(
            self,
            "capability",
            exact(capability, EvidenceAccountingCapability, "accounting capability"),
        )
        object.__setattr__(self, "disposition_refs", disposition_refs)
        object.__setattr__(self, "dispositions", dispositions)
        object.__setattr__(self, "censoring_record_refs", censoring_record_refs)
        object.__setattr__(self, "censoring_records", censoring_records)


def _validated_final_evidence_composition(
    capability: EvidenceAccountingCapability,
    dispositions: object,
    censoring_records: object,
) -> tuple[
    tuple[CanonicalCaseDispositionRef, ...],
    tuple[CanonicalCaseDisposition, ...],
    tuple[CensoringRecordRef, ...],
    tuple[CensoringRecord, ...],
]:
    validated_dispositions = canonical_set_tuple(
        exact_tuple(
            dispositions,
            CanonicalCaseDisposition,
            "finalized dispositions",
            nonempty=True,
            unique=True,
        )
    )
    validated_censoring = canonical_set_tuple(
        exact_tuple(
            censoring_records,
            CensoringRecord,
            "finalized censoring records",
            unique=True,
        )
    )
    disposition_refs = canonical_set_tuple(
        tuple(disposition.to_ref() for disposition in validated_dispositions)
    )
    censoring_refs = canonical_set_tuple(
        tuple(record.to_ref() for record in validated_censoring)
    )
    linked_censoring_refs: list[CensoringRecordRef] = []
    for disposition in validated_dispositions:
        if disposition.case_state is CaseState.CENSORED:
            censoring_ref = exact(
                disposition.state_payload.payload,
                CensoringRecordRef,
                "censored disposition payload",
            )
            linked_censoring_refs.append(censoring_ref)
            matches = tuple(
                record
                for record in validated_censoring
                if record.to_ref() == censoring_ref
            )
            if len(matches) != 1:
                raise ValueError(
                    "censored disposition requires one exact loaded censoring record"
                )
            censoring = matches[0]
            if (
                censoring.intended_evidence_unit_ref
                != disposition.intended_evidence_unit_ref
                or censoring.sampling_plan_ref != disposition.sampling_plan_ref
                or censoring.evidence_scope != disposition.evidence_scope
                or censoring.replacement_decision != disposition.replacement_decision
            ):
                raise ValueError(
                    "censoring record differs from its canonical disposition"
                )
    if canonical_set_tuple(tuple(linked_censoring_refs)) != censoring_refs:
        raise ValueError(
            "loaded censoring records must exactly equal the censored disposition links"
        )
    intended_units = tuple(
        disposition.intended_evidence_unit_ref for disposition in validated_dispositions
    )
    if len(set(intended_units)) != len(intended_units):
        raise ValueError("finalized dispositions duplicate an intended evidence unit")
    if set(intended_units) != set(capability.intended_evidence_unit_refs):
        raise ValueError("finalized dispositions do not cover the complete manifest")
    for disposition in validated_dispositions:
        if disposition.sampling_plan_ref != capability.sampling_plan_ref:
            raise ValueError("finalized disposition SamplingPlan mismatch")
        if disposition.primary_population_ref != capability.primary_population_ref:
            raise ValueError("finalized disposition primary population mismatch")
    return (
        disposition_refs,
        validated_dispositions,
        censoring_refs,
        validated_censoring,
    )


def _finalized_accounting_from_echo(
    result: object,
    *,
    capability: EvidenceAccountingCapability,
    disposition_refs: tuple[CanonicalCaseDispositionRef, ...],
    dispositions: tuple[CanonicalCaseDisposition, ...],
    censoring_record_refs: tuple[CensoringRecordRef, ...],
    censoring_records: tuple[CensoringRecord, ...],
) -> FinalizedEvidenceAccountingCapability:
    echo = exact(
        result,
        EvidenceAccountingFinalizationEcho,
        "evidence accounting finalization",
    )
    expected_authority = capability.construction_authority_ref
    if (
        type(echo.authority_ref) is not type(expected_authority)
        or echo.authority_ref != expected_authority
    ):
        raise ValueError("evidence finalization authority mismatch")
    _require_accounting_verification_echo(
        echo.accounting_verification,
        capability,
    )
    expected = {
        "capability": capability,
        "disposition_refs": disposition_refs,
        "dispositions": dispositions,
        "censoring_record_refs": censoring_record_refs,
        "censoring_records": censoring_records,
    }
    for name, value in expected.items():
        observed = getattr(echo, name)
        if not _exact_echo_value(observed, value):
            raise ValueError(f"evidence finalization {name} mismatch")
    return FinalizedEvidenceAccountingCapability(
        _capability=_FINALIZED_ACCOUNTING_CAPABILITY,
        capability=capability,
        disposition_refs=disposition_refs,
        dispositions=dispositions,
        censoring_record_refs=censoring_record_refs,
        censoring_records=censoring_records,
    )


def _finalize_evidence_accounting(
    capability: EvidenceAccountingCapability,
    dispositions: tuple[CanonicalCaseDisposition, ...],
    censoring_records: tuple[CensoringRecord, ...],
    *,
    authority: EvidenceAccountingFinalizationAuthority,
) -> FinalizedEvidenceAccountingCapability:
    """Bind a manifest capability to exact loaded final disposition history."""

    candidate = exact(capability, EvidenceAccountingCapability, "accounting capability")
    if callable(authority):
        raise TypeError("evidence finalization authority must not be a raw callable")
    verifier = getattr(authority, "finalize_evidence_accounting", None)
    if not callable(verifier):
        raise TypeError(
            "evidence finalization authority must provide finalize_evidence_accounting"
        )
    (
        disposition_refs,
        validated_dispositions,
        censoring_record_refs,
        validated_censoring,
    ) = _validated_final_evidence_composition(
        candidate,
        dispositions,
        censoring_records,
    )
    result = authority.finalize_evidence_accounting(
        authority_ref=candidate.construction_authority_ref,
        capability=candidate,
        disposition_refs=disposition_refs,
        dispositions=validated_dispositions,
        censoring_record_refs=censoring_record_refs,
        censoring_records=validated_censoring,
    )
    return _finalized_accounting_from_echo(
        result,
        capability=candidate,
        disposition_refs=disposition_refs,
        dispositions=validated_dispositions,
        censoring_record_refs=censoring_record_refs,
        censoring_records=validated_censoring,
    )


_REALIZED_EVIDENCE_FIELDS = (
    "schema_version",
    "canonicalization_profile",
    "challenge_key",
    "sampling_plan_ref",
    "primary_population_ref",
    "selection_population_ref",
    "target_population_binding",
    "official_proposal_binding",
    "evidence_weight_binding",
    "intended_estimand_or_reporting_ref",
    "evidence_scope",
    "disposition_refs",
    "complete_unit_manifest_ref",
    "accounting_evidence_ref",
    "denominator_policy_ref",
    "censoring_policy_ref",
    "missingness_adjustment_binding",
    "sensitivity_analysis_binding",
    "distribution_conformance_evidence_ref",
    "construction_authority_ref",
    "construction_audit_refs",
    "disclosure_contract",
    "downstream_use_restrictions",
)


@dataclass(frozen=True, slots=True, repr=False)
class RealizedEvidenceLoadVerificationEcho:
    """Exact external history/accounting echo for one realized record load."""

    authority_ref: object
    expected_ref: RealizedValidEvidenceRecordRef
    content_digest: str
    finalization: EvidenceAccountingFinalizationEcho


class RealizedEvidenceHistoryAuthority(Protocol):
    """External authority that reloads exact accounting and disposition history."""

    def verify_realized_evidence_load(
        self,
        *,
        authority_ref: object,
        expected_ref: RealizedValidEvidenceRecordRef,
        content_digest: str,
        decoded_record: object,
    ) -> RealizedEvidenceLoadVerificationEcho:
        """Return immutable history echoes for this digest-pinned record."""
        ...


class RealizedEvidenceLoadAuthority:
    """Non-serializable adapter backed by accounting/history verification.

    This is trusted in-process composition. B-02A does not provide durable
    authorization, credentials, signatures, or the external history service.
    """

    __slots__ = ("_authority", "authority_ref")

    def __init__(
        self,
        *,
        _capability: object,
        authority_ref: object,
        authority: RealizedEvidenceHistoryAuthority,
    ) -> None:
        if _capability is not _REALIZED_LOAD_AUTHORITY_CAPABILITY:
            raise PermissionError(
                "realized-load authority requires controlled issuance"
            )
        owner(authority_ref, "accounting_authority", "authority_ref")
        if callable(authority):
            raise TypeError("realized history authority must not be a raw callable")
        verifier = getattr(authority, "verify_realized_evidence_load", None)
        if not callable(verifier):
            raise TypeError(
                "realized history authority must provide verify_realized_evidence_load"
            )
        self.authority_ref = authority_ref
        self._authority = authority

    def verify(
        self,
        expected_ref: RealizedValidEvidenceRecordRef,
        canonical_bytes: bytes,
        record: object,
    ) -> RealizedValidEvidenceRecord:
        from .canonical import tagged_sha256
        from .model import derived_evidence_from_record

        digest = tagged_sha256(canonical_bytes)
        result = self._authority.verify_realized_evidence_load(
            authority_ref=self.authority_ref,
            expected_ref=expected_ref,
            content_digest=digest,
            decoded_record=record,
        )
        echo = exact(
            result,
            RealizedEvidenceLoadVerificationEcho,
            "realized evidence load verification",
        )
        if (
            type(echo.authority_ref) is not type(self.authority_ref)
            or echo.authority_ref != self.authority_ref
        ):
            raise ValueError("realized load verification authority mismatch")
        if (
            type(echo.expected_ref) is not type(expected_ref)
            or echo.expected_ref != expected_ref
        ):
            raise ValueError("realized load verification expected ref mismatch")
        if echo.content_digest != digest or digest != expected_ref.content_digest:
            raise ValueError("realized load verification digest mismatch")
        finalization = exact(
            echo.finalization,
            EvidenceAccountingFinalizationEcho,
            "realized evidence accounting finalization",
        )
        capability = exact(
            finalization.capability,
            EvidenceAccountingCapability,
            "accounting capability",
        )
        if (
            type(capability.construction_authority_ref) is not type(self.authority_ref)
            or capability.construction_authority_ref != self.authority_ref
        ):
            raise ValueError("realized capability authority mismatch")
        (
            disposition_refs,
            dispositions,
            censoring_record_refs,
            censoring_records,
        ) = _validated_final_evidence_composition(
            capability,
            finalization.dispositions,
            finalization.censoring_records,
        )
        finalized = _finalized_accounting_from_echo(
            finalization,
            capability=capability,
            disposition_refs=disposition_refs,
            dispositions=dispositions,
            censoring_record_refs=censoring_record_refs,
            censoring_records=censoring_records,
        )
        value = exact(
            derived_evidence_from_record(
                record,
                realized_authorization=(finalized, dispositions),
            ),
            RealizedValidEvidenceRecord,
            "realized evidence record",
        )
        if value.to_ref() != expected_ref:
            raise ValueError("realized load differs from its expected reference")
        return value


def _issue_realized_evidence_load_authority(
    *,
    authority_ref: object,
    authority: RealizedEvidenceHistoryAuthority,
) -> RealizedEvidenceLoadAuthority:
    return RealizedEvidenceLoadAuthority(
        _capability=_REALIZED_LOAD_AUTHORITY_CAPABILITY,
        authority_ref=authority_ref,
        authority=authority,
    )


def _issue_evidence_accounting_capability(
    *,
    sampling_plan_ref: SamplingPlanRef,
    complete_unit_manifest_ref: object,
    intended_evidence_unit_refs: tuple[object, ...],
    primary_population_ref: InstanceDistributionContractRef,
    selection_population_ref: InstanceDistributionContractRef,
    target_population_binding: ApplicabilityBinding[InstanceDistributionContractRef],
    official_proposal_binding: ApplicabilityBinding[InstanceDistributionContractRef],
    evidence_weight_binding: ApplicabilityBinding[InstanceDistributionContractRef],
    intended_estimand_or_reporting_ref: object,
    accounting_evidence_ref: object,
    denominator_policy_ref: object,
    censoring_policy_ref: object,
    missingness_adjustment_binding: ApplicabilityBinding[object],
    sensitivity_analysis_binding: ApplicabilityBinding[object],
    construction_authority_ref: object,
    construction_audit_refs: tuple[object, ...],
    authority: EvidenceAccountingRegistryAuthority,
) -> EvidenceAccountingCapability:
    """Package-internal adapter for a trusted external accounting registry."""

    if callable(authority):
        raise TypeError("evidence accounting authority must not be a raw callable")
    verifier = getattr(authority, "verify_evidence_accounting", None)
    if not callable(verifier):
        raise TypeError(
            "evidence accounting authority must provide verify_evidence_accounting"
        )
    capability = EvidenceAccountingCapability(
        _capability=_ACCOUNTING_CAPABILITY,
        sampling_plan_ref=sampling_plan_ref,
        complete_unit_manifest_ref=complete_unit_manifest_ref,
        intended_evidence_unit_refs=intended_evidence_unit_refs,
        primary_population_ref=primary_population_ref,
        selection_population_ref=selection_population_ref,
        target_population_binding=target_population_binding,
        official_proposal_binding=official_proposal_binding,
        evidence_weight_binding=evidence_weight_binding,
        intended_estimand_or_reporting_ref=intended_estimand_or_reporting_ref,
        accounting_evidence_ref=accounting_evidence_ref,
        denominator_policy_ref=denominator_policy_ref,
        censoring_policy_ref=censoring_policy_ref,
        missingness_adjustment_binding=missingness_adjustment_binding,
        sensitivity_analysis_binding=sensitivity_analysis_binding,
        construction_authority_ref=construction_authority_ref,
        construction_audit_refs=construction_audit_refs,
    )
    result = authority.verify_evidence_accounting(candidate=capability)
    _require_accounting_verification_echo(result, capability)
    return capability


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RealizedValidEvidenceRecord:
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    sampling_plan_ref: SamplingPlanRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    target_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    official_proposal_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    evidence_weight_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    intended_estimand_or_reporting_ref: object
    evidence_scope: EvidenceScopeBinding
    disposition_refs: tuple[CanonicalCaseDispositionRef, ...]
    complete_unit_manifest_ref: object
    accounting_evidence_ref: object
    denominator_policy_ref: object
    censoring_policy_ref: object
    missingness_adjustment_binding: ApplicabilityBinding[object]
    sensitivity_analysis_binding: ApplicabilityBinding[object]
    distribution_conformance_evidence_ref: object
    construction_authority_ref: object
    construction_audit_refs: tuple[object, ...]
    disclosure_contract: DisclosureContract
    downstream_use_restrictions: tuple[object, ...]

    def __init__(self, *, _capability: object, **fields: object) -> None:
        if _capability is not _REALIZED_CAPABILITY:
            raise PermissionError(
                "realized evidence requires controlled accounting capability"
            )
        expected = _REALIZED_EVIDENCE_FIELDS
        if set(fields) != set(expected):
            raise TypeError("realized evidence fields are closed and complete")
        for name in expected:
            object.__setattr__(self, name, fields[name])
        self.__post_init__()

    def __post_init__(self) -> None:
        _validate_derived_header(self.schema_version, self.canonicalization_profile)
        object.__setattr__(
            self, "challenge_key", copied_challenge_key(self.challenge_key)
        )
        exact(self.sampling_plan_ref, SamplingPlanRef, "sampling_plan_ref")
        _require_challenge(
            self.sampling_plan_ref, self.challenge_key, "sampling_plan_ref"
        )
        for name in ("primary_population_ref", "selection_population_ref"):
            ref = exact(getattr(self, name), InstanceDistributionContractRef, name)
            _require_challenge(ref, self.challenge_key, name)
        for name, role in (
            ("target_population_binding", PopulationRole.TARGET_WORKLOAD_P),
            ("official_proposal_binding", PopulationRole.OFFICIAL_PROPOSAL_Q),
            ("evidence_weight_binding", PopulationRole.EVIDENCE_WEIGHT_W),
        ):
            binding = exact(getattr(self, name), ApplicabilityBinding, name)
            if binding.is_bound:
                ref = exact(
                    binding.value, InstanceDistributionContractRef, f"{name} value"
                )
                if ref.expected_population_role != role.value:
                    raise ValueError(f"{name} role mismatch")
                _require_challenge(ref, self.challenge_key, name)
        owner(
            self.intended_estimand_or_reporting_ref,
            "intended_estimand_or_reporting",
            "intended_estimand_or_reporting_ref",
        )
        exact(self.evidence_scope, EvidenceScopeBinding, "evidence_scope")
        for ref in _scope_population_refs(self.evidence_scope):
            _require_challenge(ref, self.challenge_key, "evidence_scope")
        dispositions = exact_tuple(
            self.disposition_refs,
            CanonicalCaseDispositionRef,
            "disposition_refs",
            nonempty=True,
            unique=True,
        )
        object.__setattr__(self, "disposition_refs", canonical_set_tuple(dispositions))
        for name, kind in (
            ("complete_unit_manifest_ref", "protected_unit_manifest"),
            ("accounting_evidence_ref", "realized_evidence_accounting"),
            ("denominator_policy_ref", "denominator_policy"),
            ("censoring_policy_ref", "censoring_policy"),
            (
                "distribution_conformance_evidence_ref",
                "distribution_conformance",
            ),
            ("construction_authority_ref", "accounting_authority"),
        ):
            owner(getattr(self, name), kind, name)
        for name, kind in (
            ("missingness_adjustment_binding", "missingness_adjustment"),
            ("sensitivity_analysis_binding", "sensitivity_analysis"),
        ):
            binding = exact(getattr(self, name), ApplicabilityBinding, name)
            if binding.is_bound:
                owner(binding.value, kind, name)
        object.__setattr__(
            self,
            "construction_audit_refs",
            owner_tuple(
                self.construction_audit_refs,
                "audit_evidence",
                "construction_audit_refs",
                nonempty=True,
            ),
        )
        exact(self.disclosure_contract, DisclosureContract, "disclosure_contract")
        object.__setattr__(
            self,
            "downstream_use_restrictions",
            owner_tuple(
                self.downstream_use_restrictions,
                "restriction",
                "downstream_use_restrictions",
                nonempty=True,
            ),
        )

    def to_canonical_record(self):
        return _derived_to_record(self, "realized_valid_evidence_record")

    def canonical_bytes(self) -> bytes:
        return _derived_canonical_bytes(self, "realized_valid_evidence_record")

    def to_ref(self) -> RealizedValidEvidenceRecordRef:
        from .canonical import tagged_sha256

        return RealizedValidEvidenceRecordRef(
            "realized_valid_evidence_record",
            self.schema_version,
            self.canonicalization_profile,
            tagged_sha256(self.canonical_bytes()),
        )


def construct_realized_valid_evidence(
    finalization: FinalizedEvidenceAccountingCapability,
    dispositions: tuple[CanonicalCaseDisposition, ...],
    **fields: object,
) -> RealizedValidEvidenceRecord:
    """Construct only from one externally finalized disposition composition."""

    authorization = exact(
        finalization,
        FinalizedEvidenceAccountingCapability,
        "finalized accounting capability",
    )
    capability = authorization.capability
    validated = canonical_set_tuple(
        exact_tuple(
            dispositions,
            CanonicalCaseDisposition,
            "dispositions",
            nonempty=True,
            unique=True,
        )
    )
    if validated != authorization.dispositions:
        raise ValueError("dispositions differ from finalized accounting composition")
    disposition_refs = canonical_set_tuple(
        tuple(disposition.to_ref() for disposition in validated)
    )
    if disposition_refs != authorization.disposition_refs:
        raise ValueError(
            "disposition refs differ from finalized accounting composition"
        )
    if "disposition_refs" in fields or "complete_unit_manifest_ref" in fields:
        raise TypeError("disposition refs and complete manifest are capability-derived")
    if "construction_authority_ref" in fields or "construction_audit_refs" in fields:
        raise TypeError("construction authority is capability-derived")
    plan_ref = fields.get("sampling_plan_ref")
    if plan_ref != capability.sampling_plan_ref:
        raise ValueError("realized evidence SamplingPlan differs from capability")
    exact_fields = {
        "primary_population_ref": capability.primary_population_ref,
        "selection_population_ref": capability.selection_population_ref,
        "target_population_binding": capability.target_population_binding,
        "official_proposal_binding": capability.official_proposal_binding,
        "evidence_weight_binding": capability.evidence_weight_binding,
        "intended_estimand_or_reporting_ref": (
            capability.intended_estimand_or_reporting_ref
        ),
        "accounting_evidence_ref": capability.accounting_evidence_ref,
        "denominator_policy_ref": capability.denominator_policy_ref,
        "censoring_policy_ref": capability.censoring_policy_ref,
        "missingness_adjustment_binding": (capability.missingness_adjustment_binding),
        "sensitivity_analysis_binding": capability.sensitivity_analysis_binding,
    }
    for name, expected in exact_fields.items():
        if fields.get(name) != expected:
            raise ValueError(f"realized evidence {name} differs from capability")
    primary_ref = capability.primary_population_ref
    evidence_scope = fields.get("evidence_scope")
    intended_units: list[object] = []
    for disposition in validated:
        if disposition.sampling_plan_ref != capability.sampling_plan_ref:
            raise ValueError("disposition SamplingPlan differs from capability")
        if disposition.primary_population_ref != primary_ref:
            raise ValueError("disposition primary population mismatch")
        if disposition.evidence_scope != evidence_scope:
            raise ValueError("disposition evidence scope mismatch")
        intended_units.append(disposition.intended_evidence_unit_ref)
    if len(set(intended_units)) != len(intended_units):
        raise ValueError("multiple dispositions account for one intended evidence unit")
    if set(intended_units) != set(capability.intended_evidence_unit_refs):
        raise ValueError("dispositions do not exactly cover the complete unit manifest")
    return RealizedValidEvidenceRecord(
        _capability=_REALIZED_CAPABILITY,
        disposition_refs=disposition_refs,
        complete_unit_manifest_ref=capability.complete_unit_manifest_ref,
        construction_authority_ref=capability.construction_authority_ref,
        construction_audit_refs=capability.construction_audit_refs,
        **fields,
    )


def _derived_to_record(value: object, record_type: str):
    from .canonical import CanonicalRecord
    from .model import _canonical_value

    converted = _canonical_value(value)
    if type(converted) is not CanonicalRecord or converted.record_type != record_type:
        raise TypeError("value is not the requested derived-evidence record")
    return converted


def _derived_canonical_bytes(value: object, record_type: str) -> bytes:
    from .canonical import canonical_derived_document

    return canonical_derived_document(
        record_type, value.schema_version, _derived_to_record(value, record_type)
    )


def verify_derived_evidence_ref(expected: object, value: object) -> object:
    """Recompute a derived ref and require exact nominal equality."""

    expected_types = {
        CanonicalCaseDisposition: CanonicalCaseDispositionRef,
        CensoringRecord: CensoringRecordRef,
        RealizedValidEvidenceRecord: RealizedValidEvidenceRecordRef,
    }
    expected_type = expected_types.get(type(value))
    if expected_type is None or type(expected) is not expected_type:
        raise TypeError("derived ref and record have different nominal kinds")
    recomputed = value.to_ref()
    if recomputed != expected:
        raise ValueError("derived evidence ref does not match canonical bytes")
    return recomputed


def load_derived_evidence(
    expected_ref: object,
    canonical_bytes: object,
    *,
    realized_authority: RealizedEvidenceLoadAuthority | None = None,
) -> object:
    """Digest-check, decode, reconstruct, and pin one exact derived record."""

    from .canonical import (
        decode_derived_document,
        derived_record_field_names,
        tagged_sha256,
    )
    from .model import derived_evidence_from_record
    from .primitives import MAX_CANONICAL_DOCUMENT_BYTES

    ref_types = {
        CanonicalCaseDispositionRef: "canonical_case_disposition",
        CensoringRecordRef: "censoring_record",
        RealizedValidEvidenceRecordRef: "realized_valid_evidence_record",
    }
    record_type = ref_types.get(type(expected_ref))
    if record_type is None:
        raise TypeError("expected_ref is not an exact derived-evidence ref")
    if type(canonical_bytes) is not bytes:
        raise TypeError("canonical_bytes must be exact immutable bytes")
    if len(canonical_bytes) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise ValueError("derived evidence bytes exceed the canonical document bound")
    # Digest verification intentionally precedes parsing hostile bytes.
    if tagged_sha256(canonical_bytes) != expected_ref.content_digest:
        raise ValueError("derived evidence bytes do not match the expected digest")
    decoded = decode_derived_document(
        canonical_bytes,
        expected_record_type=record_type,
        expected_schema_version=expected_ref.schema_version,
        expected_record_fields=derived_record_field_names(
            record_type,
            schema_version=expected_ref.schema_version,
        ),
    )
    if type(expected_ref) is RealizedValidEvidenceRecordRef:
        if realized_authority is None:
            raise PermissionError(
                "realized evidence requires external accounting/history authority"
            )
        authority = exact(
            realized_authority,
            RealizedEvidenceLoadAuthority,
            "realized load authority",
        )
        value = authority.verify(expected_ref, canonical_bytes, decoded.record)
        verify_derived_evidence_ref(expected_ref, value)
        return value
    elif realized_authority is not None:
        raise ValueError("realized authority supplied for a non-realized record")
    value = derived_evidence_from_record(
        decoded.record,
    )
    verify_derived_evidence_ref(expected_ref, value)
    return value
