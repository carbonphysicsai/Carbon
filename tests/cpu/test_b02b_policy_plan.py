"""Focused identity and boundary tests for B-02B policy and plan values."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from carbon.authoring.primitives import CANONICALIZATION_PROFILE
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    ChallengeScope,
    GlobalScope,
    PhysicalSystemSpecRef,
    TrainingSupportContractRef,
    owner_ref,
)
from carbon.construction import model as m
from carbon.construction.errors import (
    ConstructionError,
    ConstructionReferenceMismatchError,
    ConstructionValidationError,
)
from carbon.construction.plan import (
    ResolvedConstructionPlan,
    _mark_resolved_construction_plan_verified,
    decode_resolved_construction_plan,
)
from carbon.construction.policy import (
    ResolvedTrainingSamplingPolicy,
    _mark_training_sampling_policy_verified,
    decode_training_sampling_policy,
)
from carbon.construction.policy import (
    _build_training_sampling_policy as build_training_sampling_policy,
)
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_SCHEMA_VERSION,
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
    ResolvedConstructionPlanRef,
    TrainingSamplingPolicyRef,
)
from carbon.fees.strategy_identity import StrategyHash
from carbon.registry import ChallengeKey

_DIGEST = "sha256:" + "a" * 64
_OTHER_DIGEST = "sha256:" + "b" * 64
_KEY = ChallengeKey("fixture_construction", "1.0")


def _owner(kind: str, object_id: str, *, portable: bool = False) -> object:
    return owner_ref(
        kind,
        scope_binding=GlobalScope() if portable else ChallengeScope(_KEY),
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def _top_ref(ref_type: type, object_id: str) -> object:
    return ref_type(
        _KEY,
        object_id,
        "1.0",
        "1.0",
        CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _construction_refs() -> tuple[CandidateAssemblyContractRef, ParameterCatalogRef]:
    return (
        CandidateAssemblyContractRef(
            _KEY,
            "assembly",
            "1.0",
            CONSTRUCTION_SCHEMA_VERSION,
            CONSTRUCTION_CANONICALIZATION_PROFILE,
            _DIGEST,
        ),
        ParameterCatalogRef(
            _KEY,
            "catalog",
            "1.0",
            CONSTRUCTION_SCHEMA_VERSION,
            CONSTRUCTION_CANONICALIZATION_PROFILE,
            _DIGEST,
        ),
    )


def _base_policy() -> ResolvedTrainingSamplingPolicy:
    _, catalog_ref = _construction_refs()
    policy = ResolvedTrainingSamplingPolicy(
        object_kind=ResolvedTrainingSamplingPolicy.OBJECT_KIND,
        schema_version=CONSTRUCTION_SCHEMA_VERSION,
        canonicalization_profile=CONSTRUCTION_CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        training_support_ref=_top_ref(TrainingSupportContractRef, "training_support"),
        catalog_ref=catalog_ref,
        policy_state=m.PolicyState.BASE_NO_OVERRIDE,
        bindings=(),
        randomness_purposes=(),
    )
    return _mark_training_sampling_policy_verified(policy)


def _training_entry(
    surface_id: str,
    *,
    bound: bool = True,
) -> m.ParameterCatalogEntry:
    target = m.ConsumerTarget("training_policy", surface_id)
    lever: m.TrainingLeverBinding
    if bound:
        lever = m.BoundTrainingLever(
            m.TrainingLeverKind.SAMPLING,
            _owner("semantic_clause", f"{surface_id}_executable"),
            (m.TrainingRandomnessPurpose("training_draw", "training_role"),),
        )
    else:
        lever = m.TrainingLeverNotApplicable(
            _owner("applicability_reason", f"{surface_id}_not_training")
        )
    return m.ParameterCatalogEntry(
        surface_id=surface_id,
        input_source=m.InputSource.PARAMETER_KEY,
        consumer_target=target,
        value_type=m.SurfaceValueType.UINT64,
        unit_binding=m.UnitNotApplicable(
            _owner("applicability_reason", f"{surface_id}_unit_na")
        ),
        domain=m.UInt64RangeDomain(1, 100),
        dependency_surface_ids=(),
        applicability=m.AlwaysApplicable(
            _owner("applicability", f"{surface_id}_applicability")
        ),
        requirement=m.RequiredSurface(),
        compatibility_rule_ids=(),
        static_resource_contributions=(),
        resource_impact_tags=(),
        public_outcome_family_tags=(),
        semantic_owner_binding=m.TrainingSupportSemanticOwner(
            _owner("semantic_clause", f"{surface_id}_owner"),
            _owner("policy_authority", f"{surface_id}_authority"),
        ),
        lifecycle=m.ActiveLifecycle(),
        training_lever_binding=lever,
        component_slot_binding=m.ComponentSelectionNotApplicable(
            _owner("applicability_reason", f"{surface_id}_component_na")
        ),
    )


def _resolved_training_surface(
    entry: m.ParameterCatalogEntry, value: int
) -> m.SelectedSurface:
    return m.SelectedSurface(
        entry.surface_id,
        entry.consumer_target,
        m.SurfaceValue(m.SurfaceValueType.UINT64, value),
    )


def _plan_inputs() -> dict[str, object]:
    physical_ref = _top_ref(PhysicalSystemSpecRef, "physical")
    candidate_ref = _top_ref(CandidateOutputContractRef, "candidate")
    training_ref = _top_ref(TrainingSupportContractRef, "training_support")
    assembly_ref, catalog_ref = _construction_refs()
    base_policy = _base_policy()
    origin = m.AuthoringOriginBinding._from_canonical(
        graph_origin=m.GraphOrigin.FIXTURE_DERIVED,
        graph_fingerprint=_DIGEST,
        root_ref=physical_ref,
        dependency_refs=(training_ref, candidate_ref),
        origin_evidence_refs=(
            _owner("authoring_origin_evidence", "graph_origin", portable=True),
        ),
        composition_audit_ref=_owner(
            "origin_composition_audit", "graph_audit", portable=True
        ),
    )
    dependency = m.DependencyPin("runtime_core", "1.0", _DIGEST)
    backbone_implementation = m.ImplementationPin("backbone_impl", "1.0", _DIGEST)
    component_implementation = m.ImplementationPin("component_impl", "1.0", _DIGEST)
    backbone_environment = m.EnvironmentPin("backbone_env", "1.0", _DIGEST)
    component_environment = m.EnvironmentPin("component_env", "1.0", _DIGEST)
    input_pin = m.InterfacePin(
        "tensor_input", "1.0", _DIGEST, m.InterfaceDirection.INPUT
    )
    output_pin = m.InterfacePin(
        "tensor_output", "1.0", _DIGEST, m.InterfaceDirection.OUTPUT
    )
    backbone = m.ResolvedBackboneBinding(
        surface_id="strategy_backbone",
        selector_token="fno",
        backbone_id="fno",
        backbone_version="1.0",
        content_digest=_DIGEST,
        implementation_pin=backbone_implementation,
        environment_pin=backbone_environment,
        dependency_pins=(dependency,),
        input_interface_pin=input_pin,
        output_interface_pin=output_pin,
        applicability_ref=_owner("applicability", "backbone_applicability"),
        assumption_refs=(),
        limitation_refs=(),
    )
    component_target = m.ConsumerTarget("warm_start_slot", "selection")
    component = m.ResolvedComponentBinding(
        slot_id="warm_start_slot",
        selector_surface_id="warm_start_selector",
        selector_token="registered_warm_start",
        component_id="registered_warm_start",
        component_version="1.0",
        content_digest=_DIGEST,
        role=m.ComponentRole.WARM_START,
        consumer_target=component_target,
        input_interface_pin=input_pin,
        output_interface_pin=output_pin,
        state_policy=m.ComponentStatePolicy.STATELESS,
        side_effect_policy=m.SideEffectPolicy.NONE,
        trainability_boundary=m.TrainabilityBoundary.FIXED,
        implementation_pin=component_implementation,
        environment_pin=component_environment,
        dependency_pins=(dependency,),
        applicability_ref=_owner("applicability", "component_applicability"),
        assumption_refs=(),
        limitation_refs=(),
        public_falsification_refs=(),
    )
    backbone_surface = m.SelectedSurface(
        "strategy_backbone",
        m.ConsumerTarget("strategy", "backbone"),
        m.SurfaceValue(m.SurfaceValueType.BACKBONE_SELECTOR, "fno"),
    )
    component_surface = m.DefaultedSurface(
        "warm_start_selector",
        component_target,
        m.SurfaceValue(
            m.SurfaceValueType.COMPONENT_SELECTOR,
            "registered_warm_start",
        ),
    )
    provenance = m.FixtureProvenance(
        _owner("fixture_registration", "fixture_registration"),
        (_owner("provenance", "source_provenance", portable=True),),
        (
            _owner(
                "authoring_origin_evidence",
                "provenance_origin",
                portable=True,
            ),
        ),
    )
    requirement = m.StaticResourceRequirement(
        "parameter_count",
        _owner("unit", "count_unit", portable=True),
        7,
        ("backbone", "warm_start_slot"),
        ("memory",),
    )
    return {
        "object_kind": ResolvedConstructionPlan.OBJECT_KIND,
        "schema_version": CONSTRUCTION_SCHEMA_VERSION,
        "canonicalization_profile": CONSTRUCTION_CANONICALIZATION_PROFILE,
        "challenge_key": _KEY,
        "strategy_schema_version": "1.0",
        "strategy_hash": StrategyHash(_DIGEST),
        "authoring_origin_binding": origin,
        "physical_system_ref": physical_ref,
        "candidate_output_ref": candidate_ref,
        "training_support_ref": training_ref,
        "candidate_assembly_ref": assembly_ref,
        "parameter_catalog_ref": catalog_ref,
        "compiler_identity": m.CompilerIdentity(
            "strategy_compiler",
            "1.0",
            _DIGEST,
            CONSTRUCTION_SCHEMA_VERSION,
            CONSTRUCTION_CANONICALIZATION_PROFILE,
        ),
        "backbone_binding": backbone,
        # Deliberately reversed; the plan must own canonical surface-id order.
        "resolved_surfaces": (component_surface, backbone_surface),
        "satisfied_compatibility_rule_ids": (
            "warm_start_compatible",
            "backbone_compatible",
        ),
        "resolved_components": (component,),
        "training_sampling_policy_ref": base_policy.to_ref(),
        "dependency_pins": (dependency,),
        "environment_pins": (
            component_environment,
            backbone_environment,
        ),
        "implementation_pins": (
            component_implementation,
            backbone_implementation,
        ),
        "static_resource_requirements": (requirement,),
        "resource_impact_tags": ("memory", "construction_cost"),
        "assembly_provenance": provenance,
        "catalog_provenance": provenance,
        "authority_marker": m.AuthorityMarker.CONSTRUCTION_ONLY_NOT_QUALIFICATION,
    }


def _plan(**overrides: object) -> ResolvedConstructionPlan:
    fields = _plan_inputs()
    fields.update(overrides)
    return _mark_resolved_construction_plan_verified(ResolvedConstructionPlan(**fields))


def test_policy_builder_closes_state_and_registered_purpose_union() -> None:
    first = _training_entry("sampling_scale")
    second = _training_entry("sampling_width")
    _, catalog_ref = _construction_refs()
    policy, policy_ref = build_training_sampling_policy(
        challenge_key=_KEY,
        training_support_ref=_top_ref(TrainingSupportContractRef, "training_support"),
        catalog_ref=catalog_ref,
        entries=(second, first),
        resolved_surfaces=(
            _resolved_training_surface(second, 9),
            _resolved_training_surface(first, 3),
        ),
    )

    assert policy.policy_state is m.PolicyState.RESOLVED_OVERRIDES
    assert tuple(binding.surface_id for binding in policy.bindings) == (
        "sampling_scale",
        "sampling_width",
    )
    assert policy.randomness_purposes == (
        m.TrainingRandomnessPurpose("training_draw", "training_role"),
    )
    assert policy_ref == policy.to_ref()
    assert not any(
        hasattr(policy, field)
        for field in ("seed", "entropy_domain", "proposal_q", "weight_w", "draw_id")
    )


def test_policy_builder_emits_explicit_base_and_rejects_incomplete_resolution() -> None:
    entry = _training_entry("fixed_surface", bound=False)
    _, catalog_ref = _construction_refs()
    policy, _ = build_training_sampling_policy(
        challenge_key=_KEY,
        training_support_ref=_top_ref(TrainingSupportContractRef, "training_support"),
        catalog_ref=catalog_ref,
        entries=(entry,),
        resolved_surfaces=(_resolved_training_surface(entry, 2),),
    )
    assert policy.policy_state is m.PolicyState.BASE_NO_OVERRIDE
    assert policy.bindings == ()
    assert policy.randomness_purposes == ()

    with pytest.raises(
        ConstructionValidationError,
        match="one resolution per catalog entry",
    ):
        build_training_sampling_policy(
            challenge_key=_KEY,
            training_support_ref=_top_ref(
                TrainingSupportContractRef, "training_support"
            ),
            catalog_ref=catalog_ref,
            entries=(entry,),
            resolved_surfaces=(),
        )


def test_policy_constructor_rejects_forbidden_authority_carriers() -> None:
    entry = _training_entry("sampling_scale")
    _, catalog_ref = _construction_refs()
    policy, _ = build_training_sampling_policy(
        challenge_key=_KEY,
        training_support_ref=_top_ref(TrainingSupportContractRef, "training_support"),
        catalog_ref=catalog_ref,
        entries=(entry,),
        resolved_surfaces=(_resolved_training_surface(entry, 3),),
    )

    with pytest.raises(ConstructionValidationError):
        replace(
            policy,
            randomness_purposes=(
                m.TrainingRandomnessPurpose("entropy_domain", "participant_seed"),
            ),
        )
    with pytest.raises(ConstructionValidationError):
        replace(
            policy,
            randomness_purposes=(
                m.TrainingRandomnessPurpose("training_draw", "batch_draw"),
            ),
        )


def test_replaced_policy_cannot_issue_a_forged_catalog_bound_identity() -> None:
    entry = _training_entry("sampling_scale")
    _, catalog_ref = _construction_refs()
    policy, _ = build_training_sampling_policy(
        challenge_key=_KEY,
        training_support_ref=_top_ref(TrainingSupportContractRef, "training_support"),
        catalog_ref=catalog_ref,
        entries=(entry,),
        resolved_surfaces=(_resolved_training_surface(entry, 3),),
    )
    forged = replace(
        policy,
        bindings=(
            replace(
                policy.bindings[0],
                resolved_value=m.SurfaceValue(m.SurfaceValueType.UINT64, 999),
            ),
        ),
    )

    with pytest.raises(ConstructionValidationError, match="compiler or decoder"):
        forged.to_ref()


def test_policy_round_trip_digest_tamper_and_state_law() -> None:
    policy = _base_policy()
    payload = policy.canonical_bytes()
    policy_ref = policy.to_ref()
    assert decode_training_sampling_policy(payload, expected_ref=policy_ref) == policy

    with pytest.raises(ConstructionError):
        decode_training_sampling_policy(payload + b"\x00", expected_ref=policy_ref)
    tampered = payload[:-1] + bytes((payload[-1] ^ 1,))
    with pytest.raises(ConstructionError):
        decode_training_sampling_policy(tampered, expected_ref=policy_ref)
    with pytest.raises(ConstructionReferenceMismatchError):
        decode_training_sampling_policy(
            payload,
            expected_ref=TrainingSamplingPolicyRef(
                _KEY,
                CONSTRUCTION_SCHEMA_VERSION,
                CONSTRUCTION_CANONICALIZATION_PROFILE,
                _OTHER_DIGEST,
            ),
        )
    with pytest.raises(ConstructionValidationError, match="requires at least one"):
        ResolvedTrainingSamplingPolicy(
            object_kind=ResolvedTrainingSamplingPolicy.OBJECT_KIND,
            schema_version=CONSTRUCTION_SCHEMA_VERSION,
            canonicalization_profile=CONSTRUCTION_CANONICALIZATION_PROFILE,
            challenge_key=_KEY,
            training_support_ref=policy.training_support_ref,
            catalog_ref=policy.catalog_ref,
            policy_state=m.PolicyState.RESOLVED_OVERRIDES,
            bindings=(),
            randomness_purposes=(),
        )


def test_policy_defensively_copies_bindings_and_rejects_cross_challenge_refs() -> None:
    binding = m.ResolvedTrainingBinding(
        "sampling_scale",
        m.TrainingLeverKind.SAMPLING,
        m.SurfaceValue(m.SurfaceValueType.UINT64, 3),
        _owner("semantic_clause", "sampling_executable"),
    )
    base = _base_policy()
    policy = ResolvedTrainingSamplingPolicy(
        object_kind=base.object_kind,
        schema_version=base.schema_version,
        canonicalization_profile=base.canonicalization_profile,
        challenge_key=base.challenge_key,
        training_support_ref=base.training_support_ref,
        catalog_ref=base.catalog_ref,
        policy_state=m.PolicyState.RESOLVED_OVERRIDES,
        bindings=(binding,),
        randomness_purposes=(),
    )
    object.__setattr__(binding, "surface_id", "mutated_source")
    assert policy.bindings[0].surface_id == "sampling_scale"

    other_key = ChallengeKey("other_construction", "1.0")
    with pytest.raises(ConstructionValidationError, match="ChallengeKey"):
        ResolvedTrainingSamplingPolicy(
            object_kind=base.object_kind,
            schema_version=base.schema_version,
            canonicalization_profile=base.canonicalization_profile,
            challenge_key=other_key,
            training_support_ref=base.training_support_ref,
            catalog_ref=base.catalog_ref,
            policy_state=m.PolicyState.BASE_NO_OVERRIDE,
            bindings=(),
            randomness_purposes=(),
        )


def test_plan_round_trip_is_canonical_complete_and_digest_bound() -> None:
    plan = _plan()
    payload = plan.canonical_bytes()
    plan_ref = plan.to_ref()
    decoded = decode_resolved_construction_plan(payload, expected_ref=plan_ref)

    assert decoded == plan

    assert decoded is not plan
    assert tuple(surface.surface_id for surface in plan.resolved_surfaces) == (
        "strategy_backbone",
        "warm_start_selector",
    )
    assert set(plan.implementation_pins) == {
        plan.backbone_binding.implementation_pin,
        plan.resolved_components[0].implementation_pin,
    }
    assert (
        plan.authority_marker is m.AuthorityMarker.CONSTRUCTION_ONLY_NOT_QUALIFICATION
    )
    assert type(plan.strategy_hash) is StrategyHash

    with pytest.raises(ConstructionError):
        decode_resolved_construction_plan(payload + b"\x00", expected_ref=plan_ref)
    tampered = payload[:-1] + bytes((payload[-1] ^ 1,))
    with pytest.raises(ConstructionError):
        decode_resolved_construction_plan(tampered, expected_ref=plan_ref)
    with pytest.raises(ConstructionReferenceMismatchError):
        decode_resolved_construction_plan(
            payload,
            expected_ref=ResolvedConstructionPlanRef(
                _KEY,
                CONSTRUCTION_SCHEMA_VERSION,
                CONSTRUCTION_CANONICALIZATION_PROFILE,
                _OTHER_DIGEST,
            ),
        )


def test_plan_constructor_rejects_forbidden_authority_carriers() -> None:
    plan = _plan()

    with pytest.raises(ConstructionValidationError):
        replace(
            plan,
            resource_impact_tags=(*plan.resource_impact_tags, "admission_verdict"),
        )

    surface = plan.resolved_surfaces[0]
    forbidden_surface = replace(
        surface,
        consumer_target=replace(surface.consumer_target, field_id="consumer_mode"),
    )
    with pytest.raises(ConstructionValidationError):
        replace(
            plan,
            resolved_surfaces=(forbidden_surface, *plan.resolved_surfaces[1:]),
        )

    with pytest.raises(ConstructionValidationError):
        replace(plan, satisfied_compatibility_rule_ids=("evaluation_gate",))


def test_replaced_plan_cannot_issue_a_forged_compiler_bound_identity() -> None:
    plan = _plan()
    requirement = plan.static_resource_requirements[0]
    forged = replace(
        plan,
        static_resource_requirements=(replace(requirement, quantity=8),),
    )

    with pytest.raises(ConstructionValidationError, match="compiler or decoder"):
        forged.to_ref()


def test_plan_enforces_specialized_selector_equality_and_complete_pins() -> None:
    fields = _plan_inputs()
    component = fields["resolved_components"][0]
    wrong_component = m.ResolvedComponentBinding(
        slot_id=component.slot_id,
        selector_surface_id=component.selector_surface_id,
        selector_token="different_option",
        component_id=component.component_id,
        component_version=component.component_version,
        content_digest=component.content_digest,
        role=component.role,
        consumer_target=component.consumer_target,
        input_interface_pin=component.input_interface_pin,
        output_interface_pin=component.output_interface_pin,
        state_policy=component.state_policy,
        side_effect_policy=component.side_effect_policy,
        trainability_boundary=component.trainability_boundary,
        implementation_pin=component.implementation_pin,
        environment_pin=component.environment_pin,
        dependency_pins=component.dependency_pins,
        applicability_ref=component.applicability_ref,
        assumption_refs=component.assumption_refs,
        limitation_refs=component.limitation_refs,
        public_falsification_refs=component.public_falsification_refs,
    )
    with pytest.raises(ConstructionValidationError, match="selector value"):
        _plan(resolved_components=(wrong_component,))

    with pytest.raises(ConstructionValidationError, match="exactly cover"):
        _plan(implementation_pins=(fields["backbone_binding"].implementation_pin,))


def test_plan_defensive_copy_and_authoring_graph_membership() -> None:
    fields = _plan_inputs()
    source_backbone = fields["backbone_binding"]
    plan = ResolvedConstructionPlan(**fields)
    object.__setattr__(source_backbone, "selector_token", "mutated_source")
    assert plan.backbone_binding.selector_token == "fno"

    incomplete_origin = m.AuthoringOriginBinding._from_canonical(
        graph_origin=m.GraphOrigin.FIXTURE_DERIVED,
        graph_fingerprint=_DIGEST,
        root_ref=fields["physical_system_ref"],
        dependency_refs=(fields["candidate_output_ref"],),
        origin_evidence_refs=(
            _owner("authoring_origin_evidence", "incomplete", portable=True),
        ),
        composition_audit_ref=_owner(
            "origin_composition_audit", "incomplete_audit", portable=True
        ),
    )
    with pytest.raises(ConstructionValidationError, match="exact members"):
        _plan(authoring_origin_binding=incomplete_origin)


@dataclass(frozen=True, slots=True)
class _PracticeConsumer:
    payload: bytes
    plan_ref: ResolvedConstructionPlanRef

    def receive(self) -> ResolvedConstructionPlan:
        return decode_resolved_construction_plan(
            self.payload, expected_ref=self.plan_ref
        )


@dataclass(frozen=True, slots=True)
class _OfficialShapedConsumer:
    payload: bytes
    plan_ref: ResolvedConstructionPlanRef

    def receive(self) -> ResolvedConstructionPlan:
        return decode_resolved_construction_plan(
            self.payload, expected_ref=self.plan_ref
        )


def test_nominal_consumers_receive_fresh_exact_plan_identity_only() -> None:
    plan = _plan()
    payload = plan.canonical_bytes()
    plan_ref = plan.to_ref()
    practice = _PracticeConsumer(memoryview(payload).tobytes(), plan_ref)
    official = _OfficialShapedConsumer(memoryview(payload).tobytes(), plan_ref)

    practice_plan = practice.receive()
    official_plan = official.receive()
    assert practice_plan == official_plan == plan
    assert practice_plan is not official_plan
    assert practice.plan_ref == official.plan_ref == plan_ref
    assert not any(
        hasattr(practice_plan, field)
        for field in (
            "consumer_mode",
            "entropy_domain",
            "seed",
            "draw_id",
            "resource_policy_verdict",
            "qualification",
        )
    )
