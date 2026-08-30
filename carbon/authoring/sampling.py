"""Prospective finite-evidence SamplingPlan contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from carbon.registry.model import ChallengeKey

from .model import (
    ApplicabilityBinding,
    CensoringReason,
    FiniteDesignMode,
    PopulationRole,
    ProtectedPlanFieldKind,
    PublicPlanFactKind,
    SamplingRole,
    canonical_set_tuple,
    copied_challenge_key,
    exact,
    exact_enum,
    exact_tuple,
    fraction,
    owner,
    owner_tuple,
    positive_uint64,
)
from .physical import _validate_common
from .populations import LawKind, LawSemantics
from .primitives import validate_canonical_id
from .refs import InstanceDistributionContractRef, SamplingPlanRef


class AllocationKind(str, Enum):
    COUNT = "COUNT"
    FRACTION = "FRACTION"
    OWNER_RULE = "OWNER_RULE"


@dataclass(frozen=True, slots=True)
class FractionAllocation:
    fraction: float
    exact_sum_semantics_ref: object
    zero_allocation_binding: ApplicabilityBinding[object]

    def __post_init__(self) -> None:
        checked = fraction(self.fraction, "fraction")
        object.__setattr__(self, "fraction", checked)
        owner(
            self.exact_sum_semantics_ref,
            "allocation_sum_semantics",
            "exact_sum_semantics_ref",
        )
        binding = exact(
            self.zero_allocation_binding,
            ApplicabilityBinding,
            "zero_allocation_binding",
        )
        if checked == 0.0:
            if not binding.is_bound:
                raise ValueError(
                    "zero fraction requires exact zero-allocation authority"
                )
            owner(
                binding.value, "zero_allocation_authority", "zero allocation authority"
            )
        elif binding.is_bound:
            raise ValueError("positive fraction cannot carry zero-allocation authority")


@dataclass(frozen=True, slots=True)
class Allocation:
    kind: AllocationKind
    payload: int | FractionAllocation | object

    def __post_init__(self) -> None:
        exact_enum(self.kind, AllocationKind, "allocation kind")
        if self.kind is AllocationKind.COUNT:
            positive_uint64(self.payload, "allocation count")
        elif self.kind is AllocationKind.FRACTION:
            exact(self.payload, FractionAllocation, "fraction allocation")
        else:
            owner(self.payload, "allocation_rule", "allocation rule")


@dataclass(frozen=True, slots=True)
class StratumAllocation:
    primary_stratum_id: str
    selection_stratum_binding: ApplicabilityBinding[str]
    allocation: Allocation

    def __post_init__(self) -> None:
        validate_canonical_id(self.primary_stratum_id, "primary_stratum_id")
        binding = exact(
            self.selection_stratum_binding,
            ApplicabilityBinding,
            "selection_stratum_binding",
        )
        if binding.is_bound:
            validate_canonical_id(binding.value, "selection_stratum_id")
        exact(self.allocation, Allocation, "allocation")


@dataclass(frozen=True, slots=True)
class StratifiedAllocationContract:
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    primary_stratification_id: str
    selection_stratification_id: str
    stratum_mapping_ref: object
    allocations: tuple[StratumAllocation, ...]
    allocation_total_semantics_ref: object
    apportionment_rule_ref: object
    tie_rule_ref: object
    overlap_accounting_ref: object

    def __post_init__(self) -> None:
        exact(
            self.primary_population_ref,
            InstanceDistributionContractRef,
            "primary_population_ref",
        )
        exact(
            self.selection_population_ref,
            InstanceDistributionContractRef,
            "selection_population_ref",
        )
        for name in ("primary_stratification_id", "selection_stratification_id"):
            validate_canonical_id(getattr(self, name), name)
        for name, kind in (
            ("stratum_mapping_ref", "stratum_mapping"),
            ("allocation_total_semantics_ref", "allocation_total_semantics"),
            ("apportionment_rule_ref", "apportionment_rule"),
            ("tie_rule_ref", "tie_rule"),
            ("overlap_accounting_ref", "overlap_accounting"),
        ):
            owner(getattr(self, name), kind, name)
        allocations = exact_tuple(
            self.allocations,
            StratumAllocation,
            "allocations",
            nonempty=True,
            unique=True,
        )
        if len({item.primary_stratum_id for item in allocations}) != len(allocations):
            raise ValueError("allocations contain duplicate primary strata")
        object.__setattr__(self, "allocations", canonical_set_tuple(allocations))


@dataclass(frozen=True, slots=True)
class DuplicatePolicy:
    physical_duplicate_rule_ref: object
    representation_duplicate_rule_ref: object
    near_duplicate_rule_ref: object
    repeated_observation_rule_ref: object
    replacement_duplicate_rule_ref: object

    def __post_init__(self) -> None:
        for name in self.__slots__:
            owner(getattr(self, name), "duplicate_rule", name)


class ReplacementTriggerKind(str, Enum):
    CENSORED = "CENSORED"
    GENERATION_FAILURE = "GENERATION_FAILURE"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True, slots=True)
class ReplacementTrigger:
    kind: ReplacementTriggerKind
    payload: CensoringReason | object

    def __post_init__(self) -> None:
        exact_enum(self.kind, ReplacementTriggerKind, "replacement trigger kind")
        if self.kind is ReplacementTriggerKind.CENSORED:
            exact_enum(self.payload, CensoringReason, "censoring replacement reason")
        elif self.kind is ReplacementTriggerKind.GENERATION_FAILURE:
            owner(
                self.payload,
                "replacement_eligible_generation_failure_reason",
                "generation-failure replacement reason",
            )
        else:
            owner(
                self.payload,
                "prospective_exclusion_contract",
                "exclusion replacement contract",
            )


@dataclass(frozen=True, slots=True)
class RegisteredReplacementPolicy:
    policy_ref: object
    triggers: tuple[ReplacementTrigger, ...]
    replacement_selection_law_ref: object
    stratum_treatment_ref: object
    maximum_attempt_rule_ref: object
    accounting_rule_ref: object
    denominator_effect_ref: object
    weight_effect_ref: object

    def __post_init__(self) -> None:
        owner(self.policy_ref, "replacement_policy", "policy_ref")
        triggers = exact_tuple(
            self.triggers,
            ReplacementTrigger,
            "replacement triggers",
            nonempty=True,
            unique=True,
        )
        object.__setattr__(self, "triggers", canonical_set_tuple(triggers))
        for name, kind in (
            ("replacement_selection_law_ref", "replacement_selection_law"),
            ("stratum_treatment_ref", "replacement_stratum_treatment"),
            ("maximum_attempt_rule_ref", "maximum_attempt_rule"),
            ("accounting_rule_ref", "replacement_accounting"),
            ("denominator_effect_ref", "denominator_effect"),
            ("weight_effect_ref", "weight_effect"),
        ):
            owner(getattr(self, name), kind, name)


class ReplacementPolicyKind(str, Enum):
    NEVER = "NEVER"
    ON_REGISTERED_TRIGGERS = "ON_REGISTERED_TRIGGERS"


@dataclass(frozen=True, slots=True)
class ReplacementPolicy:
    kind: ReplacementPolicyKind
    payload: RegisteredReplacementPolicy | None

    def __post_init__(self) -> None:
        exact_enum(self.kind, ReplacementPolicyKind, "replacement policy kind")
        if self.kind is ReplacementPolicyKind.NEVER:
            if self.payload is not None:
                raise ValueError("NEVER replacement policy has no payload")
        else:
            exact(
                self.payload, RegisteredReplacementPolicy, "replacement policy payload"
            )


class CandidateOutcomeAccessKind(str, Enum):
    CANDIDATE_OUTCOMES_PROHIBITED = "CANDIDATE_OUTCOMES_PROHIBITED"
    REGISTERED_ADAPTIVE = "REGISTERED_ADAPTIVE"


@dataclass(frozen=True, slots=True)
class RegisteredAdaptiveAccess:
    coverage_qualification_ref: object
    sequential_rule_ref: object

    def __post_init__(self) -> None:
        owner(
            self.coverage_qualification_ref,
            "coverage_qualification",
            "coverage_qualification_ref",
        )
        owner(
            self.sequential_rule_ref,
            "sequential_allocation_rule",
            "sequential_rule_ref",
        )


@dataclass(frozen=True, slots=True)
class CandidateOutcomeAccessBinding:
    kind: CandidateOutcomeAccessKind
    payload: RegisteredAdaptiveAccess | object

    def __post_init__(self) -> None:
        exact_enum(self.kind, CandidateOutcomeAccessKind, "candidate outcome access")
        if self.kind is CandidateOutcomeAccessKind.CANDIDATE_OUTCOMES_PROHIBITED:
            owner(self.payload, "blinding_policy", "blinding_policy_ref")
        else:
            exact(self.payload, RegisteredAdaptiveAccess, "adaptive access payload")


@dataclass(frozen=True, slots=True)
class FiniteEvidenceDesign:
    count_unit_ref: object
    design_mode: FiniteDesignMode
    base_intended_count: int
    base_evidence_requirement_ref: object
    budget_binding: ApplicabilityBinding[object]
    extension_ceiling_binding: ApplicabilityBinding[object]
    heuristic_stop_outcome: str
    insufficiency_state: str
    insufficiency_reason: str
    plan_change_rule: str

    def __post_init__(self) -> None:
        owner(self.count_unit_ref, "sampling_unit", "count_unit_ref")
        exact_enum(self.design_mode, FiniteDesignMode, "design_mode")
        positive_uint64(self.base_intended_count, "base_intended_count")
        owner(
            self.base_evidence_requirement_ref,
            "base_evidence_requirement",
            "base_evidence_requirement_ref",
        )
        budget = exact(self.budget_binding, ApplicabilityBinding, "budget_binding")
        ceiling = exact(
            self.extension_ceiling_binding,
            ApplicabilityBinding,
            "extension_ceiling_binding",
        )
        if self.design_mode is FiniteDesignMode.FIXED:
            budget.require_not_applicable("fixed budget_binding")
            ceiling.require_not_applicable("fixed extension_ceiling_binding")
        else:
            if not budget.is_bound or not ceiling.is_bound:
                raise ValueError(
                    "sequential design requires budget and extension ceiling"
                )
            owner(budget.value, "evidence_budget", "budget_binding")
            owner(ceiling.value, "extension_ceiling", "extension_ceiling_binding")
        required_literals = {
            "heuristic_stop_outcome": "EVIDENCE_DEFERRED",
            "insufficiency_state": "INDETERMINATE",
            "insufficiency_reason": "INSUFFICIENT_EVIDENCE",
            "plan_change_rule": "NEW_VERSION_REQUIRED",
        }
        for name, expected in required_literals.items():
            if type(getattr(self, name)) is not str or getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")


@dataclass(frozen=True, slots=True)
class ProspectiveStoppingExtensionPolicy:
    stopping_rule_ref: object
    extension_rule_binding: ApplicabilityBinding[object]
    interim_look_binding: ApplicabilityBinding[object]
    sequential_allocation_binding: ApplicabilityBinding[object]
    candidate_outcome_access_binding: CandidateOutcomeAccessBinding
    coverage_qualification_binding: ApplicabilityBinding[object]
    modification_authority_ref: object

    def __post_init__(self) -> None:
        owner(self.stopping_rule_ref, "stopping_rule", "stopping_rule_ref")
        for name, kind in (
            ("extension_rule_binding", "extension_rule"),
            ("interim_look_binding", "interim_look_rule"),
            ("sequential_allocation_binding", "sequential_allocation_rule"),
            ("coverage_qualification_binding", "coverage_qualification"),
        ):
            binding = exact(getattr(self, name), ApplicabilityBinding, name)
            if binding.is_bound:
                owner(binding.value, kind, name)
        exact(
            self.candidate_outcome_access_binding,
            CandidateOutcomeAccessBinding,
            "candidate_outcome_access_binding",
        )
        owner(
            self.modification_authority_ref,
            "modification_authority",
            "modification_authority_ref",
        )


_PRIMARY_ROLE = {
    SamplingRole.OFFICIAL_EVALUATION: PopulationRole.TARGET_WORKLOAD_P,
    SamplingRole.STRESS: PopulationRole.STRESS,
    SamplingRole.PRACTICE: PopulationRole.PRACTICE,
    SamplingRole.PRODUCT_QUALIFICATION: PopulationRole.PRODUCT_QUALIFICATION,
    SamplingRole.VERIFICATION: PopulationRole.EVIDENCE_CAMPAIGN,
    SamplingRole.EVIDENCE_CAMPAIGN: PopulationRole.EVIDENCE_CAMPAIGN,
}

_SELECTION_ROLE = {
    **_PRIMARY_ROLE,
    SamplingRole.OFFICIAL_EVALUATION: PopulationRole.OFFICIAL_PROPOSAL_Q,
}


def _ref_role(ref: object, expected: PopulationRole, field: str) -> None:
    checked = exact(ref, InstanceDistributionContractRef, field)
    if checked.expected_population_role != expected.value:
        raise ValueError(f"{field} has wrong role for SamplingPlan")


@dataclass(frozen=True, slots=True)
class SamplingPlan:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    supersedes: ApplicabilityBinding[SamplingPlanRef]
    sampling_role: SamplingRole
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    target_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    official_proposal_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    evidence_weight_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    query_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    observation_population_binding: ApplicabilityBinding[
        InstanceDistributionContractRef
    ]
    evidence_campaign_binding: ApplicabilityBinding[object]
    intended_estimand_or_reporting_ref: object
    finite_evidence_design: FiniteEvidenceDesign
    full_design_law_ref: object
    stratified_allocation_binding: ApplicabilityBinding[StratifiedAllocationContract]
    query_observation_allocation_binding: ApplicabilityBinding[object]
    reference_fidelity_allocation_binding: ApplicabilityBinding[object]
    replication_dependence_policy_ref: object
    uncertainty_resolution_objectives_binding: ApplicabilityBinding[object]
    tail_resolution_objectives_binding: ApplicabilityBinding[object]
    minimum_subgroup_objectives_binding: ApplicabilityBinding[object]
    draw_order_semantics_ref: object
    stopping_extension_policy: ProspectiveStoppingExtensionPolicy
    replacement_policy: ReplacementPolicy
    duplicate_policy: DuplicatePolicy
    inclusion_policy_ref: object
    exclusion_policy_ref: object
    censoring_policy_ref: object
    public_authored_facts: tuple[PublicPlanFactKind, ...]
    protected_realization_fields: tuple[ProtectedPlanFieldKind, ...]
    statistical_qualification_requirements_ref: object
    plan_provenance_refs: tuple[object, ...]
    insufficient_or_failure_policy: str

    def __post_init__(self) -> None:
        if type(self) is not SamplingPlan:
            raise TypeError("SamplingPlan subclasses are rejected")
        copied = _validate_common(
            object_kind=self.object_kind,
            expected_kind="sampling_plan",
            schema_version=self.schema_version,
            canonicalization_profile=self.canonicalization_profile,
            challenge_key=self.challenge_key,
            object_id=self.object_id,
            object_version=self.object_version,
            supersedes=self.supersedes,
            predecessor_type=SamplingPlanRef,
        )
        object.__setattr__(self, "challenge_key", copied_challenge_key(copied))
        exact_enum(self.sampling_role, SamplingRole, "sampling_role")
        _ref_role(
            self.primary_population_ref,
            _PRIMARY_ROLE[self.sampling_role],
            "primary_population_ref",
        )
        _ref_role(
            self.selection_population_ref,
            _SELECTION_ROLE[self.sampling_role],
            "selection_population_ref",
        )
        for ref in (self.primary_population_ref, self.selection_population_ref):
            if ref.challenge_key != copied:
                raise ValueError("SamplingPlan population Challenge mismatch")
        for field, role in (
            ("target_population_binding", PopulationRole.TARGET_WORKLOAD_P),
            ("official_proposal_binding", PopulationRole.OFFICIAL_PROPOSAL_Q),
            ("evidence_weight_binding", PopulationRole.EVIDENCE_WEIGHT_W),
            ("query_population_binding", PopulationRole.QUERY),
            ("observation_population_binding", PopulationRole.OBSERVATION),
        ):
            binding = exact(getattr(self, field), ApplicabilityBinding, field)
            if binding.is_bound:
                _ref_role(binding.value, role, field)
                if binding.value.challenge_key != copied:
                    raise ValueError(f"{field} Challenge mismatch")
        if self.sampling_role is SamplingRole.OFFICIAL_EVALUATION:
            target = self.target_population_binding.require_bound(
                InstanceDistributionContractRef, "official target_population_binding"
            )
            proposal = self.official_proposal_binding.require_bound(
                InstanceDistributionContractRef, "official_proposal_binding"
            )
            if (
                target != self.primary_population_ref
                or proposal != self.selection_population_ref
            ):
                raise ValueError(
                    "official plan P/Q bindings must equal primary/selection"
                )
        else:
            self.official_proposal_binding.require_not_applicable(
                "non-official official_proposal_binding"
            )
            if self.sampling_role is SamplingRole.VERIFICATION:
                self.target_population_binding.require_not_applicable(
                    "verification target_population_binding"
                )
            if self.sampling_role is SamplingRole.STRESS:
                self.target_population_binding.require_bound(
                    InstanceDistributionContractRef,
                    "stress target_population_binding",
                )
        campaign = exact(
            self.evidence_campaign_binding,
            ApplicabilityBinding,
            "evidence_campaign_binding",
        )
        if (
            self.sampling_role
            in {
                SamplingRole.PRODUCT_QUALIFICATION,
                SamplingRole.VERIFICATION,
                SamplingRole.EVIDENCE_CAMPAIGN,
            }
            and not campaign.is_bound
        ):
            raise ValueError("sampling role requires an evidence campaign")
        if campaign.is_bound:
            owner(campaign.value, "evidence_campaign", "evidence_campaign_binding")
        owner(
            self.intended_estimand_or_reporting_ref,
            "intended_estimand_or_reporting",
            "intended_estimand_or_reporting_ref",
        )
        exact(
            self.finite_evidence_design, FiniteEvidenceDesign, "finite_evidence_design"
        )
        owner(self.full_design_law_ref, "full_design_law", "full_design_law_ref")
        stratified = exact(
            self.stratified_allocation_binding,
            ApplicabilityBinding,
            "stratified_allocation_binding",
        )
        if stratified.is_bound:
            allocation = exact(
                stratified.value,
                StratifiedAllocationContract,
                "stratified allocation",
            )
            if (
                allocation.primary_population_ref != self.primary_population_ref
                or allocation.selection_population_ref != self.selection_population_ref
            ):
                raise ValueError("stratified allocation population mismatch")
        for field, kind in (
            ("query_observation_allocation_binding", "query_observation_allocation"),
            ("reference_fidelity_allocation_binding", "reference_fidelity_allocation"),
            ("uncertainty_resolution_objectives_binding", "statistics_objective"),
            ("tail_resolution_objectives_binding", "statistics_objective"),
            ("minimum_subgroup_objectives_binding", "statistics_objective"),
        ):
            binding = exact(getattr(self, field), ApplicabilityBinding, field)
            if binding.is_bound:
                owner(binding.value, kind, field)
        for name, kind in (
            ("replication_dependence_policy_ref", "replication_dependence_policy"),
            ("draw_order_semantics_ref", "draw_order_semantics"),
            ("inclusion_policy_ref", "inclusion_policy"),
            ("exclusion_policy_ref", "exclusion_policy"),
            ("censoring_policy_ref", "censoring_policy"),
            (
                "statistical_qualification_requirements_ref",
                "statistical_qualification_requirement",
            ),
        ):
            owner(getattr(self, name), kind, name)
        exact(
            self.stopping_extension_policy,
            ProspectiveStoppingExtensionPolicy,
            "stopping_extension_policy",
        )
        mode = self.finite_evidence_design.design_mode
        policy = self.stopping_extension_policy
        sequential_bindings = (
            policy.extension_rule_binding,
            policy.interim_look_binding,
            policy.sequential_allocation_binding,
            policy.coverage_qualification_binding,
        )
        if mode is FiniteDesignMode.FIXED:
            if any(binding.is_bound for binding in sequential_bindings):
                raise ValueError("fixed design cannot carry sequential controls")
            if (
                policy.candidate_outcome_access_binding.kind
                is not CandidateOutcomeAccessKind.CANDIDATE_OUTCOMES_PROHIBITED
            ):
                raise ValueError("fixed design prohibits candidate outcomes")
        elif not all(binding.is_bound for binding in sequential_bindings):
            raise ValueError("sequential design requires every sequential control")
        if (
            policy.candidate_outcome_access_binding.kind
            is CandidateOutcomeAccessKind.REGISTERED_ADAPTIVE
        ):
            adaptive = exact(
                policy.candidate_outcome_access_binding.payload,
                RegisteredAdaptiveAccess,
                "adaptive access",
            )
            if (
                adaptive.coverage_qualification_ref
                != policy.coverage_qualification_binding.value
            ):
                raise ValueError("adaptive coverage ref mismatch")
            if (
                adaptive.sequential_rule_ref
                != policy.sequential_allocation_binding.value
            ):
                raise ValueError("adaptive sequential rule mismatch")
        exact(self.replacement_policy, ReplacementPolicy, "replacement_policy")
        exact(self.duplicate_policy, DuplicatePolicy, "duplicate_policy")
        public = exact_tuple(
            self.public_authored_facts,
            PublicPlanFactKind,
            "public_authored_facts",
            unique=True,
        )
        protected = exact_tuple(
            self.protected_realization_fields,
            ProtectedPlanFieldKind,
            "protected_realization_fields",
            unique=True,
        )
        object.__setattr__(self, "public_authored_facts", canonical_set_tuple(public))
        object.__setattr__(
            self,
            "protected_realization_fields",
            canonical_set_tuple(protected),
        )
        object.__setattr__(
            self,
            "plan_provenance_refs",
            owner_tuple(
                self.plan_provenance_refs,
                "provenance",
                "plan_provenance_refs",
                nonempty=True,
            ),
        )
        if (
            type(self.insufficient_or_failure_policy) is not str
            or self.insufficient_or_failure_policy != "NON_SETTLING_FAIL_CLOSED"
        ):
            raise ValueError(
                "insufficient_or_failure_policy must be NON_SETTLING_FAIL_CLOSED"
            )

    def dependency_refs(self) -> tuple[object, ...]:
        refs: list[object] = [
            self.primary_population_ref,
            self.selection_population_ref,
        ]
        for binding in (
            self.supersedes,
            self.target_population_binding,
            self.official_proposal_binding,
            self.evidence_weight_binding,
            self.query_population_binding,
            self.observation_population_binding,
        ):
            if binding.is_bound:
                refs.append(binding.value)
        if len(set(refs)) != len(refs):
            # Repeated identity across semantically distinct fields is allowed
            # only for primary/selection in non-official same-law plans.  The
            # dependency set itself is still canonicalized without duplicates.
            refs = list(dict.fromkeys(refs))
        return tuple(refs)

    def to_canonical_record(self):
        from .model import authored_object_to_record

        return authored_object_to_record(self)

    def canonical_bytes(self) -> bytes:
        from .model import authored_object_canonical_bytes

        return authored_object_canonical_bytes(self)

    def to_ref(self) -> SamplingPlanRef:
        from .model import authored_object_to_ref

        return authored_object_to_ref(self)


def validate_sampling_selection_law(plan: SamplingPlan, law: LawSemantics) -> None:
    exact(plan, SamplingPlan, "plan")
    exact(law, LawSemantics, "selection law")
    if law.kind not in {LawKind.PROBABILITY_LAW, LawKind.FINITE_ENUMERATION}:
        raise ValueError(
            "an executable SamplingPlan requires an executable selection law"
        )
