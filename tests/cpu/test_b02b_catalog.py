from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    ChallengeScope,
    GlobalScope,
    PhysicalSystemSpecRef,
    TrainingSupportContractRef,
    owner_ref,
)
from carbon.construction.catalog import (
    CandidateAssemblyContract,
    ParameterCatalog,
    _forbidden_authority_code,
    catalog_topological_entries,
    decode_candidate_assembly,
    decode_parameter_catalog,
    validate_catalog_against_assembly,
    validate_parameter_catalog,
)
from carbon.construction.errors import (
    ConstructionCanonicalDecodingError,
    ConstructionReferenceMismatchError,
    ConstructionValidationError,
)
from carbon.construction.model import (
    ActiveLifecycle,
    AlwaysApplicable,
    AssemblySemanticOwner,
    BackboneOption,
    BackboneSurfaceContract,
    BoundComponentSelection,
    ChoiceDomain,
    CompilerIdentity,
    ComponentRole,
    ComponentSelectionNotApplicable,
    ComponentSlotContract,
    ComponentStatePolicy,
    ConsumerTarget,
    DependencyPin,
    DiscreteLookupResourceContribution,
    EnvironmentPin,
    FallbackPolicy,
    FixtureProvenance,
    ImplementationPin,
    InputSource,
    InterfaceDirection,
    InterfacePin,
    ParameterCatalogEntry,
    RequiredSurface,
    ResourceLookupCase,
    RetiredLifecycle,
    SideEffectPolicy,
    StaticResourceDimension,
    SurfaceValue,
    SurfaceValueType,
    TrainabilityBoundary,
    TrainingLeverNotApplicable,
    UnitNotApplicable,
    UnknownOrInvalidPolicy,
)
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_SCHEMA_VERSION,
    CandidateAssemblyContractRef,
)
from carbon.registry import ChallengeKey


@pytest.mark.parametrize(
    "identifier",
    ("resource_units", "graphite_method", "budgetary_units", "evaluationless_mode"),
)
def test_harmless_textual_overlap_is_not_an_authority_alias(identifier):
    assert _forbidden_authority_code(identifier) is None


_DIGEST = "sha256:" + "1" * 64
_OTHER_DIGEST = "sha256:" + "2" * 64


