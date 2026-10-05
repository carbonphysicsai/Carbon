"""Authored DEVELOPMENT contracts for Motor Level-0 construction.

The contracts describe the existing two-dimensional magnetostatic torque-curve
prediction interface and its public TRAIN support. Their fixture origin means unqualified
DEVELOPMENT authority; it does not turn a fixture into physical evidence.
"""

from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

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
from carbon.reconstruction import profile as worker_environment
from carbon.reconstruction.capability_registry import (
    MOTOR_CHALLENGE,
    catalog_surfaces,
    contract,
    rebuildable_families,
)

from . import domain
from .challenge import (
    CALIBRATION_SHA256,
    CHALLENGE,
    IDENTITY,
    PRACTICE_SHA256,
    TRAIN_CASES,
    TRAIN_SHA256,
    interface_document,
)

PROFILE = "carbon.electric-motor-magnetics-development.profile.v1"
IMPLEMENTATION_ID = "carbon_motor_kernel_ridge"
IMPLEMENTATION_VERSION = "1.0"
IMPLEMENTATION_SOURCES = {
    "challenge.py": "challenge.py",
    "domain.py": "domain.py",
    "recipes.py": "recipes.py",
    "learned_baseline.py": "../learned_baseline.py",
}


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def implementation_digest():
    here = Path(__file__).parent
    return digest(
        canonical(
            {
                name: digest((here / relative).resolve().read_bytes())
                for name, relative in IMPLEMENTATION_SOURCES.items()
            }
        )
    )


def profile_document():
    return {
        "schema": PROFILE,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "identity": IDENTITY,
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT_2D_PERIODIC_MOTOR",
        "interface": interface_document(),
        "physical_scope": "two-dimensional-periodic-motor-cross-section-v1",
        "public_material": {
            "train_cases": TRAIN_CASES,
            "train_sha256": TRAIN_SHA256,
            "practice_sha256": PRACTICE_SHA256,
            "calibration_sha256": CALIBRATION_SHA256,
        },
        "reconstruction": {
            "compiler": "B-02B",
            "implementation": IMPLEMENTATION_ID,
            "families": [name for name, _ in rebuildable_families(MOTOR_CHALLENGE)],
            "environment": worker_environment.ENVIRONMENT_ID,
            "randomness": "none; deterministic closed-form fit",
            "candidate_code": "none; registered declarative strategies only",
        },
        "contract_digest": contract(MOTOR_CHALLENGE).digest,
    }


def semantic(kind, label):
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(CHALLENGE),
        object_id=label,
        object_version="1.0",
        content_digest=digest(
            canonical({"clause": label, "profile": profile_document()})
        ),
    )


def na(label):
    return A.not_applicable(semantic("applicability_reason", label))


