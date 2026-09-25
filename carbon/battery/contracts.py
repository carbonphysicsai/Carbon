"""Battery construction contracts, compiled through the one B-02B compiler.

The same compiler and issue codes as Burgers, with the battery contract from
the capability registry: its families, surfaces and ranges. The registry's
nominal FIXTURE origin means unqualified DEVELOPMENT authority, exactly as for
the Burgers session; it does not replace training with a test fixture.
"""

from __future__ import annotations

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
from carbon.reconstruction import profile as jax
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    catalog_surfaces,
    contract,
    rebuildable_families,
)

from .challenge import (
    CAPACITY_CYCLES,
    CHALLENGE,
    GRID_POINTS,
    GRID_STEP_S,
    IDENTITY,
    INPUT_BOUNDS,
    INPUTS,
    OCV_TABLE_SHA256,
    TRAIN_V1_SHA256,
    V_MAX,
    V_MIN,
    WINDOW_S,
)

PROFILE = "carbon.battery-fastcharge-ageing-development.profile.v1"
IMPLEMENTATION_ID = "carbon_battery_recipes"
IMPLEMENTATION_VERSION = "1.0"


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


#: Every module whose bytes determine what a battery recipe rebuilds.
IMPLEMENTATION_MODULES = ("recipes.py", "training.py")


def implementation_digest():
    """The exact bytes of Carbon's battery recipe implementation."""
    here = Path(__file__).parent
    return digest(
        canonical(
            {
                name: digest((here / name).read_bytes())
                for name in IMPLEMENTATION_MODULES
            }
        )
    )


def profile_document():
    """Fresh data describing the exact prospective construction profile."""
    return {
        "schema": PROFILE,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "identity": IDENTITY,
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT_NON_PAYING",
        "inputs": {k: list(INPUT_BOUNDS[k]) for k in INPUTS},
        "outputs": {
            "voltage_v": {"grid_step_s": GRID_STEP_S, "window_s": WINDOW_S},
            "temperature_c": {"grid_step_s": GRID_STEP_S, "window_s": WINDOW_S},
            "plating_margin_v": "minimum cycle-1 charge plating overpotential",
            "capacity_ah": {"cycles": list(CAPACITY_CYCLES)},
        },
        "cycler_window_v": [V_MIN, V_MAX],
        "reference": "PyBaMM 26.8 DFN, OKane2022, unmodified; not a real cell",
        "public_material": {
            "ocv_table_sha256": OCV_TABLE_SHA256,
            "train_v1_sha256": TRAIN_V1_SHA256,
        },
        "reconstruction": {
            "compiler": "B-02B",
            "implementation": IMPLEMENTATION_ID,
            "families": [s for s, _ in rebuildable_families(BATTERY_CHALLENGE)],
            "randomness": "Carbon-assigned reconstruction seed; never miner-chosen",
            "candidate_code": "none; registered declarative strategies only",
        },
        "contract_digest": contract(BATTERY_CHALLENGE).digest,
    }


