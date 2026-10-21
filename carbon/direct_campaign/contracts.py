"""Authored DEVELOPMENT research contracts for a direct-recipe-only version.

The shared research composition (`research_service.compose_research_service`)
builds its compiler seam and its discovery refs from a Challenge's authored
Level-0 contracts, as Motor's and Cooling's are. A direct-recipe version has no
Level-0 family, so these contracts are its shell, mirroring Motor's structure:

- the causal inputs and outputs are the registered interface document's names,
  units and float32 dtype; the TRAIN support is its registered row count and
  digests;
- the backbone surface's options are the direct sources the version's
  construction limits bind: Carbon's graph training adapter (its block) and the
  backbone catalog (its digest);
- every physical statement the interface does not register (governing law,
  geometry domain, operating envelope, rights, support) is a `human_input_*`
  clause whose profile entry is `HUMAN_INPUT`.

No strategy compiles against them: practice and freeze take direct recipes
only (`compile_refused`). Their fixture origin means unqualified DEVELOPMENT
authority; it does not turn a fixture into physical evidence.
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

from .spec import HUMAN_INPUT, key_for, keyed, research_key

#: The registered interface units, as unit clause labels (a unit the map does
#: not name is refused, never guessed).
UNIT_LABELS = {
    "mm": "millimetre",
    "mm/N": "millimetre_per_newton",
    "Hz": "hertz",
    "W": "watt",
    "s": "second",
    "degC": "degree_celsius",
}
IMPLEMENTATION_VERSION = "1.0"
#: The sources the direct campaign's research path runs, by repository path.
IMPLEMENTATION_SOURCES = (
    "carbon/direct_campaign/campaign.py",
    "carbon/direct_campaign/contracts.py",
    "carbon/direct_campaign/practice.py",
    "carbon/direct_campaign/research.py",
    "carbon/direct_campaign/spec.py",
    "carbon/development_session/physical_graph_adapter.py",
    "carbon/development_session/physical_graph_trainer.py",
)
REPOSITORY = Path(__file__).resolve().parents[2]


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def implementation_digest():
    return digest(
        canonical(
            {
                name: digest((REPOSITORY / name).read_bytes())
                for name in IMPLEMENTATION_SOURCES
            }
        )
    )


def interface_document(spec):
    key = research_key(spec)
    return spec.public().interface_document(key.challenge_id, key.version)


def limits_document(spec):
    key = research_key(spec)
    return spec.public().construction_limits_document(key.challenge_id, key.version)


def construction_kit(spec):
    key = research_key(spec)
    return spec.public().construction_kit(key.challenge_id, key.version)


def direct_sources(spec):
    """The direct sources the version's limits bind, as (selector, backbone id,
    version, content digest): Carbon's training adapter (its limits block, by
    digest) and the backbone catalog (its digest). Construction identities may
    not carry a component-graph token, so the adapter is named by its role."""
    limits = limits_document(spec)
    adapter = limits["graph_training_adapter"]
    catalog = limits["backbone_catalog"]
    return (
        ("direct_adapter", "carbon_training_adapter", "1", digest(canonical(adapter))),
        ("direct_catalog", "carbon_backbone_catalog", "1", catalog["digest"]),
    )


def profile_document(spec):
    from carbon.reconstruction.served_recipe_contract import registered

    key = research_key(spec)
    limits = limits_document(spec)
    return {
        "schema": "carbon." + spec.prefix + ".direct-development.profile.v1",
        "challenge": {"id": key.challenge_id, "version": key.version},
        "scope": limits["scope"],
        "interface": interface_document(spec),
        "construction_kit": construction_kit(spec),
        "public_material": {
            "train_cases": limits["train_cases"],
            "train_dtype": limits["train_dtype"],
            "train_provenance_sha256": limits["train_provenance_sha256"],
        },
        "construction": {
            "sources": [list(source) for source in direct_sources(spec)],
            "environment": worker_environment.ENVIRONMENT_ID,
            "candidate_code": "none; direct recipes only",
        },
        "contract_digest": registered(key.challenge_id, key.version).digest,
        # Not registered for this Challenge: each is the owner's/Validator's.
        "physical_scope": HUMAN_INPUT,
        "governing_law": HUMAN_INPUT,
        "geometry_domain": HUMAN_INPUT,
        "operating_envelope": HUMAN_INPUT,
        "rights_profile": HUMAN_INPUT,
    }


def semantic(spec, kind, label):
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(research_key(spec)),
        object_id=label,
        object_version="1.0",
        content_digest=digest(
            canonical({"clause": label, "profile": profile_document(spec)})
        ),
    )


def na(spec, label):
    return A.not_applicable(semantic(spec, "applicability_reason", label))


def _field(spec, name, unit):
    clause = functools.partial(semantic, spec)
    return p.ValueFieldContract(
        field_id=name,
        semantic_role_ref=clause("semantic_clause", name),
        representation_ref=clause("representation", "dense_physical_array"),
        unit_ref=clause("unit", UNIT_LABELS[unit]),
        shape_contract=(),
        # The registered interface is float32 (`train_dtype` "<f4").
        precision_contract=(PrecisionLiteral.FLOAT32,),
        geometry_binding=A.bound(clause("geometry_domain", "human_input_geometry")),
        presence=p.Presence(p.PresenceKind.REQUIRED),
        admissibility_refs=(),
        nonfinite_policy="REJECT",
    )


def authored_contracts(spec):
    clause = functools.partial(semantic, spec)
    interface = interface_document(spec)
    limits = limits_document(spec)
    if interface["train_dtype"] != "<f4" or limits["train_dtype"] != "<f4":
        raise ValueError(spec.prefix + " direct contracts bind a float32 interface")
    common = {
        "schema_version": "1.0",
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "challenge_key": research_key(spec),
        "object_version": "1.0",
    }
    inputs = tuple(
        _field(spec, name, unit)
        for name, unit in zip(
            interface["input"]["names"], interface["input"]["units"], strict=True
        )
    )
    outputs = tuple(
        _field(spec, name, unit)
        for name, unit in zip(
            interface["output"]["names"], interface["output"]["units"], strict=True
        )
    )
    physical = p.PhysicalSystemSpec(
        **common,
        object_kind="physical_system_spec",
        object_id=spec.prefix + "_direct_physics",
        supersedes=na(spec, "first_" + spec.prefix + "_direct_physics"),
        governing_job_ref=clause("semantic_clause", "human_input_governing_job"),
        governing_law_refs=(clause("semantic_clause", "human_input_governing_law"),),
        assumptions=(),
        causal_inputs=inputs,
        required_physical_quantities=outputs,
        geometry_domain_ref=clause("geometry_domain", "human_input_geometry"),
        boundary_conditions=p.BoundaryConditionContract(()),
        initial_conditions=p.InitialConditionContract(()),
        # The registered interface maps one row to its outputs, with no time
        # coordinate or horizon; the physical time semantics are not registered.
        time_contract=p.TimeContract(
            TimeMode.STEADY,
            na(spec, "interface_has_no_time_coordinate"),
            na(spec, "interface_has_no_time_horizon"),
            clause("semantic_clause", "human_input_time_semantics"),
            clause("unit", "second"),
        ),
        operating_envelope_ref=clause(
            "operating_envelope", "human_input_operating_envelope"
        ),
        claim_scope_ref=clause("claim_scope", "public_development_only"),
        missing_input_policy="REJECT",
    )
    relation = p.CandidateInputRelation(p.CandidateInputRelationKind.IDENTITY)
    candidate = p.CandidateOutputContract(
        **common,
        object_kind="candidate_output_contract",
        object_id=spec.prefix + "_direct_causal_io",
        supersedes=na(spec, "first_" + spec.prefix + "_direct_candidate"),
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
                clause("semantic_equivalence", "physical_prediction_identity"),
            )
            for field in outputs
        ),
        candidate_representation_ref=clause(
            "representation", "physical_target_free_query"
        ),
        geometry_domain_ref=physical.geometry_domain_ref,
        boundary_input_bindings=(),
        initial_input_bindings=(),
        time_horizon_binding=p.TimeHorizonBinding(
            (),
            clause("semantic_equivalence", "interface_has_no_time_coordinate"),
            clause("semantic_equivalence", "interface_has_no_time_horizon"),
            clause("semantic_equivalence", "interface_has_no_time_endpoints"),
        ),
        operating_envelope_ref=physical.operating_envelope_ref,
        claim_scope_ref=physical.claim_scope_ref,
        missing_or_extra_policy="REJECT",
        malformed_output_policy="CANDIDATE_FORMAT_FAILURE",
    )
    training = t.TrainingSupportContract(
        **common,
        object_kind="training_support_contract",
        object_id=spec.prefix + "_public_train_support",
        supersedes=na(spec, "first_" + spec.prefix + "_direct_training"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        membership_contract=t.TrainingMembershipContract(
            clause("membership_rule", "pinned_public_train_role_only"),
            clause("physical_support", "human_input_physical_support"),
            clause(
                "representation_support",
                "public_train_" + str(limits["train_cases"]) + "_cases",
            ),
            "REJECT",
        ),
        physical_invariant_refs=(
            clause("semantic_clause", "human_input_physical_invariant"),
        ),
        representation_invariant_refs=(clause("semantic_clause", "float32_rows"),),
        permitted_source_materials=(),
        permitted_generators=t.PermittedGeneratorBinding(
            t.PermittedGeneratorKind.PERMITTED,
            (clause("generator", "pinned_public_train"),),
        ),
        rights_profile_ref=clause("rights_profile", "human_input_rights_profile"),
        permitted_use_refs=(clause("permitted_use", "development_training_only"),),
        restrictions=(
            clause("restriction", "no_private_counted_or_confirmation_labels"),
        ),
        provenance_requirements=(
            clause("provenance", "pinned_public_train_provenance"),
        ),
        disclosure_contract=DisclosureContract(
            (),
            (),
            (),
            clause("aggregation_policy", "development_only"),
            clause("release_policy", "public_train_only"),
        ),
        unknown_or_invalid_policy="REJECT",
    )
    p.validate_candidate_against_physical(candidate, physical)
    return physical, candidate, training


class DirectRecipesOnly(ValueError):
    """A Level-0 strategy on a direct-recipe-only version: never compiled."""

    code = "direct_recipe_required"


def compile_refused(strategy):
    """The recipe compiler seam: a direct-recipe version compiles no Level-0
    strategy (practice and freeze take construction recipes)."""
    raise DirectRecipesOnly("direct_recipe_required")


@dataclass(frozen=True)
class DirectContracts:
    assembly: c.CandidateAssemblyContract
    catalog: c.ParameterCatalog
    origin: object
    artifacts: tuple[object, ...]
    key: object

    def compile(self, strategy):
        return compile_refused(strategy)


def direct_contracts(spec, version):
    """The research contracts for exactly `version` (no default)."""
    return _direct_contracts(spec, key_for(spec, version).version)


@functools.lru_cache(maxsize=4)
def _direct_contracts(spec, version):
    with keyed(spec, key_for(spec, version)):
        return _authored_direct_contracts(spec)


def _authored_direct_contracts(spec):
    clause = functools.partial(semantic, spec)
    physical, candidate, training = authored_contracts(spec)
    source = clause("provenance", "prospective_" + spec.prefix + "_direct_profile")
    fixture = clause("fixture_registration", "unqualified_" + spec.prefix + "_direct")
    unqualified = FixtureAuthoringCapability().issue_origin(
        fixture_registration_ref=fixture, source_provenance_refs=(source,)
    )
    loaded = tuple(
        load_authoring_bytes(
            value.to_ref(),
            value.canonical_bytes(),
            origin=unqualified,
            origin_evidence_ref=clause(
                "authoring_origin_evidence", f"{spec.prefix}_object_{index}"
            ),
            source_provenance_refs=(source,),
            audit_evidence_refs=(
                clause("audit_evidence", f"{spec.prefix}_object_{index}"),
            ),
            qualification_evidence=na(spec, "not_scientifically_qualified"),
        )
        for index, value in enumerate((physical, candidate, training))
    )
    origin = compose_authoring_graph_origin(
        root=loaded[2],
        dependencies=loaded[:2],
        expected_dependency_refs=(physical.to_ref(), candidate.to_ref()),
        composition_audit_ref=clause(
            "origin_composition_audit", spec.prefix + "_direct_contracts"
        ),
        registered_authority=None,
    )
    provenance = c.FixtureProvenance(
        fixture,
        (source,),
        (clause("authoring_origin_evidence", spec.prefix + "_direct_contracts"),),
    )
    env = c.EnvironmentPin(
        worker_environment.ENVIRONMENT_ID,
        worker_environment.ENVIRONMENT_VERSION,
        worker_environment.ENVIRONMENT_DIGEST,
    )
    deps = tuple(
        c.DependencyPin(*spec_) for spec_ in worker_environment.DEPENDENCY_SPECS
    )
    impl = c.ImplementationPin(
        "carbon_" + spec.prefix + "_direct_recipe",
        IMPLEMENTATION_VERSION,
        implementation_digest(),
    )
    interface = interface_document(spec)
    ip = c.InterfacePin(
        "carbon_" + spec.prefix + "_input",
        "1.0",
        digest(canonical(interface["input"])),
        c.InterfaceDirection.INPUT,
    )
    op = c.InterfacePin(
        "carbon_" + spec.prefix + "_output",
        "1.0",
        digest(canonical(interface["output"])),
        c.InterfaceDirection.OUTPUT,
    )
    sources = direct_sources(spec)
    options = tuple(
        c.BackboneOption(
            selector,
            backbone_id,
            backbone_version,
            content,
            impl,
            env,
            deps,
            ip,
            op,
            clause("applicability", spec.prefix + "_direct_recipe"),
            (clause("semantic_clause", "direct_recipe_on_pinned_public_train"),),
            (clause("restriction", "unqualified_development_only"),),
            (),
            (),
        )
        for selector, backbone_id, backbone_version, content in sources
    )
    backbone_target = c.ConsumerTarget("carbon_" + spec.prefix + "_model", "recipe")
    common = {
        "schema_version": "1.0",
        "canonicalization_profile": CONSTRUCTION_CANONICALIZATION_PROFILE,
        "challenge_key": research_key(spec),
        "object_version": "1.0",
        "provenance": provenance,
        "unknown_or_invalid_policy": c.UnknownOrInvalidPolicy.REJECT,
    }
    assembly = c.CandidateAssemblyContract(
        **common,
        object_kind="candidate_assembly_contract",
        object_id=spec.prefix + "_direct_assembly",
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
    reason = clause("applicability_reason", "not_applicable")
    entry = c.ParameterCatalogEntry(
        "strategy_backbone",
        c.InputSource.TOP_LEVEL_BACKBONE,
        backbone_target,
        c.SurfaceValueType.BACKBONE_SELECTOR,
        c.UnitNotApplicable(reason),
        c.ChoiceDomain(tuple(selector for selector, *_ in sources)),
        (),
        c.AlwaysApplicable(clause("applicability", "all_direct_recipes")),
        c.RequiredSurface(),
        (),
        (),
        (),
        (),
        c.AssemblySemanticOwner(
            "strategy_backbone",
            clause("scientific_authority", "unqualified_" + spec.prefix + "_profile"),
        ),
        c.ActiveLifecycle(),
        c.TrainingLeverNotApplicable(reason),
        c.ComponentSelectionNotApplicable(reason),
    )
    catalog = c.ParameterCatalog(
        **common,
        object_kind="parameter_catalog",
        object_id=spec.prefix + "_direct_parameters",
        candidate_assembly_ref=assembly.to_ref(),
        training_support_ref=training.to_ref(),
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        entries=(entry,),
        compatibility_rules=(),
    )
    return DirectContracts(
        assembly, catalog, origin, (loaded[2], *loaded[:2]), research_key(spec)
    )
