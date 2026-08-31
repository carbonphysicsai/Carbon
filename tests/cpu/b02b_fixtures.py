"""Closed non-authoritative B-02B fixtures shared by focused tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import test_b02a_contract_models as domain_fixtures

from carbon.authoring.loading import (
    FixtureAuthoringCapability,
    compose_authoring_graph_origin,
    load_authoring_bytes,
)
from carbon.authoring.model import ApplicabilityBinding
from carbon.authoring.refs import ChallengeScope, GlobalScope, owner_ref
from carbon.construction.catalog import CandidateAssemblyContract, ParameterCatalog
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY
from carbon.construction.model import (
    ActiveLifecycle,
    AlwaysApplicable,
    AssemblySemanticOwner,
    BackboneOption,
    BackboneSurfaceContract,
    BoundComponentSelection,
    BoundTrainingLever,
    BoundUnit,
    ChoiceDomain,
    CompatibilityRule,
    ComponentRole,
    ComponentSelectionNotApplicable,
    ComponentSlotContract,
    ComponentStatePolicy,
    ConsumerTarget,
    DependencyPin,
    DiscreteLookupResourceContribution,
    EnvironmentPin,
    ExplicitDefaultSurface,
    FallbackPolicy,
    FixedResourceContribution,
    FixtureProvenance,
    ImplementationPin,
    InputSource,
    InterfaceDirection,
    InterfacePin,
    ParameterCatalogEntry,
    RegisteredComponentOption,
    RequiredSurface,
    ResourceLookupCase,
    SideEffectPolicy,
    StaticResourceDimension,
    SurfaceValue,
    SurfaceValueType,
    TrainabilityBoundary,
    TrainingLeverKind,
    TrainingLeverNotApplicable,
    TrainingRandomnessPurpose,
    TrainingSupportSemanticOwner,
    UInt64RangeDomain,
    UnitNotApplicable,
    UnknownOrInvalidPolicy,
    ValueCompatibilityCell,
)
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_SCHEMA_VERSION,
)
from carbon.fees.strategy_identity import SubmissionResourceLimits
from carbon.registry import ChallengeKey

_DIGEST = "sha256:" + "3" * 64


@dataclass(frozen=True, slots=True)
class CompileFixture:
    key: ChallengeKey
    assembly: CandidateAssemblyContract
    catalog: ParameterCatalog
    authoring_origin: object
    authoring_artifacts: tuple[object, ...]
    strategy: dict[str, object]


def strategy_limits(**overrides: object) -> SubmissionResourceLimits:
    values: dict[str, object] = {
        "max_total_value_nodes": 10_000,
        "max_object_members": 256,
        "max_list_items": 256,
        "max_string_utf8_bytes": 4096,
        "max_object_key_utf8_bytes": 512,
        "max_strategy_identity_bytes": 1_000_000,
        "max_challenge_id_bytes": 256,
        "max_concurrent_identity_builds": 8,
        "max_retained_submission_records": 256,
        "max_retained_value_nodes": 1_000_000,
        "max_retained_strategy_identity_bytes": 16_000_000,
    }
    values.update(overrides)
    return SubmissionResourceLimits(**values)  # type: ignore[arg-type]


def make_compile_fixture(tmp_path: Path) -> CompileFixture:
    del tmp_path
    key = ChallengeKey("fixture_authoring", "1.0")

    def pinned(kind: str, object_id: str) -> object:
        return owner_ref(
            kind,
            scope_binding=ChallengeScope(key),
            object_id=object_id,
            object_version="1.0",
            content_digest=_DIGEST,
        )

    def portable(kind: str, object_id: str) -> object:
        return owner_ref(
            kind,
            scope_binding=GlobalScope(),
            object_id=object_id,
            object_version="1.0",
            content_digest=_DIGEST,
        )

    physical = domain_fixtures._physical()
    candidate = domain_fixtures._candidate(physical)
    training = domain_fixtures._training_support(physical, candidate)
    authored = (physical, candidate, training)
    source_provenance_ref = portable("provenance", "fixture_authoring_source")
    fixture_origin = FixtureAuthoringCapability().issue_origin(
        fixture_registration_ref=portable(
            "fixture_registration", "fixture_authoring_registration"
        ),
        source_provenance_refs=(source_provenance_ref,),
    )
    loaded = tuple(
        load_authoring_bytes(
            value.to_ref(),
            value.canonical_bytes(),
            origin=fixture_origin,
            origin_evidence_ref=portable(
                "authoring_origin_evidence", f"fixture_authoring_node_{index}"
            ),
            source_provenance_refs=(source_provenance_ref,),
            audit_evidence_refs=(
                portable("audit_evidence", f"fixture_authoring_audit_{index}"),
            ),
            qualification_evidence=ApplicabilityBinding.not_applicable(
                portable("applicability_reason", f"fixture_unqualified_node_{index}")
            ),
        )
        for index, value in enumerate(authored)
    )
    dependency_refs = (physical.to_ref(), candidate.to_ref())
    origin = compose_authoring_graph_origin(
        root=loaded[2],
        dependencies=loaded[:2],
        expected_dependency_refs=dependency_refs,
        composition_audit_ref=portable(
            "origin_composition_audit", "fixture_authoring_composition"
        ),
        registered_authority=None,
    )
    artifacts = (loaded[2], *loaded[:2])
    physical_ref = physical.to_ref()
    candidate_ref = candidate.to_ref()
    training_ref = training.to_ref()

    unit_ref = portable("unit", "fixture_abstract_count")
    provenance = FixtureProvenance(
        fixture_registration_ref=pinned(
            "fixture_registration", "fixture_construction_registration"
        ),
        source_provenance_refs=(portable("provenance", "fixture_construction_source"),),
        origin_evidence_refs=(
            portable("authoring_origin_evidence", "fixture_construction_origin"),
        ),
    )
    implementation = ImplementationPin("fixture_solver_impl", "1.0", _DIGEST)
    environment = EnvironmentPin("fixture_construction_env", "1.0", _DIGEST)
    dependency = DependencyPin("fixture_stdlib", "1.0", _DIGEST)
    input_pin = InterfacePin(
        "fixture_solver_input", "1.0", _DIGEST, InterfaceDirection.INPUT
    )
    output_pin = InterfacePin(
        "fixture_solver_output", "1.0", _DIGEST, InterfaceDirection.OUTPUT
    )
    backbone_target = ConsumerTarget("fixture_solver", "backbone")
    component_target = ConsumerTarget("fixture_solver", "residual_correction")
    sampling_target = ConsumerTarget("fixture_training", "sampling_level")
    resource_dimension = StaticResourceDimension("abstract_units", unit_ref)

    backbone = BackboneSurfaceContract(
        "strategy_backbone",
        backbone_target,
        (
            BackboneOption(
                "fno",
                "fixture_fno",
                "1.0",
                _DIGEST,
                implementation,
                environment,
                (dependency,),
                input_pin,
                output_pin,
                pinned("applicability", "fixture_backbone_applicable"),
                (pinned("semantic_clause", "fixture_backbone_assumption"),),
                (pinned("restriction", "fixture_backbone_limitation"),),
                (
                    FixedResourceContribution(
                        "abstract_units", unit_ref, 2, ("backbone_impact",)
                    ),
                ),
                ("backbone_impact",),
            ),
        ),
    )
    component_option = RegisteredComponentOption(
        selector_token="fixture_residual",
        component_id="fixture_residual",
        component_version="1.0",
        content_digest=_DIGEST,
        role=ComponentRole.RESIDUAL_CORRECTION,
        consumer_target=component_target,
        input_interface_pin=input_pin,
        output_interface_pin=output_pin,
        state_policy=ComponentStatePolicy.STATELESS,
        side_effect_policy=SideEffectPolicy.NONE,
        trainability_boundary=TrainabilityBoundary.FIXED,
        implementation_pin=implementation,
        environment_pin=environment,
        dependency_pins=(dependency,),
        applicability_ref=pinned("applicability", "fixture_component_applicable"),
        assumption_refs=(pinned("semantic_clause", "fixture_component_assumption"),),
        limitation_refs=(pinned("restriction", "fixture_component_limitation"),),
        static_resource_contributions=(
            FixedResourceContribution(
                "abstract_units", unit_ref, 3, ("component_impact",)
            ),
        ),
        resource_impact_tags=("component_impact",),
        public_falsification_refs=(
            pinned("audit_evidence", "fixture_component_falsification"),
        ),
    )
    component_slot = ComponentSlotContract(
        "fixture_residual_slot",
        "fixture_residual_selector",
        ComponentRole.RESIDUAL_CORRECTION,
        component_target,
        input_pin,
        output_pin,
        ComponentStatePolicy.STATELESS,
        SideEffectPolicy.NONE,
        TrainabilityBoundary.FIXED,
        pinned("applicability", "fixture_slot_applicable"),
        (component_option,),
        FallbackPolicy.FAIL_CLOSED,
    )
    assembly = CandidateAssemblyContract(
        object_kind="candidate_assembly_contract",
        schema_version=CONSTRUCTION_SCHEMA_VERSION,
        canonicalization_profile=CONSTRUCTION_CANONICALIZATION_PROFILE,
        challenge_key=key,
        object_id="fixture_candidate_assembly",
        object_version="1.0",
        physical_system_ref=physical_ref,
        candidate_output_ref=candidate_ref,
        training_support_ref=training_ref,
        backbone_surface=backbone,
        component_slots=(component_slot,),
        resource_dimensions=(resource_dimension,),
        dependency_pins=(dependency,),
        environment_pins=(environment,),
        provenance=provenance,
        unknown_or_invalid_policy=UnknownOrInvalidPolicy.REJECT,
    )

    reason = pinned("applicability_reason", "fixture_not_applicable")
    assembly_authority = pinned("scientific_authority", "fixture_assembly_authority")
    compatibility_id = "fixture_compatibility"
    top_entry = ParameterCatalogEntry(
        "strategy_backbone",
        InputSource.TOP_LEVEL_BACKBONE,
        backbone_target,
        SurfaceValueType.BACKBONE_SELECTOR,
        UnitNotApplicable(reason),
        ChoiceDomain(("fno",)),
        (),
        AlwaysApplicable(pinned("applicability", "fixture_backbone_surface")),
        RequiredSurface(),
        (compatibility_id,),
        (),
        (),
        (),
        AssemblySemanticOwner("strategy_backbone", assembly_authority),
        ActiveLifecycle(),
        TrainingLeverNotApplicable(reason),
        ComponentSelectionNotApplicable(reason),
    )
    component_entry = ParameterCatalogEntry(
        "fixture_residual_selector",
        InputSource.PARAMETER_KEY,
        component_target,
        SurfaceValueType.COMPONENT_SELECTOR,
        UnitNotApplicable(reason),
        ChoiceDomain(("fixture_residual",)),
        (),
        AlwaysApplicable(pinned("applicability", "fixture_component_surface")),
        ExplicitDefaultSurface(
            SurfaceValue(SurfaceValueType.COMPONENT_SELECTOR, "fixture_residual")
        ),
        (compatibility_id,),
        (),
        (),
        (),
        AssemblySemanticOwner("fixture_residual_slot", assembly_authority),
        ActiveLifecycle(),
        TrainingLeverNotApplicable(reason),
        BoundComponentSelection(
            "fixture_residual_slot", ComponentRole.RESIDUAL_CORRECTION
        ),
    )
    sampling_entry = ParameterCatalogEntry(
        "fixture_sampling_level",
        InputSource.PARAMETER_KEY,
        sampling_target,
        SurfaceValueType.UINT64,
        BoundUnit(unit_ref),
        UInt64RangeDomain(1, 2),
        (),
        AlwaysApplicable(pinned("applicability", "fixture_sampling_surface")),
        RequiredSurface(),
        (compatibility_id,),
        (
            DiscreteLookupResourceContribution(
                "abstract_units",
                unit_ref,
                "fixture_sampling_level",
                (
                    ResourceLookupCase(SurfaceValue(SurfaceValueType.UINT64, 1), 4),
                    ResourceLookupCase(SurfaceValue(SurfaceValueType.UINT64, 2), 8),
                ),
                ("sampling_impact",),
            ),
        ),
        ("sampling_impact",),
        ("fixture_training_outcome",),
        TrainingSupportSemanticOwner(
            pinned("semantic_clause", "fixture_sampling_clause"),
            pinned("policy_authority", "fixture_training_policy_authority"),
        ),
        ActiveLifecycle(),
        BoundTrainingLever(
            TrainingLeverKind.SAMPLING,
            pinned("semantic_clause", "fixture_sampling_executable"),
            (
                TrainingRandomnessPurpose(
                    "fixture_training_case", "fixture_training_role_key"
                ),
            ),
        ),
        ComponentSelectionNotApplicable(reason),
    )
    compatibility = CompatibilityRule(
        compatibility_id,
        (
            "strategy_backbone",
            "fixture_residual_selector",
            "fixture_sampling_level",
        ),
        (
            (
                ValueCompatibilityCell(
                    SurfaceValue(SurfaceValueType.BACKBONE_SELECTOR, "fno")
                ),
                ValueCompatibilityCell(
                    SurfaceValue(
                        SurfaceValueType.COMPONENT_SELECTOR, "fixture_residual"
                    )
                ),
                ValueCompatibilityCell(SurfaceValue(SurfaceValueType.UINT64, 1)),
            ),
            (
                ValueCompatibilityCell(
                    SurfaceValue(SurfaceValueType.BACKBONE_SELECTOR, "fno")
                ),
                ValueCompatibilityCell(
                    SurfaceValue(
                        SurfaceValueType.COMPONENT_SELECTOR, "fixture_residual"
                    )
                ),
                ValueCompatibilityCell(SurfaceValue(SurfaceValueType.UINT64, 2)),
            ),
        ),
        pinned("semantic_clause", "fixture_compatibility_clause"),
    )
    catalog = ParameterCatalog(
        object_kind="parameter_catalog",
        schema_version=CONSTRUCTION_SCHEMA_VERSION,
        canonicalization_profile=CONSTRUCTION_CANONICALIZATION_PROFILE,
        challenge_key=key,
        object_id="fixture_parameter_catalog",
        object_version="1.0",
        candidate_assembly_ref=assembly.to_ref(),
        training_support_ref=training_ref,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        entries=(top_entry, component_entry, sampling_entry),
        compatibility_rules=(compatibility,),
        provenance=provenance,
        unknown_or_invalid_policy=UnknownOrInvalidPolicy.REJECT,
    )
    strategy = {
        "schema_version": "1.0",
        "challenge_id": key.challenge_id,
        "backbone": "fno",
        "parameters": {"fixture_sampling_level": 2},
    }
    return CompileFixture(key, assembly, catalog, origin, artifacts, strategy)


__all__ = ["CompileFixture", "make_compile_fixture", "strategy_limits"]
