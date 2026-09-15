"""Honest Burgers causal contracts compiled through the existing B-02B owner.

The registry's nominal FIXTURE origin means unqualified DEVELOPMENT authority;
it does not replace the physical job or numerical training with a test fixture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from carbon import construction as c
from carbon.authoring import physical as p
from carbon.authoring import training_support as t
from carbon.authoring.loading import (
    FixtureAuthoringCapability,
    compose_authoring_graph_origin,
    load_authoring_bytes,
)
from carbon.authoring.model import ApplicabilityBinding as A
from carbon.authoring.model import DisclosureContract, PrecisionLiteral, TimeMode
from carbon.authoring.primitives import CANONICALIZATION_PROFILE
from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY
from carbon.construction.refs import CONSTRUCTION_CANONICALIZATION_PROFILE
from carbon.fees import SubmissionResourceLimits
from carbon.reconstruction import profile as jax

from .profile import CHALLENGE, TIME_SCALE, canonical, digest, profile_document


def semantic(kind: str, label: str):
    """Bind each semantic clause to the exact prospective executable profile."""
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(CHALLENGE),
        object_id=label,
        object_version="1.0",
        content_digest=digest(
            canonical({"clause": label, "profile": profile_document()})
        ),
    )


def na(label: str):
    return A.not_applicable(semantic("applicability_reason", label))


def _field(name: str, axes: tuple[tuple[str, int], ...], unit: str):
    return p.ValueFieldContract(
        field_id=name,
        semantic_role_ref=semantic("semantic_clause", name),
        representation_ref=semantic("representation", "dense_physical_array"),
        unit_ref=semantic("unit", unit),
        shape_contract=tuple(
            p.AxisContract(
                axis,
                semantic("semantic_clause", axis),
                semantic("unit", "count"),
                p.AxisExtent(p.AxisExtentKind.FIXED, fixed_extent=size),
            )
            for axis, size in axes
        ),
        precision_contract=(PrecisionLiteral.FLOAT32, PrecisionLiteral.FLOAT64),
        geometry_binding=A.bound(semantic("geometry_domain", "periodic_2pi")),
        presence=p.Presence(p.PresenceKind.REQUIRED),
        admissibility_refs=(),
        nonfinite_policy="REJECT",
    )


def authored_contracts():
    common = {
        "schema_version": "1.0",
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "challenge_key": CHALLENGE,
        "object_version": "1.0",
    }
    inputs = (
        _field("initial", (("space", 64),), "velocity"),
        _field("viscosity", (), "kinematic_viscosity"),
        _field("requested_times", (("time", 13),), "time"),
        _field("positions", (("space", 64),), "length"),
    )
    output = _field("solution", (("time", 13), ("space", 64)), "velocity")
    physical = p.PhysicalSystemSpec(
        **common,
        object_kind="physical_system_spec",
        object_id="burgers_session_physics",
        supersedes=na("first_session_physics"),
        governing_job_ref=semantic(
            "semantic_clause", "periodic_unforced_viscous_burgers"
        ),
        governing_law_refs=(
            semantic("semantic_clause", "u_t_plus_flux_x_equals_nu_u_xx"),
        ),
        assumptions=(),
        causal_inputs=(inputs[0], inputs[1], inputs[3]),
        required_physical_quantities=(output,),
        geometry_domain_ref=semantic("geometry_domain", "periodic_2pi"),
        boundary_conditions=p.BoundaryConditionContract(
            (
                p.BoundaryRegionClause(
                    "periodic",
                    semantic("geometry_region", "identified_endpoints"),
                    semantic("semantic_clause", "periodic_values_and_flux"),
                    na("fixed_periodic_no_causal_boundary"),
                    semantic("unit", "velocity"),
                    na("fixed_boundary_encoded_in_geometry"),
                ),
            )
        ),
        initial_conditions=p.InitialConditionContract(
            (
                p.InitialStateClause(
                    "initial",
                    semantic("semantic_clause", "initial_at_zero"),
                    na("initial_already_bound_as_causal_input"),
                    semantic("geometry_domain", "periodic_2pi"),
                    semantic("semantic_clause", "zero_time"),
                    na("initial_already_bound_as_causal_input"),
                ),
            )
        ),
        time_contract=p.TimeContract(
            TimeMode.TRANSIENT,
            A.bound(inputs[2]),
            A.bound(semantic("semantic_clause", "four_characteristic_times")),
            semantic("semantic_clause", "zero_and_horizon_included"),
            semantic("unit", "time"),
        ),
        operating_envelope_ref=semantic("operating_envelope", "c_auth1_twelve_cells"),
        claim_scope_ref=semantic(
            "claim_scope", "unqualified_reduced_development_subset"
        ),
        missing_input_policy="REJECT",
    )
    relation = p.CandidateInputRelation(p.CandidateInputRelationKind.IDENTITY)
    candidate = p.CandidateOutputContract(
        **common,
        object_kind="candidate_output_contract",
        object_id="burgers_session_causal_io",
        supersedes=na("first_session_candidate"),
        physical_system_ref=physical.to_ref(),
        candidate_inputs=inputs,
        causal_input_bindings=tuple(
            p.CandidateInputBinding(field.field_id, field.field_id, relation)
            for field in physical.causal_inputs
        ),
        required_outputs=(output,),
        physical_output_bindings=(
            p.CandidateOutputBinding(
                "solution",
                "solution",
                p.CandidateOutputRelation(p.CandidateOutputRelationKind.IDENTITY),
                semantic("semantic_equivalence", "physical_prediction_identity"),
            ),
        ),
        candidate_representation_ref=semantic(
            "representation", "physical_target_free_query"
        ),
        geometry_domain_ref=physical.geometry_domain_ref,
        boundary_input_bindings=(),
        initial_input_bindings=(),
        time_horizon_binding=p.TimeHorizonBinding(
            ("requested_times",),
            semantic("semantic_equivalence", "physical_times"),
            semantic("semantic_equivalence", "physical_horizon"),
            semantic("semantic_equivalence", "physical_endpoints"),
        ),
        operating_envelope_ref=physical.operating_envelope_ref,
        claim_scope_ref=physical.claim_scope_ref,
        missing_or_extra_policy="REJECT",
        malformed_output_policy="CANDIDATE_FORMAT_FAILURE",
    )
    training = t.TrainingSupportContract(
        **common,
        object_kind="training_support_contract",
        object_id="burgers_session_train_support",
        supersedes=na("first_session_training"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        membership_contract=t.TrainingMembershipContract(
            semantic("membership_rule", "train_role_only"),
            semantic("physical_support", "c_auth1_twelve_cells"),
            semantic("representation_support", "train_64_by_13"),
            "REJECT",
        ),
        physical_invariant_refs=(
            semantic("semantic_clause", "periodic_unforced_viscous_burgers"),
        ),
        representation_invariant_refs=(semantic("semantic_clause", "physical_arrays"),),
        permitted_source_materials=(),
        permitted_generators=t.PermittedGeneratorBinding(
            t.PermittedGeneratorKind.PERMITTED,
            (semantic("generator", "c_auth1_train_role_only"),),
        ),
        rights_profile_ref=semantic("rights_profile", "public_synthetic"),
        permitted_use_refs=(semantic("permitted_use", "development_training_only"),),
        restrictions=(
            semantic("restriction", "no_eval_stress_labels_or_qualified_use"),
        ),
        provenance_requirements=(semantic("provenance", "c04_train_reference"),),
        disclosure_contract=DisclosureContract(
            (),
            (),
            (),
            semantic("aggregation_policy", "development_only"),
            semantic("release_policy", "train_only"),
        ),
        unknown_or_invalid_policy="REJECT",
    )
    p.validate_candidate_against_physical(candidate, physical)
    return physical, candidate, training


def strategy_limits() -> SubmissionResourceLimits:
    return SubmissionResourceLimits(
        max_total_value_nodes=512,
        max_object_members=32,
        max_list_items=32,
        max_string_utf8_bytes=1024,
        max_object_key_utf8_bytes=128,
        max_strategy_identity_bytes=16384,
        max_challenge_id_bytes=128,
        max_concurrent_identity_builds=1,
        max_retained_submission_records=3,
        max_retained_value_nodes=1536,
        max_retained_strategy_identity_bytes=49152,
    )


@dataclass(frozen=True)
class SessionContracts:
    assembly: c.CandidateAssemblyContract
    catalog: c.ParameterCatalog
    origin: object
    artifacts: tuple[object, ...]

    def compile(self, strategy: dict[str, object]):
        return c.compile_strategy(
            strategy,
            challenge_key=CHALLENGE,
            candidate_assembly=self.assembly,
            candidate_assembly_ref=self.assembly.to_ref(),
            parameter_catalog=self.catalog,
            parameter_catalog_ref=self.catalog.to_ref(candidate_assembly=self.assembly),
            authoring_origin=self.origin,
            authoring_artifacts=self.artifacts,
            compiler_identity=SUPPORTED_COMPILER_IDENTITY,
            strategy_limits=strategy_limits(),
        )


def build_contracts() -> SessionContracts:
    physical, candidate, training = authored_contracts()
    source = semantic("provenance", "prospective_session_profile")
    unqualified = FixtureAuthoringCapability().issue_origin(
        fixture_registration_ref=semantic(
            "fixture_registration", "unqualified_session"
        ),
        source_provenance_refs=(source,),
    )
    loaded = tuple(
        load_authoring_bytes(
            value.to_ref(),
            value.canonical_bytes(),
            origin=unqualified,
            origin_evidence_ref=semantic(
                "authoring_origin_evidence", f"session_object_{index}"
            ),
            source_provenance_refs=(source,),
            audit_evidence_refs=(
                semantic("audit_evidence", f"session_object_{index}"),
            ),
            qualification_evidence=na("not_scientifically_qualified"),
        )
        for index, value in enumerate((physical, candidate, training))
    )
    origin = compose_authoring_graph_origin(
        root=loaded[2],
        dependencies=loaded[:2],
        expected_dependency_refs=(physical.to_ref(), candidate.to_ref()),
        composition_audit_ref=semantic(
            "origin_composition_audit", "session_causal_contracts"
        ),
        registered_authority=None,
    )
    provenance = c.FixtureProvenance(
        semantic("fixture_registration", "unqualified_session"),
        (source,),
        (semantic("authoring_origin_evidence", "session_causal_contracts"),),
    )
    env = c.EnvironmentPin(
        jax.ENVIRONMENT_ID, jax.ENVIRONMENT_VERSION, jax.ENVIRONMENT_DIGEST
    )
    deps = tuple(c.DependencyPin(*spec) for spec in jax.DEPENDENCY_SPECS)
    impl = c.ImplementationPin(
        jax.IMPLEMENTATION_ID, jax.IMPLEMENTATION_VERSION, jax.UPSTREAM_WHEEL_DIGEST
    )
    ip = c.InterfacePin(
        "carbon_jax_burgers_input",
        "1.0",
        jax.INPUT_INTERFACE_DIGEST,
        c.InterfaceDirection.INPUT,
    )
    op = c.InterfacePin(
        "carbon_jax_burgers_output",
        "1.0",
        jax.OUTPUT_INTERFACE_DIGEST,
        c.InterfaceDirection.OUTPUT,
    )
    options = tuple(
        c.BackboneOption(
            selector,
            f"carbon_jax_{selector}1d",
            "1.0",
            jax.UPSTREAM_WHEEL_DIGEST,
            impl,
            env,
            deps,
            ip,
            op,
            semantic("applicability", "session_burgers"),
            (semantic("semantic_clause", "declarative_target_free_neural_operator"),),
            (semantic("restriction", "unqualified_session_only"),),
            (),
            (),
        )
        for selector in ("fno", "deeponet")
    )
    backbone_target = c.ConsumerTarget("carbon_jax_lab_model", "kind")
    common = {
        "schema_version": "1.0",
        "canonicalization_profile": CONSTRUCTION_CANONICALIZATION_PROFILE,
        "challenge_key": CHALLENGE,
        "object_version": "1.0",
        "provenance": provenance,
        "unknown_or_invalid_policy": c.UnknownOrInvalidPolicy.REJECT,
    }
    assembly = c.CandidateAssemblyContract(
        **common,
        object_kind="candidate_assembly_contract",
        object_id="burgers_session_assembly",
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        training_support_ref=training.to_ref(),
        backbone_surface=c.BackboneSurfaceContract(
            "strategy_backbone", backbone_target, options
        ),
        component_slots=(),
        resource_dimensions=(),
        dependency_pins=deps,
        environment_pins=(env,),
    )
    reason = semantic("applicability_reason", "not_applicable")

    def entry(name, target, value_type, domain, fallback, *, top=False):
        return c.ParameterCatalogEntry(
            name,
            c.InputSource.TOP_LEVEL_BACKBONE if top else c.InputSource.PARAMETER_KEY,
            target,
            value_type,
            c.UnitNotApplicable(reason),
            domain,
            (),
            c.AlwaysApplicable(semantic("applicability", "all_session_strategies")),
            fallback,
            (),
            (),
            (),
            (),
            c.AssemblySemanticOwner(
                "strategy_backbone",
                semantic("scientific_authority", "unqualified_session_profile"),
            ),
            c.ActiveLifecycle(),
            c.TrainingLeverNotApplicable(reason),
            c.ComponentSelectionNotApplicable(reason),
        )

    entries = [
        entry(
            "strategy_backbone",
            backbone_target,
            c.SurfaceValueType.BACKBONE_SELECTOR,
            c.ChoiceDomain(("fno", "deeponet")),
            c.RequiredSurface(),
            top=True,
        )
    ]
    # These are exact physical coordinates, not agent-selectable scientific values.
    for name, value in (
        ("domain_length", 2 * math.pi),
        ("time_scale", TIME_SCALE),
        ("velocity_scale", 1.0),
    ):
        entries.append(
            entry(
                name,
                c.ConsumerTarget("carbon_jax_lab_task", name),
                c.SurfaceValueType.FLOAT64,
                c.Float64RangeDomain(value, value, True, True),
                c.ExplicitDefaultSurface(
                    c.SurfaceValue(c.SurfaceValueType.FLOAT64, value)
                ),
            )
        )
    entries.append(
        entry(
            "steps",
            c.ConsumerTarget("carbon_jax_lab_train", "steps"),
            c.SurfaceValueType.UINT64,
            c.UInt64RangeDomain(32, 64),
            c.RequiredSurface(),
        )
    )
    catalog = c.ParameterCatalog(
        **common,
        object_kind="parameter_catalog",
        object_id="burgers_session_parameters",
        candidate_assembly_ref=assembly.to_ref(),
        training_support_ref=training.to_ref(),
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        entries=tuple(entries),
        compatibility_rules=(),
    )
    return SessionContracts(assembly, catalog, origin, (loaded[2], *loaded[:2]))