def _fixture():
    key = ChallengeKey("fixture_catalog", "1.0")

    def pinned(kind: str, object_id: str | None = None):
        return owner_ref(
            kind,
            scope_binding=ChallengeScope(key),
            object_id=object_id or kind,
            object_version="1.0",
            content_digest=_DIGEST,
        )

    unit_ref = owner_ref(
        "unit",
        scope_binding=GlobalScope(),
        object_id="abstract_count",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    provenance = FixtureProvenance(
        fixture_registration_ref=pinned("fixture_registration"),
        source_provenance_refs=(
            owner_ref(
                "provenance",
                scope_binding=GlobalScope(),
                object_id="fixture_source",
                object_version="1.0",
                content_digest=_DIGEST,
            ),
        ),
        origin_evidence_refs=(
            owner_ref(
                "authoring_origin_evidence",
                scope_binding=GlobalScope(),
                object_id="fixture_origin",
                object_version="1.0",
                content_digest=_DIGEST,
            ),
        ),
    )
    physical_ref = PhysicalSystemSpecRef(
        key,
        "physical",
        "1.0",
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        _DIGEST,
    )
    candidate_ref = CandidateOutputContractRef(
        key,
        "candidate",
        "1.0",
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        _DIGEST,
    )
    training_ref = TrainingSupportContractRef(
        key,
        "training",
        "1.0",
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        _DIGEST,
    )
    implementation = ImplementationPin("fixture_impl", "1.0", _DIGEST)
    environment = EnvironmentPin("fixture_env", "1.0", _DIGEST)
    dependency = DependencyPin("stdlib", "1.0", _DIGEST)
    input_pin = InterfacePin(
        "candidate_input", "1.0", _DIGEST, InterfaceDirection.INPUT
    )
    output_pin = InterfacePin(
        "candidate_output", "1.0", _DIGEST, InterfaceDirection.OUTPUT
    )
    backbone_target = ConsumerTarget("solver", "backbone")
    component_target = ConsumerTarget("solver", "warm_start")
    backbone = BackboneSurfaceContract(
        "strategy_backbone",
        backbone_target,
        (
            BackboneOption(
                "basic_backbone",
                "basic_backbone",
                "1.0",
                _DIGEST,
                implementation,
                environment,
                (dependency,),
                input_pin,
                output_pin,
                pinned("applicability", "backbone_applicable"),
                (),
                (),
                (),
                (),
            ),
        ),
    )
    component_option_args = {
        "selector_token": "zero_warm_start",
        "component_id": "zero_warm_start",
        "component_version": "1.0",
        "content_digest": _DIGEST,
        "role": ComponentRole.WARM_START,
        "consumer_target": component_target,
        "input_interface_pin": input_pin,
        "output_interface_pin": output_pin,
        "state_policy": ComponentStatePolicy.STATELESS,
        "side_effect_policy": SideEffectPolicy.NONE,
        "trainability_boundary": TrainabilityBoundary.FIXED,
        "implementation_pin": implementation,
        "environment_pin": environment,
        "dependency_pins": (dependency,),
        "applicability_ref": pinned("applicability", "component_applicable"),
        "assumption_refs": (),
        "limitation_refs": (),
        "static_resource_contributions": (),
        "resource_impact_tags": (),
        "public_falsification_refs": (),
    }
    from carbon.construction.model import RegisteredComponentOption

    component_option = RegisteredComponentOption(**component_option_args)
    slot = ComponentSlotContract(
        "warm_start_slot",
        "warm_start_selector",
        ComponentRole.WARM_START,
        component_target,
        input_pin,
        output_pin,
        ComponentStatePolicy.STATELESS,
        SideEffectPolicy.NONE,
        TrainabilityBoundary.FIXED,
        pinned("applicability", "slot_applicable"),
        (component_option,),
        FallbackPolicy.FAIL_CLOSED,
    )
    dimension = StaticResourceDimension("abstract_units", unit_ref)
    assembly = CandidateAssemblyContract(
        object_kind="candidate_assembly_contract",
        schema_version=CONSTRUCTION_SCHEMA_VERSION,
        canonicalization_profile=CONSTRUCTION_CANONICALIZATION_PROFILE,
        challenge_key=key,
        object_id="fixture_assembly",
        object_version="1.0",
        physical_system_ref=physical_ref,
        candidate_output_ref=candidate_ref,
        training_support_ref=training_ref,
        backbone_surface=backbone,
        component_slots=(slot,),
        resource_dimensions=(dimension,),
        dependency_pins=(dependency,),
        environment_pins=(environment,),
        provenance=provenance,
        unknown_or_invalid_policy=UnknownOrInvalidPolicy.REJECT,
    )
    reason = pinned("applicability_reason", "not_applicable")
    authority = pinned("scientific_authority", "assembly_authority")
    top_entry = ParameterCatalogEntry(
        "strategy_backbone",
        InputSource.TOP_LEVEL_BACKBONE,
        backbone_target,
        SurfaceValueType.BACKBONE_SELECTOR,
        UnitNotApplicable(reason),
        ChoiceDomain(("basic_backbone",)),
        (),
        AlwaysApplicable(pinned("applicability", "backbone_surface_applicable")),
        RequiredSurface(),
        (),
        (),
        (),
        (),
        AssemblySemanticOwner("strategy_backbone", authority),
        ActiveLifecycle(),
        TrainingLeverNotApplicable(reason),
        ComponentSelectionNotApplicable(reason),
    )
    component_entry = ParameterCatalogEntry(
        "warm_start_selector",
        InputSource.PARAMETER_KEY,
        component_target,
        SurfaceValueType.COMPONENT_SELECTOR,
        UnitNotApplicable(reason),
        ChoiceDomain(("zero_warm_start",)),
        (),
        AlwaysApplicable(pinned("applicability", "component_surface_applicable")),
        RequiredSurface(),
        (),
        (),
        (),
        (),
        AssemblySemanticOwner("warm_start_slot", authority),
        ActiveLifecycle(),
        TrainingLeverNotApplicable(reason),
        BoundComponentSelection("warm_start_slot", ComponentRole.WARM_START),
    )
    compiler = CompilerIdentity(
        "strategy_compiler",
        "1.0",
        _DIGEST,
        CONSTRUCTION_SCHEMA_VERSION,
        CONSTRUCTION_CANONICALIZATION_PROFILE,
    )
    catalog = ParameterCatalog(
        object_kind="parameter_catalog",
        schema_version=CONSTRUCTION_SCHEMA_VERSION,
        canonicalization_profile=CONSTRUCTION_CANONICALIZATION_PROFILE,
        challenge_key=key,
        object_id="fixture_catalog",
        object_version="1.0",
        candidate_assembly_ref=assembly.to_ref(),
        training_support_ref=training_ref,
        compiler_identity=compiler,
        entries=(component_entry, top_entry),
        compatibility_rules=(),
        provenance=provenance,
        unknown_or_invalid_policy=UnknownOrInvalidPolicy.REJECT,
    )
    return {
        "assembly": assembly,
        "catalog": catalog,
        "compiler": compiler,
        "key": key,
        "pinned": pinned,
        "reason": reason,
        "unit_ref": unit_ref,
        "dimension": dimension,
        "top_entry": top_entry,
        "component_entry": component_entry,
        "component_option_args": component_option_args,
    }


def test_catalog_and_assembly_are_exact_frozen_round_trip_identity_documents():
    fixture = _fixture()
    assembly = fixture["assembly"]
    catalog = fixture["catalog"]

    assert not hasattr(assembly, "__dict__")
    assert not hasattr(catalog, "__dict__")
    with pytest.raises(FrozenInstanceError):
        assembly.object_id = "changed"

    assembly_bytes = assembly.canonical_bytes()
    catalog_bytes = catalog.canonical_bytes(candidate_assembly=assembly)
    assert (
        decode_candidate_assembly(assembly_bytes, expected_ref=assembly.to_ref())
        == assembly
    )
    assert (
        decode_parameter_catalog(
            catalog_bytes,
            candidate_assembly=assembly,
            expected_ref=catalog.to_ref(candidate_assembly=assembly),
        )
        == catalog
    )
    assert assembly.to_ref().content_digest.startswith("sha256:")
    assert catalog.to_ref(candidate_assembly=assembly).content_digest.startswith(
        "sha256:"
    )

    wrong_assembly_ref = replace(assembly.to_ref(), content_digest=_OTHER_DIGEST)
    with pytest.raises(ConstructionReferenceMismatchError):
        decode_candidate_assembly(
            assembly_bytes,
            expected_ref=wrong_assembly_ref,
        )
    with pytest.raises(ConstructionCanonicalDecodingError):
        decode_candidate_assembly(
            assembly_bytes,
            expected_ref=catalog.to_ref(candidate_assembly=assembly),
        )


def test_projection_is_exact_and_rejects_selector_widening_or_omission():
    fixture = _fixture()
    catalog = fixture["catalog"]
    widened = replace(
        fixture["component_entry"],
        domain=ChoiceDomain(("zero_warm_start", "participant_extra")),
    )
    bad_catalog = replace(
        catalog,
        entries=(fixture["top_entry"], widened),
    )
    with pytest.raises(ConstructionValidationError) as error:
        validate_parameter_catalog(bad_catalog, candidate_assembly=fixture["assembly"])
    assert error.value.code == "construction.component_projection_mismatch"

    omitted = replace(catalog, entries=(fixture["top_entry"],))
    with pytest.raises(ConstructionValidationError) as error:
        validate_parameter_catalog(omitted, candidate_assembly=fixture["assembly"])
    assert error.value.code == "construction.component_projection_missing"


def test_intrinsic_catalog_validation_rejects_cycles_and_invalid_defaults():
    fixture = _fixture()
    top = fixture["top_entry"]
    component = fixture["component_entry"]
    top_cycle = replace(
        top,
        dependency_surface_ids=(component.surface_id,),
    )
    component_cycle = replace(
        component,
        dependency_surface_ids=(top.surface_id,),
    )
    with pytest.raises(ConstructionValidationError) as error:
        replace(fixture["catalog"], entries=(top_cycle, component_cycle))
    assert error.value.code == "construction.catalog_dependency_cycle"


def test_lookup_cases_are_exactly_typed_and_dimension_bound():
    fixture = _fixture()
    bad_lookup = DiscreteLookupResourceContribution(
        "abstract_units",
        fixture["unit_ref"],
        "strategy_backbone",
        (
            ResourceLookupCase(
                SurfaceValue(SurfaceValueType.CANONICAL_CHOICE, "basic_backbone"),
                1,
            ),
        ),
        (),
    )
    top = replace(fixture["top_entry"], static_resource_contributions=(bad_lookup,))
    catalog = replace(fixture["catalog"], entries=(top, fixture["component_entry"]))
    with pytest.raises(ConstructionValidationError) as error:
        validate_parameter_catalog(catalog, candidate_assembly=fixture["assembly"])
    assert error.value.code == "construction.surface_value_out_of_domain"


def test_owner_scopes_and_global_selector_tokens_fail_closed():
    fixture = _fixture()
    other_key = ChallengeKey("other_fixture", "1.0")
    wrong_authority = owner_ref(
        "scientific_authority",
        scope_binding=ChallengeScope(other_key),
        object_id="wrong_authority",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    wrong_top = replace(
        fixture["top_entry"],
        semantic_owner_binding=AssemblySemanticOwner(
            "strategy_backbone", wrong_authority
        ),
    )
    with pytest.raises(ConstructionValidationError) as error:
        replace(
            fixture["catalog"],
            entries=(wrong_top, fixture["component_entry"]),
        )
    assert error.value.code == "construction.owner_ref_challenge_mismatch"

    from carbon.construction.model import RegisteredComponentOption

    alias_option = RegisteredComponentOption(
        **{
            **fixture["component_option_args"],
            "selector_token": "basic_backbone",
        }
    )
    slot = replace(fixture["assembly"].component_slots[0], options=(alias_option,))
    with pytest.raises(ConstructionValidationError) as error:
        replace(fixture["assembly"], component_slots=(slot,))
    assert error.value.code == "construction.selector_token_collision"


def test_retired_and_exact_compiler_ref_gates_are_explicit():
    fixture = _fixture()
    retired = replace(
        fixture["component_entry"],
        lifecycle=RetiredLifecycle(
            fixture["reason"], fixture["pinned"]("semantic_equivalence")
        ),
    )
    catalog = replace(fixture["catalog"], entries=(fixture["top_entry"], retired))
    validate_parameter_catalog(catalog, candidate_assembly=fixture["assembly"])
    with pytest.raises(ConstructionValidationError) as error:
        validate_parameter_catalog(
            catalog,
            candidate_assembly=fixture["assembly"],
            reject_retired=True,
        )
    assert error.value.code == "construction.catalog_entry_retired"

    wrong_ref = CandidateAssemblyContractRef(
        fixture["key"],
        "fixture_assembly",
        "1.0",
        CONSTRUCTION_SCHEMA_VERSION,
        CONSTRUCTION_CANONICALIZATION_PROFILE,
        _OTHER_DIGEST,
    )
    with pytest.raises(ConstructionValidationError) as error:
        validate_catalog_against_assembly(
            fixture["catalog"],
            fixture["assembly"],
            wrong_ref,
            fixture["compiler"],
        )
    assert error.value.code == "construction.assembly_reference_mismatch"


def test_topological_order_uses_canonical_surface_id_tie_breaking():
    fixture = _fixture()
    ordered = catalog_topological_entries(fixture["catalog"])
    assert tuple(entry.surface_id for entry in ordered) == (
        "strategy_backbone",
        "warm_start_selector",
    )
