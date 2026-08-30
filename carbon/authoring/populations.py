"""Population-role contracts with strict P/Q/w separation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from carbon.registry.model import ChallengeKey

from .model import (
    AllowedConsumer,
    ApplicabilityBinding,
    DisclosureContract,
    PopulationRole,
    WeightingRole,
    canonical_set_tuple,
    exact,
    exact_enum,
    exact_tuple,
    owner,
    owner_tuple,
)
from .physical import _validate_common
from .primitives import validate_canonical_id
from .refs import (
    CandidateOutputContractRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
)


@dataclass(frozen=True, slots=True)
class SupportContract:
    membership_rule_ref: object
    physical_support_ref: object
    representation_support_ref: object
    boundary_semantics_ref: object
    membership_decision_ref: object
    failure_outcome: str

    def __post_init__(self) -> None:
        for name, kind in (
            ("membership_rule_ref", "membership_rule"),
            ("physical_support_ref", "physical_support"),
            ("representation_support_ref", "representation_support"),
            ("boundary_semantics_ref", "support_boundary"),
            ("membership_decision_ref", "membership_decision"),
        ):
            owner(getattr(self, name), kind, name)
        if type(self.failure_outcome) is not str or self.failure_outcome != "REJECT":
            raise ValueError("support failure_outcome must be REJECT")


class LawKind(str, Enum):
    PROBABILITY_LAW = "PROBABILITY_LAW"
    FINITE_ENUMERATION = "FINITE_ENUMERATION"
    SET_MEMBERSHIP_ONLY = "SET_MEMBERSHIP_ONLY"
    NOT_A_PROBABILITY_LAW = "NOT_A_PROBABILITY_LAW"


@dataclass(frozen=True, slots=True)
class ProbabilityLaw:
    base_measure_ref: object
    law_ref: object
    normalization_claim_ref: object

    def __post_init__(self) -> None:
        owner(self.base_measure_ref, "base_measure", "base_measure_ref")
        owner(self.law_ref, "probability_law", "law_ref")
        owner(
            self.normalization_claim_ref,
            "normalization_claim",
            "normalization_claim_ref",
        )


@dataclass(frozen=True, slots=True)
class FiniteEnumeration:
    member_set_ref: object
    multiplicity_semantics_ref: object

    def __post_init__(self) -> None:
        owner(self.member_set_ref, "member_set", "member_set_ref")
        owner(
            self.multiplicity_semantics_ref,
            "multiplicity_semantics",
            "multiplicity_semantics_ref",
        )


@dataclass(frozen=True, slots=True)
class LawSemantics:
    kind: LawKind
    payload: ProbabilityLaw | FiniteEnumeration | object

    def __post_init__(self) -> None:
        exact_enum(self.kind, LawKind, "law kind")
        if self.kind is LawKind.PROBABILITY_LAW:
            exact(self.payload, ProbabilityLaw, "probability law payload")
        elif self.kind is LawKind.FINITE_ENUMERATION:
            exact(self.payload, FiniteEnumeration, "finite enumeration payload")
        elif self.kind is LawKind.SET_MEMBERSHIP_ONLY:
            owner(self.payload, "no_prevalence_claim", "set-only reason")
        else:
            owner(self.payload, "non_probability_reason", "non-probability reason")

    @property
    def executable(self) -> bool:
        return self.kind in {LawKind.PROBABILITY_LAW, LawKind.FINITE_ENUMERATION}


@dataclass(frozen=True, slots=True)
class WeightingPayload:
    weighting_role: WeightingRole
    estimand_scope_ref: object
    weighting_rule_ref: object
    normalization_semantics_ref: object
    target_population_ref: InstanceDistributionContractRef
    proposal_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]

    def __post_init__(self) -> None:
        exact_enum(self.weighting_role, WeightingRole, "weighting role")
        owner(self.estimand_scope_ref, "estimand_scope", "estimand_scope_ref")
        owner(self.weighting_rule_ref, "weighting_rule", "weighting_rule_ref")
        owner(
            self.normalization_semantics_ref,
            "weight_normalization",
            "normalization_semantics_ref",
        )
        ref = exact(
            self.target_population_ref,
            InstanceDistributionContractRef,
            "target_population_ref",
        )
        if ref.expected_population_role != PopulationRole.TARGET_WORKLOAD_P.value:
            raise ValueError("weighting target_population_ref must be P")
        binding = exact(
            self.proposal_population_binding,
            ApplicabilityBinding,
            "proposal_population_binding",
        )
        if binding.is_bound:
            proposal = exact(
                binding.value,
                InstanceDistributionContractRef,
                "proposal_population_binding value",
            )
            if (
                proposal.expected_population_role
                != PopulationRole.OFFICIAL_PROPOSAL_Q.value
            ):
                raise ValueError("weighting proposal binding must be Q")


class WeightingSemanticsKind(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    WEIGHTING = "WEIGHTING"


@dataclass(frozen=True, slots=True)
class WeightingSemantics:
    kind: WeightingSemanticsKind
    payload: WeightingPayload | object

    def __post_init__(self) -> None:
        exact_enum(self.kind, WeightingSemanticsKind, "weighting semantics")
        if self.kind is WeightingSemanticsKind.WEIGHTING:
            exact(self.payload, WeightingPayload, "weighting payload")
        else:
            owner(self.payload, "applicability_reason", "weighting inapplicability")


@dataclass(frozen=True, slots=True)
class StratumContract:
    stratum_id: str
    membership_rule_ref: object
    applicability_ref: object
    hierarchy_binding: ApplicabilityBinding[str]

    def __post_init__(self) -> None:
        validate_canonical_id(self.stratum_id, "stratum_id")
        owner(self.membership_rule_ref, "membership_rule", "membership_rule_ref")
        owner(self.applicability_ref, "applicability", "applicability_ref")
        binding = exact(
            self.hierarchy_binding, ApplicabilityBinding, "hierarchy_binding"
        )
        if binding.is_bound:
            validate_canonical_id(binding.value, "parent_stratum_id")


class StratificationRelationKind(str, Enum):
    DISJOINT_EXHAUSTIVE = "DISJOINT_EXHAUSTIVE"
    DISJOINT_NONEXHAUSTIVE = "DISJOINT_NONEXHAUSTIVE"
    OVERLAP_ALLOWED = "OVERLAP_ALLOWED"


@dataclass(frozen=True, slots=True)
class StratificationRelation:
    kind: StratificationRelationKind
    semantics_ref: object | None = None

    def __post_init__(self) -> None:
        exact_enum(self.kind, StratificationRelationKind, "stratification relation")
        if self.kind is StratificationRelationKind.DISJOINT_EXHAUSTIVE:
            if self.semantics_ref is not None:
                raise ValueError("exhaustive relation has no semantics payload")
        elif self.kind is StratificationRelationKind.DISJOINT_NONEXHAUSTIVE:
            owner(
                self.semantics_ref,
                "nonexhaustive_semantics",
                "nonexhaustive semantics",
            )
        else:
            owner(self.semantics_ref, "overlap_semantics", "overlap semantics")


@dataclass(frozen=True, slots=True)
class StratificationContract:
    stratification_id: str
    basis_population_role: PopulationRole
    strata: tuple[StratumContract, ...]
    relation: StratificationRelation
    assignment_rule_ref: object
    hierarchy_semantics_ref: object
    unassigned_member_rule_ref: object
    disclosure_contract: DisclosureContract

    def __post_init__(self) -> None:
        validate_canonical_id(self.stratification_id, "stratification_id")
        exact_enum(self.basis_population_role, PopulationRole, "basis population role")
        strata = exact_tuple(
            self.strata, StratumContract, "strata", nonempty=True, unique=True
        )
        if len({item.stratum_id for item in strata}) != len(strata):
            raise ValueError("strata contain duplicate IDs")
        known = {item.stratum_id for item in strata}
        for item in strata:
            if (
                item.hierarchy_binding.is_bound
                and item.hierarchy_binding.value not in known
            ):
                raise ValueError("stratum parent is unknown")
            if (
                item.hierarchy_binding.is_bound
                and item.hierarchy_binding.value == item.stratum_id
            ):
                raise ValueError("stratum cannot parent itself")
        parent_by_id = {
            item.stratum_id: (
                item.hierarchy_binding.value
                if item.hierarchy_binding.is_bound
                else None
            )
            for item in strata
        }
        for stratum_id in parent_by_id:
            seen: set[str] = set()
            current: str | None = stratum_id
            while current is not None:
                if current in seen:
                    raise ValueError("stratum hierarchy contains a cycle")
                seen.add(current)
                current = parent_by_id[current]
        object.__setattr__(self, "strata", canonical_set_tuple(strata))
        exact(self.relation, StratificationRelation, "relation")
        owner(self.assignment_rule_ref, "stratum_assignment", "assignment_rule_ref")
        owner(
            self.hierarchy_semantics_ref,
            "stratum_hierarchy",
            "hierarchy_semantics_ref",
        )
        owner(
            self.unassigned_member_rule_ref,
            "stratum_unassigned_rule",
            "unassigned_member_rule_ref",
        )
        exact(self.disclosure_contract, DisclosureContract, "disclosure_contract")


@dataclass(frozen=True, slots=True)
class ExclusionContract:
    exclusion_id: str
    membership_rule_ref: object
    scientific_authority_ref: object
    applicable_claim_ref: object
    audit_semantics_ref: object

    def __post_init__(self) -> None:
        validate_canonical_id(self.exclusion_id, "exclusion_id")
        owner(self.membership_rule_ref, "membership_rule", "membership_rule_ref")
        owner(
            self.scientific_authority_ref,
            "scientific_authority",
            "scientific_authority_ref",
        )
        owner(self.applicable_claim_ref, "claim_scope", "applicable_claim_ref")
        owner(self.audit_semantics_ref, "audit_semantics", "audit_semantics_ref")


def _population_binding(
    binding: ApplicabilityBinding[InstanceDistributionContractRef],
    field: str,
    expected_role: PopulationRole | None,
) -> InstanceDistributionContractRef | None:
    exact(binding, ApplicabilityBinding, field)
    if not binding.is_bound:
        return None
    ref = exact(binding.value, InstanceDistributionContractRef, f"{field} value")
    if (
        expected_role is not None
        and ref.expected_population_role != expected_role.value
    ):
        raise ValueError(f"{field} has the wrong population role")
    return ref


@dataclass(frozen=True, slots=True)
class InstanceDistributionContract:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    supersedes: ApplicabilityBinding[InstanceDistributionContractRef]
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    population_role: PopulationRole
    owning_claim_scope_ref: object
    target_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    proposal_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    support_contract: SupportContract
    law_semantics: LawSemantics
    weighting_semantics: WeightingSemantics
    stratification_binding: ApplicabilityBinding[StratificationContract]
    applicability_refs: tuple[object, ...]
    exclusions: tuple[ExclusionContract, ...]
    rights_profile_ref: object
    permitted_use_refs: tuple[object, ...]
    restrictions: tuple[object, ...]
    disclosure_contract: DisclosureContract
    allowed_consumers: tuple[AllowedConsumer, ...]
    population_provenance: tuple[object, ...]

    def __post_init__(self) -> None:
        if type(self) is not InstanceDistributionContract:
            raise TypeError("InstanceDistributionContract subclasses are rejected")
        copied = _validate_common(
            object_kind=self.object_kind,
            expected_kind="instance_distribution_contract",
            schema_version=self.schema_version,
            canonicalization_profile=self.canonicalization_profile,
            challenge_key=self.challenge_key,
            object_id=self.object_id,
            object_version=self.object_version,
            supersedes=self.supersedes,
            predecessor_type=InstanceDistributionContractRef,
        )
        object.__setattr__(self, "challenge_key", copied)
        for name, ref_type in (
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_ref", CandidateOutputContractRef),
        ):
            ref = exact(getattr(self, name), ref_type, name)
            if ref.challenge_key != copied:
                raise ValueError(f"{name} Challenge mismatch")
        exact_enum(self.population_role, PopulationRole, "population_role")
        owner(
            self.owning_claim_scope_ref,
            "claim_scope",
            "owning_claim_scope_ref",
        )
        target = _population_binding(
            self.target_population_binding,
            "target_population_binding",
            PopulationRole.TARGET_WORKLOAD_P,
        )
        proposal = _population_binding(
            self.proposal_population_binding,
            "proposal_population_binding",
            PopulationRole.OFFICIAL_PROPOSAL_Q,
        )
        exact(self.support_contract, SupportContract, "support_contract")
        exact(self.law_semantics, LawSemantics, "law_semantics")
        exact(self.weighting_semantics, WeightingSemantics, "weighting_semantics")
        role = self.population_role
        if role is PopulationRole.TARGET_WORKLOAD_P:
            if target is not None or proposal is not None:
                raise ValueError("P cannot bind target or proposal populations")
            if self.law_semantics.kind is LawKind.NOT_A_PROBABILITY_LAW:
                raise ValueError("P cannot use NOT_A_PROBABILITY_LAW")
            if (
                self.weighting_semantics.kind
                is not WeightingSemanticsKind.NOT_APPLICABLE
            ):
                raise ValueError("P cannot carry weighting semantics")
        elif role is PopulationRole.OFFICIAL_PROPOSAL_Q:
            if target is None or proposal is not None:
                raise ValueError("Q must bind exact P and no proposal")
            if not self.law_semantics.executable:
                raise ValueError("Q requires an executable selection law")
            if (
                self.weighting_semantics.kind
                is not WeightingSemanticsKind.NOT_APPLICABLE
            ):
                raise ValueError("Q cannot carry weighting semantics")
        elif role is PopulationRole.EVIDENCE_WEIGHT_W:
            if target is None:
                raise ValueError("w must bind exact P")
            if self.law_semantics.kind is not LawKind.NOT_A_PROBABILITY_LAW:
                raise ValueError("w must not be a probability law")
            if self.weighting_semantics.kind is not WeightingSemanticsKind.WEIGHTING:
                raise ValueError("w requires exact weighting semantics")
            payload = exact(
                self.weighting_semantics.payload, WeightingPayload, "weighting payload"
            )
            if payload.target_population_ref != target:
                raise ValueError("nested weighting P must equal outer P")
            if payload.proposal_population_binding != self.proposal_population_binding:
                raise ValueError("nested weighting Q binding must equal outer binding")
        else:
            if proposal is not None:
                raise ValueError("non-w/P/Q role cannot bind official Q")
            if self.law_semantics.kind is LawKind.NOT_A_PROBABILITY_LAW:
                raise ValueError("non-w population needs population/set semantics")
            if (
                self.weighting_semantics.kind
                is not WeightingSemanticsKind.NOT_APPLICABLE
            ):
                raise ValueError("non-w role cannot carry weighting semantics")
        stratification = exact(
            self.stratification_binding,
            ApplicabilityBinding,
            "stratification_binding",
        )
        if stratification.is_bound:
            value = exact(
                stratification.value,
                StratificationContract,
                "stratification binding value",
            )
            if value.basis_population_role is not role:
                raise ValueError("stratification role mismatch")
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
        exclusions = exact_tuple(
            self.exclusions, ExclusionContract, "exclusions", unique=True
        )
        if len({item.exclusion_id for item in exclusions}) != len(exclusions):
            raise ValueError("exclusions contain duplicate IDs")
        if any(
            item.applicable_claim_ref != self.owning_claim_scope_ref
            for item in exclusions
        ):
            raise ValueError(
                "exclusion applicable_claim_ref differs from population claim scope"
            )
        object.__setattr__(self, "exclusions", canonical_set_tuple(exclusions))
        owner(self.rights_profile_ref, "rights_profile", "rights_profile_ref")
        object.__setattr__(
            self,
            "permitted_use_refs",
            owner_tuple(
                self.permitted_use_refs,
                "permitted_use",
                "permitted_use_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "restrictions",
            owner_tuple(self.restrictions, "restriction", "restrictions"),
        )
        exact(self.disclosure_contract, DisclosureContract, "disclosure_contract")
        consumers = exact_tuple(
            self.allowed_consumers,
            AllowedConsumer,
            "allowed_consumers",
            nonempty=True,
            unique=True,
        )
        object.__setattr__(self, "allowed_consumers", canonical_set_tuple(consumers))
        object.__setattr__(
            self,
            "population_provenance",
            owner_tuple(
                self.population_provenance,
                "provenance",
                "population_provenance",
                nonempty=True,
            ),
        )

    def dependency_refs(self) -> tuple[object, ...]:
        refs: list[object] = [self.physical_system_ref, self.candidate_output_ref]
        for binding in (
            self.supersedes,
            self.target_population_binding,
            self.proposal_population_binding,
        ):
            if binding.is_bound:
                refs.append(binding.value)
        if len(set(refs)) != len(refs):
            raise ValueError("dependency refs contain a duplicate")
        return tuple(refs)

    def to_canonical_record(self):
        from .model import authored_object_to_record

        return authored_object_to_record(self)

    def canonical_bytes(self) -> bytes:
        from .model import authored_object_canonical_bytes

        return authored_object_canonical_bytes(self)

    def to_ref(self) -> InstanceDistributionContractRef:
        from .model import authored_object_to_ref

        return authored_object_to_ref(self)


def assert_population_role(
    value: InstanceDistributionContract, expected: PopulationRole
) -> None:
    exact(value, InstanceDistributionContract, "population")
    exact_enum(expected, PopulationRole, "expected population role")
    if value.population_role is not expected:
        raise ValueError("population role confusion")


def validate_population_graph(
    value: InstanceDistributionContract,
    *,
    target: InstanceDistributionContract | None = None,
    proposal: InstanceDistributionContract | None = None,
) -> None:
    """Validate loaded P/Q/w refs without inferring identity from support."""

    exact(value, InstanceDistributionContract, "population")
    if value.target_population_binding.is_bound:
        if type(target) is not InstanceDistributionContract:
            raise ValueError("bound target population must be loaded exactly")
        assert_population_role(target, PopulationRole.TARGET_WORKLOAD_P)
        if target.challenge_key != value.challenge_key:
            raise ValueError("target population Challenge mismatch")
        if (
            target.physical_system_ref != value.physical_system_ref
            or target.candidate_output_ref != value.candidate_output_ref
            or target.owning_claim_scope_ref != value.owning_claim_scope_ref
        ):
            raise ValueError("target population contract graph mismatch")
    elif target is not None:
        raise ValueError("unbound target cannot be supplied")
    if value.proposal_population_binding.is_bound:
        if type(proposal) is not InstanceDistributionContract:
            raise ValueError("bound proposal population must be loaded exactly")
        assert_population_role(proposal, PopulationRole.OFFICIAL_PROPOSAL_Q)
        if proposal.challenge_key != value.challenge_key:
            raise ValueError("proposal population Challenge mismatch")
        if (
            proposal.physical_system_ref != value.physical_system_ref
            or proposal.candidate_output_ref != value.candidate_output_ref
            or proposal.owning_claim_scope_ref != value.owning_claim_scope_ref
        ):
            raise ValueError("proposal population contract graph mismatch")
        if not proposal.target_population_binding.is_bound:
            raise ValueError("proposal population does not bind a target")
        if (
            target is None
            or proposal.target_population_binding.value != target.to_ref()
        ):
            raise ValueError("proposal population target differs from weighting target")
    elif proposal is not None:
        raise ValueError("unbound proposal cannot be supplied")
