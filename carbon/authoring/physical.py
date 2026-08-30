"""Physical-system and candidate causal contracts owned by B-02A."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from carbon.registry.model import ChallengeKey

from .model import (
    ApplicabilityBinding,
    ApplicabilityTag,
    PrecisionLiteral,
    TimeMode,
    canonical_id_sequence,
    canonical_set_tuple,
    copied_challenge_key,
    exact,
    exact_enum,
    exact_tuple,
    owner,
    owner_sequence,
    owner_tuple,
)
from .primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
    validate_canonical_id,
    validate_positive_uint64,
    validate_version_token,
)
from .refs import CandidateOutputContractRef, PhysicalSystemSpecRef


class AxisExtentKind(str, Enum):
    FIXED = "FIXED"
    SYMBOLIC = "SYMBOLIC"
    OWNER_CONSTRAINT = "OWNER_CONSTRAINT"


@dataclass(frozen=True, slots=True)
class AxisExtent:
    kind: AxisExtentKind
    fixed_extent: int | None = None
    symbolic_axis_id: str | None = None
    constraint_ref: object | None = None

    def __post_init__(self) -> None:
        exact_enum(self.kind, AxisExtentKind, "axis extent kind")
        if self.kind is AxisExtentKind.FIXED:
            validate_positive_uint64(self.fixed_extent, "fixed_extent")
            if self.symbolic_axis_id is not None or self.constraint_ref is not None:
                raise ValueError("FIXED extent has only fixed_extent")
            return
        if self.fixed_extent is not None:
            raise ValueError("non-FIXED extent cannot carry fixed_extent")
        if self.kind is AxisExtentKind.SYMBOLIC:
            validate_canonical_id(self.symbolic_axis_id, "symbolic_axis_id")
        elif self.symbolic_axis_id is not None:
            raise ValueError("OWNER_CONSTRAINT has no symbolic_axis_id")
        owner(self.constraint_ref, "axis_constraint", "constraint_ref")


@dataclass(frozen=True, slots=True)
class AxisContract:
    axis_id: str
    semantic_role_ref: object
    unit_ref: object
    extent: AxisExtent

    def __post_init__(self) -> None:
        validate_canonical_id(self.axis_id, "axis_id")
        owner(self.semantic_role_ref, "semantic_clause", "semantic_role_ref")
        owner(self.unit_ref, "unit", "unit_ref")
        exact(self.extent, AxisExtent, "extent")


class PresenceKind(str, Enum):
    REQUIRED = "REQUIRED"
    CONDITIONALLY_REQUIRED = "CONDITIONALLY_REQUIRED"


@dataclass(frozen=True, slots=True)
class Presence:
    kind: PresenceKind
    applicability_ref: object | None = None

    def __post_init__(self) -> None:
        exact_enum(self.kind, PresenceKind, "presence kind")
        if self.kind is PresenceKind.REQUIRED:
            if self.applicability_ref is not None:
                raise ValueError("REQUIRED presence has no applicability ref")
        else:
            owner(self.applicability_ref, "applicability", "applicability_ref")


@dataclass(frozen=True, slots=True)
class ValueFieldContract:
    field_id: str
    semantic_role_ref: object
    representation_ref: object
    unit_ref: object
    shape_contract: tuple[AxisContract, ...]
    precision_contract: tuple[PrecisionLiteral, ...]
    geometry_binding: ApplicabilityBinding[object]
    presence: Presence
    admissibility_refs: tuple[object, ...]
    nonfinite_policy: str

    def __post_init__(self) -> None:
        validate_canonical_id(self.field_id, "field_id")
        owner(self.semantic_role_ref, "semantic_clause", "semantic_role_ref")
        owner(self.representation_ref, "representation", "representation_ref")
        owner(self.unit_ref, "unit", "unit_ref")
        axes = exact_tuple(self.shape_contract, AxisContract, "shape_contract")
        if len({axis.axis_id for axis in axes}) != len(axes):
            raise ValueError("shape_contract contains duplicate axis IDs")
        object.__setattr__(self, "shape_contract", tuple(axes))
        precisions = exact_tuple(
            self.precision_contract,
            PrecisionLiteral,
            "precision_contract",
            nonempty=True,
            unique=True,
        )
        object.__setattr__(self, "precision_contract", canonical_set_tuple(precisions))
        binding = exact(self.geometry_binding, ApplicabilityBinding, "geometry_binding")
        if binding.is_bound:
            owner(binding.value, "geometry_domain", "geometry_binding")
        exact(self.presence, Presence, "presence")
        object.__setattr__(
            self,
            "admissibility_refs",
            owner_tuple(
                self.admissibility_refs, "semantic_clause", "admissibility_refs"
            ),
        )
        if type(self.nonfinite_policy) is not str or self.nonfinite_policy != "REJECT":
            raise ValueError("nonfinite_policy must be REJECT")


@dataclass(frozen=True, slots=True)
class AssumptionClause:
    assumption_id: str
    semantic_ref: object
    applicability: ApplicabilityBinding[object]
    authority_ref: object

    def __post_init__(self) -> None:
        validate_canonical_id(self.assumption_id, "assumption_id")
        owner(self.semantic_ref, "semantic_clause", "semantic_ref")
        exact(self.applicability, ApplicabilityBinding, "applicability")
        if self.applicability.is_bound:
            owner(self.applicability.value, "applicability", "applicability")
        owner(self.authority_ref, "scientific_authority", "authority_ref")


@dataclass(frozen=True, slots=True)
class BoundaryRegionClause:
    region_clause_id: str
    geometry_region_ref: object
    condition_semantic_ref: object
    causal_input_binding: ApplicabilityBinding[str]
    unit_ref: object
    applicability: ApplicabilityBinding[object]

    def __post_init__(self) -> None:
        validate_canonical_id(self.region_clause_id, "region_clause_id")
        owner(self.geometry_region_ref, "geometry_region", "geometry_region_ref")
        owner(
            self.condition_semantic_ref,
            "semantic_clause",
            "condition_semantic_ref",
        )
        exact(self.causal_input_binding, ApplicabilityBinding, "causal_input_binding")
        if self.causal_input_binding.is_bound:
            validate_canonical_id(
                self.causal_input_binding.value, "causal_input_binding"
            )
        owner(self.unit_ref, "unit", "unit_ref")
        exact(self.applicability, ApplicabilityBinding, "applicability")
        if self.applicability.is_bound:
            owner(self.applicability.value, "applicability", "applicability")


@dataclass(frozen=True, slots=True)
class BoundaryConditionContract:
    clauses: tuple[BoundaryRegionClause, ...]

    def __post_init__(self) -> None:
        clauses = exact_tuple(self.clauses, BoundaryRegionClause, "boundary clauses")
        if len({item.region_clause_id for item in clauses}) != len(clauses):
            raise ValueError("boundary clauses contain duplicate IDs")
        object.__setattr__(self, "clauses", tuple(clauses))


@dataclass(frozen=True, slots=True)
class InitialStateClause:
    state_clause_id: str
    state_semantic_ref: object
    causal_input_binding: ApplicabilityBinding[str]
    geometry_domain_ref: object
    time_origin_ref: object
    applicability: ApplicabilityBinding[object]

    def __post_init__(self) -> None:
        validate_canonical_id(self.state_clause_id, "state_clause_id")
        owner(self.state_semantic_ref, "semantic_clause", "state_semantic_ref")
        exact(self.causal_input_binding, ApplicabilityBinding, "causal_input_binding")
        if self.causal_input_binding.is_bound:
            validate_canonical_id(
                self.causal_input_binding.value, "causal_input_binding"
            )
        owner(self.geometry_domain_ref, "geometry_domain", "geometry_domain_ref")
        owner(self.time_origin_ref, "semantic_clause", "time_origin_ref")
        exact(self.applicability, ApplicabilityBinding, "applicability")
        if self.applicability.is_bound:
            owner(self.applicability.value, "applicability", "applicability")


@dataclass(frozen=True, slots=True)
class InitialConditionContract:
    clauses: tuple[InitialStateClause, ...]

    def __post_init__(self) -> None:
        clauses = exact_tuple(self.clauses, InitialStateClause, "initial clauses")
        if len({item.state_clause_id for item in clauses}) != len(clauses):
            raise ValueError("initial clauses contain duplicate IDs")
        object.__setattr__(self, "clauses", tuple(clauses))


@dataclass(frozen=True, slots=True)
class TimeContract:
    mode: TimeMode
    time_coordinate_binding: ApplicabilityBinding[ValueFieldContract]
    horizon_binding: ApplicabilityBinding[object]
    endpoint_inclusion_semantic_ref: object
    time_unit_ref: object

    def __post_init__(self) -> None:
        exact_enum(self.mode, TimeMode, "time mode")
        exact(
            self.time_coordinate_binding,
            ApplicabilityBinding,
            "time_coordinate_binding",
        )
        exact(self.horizon_binding, ApplicabilityBinding, "horizon_binding")
        if self.mode is TimeMode.STEADY:
            self.time_coordinate_binding.require_not_applicable(
                "steady time_coordinate_binding"
            )
            self.horizon_binding.require_not_applicable("steady horizon_binding")
        else:
            self.time_coordinate_binding.require_bound(
                ValueFieldContract, "transient time_coordinate_binding"
            )
            if not self.horizon_binding.is_bound:
                raise ValueError("transient horizon_binding must be BOUND")
            owner(self.horizon_binding.value, "semantic_clause", "horizon_binding")
        owner(
            self.endpoint_inclusion_semantic_ref,
            "semantic_clause",
            "endpoint_inclusion_semantic_ref",
        )
        owner(self.time_unit_ref, "unit", "time_unit_ref")


class CandidateInputRelationKind(str, Enum):
    IDENTITY = "IDENTITY"
    STRUCTURAL_PACK = "STRUCTURAL_PACK"
    REPRESENTATION_ADAPTER = "REPRESENTATION_ADAPTER"


@dataclass(frozen=True, slots=True)
class CandidateInputRelation:
    kind: CandidateInputRelationKind
    adapter_contract_ref: object | None = None

    def __post_init__(self) -> None:
        exact_enum(self.kind, CandidateInputRelationKind, "input relation")
        if self.kind is CandidateInputRelationKind.IDENTITY:
            if self.adapter_contract_ref is not None:
                raise ValueError("IDENTITY relation has no adapter")
        else:
            owner(
                self.adapter_contract_ref,
                "representation_adapter",
                "adapter_contract_ref",
            )


class CandidateOutputRelationKind(str, Enum):
    IDENTITY = "IDENTITY"
    STRUCTURAL_UNPACK = "STRUCTURAL_UNPACK"
    REPRESENTATION_ADAPTER = "REPRESENTATION_ADAPTER"


@dataclass(frozen=True, slots=True)
class CandidateOutputRelation:
    kind: CandidateOutputRelationKind
    adapter_contract_ref: object | None = None

    def __post_init__(self) -> None:
        exact_enum(self.kind, CandidateOutputRelationKind, "output relation")
        if self.kind is CandidateOutputRelationKind.IDENTITY:
            if self.adapter_contract_ref is not None:
                raise ValueError("IDENTITY relation has no adapter")
        else:
            owner(
                self.adapter_contract_ref,
                "representation_adapter",
                "adapter_contract_ref",
            )


@dataclass(frozen=True, slots=True)
class CandidateInputBinding:
    physical_field_id: str
    candidate_field_id: str
    relation: CandidateInputRelation

    def __post_init__(self) -> None:
        validate_canonical_id(self.physical_field_id, "physical_field_id")
        validate_canonical_id(self.candidate_field_id, "candidate_field_id")
        exact(self.relation, CandidateInputRelation, "relation")


@dataclass(frozen=True, slots=True)
class CandidateOutputBinding:
    physical_quantity_id: str
    candidate_field_id: str
    relation: CandidateOutputRelation
    semantic_equivalence_ref: object

    def __post_init__(self) -> None:
        validate_canonical_id(self.physical_quantity_id, "physical_quantity_id")
        validate_canonical_id(self.candidate_field_id, "candidate_field_id")
        exact(self.relation, CandidateOutputRelation, "relation")
        owner(
            self.semantic_equivalence_ref,
            "semantic_equivalence",
            "semantic_equivalence_ref",
        )


@dataclass(frozen=True, slots=True)
class ConditionInputBinding:
    condition_clause_id: str
    candidate_field_id: str
    relation: CandidateInputRelation

    def __post_init__(self) -> None:
        validate_canonical_id(self.condition_clause_id, "condition_clause_id")
        validate_canonical_id(self.candidate_field_id, "candidate_field_id")
        exact(self.relation, CandidateInputRelation, "relation")


@dataclass(frozen=True, slots=True)
class TimeHorizonBinding:
    candidate_field_ids: tuple[str, ...]
    time_coordinate_equivalence_ref: object
    horizon_equivalence_ref: object
    endpoint_equivalence_ref: object

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_field_ids",
            canonical_id_sequence(self.candidate_field_ids, "candidate_field_ids"),
        )
        for name in (
            "time_coordinate_equivalence_ref",
            "horizon_equivalence_ref",
            "endpoint_equivalence_ref",
        ):
            owner(getattr(self, name), "semantic_equivalence", name)


def _validate_common(
    *,
    object_kind: object,
    expected_kind: str,
    schema_version: object,
    canonicalization_profile: object,
    challenge_key: object,
    object_id: object,
    object_version: object,
    supersedes: object,
    predecessor_type: type[object],
) -> ChallengeKey:
    if type(object_kind) is not str or object_kind != expected_kind:
        raise ValueError(f"object_kind must be {expected_kind}")
    validate_version_token(schema_version, "schema_version")
    if schema_version != AUTHORING_SCHEMA_VERSION:
        raise ValueError("unsupported authored schema_version")
    if (
        type(canonicalization_profile) is not str
        or canonicalization_profile != CANONICALIZATION_PROFILE
    ):
        raise ValueError("unsupported canonicalization_profile")
    copied = copied_challenge_key(challenge_key)
    validate_canonical_id(object_id, "object_id")
    validate_version_token(object_version, "object_version")
    binding = exact(supersedes, ApplicabilityBinding, "supersedes")
    if binding.is_bound:
        predecessor = exact(binding.value, predecessor_type, "supersedes value")
        if (
            predecessor.challenge_key != copied
            or predecessor.object_id != object_id
            or predecessor.object_kind != expected_kind
        ):
            raise ValueError("supersedes must bind same Challenge, kind, and object ID")
    return copied


@dataclass(frozen=True, slots=True)
class PhysicalSystemSpec:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    supersedes: ApplicabilityBinding[PhysicalSystemSpecRef]
    governing_job_ref: object
    governing_law_refs: tuple[object, ...]
    assumptions: tuple[AssumptionClause, ...]
    causal_inputs: tuple[ValueFieldContract, ...]
    required_physical_quantities: tuple[ValueFieldContract, ...]
    geometry_domain_ref: object
    boundary_conditions: BoundaryConditionContract
    initial_conditions: InitialConditionContract
    time_contract: TimeContract
    operating_envelope_ref: object
    claim_scope_ref: object
    missing_input_policy: str

    def __post_init__(self) -> None:
        if type(self) is not PhysicalSystemSpec:
            raise TypeError("PhysicalSystemSpec subclasses are rejected")
        copied = _validate_common(
            object_kind=self.object_kind,
            expected_kind="physical_system_spec",
            schema_version=self.schema_version,
            canonicalization_profile=self.canonicalization_profile,
            challenge_key=self.challenge_key,
            object_id=self.object_id,
            object_version=self.object_version,
            supersedes=self.supersedes,
            predecessor_type=PhysicalSystemSpecRef,
        )
        object.__setattr__(self, "challenge_key", copied)
        owner(self.governing_job_ref, "semantic_clause", "governing_job_ref")
        object.__setattr__(
            self,
            "governing_law_refs",
            owner_sequence(
                self.governing_law_refs,
                "semantic_clause",
                "governing_law_refs",
                nonempty=True,
            ),
        )
        assumptions = exact_tuple(
            self.assumptions, AssumptionClause, "assumptions", unique=True
        )
        if len({item.assumption_id for item in assumptions}) != len(assumptions):
            raise ValueError("assumptions contain duplicate IDs")
        object.__setattr__(self, "assumptions", canonical_set_tuple(assumptions))
        for name in ("causal_inputs", "required_physical_quantities"):
            fields = exact_tuple(
                getattr(self, name), ValueFieldContract, name, nonempty=True
            )
            if len({item.field_id for item in fields}) != len(fields):
                raise ValueError(f"{name} contains duplicate field IDs")
            object.__setattr__(self, name, tuple(fields))
        owner(self.geometry_domain_ref, "geometry_domain", "geometry_domain_ref")
        exact(
            self.boundary_conditions, BoundaryConditionContract, "boundary_conditions"
        )
        exact(self.initial_conditions, InitialConditionContract, "initial_conditions")
        exact(self.time_contract, TimeContract, "time_contract")
        causal_by_id = {item.field_id: item for item in self.causal_inputs}
        _validate_condition_sources(
            clauses=self.boundary_conditions.clauses,
            source_id_field="region_clause_id",
            causal_by_id=causal_by_id,
            family="boundary",
        )
        _validate_condition_sources(
            clauses=self.initial_conditions.clauses,
            source_id_field="state_clause_id",
            causal_by_id=causal_by_id,
            family="initial",
        )
        for clause in self.boundary_conditions.clauses:
            if clause.causal_input_binding.is_bound:
                source = causal_by_id[clause.causal_input_binding.value]
                if source.unit_ref != clause.unit_ref:
                    raise ValueError("boundary clause unit differs from causal input")
        for clause in self.initial_conditions.clauses:
            if clause.geometry_domain_ref != self.geometry_domain_ref:
                raise ValueError("initial clause geometry differs from physical system")
        owner(
            self.operating_envelope_ref,
            "operating_envelope",
            "operating_envelope_ref",
        )
        owner(self.claim_scope_ref, "claim_scope", "claim_scope_ref")
        if (
            type(self.missing_input_policy) is not str
            or self.missing_input_policy != "REJECT"
        ):
            raise ValueError("missing_input_policy must be REJECT")

    def dependency_refs(self) -> tuple[object, ...]:
        if self.supersedes.is_bound:
            return (self.supersedes.value,)
        return ()

    def to_canonical_record(self):
        from .model import authored_object_to_record

        return authored_object_to_record(self)

    def canonical_bytes(self) -> bytes:
        from .model import authored_object_canonical_bytes

        return authored_object_canonical_bytes(self)

    def to_ref(self) -> PhysicalSystemSpecRef:
        from .model import authored_object_to_ref

        return authored_object_to_ref(self)


@dataclass(frozen=True, slots=True)
class CandidateOutputContract:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    supersedes: ApplicabilityBinding[CandidateOutputContractRef]
    physical_system_ref: PhysicalSystemSpecRef
    candidate_inputs: tuple[ValueFieldContract, ...]
    causal_input_bindings: tuple[CandidateInputBinding, ...]
    required_outputs: tuple[ValueFieldContract, ...]
    physical_output_bindings: tuple[CandidateOutputBinding, ...]
    candidate_representation_ref: object
    geometry_domain_ref: object
    boundary_input_bindings: tuple[ConditionInputBinding, ...]
    initial_input_bindings: tuple[ConditionInputBinding, ...]
    time_horizon_binding: TimeHorizonBinding
    operating_envelope_ref: object
    claim_scope_ref: object
    missing_or_extra_policy: str
    malformed_output_policy: str

    def __post_init__(self) -> None:
        if type(self) is not CandidateOutputContract:
            raise TypeError("CandidateOutputContract subclasses are rejected")
        copied = _validate_common(
            object_kind=self.object_kind,
            expected_kind="candidate_output_contract",
            schema_version=self.schema_version,
            canonicalization_profile=self.canonicalization_profile,
            challenge_key=self.challenge_key,
            object_id=self.object_id,
            object_version=self.object_version,
            supersedes=self.supersedes,
            predecessor_type=CandidateOutputContractRef,
        )
        object.__setattr__(self, "challenge_key", copied)
        physical_ref = exact(
            self.physical_system_ref, PhysicalSystemSpecRef, "physical_system_ref"
        )
        if physical_ref.challenge_key != copied:
            raise ValueError("physical_system_ref Challenge mismatch")
        for name in ("candidate_inputs", "required_outputs"):
            fields = exact_tuple(
                getattr(self, name), ValueFieldContract, name, nonempty=True
            )
            if len({item.field_id for item in fields}) != len(fields):
                raise ValueError(f"{name} contains duplicate field IDs")
            object.__setattr__(self, name, tuple(fields))
        for name, item_type in (
            ("causal_input_bindings", CandidateInputBinding),
            ("physical_output_bindings", CandidateOutputBinding),
            ("boundary_input_bindings", ConditionInputBinding),
            ("initial_input_bindings", ConditionInputBinding),
        ):
            object.__setattr__(
                self, name, exact_tuple(getattr(self, name), item_type, name)
            )
        candidate_ids = {item.field_id for item in self.candidate_inputs}
        target_ids = [item.candidate_field_id for item in self.causal_input_bindings]
        target_ids += [item.candidate_field_id for item in self.boundary_input_bindings]
        target_ids += [item.candidate_field_id for item in self.initial_input_bindings]
        target_ids += list(self.time_horizon_binding.candidate_field_ids)
        if set(target_ids) != candidate_ids or len(target_ids) != len(candidate_ids):
            raise ValueError("candidate inputs must be targeted exactly once")
        output_ids = {item.field_id for item in self.required_outputs}
        output_targets = [
            item.candidate_field_id for item in self.physical_output_bindings
        ]
        if set(output_targets) != output_ids or len(output_targets) != len(output_ids):
            raise ValueError("candidate outputs must be bound exactly once")
        exact(self.time_horizon_binding, TimeHorizonBinding, "time_horizon_binding")
        owner(
            self.candidate_representation_ref,
            "representation",
            "candidate_representation_ref",
        )
        owner(self.geometry_domain_ref, "geometry_domain", "geometry_domain_ref")
        owner(
            self.operating_envelope_ref,
            "operating_envelope",
            "operating_envelope_ref",
        )
        owner(self.claim_scope_ref, "claim_scope", "claim_scope_ref")
        if (
            type(self.missing_or_extra_policy) is not str
            or self.missing_or_extra_policy != "REJECT"
        ):
            raise ValueError("missing_or_extra_policy must be REJECT")
        if (
            type(self.malformed_output_policy) is not str
            or self.malformed_output_policy != "CANDIDATE_FORMAT_FAILURE"
        ):
            raise ValueError("malformed_output_policy must be CANDIDATE_FORMAT_FAILURE")

    def dependency_refs(self) -> tuple[object, ...]:
        refs: list[object] = [self.physical_system_ref]
        if self.supersedes.is_bound:
            refs.append(self.supersedes.value)
        if len(set(refs)) != len(refs):
            raise ValueError("dependency refs contain a duplicate")
        return tuple(refs)

    def to_canonical_record(self):
        from .model import authored_object_to_record

        return authored_object_to_record(self)

    def canonical_bytes(self) -> bytes:
        from .model import authored_object_canonical_bytes

        return authored_object_canonical_bytes(self)

    def to_ref(self) -> CandidateOutputContractRef:
        from .model import authored_object_to_ref

        return authored_object_to_ref(self)


def validate_candidate_against_physical(
    candidate: CandidateOutputContract, physical: PhysicalSystemSpec
) -> None:
    """Validate the cross-object causal contract without adding adapters."""

    exact(candidate, CandidateOutputContract, "candidate")
    exact(physical, PhysicalSystemSpec, "physical")
    if candidate.physical_system_ref != physical.to_ref():
        raise ValueError("candidate binds a different physical object")
    if candidate.challenge_key != physical.challenge_key:
        raise ValueError("candidate and physical Challenge mismatch")
    for field in ("geometry_domain_ref", "operating_envelope_ref", "claim_scope_ref"):
        if getattr(candidate, field) != getattr(physical, field):
            raise ValueError(f"candidate {field} does not exactly match physical")
    physical_inputs = {item.field_id for item in physical.causal_inputs}
    bound_inputs = [item.physical_field_id for item in candidate.causal_input_bindings]
    if set(bound_inputs) != physical_inputs or len(bound_inputs) != len(
        physical_inputs
    ):
        raise ValueError("physical causal inputs are not bound exactly once")
    physical_input_by_id = {item.field_id: item for item in physical.causal_inputs}
    candidate_input_by_id = {item.field_id: item for item in candidate.candidate_inputs}
    for binding in candidate.causal_input_bindings:
        source = physical_input_by_id[binding.physical_field_id]
        target = candidate_input_by_id[binding.candidate_field_id]
        _validate_value_field_relation(
            source,
            target,
            identity=binding.relation.kind is CandidateInputRelationKind.IDENTITY,
            field="causal input",
        )
    physical_outputs = {item.field_id for item in physical.required_physical_quantities}
    bound_outputs = [
        item.physical_quantity_id for item in candidate.physical_output_bindings
    ]
    if set(bound_outputs) != physical_outputs or len(bound_outputs) != len(
        physical_outputs
    ):
        raise ValueError("physical quantities are not bound exactly once")
    physical_output_by_id = {
        item.field_id: item for item in physical.required_physical_quantities
    }
    candidate_output_by_id = {
        item.field_id: item for item in candidate.required_outputs
    }
    for binding in candidate.physical_output_bindings:
        source = physical_output_by_id[binding.physical_quantity_id]
        target = candidate_output_by_id[binding.candidate_field_id]
        _validate_value_field_relation(
            source,
            target,
            identity=binding.relation.kind is CandidateOutputRelationKind.IDENTITY,
            preserve_precision=True,
            field="required output",
        )
    boundary_ids = [
        item.region_clause_id
        for item in physical.boundary_conditions.clauses
        if item.applicability.tag is ApplicabilityTag.BOUND
    ]
    candidate_boundary_ids = [
        item.condition_clause_id for item in candidate.boundary_input_bindings
    ]
    if set(candidate_boundary_ids) != set(boundary_ids) or len(
        candidate_boundary_ids
    ) != len(boundary_ids):
        raise ValueError("applicable boundary clauses are not bound exactly once")
    boundary_by_id = {
        item.region_clause_id: item for item in physical.boundary_conditions.clauses
    }
    for binding in candidate.boundary_input_bindings:
        clause = boundary_by_id[binding.condition_clause_id]
        source = physical_input_by_id[clause.causal_input_binding.value]
        target = candidate_input_by_id[binding.candidate_field_id]
        _validate_value_field_relation(
            source,
            target,
            identity=binding.relation.kind is CandidateInputRelationKind.IDENTITY,
            field="boundary input",
        )
    initial_ids = [
        item.state_clause_id
        for item in physical.initial_conditions.clauses
        if item.applicability.tag is ApplicabilityTag.BOUND
    ]
    candidate_initial_ids = [
        item.condition_clause_id for item in candidate.initial_input_bindings
    ]
    if set(candidate_initial_ids) != set(initial_ids) or len(
        candidate_initial_ids
    ) != len(initial_ids):
        raise ValueError("applicable initial clauses are not bound exactly once")
    initial_by_id = {
        item.state_clause_id: item for item in physical.initial_conditions.clauses
    }
    for binding in candidate.initial_input_bindings:
        clause = initial_by_id[binding.condition_clause_id]
        source = physical_input_by_id[clause.causal_input_binding.value]
        target = candidate_input_by_id[binding.candidate_field_id]
        _validate_value_field_relation(
            source,
            target,
            identity=binding.relation.kind is CandidateInputRelationKind.IDENTITY,
            field="initial input",
        )
    time_ids = candidate.time_horizon_binding.candidate_field_ids
    if physical.time_contract.mode is TimeMode.STEADY:
        if time_ids:
            raise ValueError("steady physical system cannot bind candidate time inputs")
    else:
        if not time_ids:
            raise ValueError("transient physical system requires candidate time inputs")
        time_source = physical.time_contract.time_coordinate_binding.require_bound(
            ValueFieldContract, "transient time coordinate"
        )
        time_targets = tuple(candidate_input_by_id[field_id] for field_id in time_ids)
        if not any(
            _value_field_semantics_equal(time_source, target) for target in time_targets
        ):
            raise ValueError(
                "transient candidate inputs omit the physical time coordinate"
            )
        if any(
            target.unit_ref != physical.time_contract.time_unit_ref
            for target in time_targets
        ):
            raise ValueError(
                "candidate time/horizon input unit differs from physical time"
            )


def _validate_condition_sources(
    *,
    clauses: tuple[BoundaryRegionClause, ...] | tuple[InitialStateClause, ...],
    source_id_field: str,
    causal_by_id: dict[str, ValueFieldContract],
    family: str,
) -> None:
    """Require each applicable condition to resolve one unique causal source."""

    bound_source_ids: list[str] = []
    for clause in clauses:
        binding = clause.causal_input_binding
        if clause.applicability.tag is ApplicabilityTag.BOUND:
            if not binding.is_bound:
                raise ValueError(f"applicable {family} clause lacks a causal input")
            source_id = binding.value
            if source_id not in causal_by_id:
                clause_id = getattr(clause, source_id_field)
                raise ValueError(
                    f"{family} clause {clause_id} references an unknown causal input"
                )
            bound_source_ids.append(source_id)
        elif binding.is_bound:
            raise ValueError(f"inapplicable {family} clause binds a causal input")
    if len(set(bound_source_ids)) != len(bound_source_ids):
        raise ValueError(f"{family} clauses reuse a causal input source")


def _value_field_semantics_equal(
    source: ValueFieldContract, target: ValueFieldContract
) -> bool:
    return all(
        getattr(source, name) == getattr(target, name)
        for name in (
            "semantic_role_ref",
            "unit_ref",
            "geometry_binding",
            "presence",
            "admissibility_refs",
            "nonfinite_policy",
        )
    )


def _validate_value_field_relation(
    source: ValueFieldContract,
    target: ValueFieldContract,
    *,
    identity: bool,
    preserve_precision: bool = False,
    field: str,
) -> None:
    """Validate physical meaning that an encoding adapter may not change."""

    for name in (
        "semantic_role_ref",
        "unit_ref",
        "geometry_binding",
        "presence",
        "admissibility_refs",
        "nonfinite_policy",
    ):
        if getattr(source, name) != getattr(target, name):
            raise ValueError(f"{field} {name} does not preserve physical semantics")
    if preserve_precision and source.precision_contract != target.precision_contract:
        raise ValueError(f"{field} precision_contract does not preserve output claims")
    # The v1 identity relation means exact encoding identity.  Registered
    # representation/pack adapters may change only these encoding fields; their
    # exact owner ref remains identity-bearing in the binding.
    if identity:
        for name in (
            "representation_ref",
            "shape_contract",
            "precision_contract",
        ):
            if getattr(source, name) != getattr(target, name):
                raise ValueError(f"IDENTITY {field} changes {name}")
