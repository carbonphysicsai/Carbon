"""Challenge-bounded training support, excluding B-02B's R_strategy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from carbon.registry.model import ChallengeKey

from .model import (
    ApplicabilityBinding,
    DisclosureContract,
    canonical_set_tuple,
    copied_challenge_key,
    exact,
    exact_enum,
    exact_tuple,
    owner,
    owner_tuple,
)
from .physical import _validate_common
from .refs import (
    CandidateOutputContractRef,
    PhysicalSystemSpecRef,
    TrainingSupportContractRef,
)


@dataclass(frozen=True, slots=True)
class TrainingMembershipContract:
    admission_rule_ref: object
    physical_support_ref: object
    representation_support_ref: object
    failure_outcome: str

    def __post_init__(self) -> None:
        owner(self.admission_rule_ref, "membership_rule", "admission_rule_ref")
        owner(self.physical_support_ref, "physical_support", "physical_support_ref")
        owner(
            self.representation_support_ref,
            "representation_support",
            "representation_support_ref",
        )
        if type(self.failure_outcome) is not str or self.failure_outcome != "REJECT":
            raise ValueError("membership failure_outcome must be REJECT")


@dataclass(frozen=True, slots=True)
class SourceMaterialBinding:
    source_material_ref: object
    source_role_ref: object
    membership_proof_ref: object
    provenance_ref: object
    rights_ref: object
    permitted_use_ref: object

    def __post_init__(self) -> None:
        for name, kind in (
            ("source_material_ref", "source_material"),
            ("source_role_ref", "source_material_role"),
            ("membership_proof_ref", "membership_proof"),
            ("provenance_ref", "provenance"),
            ("rights_ref", "rights_profile"),
            ("permitted_use_ref", "permitted_use"),
        ):
            owner(getattr(self, name), kind, name)


class PermittedGeneratorKind(str, Enum):
    PERMITTED = "PERMITTED"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class PermittedGeneratorBinding:
    kind: PermittedGeneratorKind
    payload: tuple[object, ...] | object

    def __post_init__(self) -> None:
        exact_enum(self.kind, PermittedGeneratorKind, "generator binding kind")
        if self.kind is PermittedGeneratorKind.PERMITTED:
            object.__setattr__(
                self,
                "payload",
                owner_tuple(
                    self.payload,
                    "generator",
                    "permitted generator refs",
                    nonempty=True,
                ),
            )
        else:
            owner(self.payload, "no_generator_reason", "no-generator reason")


@dataclass(frozen=True, slots=True)
class TrainingSupportContract:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    supersedes: ApplicabilityBinding[TrainingSupportContractRef]
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    membership_contract: TrainingMembershipContract
    physical_invariant_refs: tuple[object, ...]
    representation_invariant_refs: tuple[object, ...]
    permitted_source_materials: tuple[SourceMaterialBinding, ...]
    permitted_generators: PermittedGeneratorBinding
    rights_profile_ref: object
    permitted_use_refs: tuple[object, ...]
    restrictions: tuple[object, ...]
    provenance_requirements: tuple[object, ...]
    disclosure_contract: DisclosureContract
    unknown_or_invalid_policy: str

    def __post_init__(self) -> None:
        if type(self) is not TrainingSupportContract:
            raise TypeError("TrainingSupportContract subclasses are rejected")
        copied = _validate_common(
            object_kind=self.object_kind,
            expected_kind="training_support_contract",
            schema_version=self.schema_version,
            canonicalization_profile=self.canonicalization_profile,
            challenge_key=self.challenge_key,
            object_id=self.object_id,
            object_version=self.object_version,
            supersedes=self.supersedes,
            predecessor_type=TrainingSupportContractRef,
        )
        object.__setattr__(self, "challenge_key", copied_challenge_key(copied))
        for name, ref_type in (
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_ref", CandidateOutputContractRef),
        ):
            ref = exact(getattr(self, name), ref_type, name)
            if ref.challenge_key != copied:
                raise ValueError(f"{name} Challenge mismatch")
        exact(self.membership_contract, TrainingMembershipContract, "membership_contract")
        object.__setattr__(
            self,
            "physical_invariant_refs",
            owner_tuple(
                self.physical_invariant_refs,
                "semantic_clause",
                "physical_invariant_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "representation_invariant_refs",
            owner_tuple(
                self.representation_invariant_refs,
                "semantic_clause",
                "representation_invariant_refs",
                nonempty=True,
            ),
        )
        materials = exact_tuple(
            self.permitted_source_materials,
            SourceMaterialBinding,
            "permitted_source_materials",
            unique=True,
        )
        object.__setattr__(
            self, "permitted_source_materials", canonical_set_tuple(materials)
        )
        exact(self.permitted_generators, PermittedGeneratorBinding, "permitted_generators")
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
        object.__setattr__(
            self,
            "provenance_requirements",
            owner_tuple(
                self.provenance_requirements,
                "provenance",
                "provenance_requirements",
                nonempty=True,
            ),
        )
        exact(self.disclosure_contract, DisclosureContract, "disclosure_contract")
        if (
            type(self.unknown_or_invalid_policy) is not str
            or self.unknown_or_invalid_policy != "REJECT"
        ):
            raise ValueError("unknown_or_invalid_policy must be REJECT")

    def dependency_refs(self) -> tuple[object, ...]:
        refs: list[object] = [self.physical_system_ref, self.candidate_output_ref]
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

    def to_ref(self) -> TrainingSupportContractRef:
        from .model import authored_object_to_ref

        return authored_object_to_ref(self)


def reject_training_support_substitution(value: object, field: str) -> None:
    """Stable guard for any official population/evaluation input."""

    if type(value) is TrainingSupportContract or type(value) is TrainingSupportContractRef:
        raise TypeError(f"{field} does not accept Challenge training support")


# No ResolvedTrainingSamplingPolicy or TrainingSamplingPolicyRef is defined in
# this package.  Their absence is deliberate: those are B-02B-owned types.