def semantic(kind, label):
    """Bind each semantic clause to the exact prospective battery profile."""
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
        geometry_binding=na("lumped_cell_has_no_spatial_geometry"),
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
    units = {"c1": "c_rate", "c2": "c_rate", "t_amb_c": "celsius", "soc0": "fraction"}
    inputs = tuple(_field(k, (), units[k]) for k in INPUTS)
    grid = (("time", GRID_POINTS),)
    outputs = (
        _field("voltage_v", grid, "volt"),
        _field("temperature_c", grid, "celsius"),
        _field("plating_margin_v", (), "volt"),
        _field("capacity_ah", (("cycle", len(CAPACITY_CYCLES)),), "ampere_hour"),
    )
    sample_times = _field("sample_times", grid, "second")
    physical = p.PhysicalSystemSpec(
        **common,
        object_kind="physical_system_spec",
        object_id="battery_fastcharge_physics",
        supersedes=na("first_battery_physics"),
        governing_job_ref=semantic("semantic_clause", "pybamm_dfn_okane2022_cycling"),
        governing_law_refs=(
            semantic("semantic_clause", "dfn_sei_plating_lumped_thermal"),
        ),
        assumptions=(),
        causal_inputs=inputs,
        required_physical_quantities=outputs,
        geometry_domain_ref=semantic("geometry_domain", "lumped_cell"),
        boundary_conditions=p.BoundaryConditionContract(
            (
                p.BoundaryRegionClause(
                    "cycler_protocol",
                    semantic("geometry_region", "cell_terminals"),
                    semantic("semantic_clause", "two_stage_cc_cv_rest_discharge"),
                    na("protocol_fixed_rates_are_causal_inputs"),
                    semantic("unit", "c_rate"),
                    na("protocol_fixed_by_challenge"),
                ),
            )
        ),
        initial_conditions=p.InitialConditionContract(
            (
                p.InitialStateClause(
                    "rest_at_initial_charge",
                    semantic("semantic_clause", "equilibrium_at_soc0_and_ambient"),
                    na("initial_state_already_bound_as_causal_input"),
                    semantic("geometry_domain", "lumped_cell"),
                    semantic("semantic_clause", "zero_time"),
                    na("initial_state_already_bound_as_causal_input"),
                ),
            )
        ),
        time_contract=p.TimeContract(
            TimeMode.TRANSIENT,
            A.bound(sample_times),
            A.bound(semantic("semantic_clause", "first_hour_thirty_second_grid")),
            semantic("semantic_clause", "zero_and_horizon_included"),
            semantic("unit", "second"),
        ),
        operating_envelope_ref=semantic("operating_envelope", "od1_input_bounds"),
        claim_scope_ref=semantic("claim_scope", "unqualified_development_non_paying"),
        missing_input_policy="REJECT",
    )
    candidate = p.CandidateOutputContract(
        **common,
        object_kind="candidate_output_contract",
        object_id="battery_fastcharge_causal_io",
        supersedes=na("first_battery_candidate"),
        physical_system_ref=physical.to_ref(),
        # The candidate is queried at the fixed grid: its times are an input
        # the candidate receives, never one it chooses.
        candidate_inputs=(*inputs, sample_times),
        causal_input_bindings=tuple(
            p.CandidateInputBinding(
                f.field_id,
                f.field_id,
                p.CandidateInputRelation(p.CandidateInputRelationKind.IDENTITY),
            )
            for f in inputs
        ),
        required_outputs=outputs,
        physical_output_bindings=tuple(
            p.CandidateOutputBinding(
                f.field_id,
                f.field_id,
                p.CandidateOutputRelation(p.CandidateOutputRelationKind.IDENTITY),
                semantic("semantic_equivalence", "physical_prediction_identity"),
            )
            for f in outputs
        ),
        candidate_representation_ref=semantic(
            "representation", "physical_target_free_query"
        ),
        geometry_domain_ref=physical.geometry_domain_ref,
        boundary_input_bindings=(),
        initial_input_bindings=(),
        time_horizon_binding=p.TimeHorizonBinding(
            ("sample_times",),
            semantic("semantic_equivalence", "fixed_grid_times"),
            semantic("semantic_equivalence", "fixed_grid_horizon"),
            semantic("semantic_equivalence", "fixed_grid_endpoints"),
        ),
        operating_envelope_ref=physical.operating_envelope_ref,
        claim_scope_ref=physical.claim_scope_ref,
        missing_or_extra_policy="REJECT",
        malformed_output_policy="CANDIDATE_FORMAT_FAILURE",
    )
    training = t.TrainingSupportContract(
        **common,
        object_kind="training_support_contract",
        object_id="battery_fastcharge_train_support",
        supersedes=na("first_battery_training"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        membership_contract=t.TrainingMembershipContract(
            semantic("membership_rule", "train_v1_role_only"),
            semantic("physical_support", "od1_input_bounds"),
            semantic("representation_support", "train_v1_400_cases"),
            "REJECT",
        ),
        physical_invariant_refs=(
            semantic("semantic_clause", "pybamm_dfn_okane2022_cycling"),
        ),
        representation_invariant_refs=(semantic("semantic_clause", "physical_arrays"),),
        permitted_source_materials=(),
        permitted_generators=t.PermittedGeneratorBinding(
            t.PermittedGeneratorKind.PERMITTED,
            (semantic("generator", "train_v1_public_role_only"),),
        ),
        rights_profile_ref=semantic("rights_profile", "public_synthetic"),
        permitted_use_refs=(semantic("permitted_use", "development_training_only"),),
        restrictions=(semantic("restriction", "no_private_labels_or_qualified_use"),),
        provenance_requirements=(semantic("provenance", "exam_design_train_v1"),),
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


@dataclass(frozen=True)
class BatteryContracts:
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


def battery_contracts():
    physical, candidate, training = authored_contracts()
    source = semantic("provenance", "prospective_battery_profile")
    unqualified = FixtureAuthoringCapability().issue_origin(
        fixture_registration_ref=semantic(
            "fixture_registration", "unqualified_battery"
        ),
        source_provenance_refs=(source,),
    )
    loaded = tuple(
        load_authoring_bytes(
            value.to_ref(),
            value.canonical_bytes(),
            origin=unqualified,
            origin_evidence_ref=semantic(
                "authoring_origin_evidence", f"battery_object_{index}"
            ),
            source_provenance_refs=(source,),
            audit_evidence_refs=(
                semantic("audit_evidence", f"battery_object_{index}"),
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
            "origin_composition_audit", "battery_causal_contracts"
        ),
        registered_authority=None,
    )
    provenance = c.FixtureProvenance(
        semantic("fixture_registration", "unqualified_battery"),
        (source,),
        (semantic("authoring_origin_evidence", "battery_causal_contracts"),),
    )
    # The recipes need only JAX and NumPy from the pinned science-jax
    # environment that also carries the Burgers lab.
    env = c.EnvironmentPin(
        jax.ENVIRONMENT_ID, jax.ENVIRONMENT_VERSION, jax.ENVIRONMENT_DIGEST
    )
    deps = tuple(c.DependencyPin(*spec) for spec in jax.DEPENDENCY_SPECS)
    impl = c.ImplementationPin(
        IMPLEMENTATION_ID, IMPLEMENTATION_VERSION, implementation_digest()
    )
    interface = digest(canonical(profile_document()["outputs"]))
    ip = c.InterfacePin(
        "carbon_battery_input",
        "1.0",
        digest(canonical(profile_document()["inputs"])),
        c.InterfaceDirection.INPUT,
    )
    op = c.InterfacePin(
        "carbon_battery_output", "1.0", interface, c.InterfaceDirection.OUTPUT
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
            semantic("applicability", "battery_fastcharge"),
            (semantic("semantic_clause", "declarative_target_free_surrogate"),),
            (semantic("restriction", "unqualified_development_only"),),
            (),
            (),
        )
        for selector, lab_kind in rebuildable_families(BATTERY_CHALLENGE)
    )
    backbone_target = c.ConsumerTarget("carbon_battery_model", "family")
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
        object_id="battery_fastcharge_assembly",
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
    types = {
        "uint": c.SurfaceValueType.UINT64,
        "float": c.SurfaceValueType.FLOAT64,
        "bool": c.SurfaceValueType.BOOL,
        "choice": c.SurfaceValueType.CANONICAL_CHOICE,
    }

    def entry(name, target, value_type, domain, fallback, applicability, deps=()):
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
            domain,
            deps,
            applicability,
            fallback,
            (),
            (),
            (),
            (),
            c.AssemblySemanticOwner(
                "strategy_backbone",
                semantic("scientific_authority", "unqualified_battery_profile"),
            ),
            c.ActiveLifecycle(),
            c.TrainingLeverNotApplicable(reason),
            c.ComponentSelectionNotApplicable(reason),
        )

    always = c.AlwaysApplicable(semantic("applicability", "all_battery_strategies"))
    entries = [
        entry(
            "strategy_backbone",
            backbone_target,
            c.SurfaceValueType.BACKBONE_SELECTOR,
            c.ChoiceDomain(
                tuple(s for s, _ in rebuildable_families(BATTERY_CHALLENGE))
            ),
            c.RequiredSurface(),
            always,
        )
    ]
    for name, (group, kind, low, high, default, families) in catalog_surfaces(
        BATTERY_CHALLENGE
    ).items():
        value_type = types[kind]
        if kind == "uint":
            domain = c.UInt64RangeDomain(low, high)
        elif kind == "float":
            domain = c.Float64RangeDomain(low, high, True, True)
        elif kind == "bool":
            domain = c.BooleanDomain((False, True))
        else:
            domain = c.ChoiceDomain(low)
        applicability = always
        if families is not None:
            applicability = c.WhenSurfaceIn(
                semantic("applicability", "battery_" + name),
                "strategy_backbone",
                tuple(
                    c.SurfaceValue(c.SurfaceValueType.BACKBONE_SELECTOR, f)
                    for f in families
                ),
                semantic("applicability_reason", "unused_by_other_family"),
            )
        entries.append(
            entry(
                name,
                c.ConsumerTarget("carbon_battery_" + group, name),
                value_type,
                domain,
                c.ExplicitDefaultSurface(c.SurfaceValue(value_type, default)),
                applicability,
                ("strategy_backbone",) if families is not None else (),
            )
        )
    catalog = c.ParameterCatalog(
        **common,
        object_kind="parameter_catalog",
        object_id="battery_fastcharge_parameters",
        candidate_assembly_ref=assembly.to_ref(),
        training_support_ref=training.to_ref(),
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        entries=tuple(entries),
        compatibility_rules=(),
    )
    return BatteryContracts(assembly, catalog, origin, (loaded[2], *loaded[:2]))