def _field(name, axes, unit):
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
        geometry_binding=A.bound(
            semantic("geometry_domain", "two_dimensional_periodic_motor_cross_section")
        ),
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
    units = {
        "magnet_mm": "millimetre",
        "embrace": "dimensionless",
        "airgap_mm": "millimetre",
        "slot_open_deg": "degree",
        "tooth_mm": "millimetre",
        "slot_bottom_mm": "millimetre",
        "current_density_a_mm2": "ampere_per_square_millimetre",
        "current_angle_deg": "degree",
    }
    inputs = tuple(_field(name, (), units[name]) for name in domain.INPUTS)
    outputs = (
        _field("torque_nm", (("rotor_angle", domain.ANGLE_STEPS),), "newton_metre"),
    )
    physical = p.PhysicalSystemSpec(
        **common,
        object_kind="physical_system_spec",
        object_id="motor_periodic_cross_section_physics",
        supersedes=na("first_motor_construction_physics"),
        governing_job_ref=semantic(
            "semantic_clause", "magnetostatic_periodic_rotor_angle_sweep"
        ),
        governing_law_refs=(
            semantic("semantic_clause", "magnetostatic_maxwell_equations"),
            semantic("semantic_clause", "maxwell_stress_torque"),
        ),
        # The v1 schema's assumptions are full AssumptionClause objects.  The
        # bounded scope is already carried by the governing-law and claim
        # references, so this contract does not invent a partial clause.
        assumptions=(),
        causal_inputs=inputs,
        required_physical_quantities=outputs,
        geometry_domain_ref=semantic(
            "geometry_domain", "two_dimensional_periodic_motor_cross_section"
        ),
        boundary_conditions=p.BoundaryConditionContract(()),
        initial_conditions=p.InitialConditionContract(()),
        time_contract=p.TimeContract(
            TimeMode.STEADY,
            na("steady_system_has_no_time_coordinate"),
            na("steady_system_has_no_time_horizon"),
            semantic("semantic_clause", "steady_no_time_endpoints"),
            semantic("unit", "second"),
        ),
        operating_envelope_ref=semantic(
            "operating_envelope", "development_input_bounds_and_buildable_geometry"
        ),
        claim_scope_ref=semantic(
            "claim_scope", "unqualified_2d_magnetostatic_development_only"
        ),
        missing_input_policy="REJECT",
    )
    relation = p.CandidateInputRelation(p.CandidateInputRelationKind.IDENTITY)
    candidate = p.CandidateOutputContract(
        **common,
        object_kind="candidate_output_contract",
        object_id="motor_periodic_cross_section_causal_io",
        supersedes=na("first_motor_construction_candidate"),
        physical_system_ref=physical.to_ref(),
        candidate_inputs=inputs,
        causal_input_bindings=tuple(
            p.CandidateInputBinding(field.field_id, field.field_id, relation)
            for field in inputs
        ),
        required_outputs=outputs,
        physical_output_bindings=tuple(
            p.CandidateOutputBinding(
                field.field_id,
                field.field_id,
                p.CandidateOutputRelation(p.CandidateOutputRelationKind.IDENTITY),
                semantic("semantic_equivalence", "physical_prediction_identity"),
            )
            for field in outputs
        ),
        candidate_representation_ref=semantic(
            "representation", "physical_target_free_query"
        ),
        geometry_domain_ref=physical.geometry_domain_ref,
        boundary_input_bindings=(),
        initial_input_bindings=(),
        time_horizon_binding=p.TimeHorizonBinding(
            (),
            semantic("semantic_equivalence", "steady_no_time_coordinate"),
            semantic("semantic_equivalence", "steady_no_horizon"),
            semantic("semantic_equivalence", "steady_no_endpoints"),
        ),
        operating_envelope_ref=physical.operating_envelope_ref,
        claim_scope_ref=physical.claim_scope_ref,
        missing_or_extra_policy="REJECT",
        malformed_output_policy="CANDIDATE_FORMAT_FAILURE",
    )
    training = t.TrainingSupportContract(
        **common,
        object_kind="training_support_contract",
        object_id="motor_public_train_support",
        supersedes=na("first_motor_construction_training"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        membership_contract=t.TrainingMembershipContract(
            semantic("membership_rule", "public_train_v1_role_only"),
            semantic("physical_support", "development_population_v1"),
            semantic("representation_support", "public_train_v1_150_cases"),
            "REJECT",
        ),
        physical_invariant_refs=(
            semantic("semantic_clause", "two_dimensional_periodic_motor_cross_section"),
        ),
        representation_invariant_refs=(semantic("semantic_clause", "physical_arrays"),),
        permitted_source_materials=(),
        permitted_generators=t.PermittedGeneratorBinding(
            t.PermittedGeneratorKind.PERMITTED,
            (semantic("generator", "motor_public_train_v1"),),
        ),
        rights_profile_ref=semantic("rights_profile", "public_synthetic"),
        permitted_use_refs=(semantic("permitted_use", "development_training_only"),),
        restrictions=(
            semantic("restriction", "no_private_counted_or_confirmation_labels"),
        ),
        provenance_requirements=(
            semantic("provenance", "pinned_gmsh_getdp_public_train_v1"),
        ),
        disclosure_contract=DisclosureContract(
            (),
            (),
            (),
            semantic("aggregation_policy", "development_only"),
            semantic("release_policy", "public_train_only"),
        ),
        unknown_or_invalid_policy="REJECT",
    )
    p.validate_candidate_against_physical(candidate, physical)
    return physical, candidate, training


@dataclass(frozen=True)
class MotorContracts:
    assembly: c.CandidateAssemblyContract
    catalog: c.ParameterCatalog
    origin: object
    artifacts: tuple[object, ...]

    def compile(self, strategy):
        from carbon.development_session.contracts import strategy_limits

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


@functools.lru_cache(maxsize=1)
def motor_contracts():
    physical, candidate, training = authored_contracts()
    source = semantic("provenance", "prospective_motor_profile")
    unqualified = FixtureAuthoringCapability().issue_origin(
        fixture_registration_ref=semantic("fixture_registration", "unqualified_motor"),
        source_provenance_refs=(source,),
    )
    loaded = tuple(
        load_authoring_bytes(
            value.to_ref(),
            value.canonical_bytes(),
            origin=unqualified,
            origin_evidence_ref=semantic(
                "authoring_origin_evidence", f"motor_object_{index}"
            ),
            source_provenance_refs=(source,),
            audit_evidence_refs=(semantic("audit_evidence", f"motor_object_{index}"),),
            qualification_evidence=na("not_scientifically_qualified"),
        )
        for index, value in enumerate((physical, candidate, training))
    )
    origin = compose_authoring_graph_origin(
        root=loaded[2],
        dependencies=loaded[:2],
        expected_dependency_refs=(physical.to_ref(), candidate.to_ref()),
        composition_audit_ref=semantic(
            "origin_composition_audit", "motor_causal_contracts"
        ),
        registered_authority=None,
    )
    provenance = c.FixtureProvenance(
        semantic("fixture_registration", "unqualified_motor"),
        (source,),
        (semantic("authoring_origin_evidence", "motor_causal_contracts"),),
    )
    env = c.EnvironmentPin(
        worker_environment.ENVIRONMENT_ID,
        worker_environment.ENVIRONMENT_VERSION,
        worker_environment.ENVIRONMENT_DIGEST,
    )
    deps = tuple(c.DependencyPin(*spec) for spec in worker_environment.DEPENDENCY_SPECS)
    impl = c.ImplementationPin(
        IMPLEMENTATION_ID, IMPLEMENTATION_VERSION, implementation_digest()
    )
    interface = interface_document()
    ip = c.InterfacePin(
        "carbon_motor_input",
        "1.0",
        digest(canonical(interface["inputs"])),
        c.InterfaceDirection.INPUT,
    )
    op = c.InterfacePin(
        "carbon_motor_output",
        "1.0",
        digest(canonical(interface["outputs"])),
        c.InterfaceDirection.OUTPUT,
    )
    options = tuple(
        c.BackboneOption(
            selector,
            "carbon_" + lab_kind,
            "1.0",
            implementation_digest(),
            impl,
            env,
            deps,
            ip,
            op,
            semantic("applicability", "motor_2d_periodic_cross_section"),
            (semantic("semantic_clause", "declarative_public_train_surrogate"),),
            (semantic("restriction", "unqualified_development_only"),),
            (),
            (),
        )
        for selector, lab_kind in rebuildable_families(MOTOR_CHALLENGE)
    )
    backbone_target = c.ConsumerTarget("carbon_motor_model", "family")
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
        object_id="motor_periodic_cross_section_assembly",
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

    def entry(name, target, value_type, domain_value, fallback, applicability, deps=()):
        return c.ParameterCatalogEntry(
            name,
            (
                c.InputSource.TOP_LEVEL_BACKBONE
                if name == "strategy_backbone"
                else c.InputSource.PARAMETER_KEY
            ),
            target,
            value_type,
            c.UnitNotApplicable(reason),
            domain_value,
            deps,
            applicability,
            fallback,
            (),
            (),
            (),
            (),
            c.AssemblySemanticOwner(
                "strategy_backbone",
                semantic("scientific_authority", "unqualified_motor_profile"),
            ),
            c.ActiveLifecycle(),
            c.TrainingLeverNotApplicable(reason),
            c.ComponentSelectionNotApplicable(reason),
        )

    always = c.AlwaysApplicable(semantic("applicability", "all_motor_strategies"))
    entries = [
        entry(
            "strategy_backbone",
            backbone_target,
            c.SurfaceValueType.BACKBONE_SELECTOR,
            c.ChoiceDomain(
                tuple(selector for selector, _ in rebuildable_families(MOTOR_CHALLENGE))
            ),
            c.RequiredSurface(),
            always,
        )
    ]
    for name, (group, kind, low, _high, default, families) in catalog_surfaces(
        MOTOR_CHALLENGE
    ).items():
        if kind != "choice":
            raise ValueError("the motor Level-0 catalog is finite choices")
        applicability = c.WhenSurfaceIn(
            semantic("applicability", "motor_" + name),
            "strategy_backbone",
            tuple(
                c.SurfaceValue(c.SurfaceValueType.BACKBONE_SELECTOR, family)
                for family in families
            ),
            semantic("applicability_reason", "unused_by_other_family"),
        )
        entries.append(
            entry(
                name,
                c.ConsumerTarget("carbon_motor_" + group, name),
                c.SurfaceValueType.CANONICAL_CHOICE,
                c.ChoiceDomain(low),
                c.ExplicitDefaultSurface(
                    c.SurfaceValue(c.SurfaceValueType.CANONICAL_CHOICE, default)
                ),
                applicability,
                ("strategy_backbone",),
            )
        )
    catalog = c.ParameterCatalog(
        **common,
        object_kind="parameter_catalog",
        object_id="motor_periodic_cross_section_parameters",
        candidate_assembly_ref=assembly.to_ref(),
        training_support_ref=training.to_ref(),
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        entries=tuple(entries),
        compatibility_rules=(),
    )
    return MotorContracts(assembly, catalog, origin, (loaded[2], *loaded[:2]))
