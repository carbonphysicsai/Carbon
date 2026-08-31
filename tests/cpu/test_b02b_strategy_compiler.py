"""End-to-end fixture coverage for the bounded B-02B compiler."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from b02b_fixtures import make_compile_fixture, strategy_limits

from carbon.authoring.graph import scientific_authoring_graph_fingerprint
from carbon.authoring.loading import GraphOriginTag
from carbon.construction.compiler import (
    SUPPORTED_COMPILER_IDENTITY,
    CompileAccepted,
    CompileRejected,
    compile_strategy,
)
from carbon.construction.errors import ConstructionValidationError
from carbon.construction.model import (
    BoundComponentSelection,
    ComponentRole,
    DefaultedSurface,
    PolicyState,
    SelectedSurface,
    TrainingLeverNotApplicable,
)
from carbon.construction.plan import decode_resolved_construction_plan
from carbon.construction.policy import decode_training_sampling_policy
from carbon.construction.refs import CandidateAssemblyContractRef
from carbon.registry import ChallengeKey


def _compile(fixture, strategy=None, **overrides):
    arguments = {
        "challenge_key": fixture.key,
        "candidate_assembly": fixture.assembly,
        "candidate_assembly_ref": fixture.assembly.to_ref(),
        "parameter_catalog": fixture.catalog,
        "parameter_catalog_ref": fixture.catalog.to_ref(
            candidate_assembly=fixture.assembly
        ),
        "authoring_origin": fixture.authoring_origin,
        "authoring_artifacts": fixture.authoring_artifacts,
        "compiler_identity": SUPPORTED_COMPILER_IDENTITY,
        "strategy_limits": strategy_limits(),
    }
    arguments.update(overrides)
    return compile_strategy(strategy or fixture.strategy, **arguments)


def _codes(result: CompileRejected) -> tuple[str, ...]:
    return tuple(issue.code for issue in result.issues)


def _compile_with_exact_refs(fixture, assembly_ref, catalog_ref):
    return compile_strategy(
        fixture.strategy,
        challenge_key=fixture.key,
        candidate_assembly=fixture.assembly,
        candidate_assembly_ref=assembly_ref,
        parameter_catalog=fixture.catalog,
        parameter_catalog_ref=catalog_ref,
        authoring_origin=fixture.authoring_origin,
        authoring_artifacts=fixture.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )


def test_exact_strategy_compiles_complete_policy_resources_and_plan(tmp_path):
    fixture = make_compile_fixture(tmp_path)

    result = _compile(fixture)

    assert type(result) is CompileAccepted
    assert result.training_policy.policy_state is PolicyState.RESOLVED_OVERRIDES
    assert tuple(binding.surface_id for binding in result.training_policy.bindings) == (
        "fixture_sampling_level",
    )
    assert tuple(
        surface.surface_id for surface in result.construction_plan.resolved_surfaces
    ) == (
        "fixture_residual_selector",
        "fixture_sampling_level",
        "strategy_backbone",
    )
    component_surface = result.construction_plan.resolved_surfaces[0]
    assert type(component_surface) is DefaultedSurface
    assert component_surface.value.value == "fixture_residual"
    assert result.construction_plan.resolved_components[0].role is (
        ComponentRole.RESIDUAL_CORRECTION
    )
    assert result.construction_plan.static_resource_requirements[0].quantity == 13
    assert result.construction_plan.training_sampling_policy_ref == (
        result.training_policy_ref
    )
    assert result.construction_plan.to_ref() == result.construction_plan_ref
    assert result.construction_plan.authoring_origin_binding.graph_fingerprint == (
        scientific_authoring_graph_fingerprint(fixture.authoring_origin)
    )
    with pytest.raises(TypeError):
        type(result.construction_plan.authoring_origin_binding).from_capability(
            fixture.authoring_origin,
            graph_fingerprint="sha256:" + "9" * 64,
        )


def test_determinism_explicit_default_identity_and_fresh_decoders(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    explicit_a = {
        **fixture.strategy,
        "parameters": {
            "fixture_residual_selector": "fixture_residual",
            "fixture_sampling_level": 2,
        },
    }
    explicit_b = {
        **fixture.strategy,
        "parameters": {
            "fixture_sampling_level": 2,
            "fixture_residual_selector": "fixture_residual",
        },
    }

    defaulted = _compile(fixture)
    first = _compile(fixture, explicit_a)
    second = _compile(fixture, explicit_b)

    assert type(defaulted) is type(first) is type(second) is CompileAccepted
    assert (
        first.construction_plan.canonical_bytes()
        == second.construction_plan.canonical_bytes()
    )
    assert first.construction_plan_ref == second.construction_plan_ref
    assert defaulted.construction_plan_ref != first.construction_plan_ref
    assert type(first.construction_plan.resolved_surfaces[0]) is SelectedSurface
    payload = first.construction_plan.canonical_bytes()
    copy_a = decode_resolved_construction_plan(
        payload, expected_ref=first.construction_plan_ref
    )
    copy_b = decode_resolved_construction_plan(
        payload, expected_ref=first.construction_plan_ref
    )
    assert copy_a == copy_b == first.construction_plan
    assert copy_a is not copy_b
    policy_copy = decode_training_sampling_policy(
        first.training_policy.canonical_bytes(),
        expected_ref=first.training_policy_ref,
    )
    assert policy_copy == first.training_policy


@pytest.mark.parametrize(
    ("parameters", "expected_code"),
    (
        ({"fixture_sampling_level": True}, "parameter.bool_int_confusion"),
        ({"fixture_sampling_level": -0.0}, "strategy.negative_zero"),
        ({"fixture_sampling_level": [2]}, "strategy.parameter_shape_invalid"),
        (
            {"fixture_sampling_level": 2, "attacker_secret_123": 7},
            "parameter.unknown",
        ),
    ),
)
def test_hostile_flat_projection_rejects_with_closed_non_echoing_issues(
    tmp_path, parameters, expected_code
):
    fixture = make_compile_fixture(tmp_path)
    strategy = {**fixture.strategy, "parameters": parameters}

    result = _compile(fixture, strategy)

    assert type(result) is CompileRejected
    assert _codes(result) == (expected_code,)
    assert "attacker_secret_123" not in str(result)
    assert not hasattr(result, "construction_plan")


def test_challenge_ref_origin_and_gate_bypass_fail_before_partial_output(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    mismatch = _compile(
        fixture,
        challenge_key=ChallengeKey("different_family", "1.0"),
    )
    assert type(mismatch) is CompileRejected
    assert _codes(mismatch) == ("strategy.challenge_mismatch",)

    exact_ref = fixture.assembly.to_ref()
    wrong_ref = CandidateAssemblyContractRef(
        exact_ref.challenge_key,
        exact_ref.object_id,
        exact_ref.object_version,
        exact_ref.schema_version,
        exact_ref.canonicalization_profile,
        "sha256:" + "9" * 64,
    )
    digest = _compile(fixture, candidate_assembly_ref=wrong_ref)
    assert type(digest) is CompileRejected
    assert _codes(digest) == ("reference.digest_mismatch",)

    missing_origin_member = _compile(
        fixture,
        authoring_artifacts=fixture.authoring_artifacts[:-1],
    )
    assert type(missing_origin_member) is CompileRejected
    assert _codes(missing_origin_member) == ("authority.origin_invalid",)

    bypass = {
        **fixture.strategy,
        "parameters": {"fixture_sampling_level": 2, "disable_gates": True},
    }
    rejected_bypass = _compile(fixture, bypass)
    assert type(rejected_bypass) is CompileRejected
    assert _codes(rejected_bypass) == ("strategy.invalid",)


def test_registered_schema_backbone_missing_from_assembly_has_exact_diagnostic(
    tmp_path,
):
    fixture = make_compile_fixture(tmp_path)
    strategy = {**fixture.strategy, "backbone": "uno"}

    result = _compile(fixture, strategy)

    assert type(result) is CompileRejected
    assert _codes(result) == ("strategy.backbone_mismatch",)
    assert result.issues[0].path == "/backbone"
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")


def test_unregistered_component_selector_has_exact_diagnostic(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    strategy = {
        **fixture.strategy,
        "parameters": {
            **fixture.strategy["parameters"],
            "fixture_residual_selector": "not_registered",
        },
    }

    result = _compile(fixture, strategy)

    assert type(result) is CompileRejected
    assert _codes(result) == ("component.unknown",)
    assert result.issues[0].path == "/components/fixture_residual_slot"
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")


def test_compile_accepted_requires_exact_output_refs_and_mutual_binding(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    result = _compile(fixture)
    assert type(result) is CompileAccepted

    wrong_policy_ref = replace(
        result.training_policy_ref,
        content_digest="sha256:" + "9" * 64,
    )
    with pytest.raises(ValueError, match="policy and reference"):
        replace(result, training_policy_ref=wrong_policy_ref)

    wrong_plan_ref = replace(
        result.construction_plan_ref,
        content_digest="sha256:" + "9" * 64,
    )
    with pytest.raises(ValueError, match="plan and reference"):
        replace(result, construction_plan_ref=wrong_plan_ref)


def test_training_support_owned_surface_cannot_be_silently_unbound(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    sampling_entry = next(
        entry
        for entry in fixture.catalog.entries
        if entry.surface_id == "fixture_sampling_level"
    )
    nontraining_entry = next(
        entry
        for entry in fixture.catalog.entries
        if entry.surface_id == "fixture_residual_selector"
    )
    smuggled_entry = replace(
        sampling_entry,
        training_lever_binding=TrainingLeverNotApplicable(
            nontraining_entry.training_lever_binding.reason_ref
        ),
    )
    smuggled_entries = tuple(
        smuggled_entry if entry is sampling_entry else entry
        for entry in fixture.catalog.entries
    )

    with pytest.raises(ConstructionValidationError) as caught:
        replace(fixture.catalog, entries=smuggled_entries)
    assert caught.value.code == "construction.training_owner_mismatch"

    object.__setattr__(fixture.catalog, "entries", smuggled_entries)
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)
    assert type(result) is CompileRejected
    assert _codes(result) == ("training_policy.binding_invalid",)
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")


@pytest.mark.parametrize("role", tuple(ComponentRole))
def test_all_six_component_roles_remain_nominally_distinct(tmp_path, role):
    fixture = make_compile_fixture(tmp_path)
    old_slot = fixture.assembly.component_slots[0]
    option = replace(old_slot.options[0], role=role)
    slot = replace(old_slot, role=role, options=(option,))
    assembly = replace(fixture.assembly, component_slots=(slot,))
    entries = tuple(
        (
            replace(
                entry,
                component_slot_binding=BoundComponentSelection(slot.slot_id, role),
            )
            if entry.surface_id == slot.selector_surface_id
            else entry
        )
        for entry in fixture.catalog.entries
    )
    catalog = replace(
        fixture.catalog,
        candidate_assembly_ref=assembly.to_ref(),
        entries=entries,
    )

    result = _compile(
        fixture,
        candidate_assembly=assembly,
        candidate_assembly_ref=assembly.to_ref(),
        parameter_catalog=catalog,
        parameter_catalog_ref=catalog.to_ref(candidate_assembly=assembly),
    )

    assert type(result) is CompileAccepted
    assert result.construction_plan.resolved_components[0].role is role


def test_checked_resource_overflow_is_policy_agnostic_rejection(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    backbone = fixture.assembly.backbone_surface
    option = backbone.options[0]
    contribution = option.static_resource_contributions[0]
    overflowing = replace(contribution, quantity=(1 << 64) - 1)
    option = replace(option, static_resource_contributions=(overflowing,))
    assembly = replace(
        fixture.assembly,
        backbone_surface=replace(backbone, options=(option,)),
    )
    catalog = replace(
        fixture.catalog,
        candidate_assembly_ref=assembly.to_ref(),
    )

    result = _compile(
        fixture,
        candidate_assembly=assembly,
        candidate_assembly_ref=assembly.to_ref(),
        parameter_catalog=catalog,
        parameter_catalog_ref=catalog.to_ref(candidate_assembly=assembly),
    )

    assert type(result) is CompileRejected
    assert _codes(result) == ("resource.overflow",)
    assert all("policy" not in field for field in result.__dataclass_fields__)


def test_policy_and_plan_structures_have_no_random_draw_or_qualification_fields(
    tmp_path,
):
    fixture = make_compile_fixture(tmp_path)
    result = _compile(fixture)
    assert type(result) is CompileAccepted
    forbidden = {
        "seed",
        "nonce",
        "entropy_domain",
        "draw_id",
        "sampling_plan",
        "score",
        "gate",
        "qualification",
        "resource_ceiling",
        "admitted",
    }
    policy_fields = set(result.training_policy.__dataclass_fields__)
    plan_fields = set(result.construction_plan.__dataclass_fields__)
    assert forbidden.isdisjoint(policy_fields | plan_fields)
    assert result.training_policy.randomness_purposes[0].purpose_id == (
        "fixture_training_case"
    )


def test_unclassified_tampered_trusted_input_fails_closed_without_partial_output(
    tmp_path,
):
    fixture = make_compile_fixture(tmp_path)
    tampered = replace(fixture.assembly)
    exact_ref = tampered.to_ref()
    object.__setattr__(tampered, "backbone_surface", object())

    result = _compile(
        fixture,
        candidate_assembly=tampered,
        candidate_assembly_ref=exact_ref,
    )

    assert type(result) is CompileRejected
    assert _codes(result) == ("compile.internal_failure",)
    assert not hasattr(result, "construction_plan")


def test_fixture_authoring_origin_cannot_be_relabelled_as_registered(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    object.__setattr__(
        fixture.authoring_origin,
        "graph_origin",
        GraphOriginTag.REGISTERED_GRAPH,
    )

    result = _compile(fixture)

    assert type(result) is CompileRejected
    assert _codes(result) == ("authority.origin_invalid",)
    assert not hasattr(result, "construction_plan")


def test_compile_is_byte_identical_across_fresh_process_hash_seeds(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    test_support = repository_root / "tests" / "cpu"
    script = """
import json
from pathlib import Path

from b02b_fixtures import make_compile_fixture, strategy_limits
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY, CompileAccepted, compile_strategy

fixture = make_compile_fixture(Path.cwd())
result = compile_strategy(
    fixture.strategy,
    challenge_key=fixture.key,
    candidate_assembly=fixture.assembly,
    candidate_assembly_ref=fixture.assembly.to_ref(),
    parameter_catalog=fixture.catalog,
    parameter_catalog_ref=fixture.catalog.to_ref(candidate_assembly=fixture.assembly),
    authoring_origin=fixture.authoring_origin,
    authoring_artifacts=fixture.authoring_artifacts,
    compiler_identity=SUPPORTED_COMPILER_IDENTITY,
    strategy_limits=strategy_limits(),
)
assert type(result) is CompileAccepted
print(json.dumps({
    "plan_bytes": result.construction_plan.canonical_bytes().hex(),
    "plan_digest": result.construction_plan_ref.content_digest,
    "policy_bytes": result.training_policy.canonical_bytes().hex(),
    "policy_digest": result.training_policy_ref.content_digest,
}, sort_keys=True))
"""
    outputs = []
    for hash_seed in ("1", "8675309"):
        environment = {
            **os.environ,
            "PYTHONHASHSEED": hash_seed,
            "PYTHONPATH": os.pathsep.join((str(repository_root), str(test_support))),
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        outputs.append(json.loads(result.stdout))

    assert outputs[0] == outputs[1]


@pytest.mark.parametrize(
    ("forbidden_identifier", "construction_code", "compile_code"),
    (
        (
            "target_population_p",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "proposal_q",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "proposalq",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "weight_w",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "evaluation_gate",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "official_measurement",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "qualification_status",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "entropy_domain",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "entropy-domain",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "participant_seed",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "resource_ceiling",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "resource-policy",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "admission_verdict",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "participant_graph",
            "construction.component_graph_authority_forbidden",
            "component.graph_forbidden",
        ),
        (
            "participantgraph",
            "construction.component_graph_authority_forbidden",
            "component.graph_forbidden",
        ),
        (
            "source_code",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "sourcecode",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "network_endpoint",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "queue",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "scheduling",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "kill",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "price",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "forecast",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "runtime",
            "construction.resource_policy_authority_forbidden",
            "resource.policy_forbidden",
        ),
        (
            "reflection",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "deserialization",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "unregistered_composition",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "participantnonce",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "seedmaterial",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "actualdraw",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "serializedblob",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "arbitrarydependency",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "unregisteredcomposition",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "minerseed",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "participantcode",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "filepath",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "datauri",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "evalcontrol",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "realizedsample",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "rngseed",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "golive",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "customcode",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "modelpath",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "consumer_mode",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "draw",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "scientific_result",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "hidden_case",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "ordering",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "practice_mode",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "entrypoint",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "subprocess",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "requirements",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "state_dict",
            "construction.capability_authority_forbidden",
            "capability.forbidden",
        ),
        (
            "predictions",
            "construction.scientific_authority_forbidden",
            "training_policy.forbidden_authority",
        ),
        (
            "block_hash",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "prng_state",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
        (
            "random_number_generator_state",
            "construction.training_randomness_authority_forbidden",
            "training_policy.randomness_forbidden",
        ),
    ),
)
def test_catalog_cannot_smuggle_forbidden_authority_into_a_plan(
    tmp_path,
    forbidden_identifier,
    construction_code,
    compile_code,
):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    sampling_entry = next(
        entry
        for entry in fixture.catalog.entries
        if entry.surface_id == "fixture_sampling_level"
    )
    forbidden_entry = replace(
        sampling_entry,
        consumer_target=replace(
            sampling_entry.consumer_target,
            field_id=forbidden_identifier,
        ),
    )
    forbidden_entries = tuple(
        forbidden_entry if entry is sampling_entry else entry
        for entry in fixture.catalog.entries
    )

    with pytest.raises(ConstructionValidationError) as caught:
        replace(fixture.catalog, entries=forbidden_entries)
    assert caught.value.code == construction_code

    object.__setattr__(fixture.catalog, "entries", forbidden_entries)
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)

    assert type(result) is CompileRejected
    assert _codes(result) == (compile_code,)
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")


def test_compatibility_rule_id_cannot_carry_gate_authority(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    rule = fixture.catalog.compatibility_rules[0]
    forbidden_rule = replace(rule, rule_id="evaluation_gate")
    forbidden_entries = tuple(
        replace(entry, compatibility_rule_ids=("evaluation_gate",))
        for entry in fixture.catalog.entries
    )

    with pytest.raises(ConstructionValidationError) as caught:
        replace(
            fixture.catalog,
            entries=forbidden_entries,
            compatibility_rules=(forbidden_rule,),
        )
    assert caught.value.code == "construction.scientific_authority_forbidden"

    object.__setattr__(fixture.catalog, "entries", forbidden_entries)
    object.__setattr__(fixture.catalog, "compatibility_rules", (forbidden_rule,))
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)

    assert type(result) is CompileRejected
    assert _codes(result) == ("training_policy.forbidden_authority",)
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")


def test_training_executable_semantics_ref_cannot_carry_gate_authority(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    sampling_entry = next(
        entry
        for entry in fixture.catalog.entries
        if entry.surface_id == "fixture_sampling_level"
    )
    forbidden_ref = replace(
        sampling_entry.training_lever_binding.executable_semantics_ref,
        object_id="official_evaluation_gate",
    )
    forbidden_entry = replace(
        sampling_entry,
        training_lever_binding=replace(
            sampling_entry.training_lever_binding,
            executable_semantics_ref=forbidden_ref,
        ),
    )
    forbidden_entries = tuple(
        forbidden_entry if entry is sampling_entry else entry
        for entry in fixture.catalog.entries
    )

    with pytest.raises(ConstructionValidationError) as caught:
        replace(fixture.catalog, entries=forbidden_entries)
    assert caught.value.code == "construction.scientific_authority_forbidden"

    object.__setattr__(fixture.catalog, "entries", forbidden_entries)
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)

    assert type(result) is CompileRejected
    assert _codes(result) == ("training_policy.forbidden_authority",)
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")


def test_assembly_identity_cannot_carry_gate_authority(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    option = fixture.assembly.backbone_surface.options[0]
    forbidden_option = replace(option, backbone_id="evaluation_gate")
    forbidden_surface = replace(
        fixture.assembly.backbone_surface,
        options=(forbidden_option,),
    )

    with pytest.raises(ConstructionValidationError) as caught:
        replace(fixture.assembly, backbone_surface=forbidden_surface)
    assert caught.value.code == "construction.scientific_authority_forbidden"

    object.__setattr__(fixture.assembly, "backbone_surface", forbidden_surface)
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)

    assert type(result) is CompileRejected
    assert _codes(result) == ("training_policy.forbidden_authority",)
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")


def test_assembly_option_cannot_emit_resource_policy_impact_tags(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    option = fixture.assembly.backbone_surface.options[0]
    forbidden_option = replace(
        option,
        resource_impact_tags=("resource_ceiling",),
    )
    forbidden_surface = replace(
        fixture.assembly.backbone_surface,
        options=(forbidden_option,),
    )

    with pytest.raises(ConstructionValidationError) as caught:
        replace(fixture.assembly, backbone_surface=forbidden_surface)
    assert caught.value.code == "construction.resource_policy_authority_forbidden"

    object.__setattr__(fixture.assembly, "backbone_surface", forbidden_surface)
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)

    assert type(result) is CompileRejected
    assert _codes(result) == ("resource.policy_forbidden",)
    assert not hasattr(result, "construction_plan")


@pytest.mark.parametrize(
    "forbidden_tag",
    ("admission_verdict", "queue", "runtime"),
)
def test_contribution_cannot_emit_resource_policy_impact_tags(tmp_path, forbidden_tag):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    sampling_entry = next(
        entry
        for entry in fixture.catalog.entries
        if entry.surface_id == "fixture_sampling_level"
    )
    contribution = sampling_entry.static_resource_contributions[0]
    forbidden_contribution = replace(
        contribution,
        impact_tags=(forbidden_tag,),
    )
    forbidden_entry = replace(
        sampling_entry,
        static_resource_contributions=(forbidden_contribution,),
    )
    forbidden_entries = tuple(
        forbidden_entry if entry is sampling_entry else entry
        for entry in fixture.catalog.entries
    )

    forbidden_catalog = replace(fixture.catalog, entries=forbidden_entries)
    with pytest.raises(ConstructionValidationError) as caught:
        forbidden_catalog.to_ref(candidate_assembly=fixture.assembly)
    assert caught.value.code == "construction.resource_policy_authority_forbidden"

    object.__setattr__(fixture.catalog, "entries", forbidden_entries)
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)

    assert type(result) is CompileRejected
    assert _codes(result) == ("resource.policy_forbidden",)
    assert not hasattr(result, "construction_plan")


def test_training_purpose_cannot_carry_entropy_or_seed_authority(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    sampling_entry = next(
        entry
        for entry in fixture.catalog.entries
        if entry.surface_id == "fixture_sampling_level"
    )
    lever = sampling_entry.training_lever_binding
    forbidden_lever = replace(
        lever,
        randomness_purposes=(
            replace(
                lever.randomness_purposes[0],
                purpose_id="entropy_domain",
                role_key_label="participant_seed",
            ),
        ),
    )
    forbidden_entry = replace(
        sampling_entry,
        training_lever_binding=forbidden_lever,
    )
    forbidden_entries = tuple(
        forbidden_entry if entry is sampling_entry else entry
        for entry in fixture.catalog.entries
    )

    with pytest.raises(ConstructionValidationError) as caught:
        replace(fixture.catalog, entries=forbidden_entries)
    assert caught.value.code == ("construction.training_randomness_authority_forbidden")

    object.__setattr__(fixture.catalog, "entries", forbidden_entries)
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)

    assert type(result) is CompileRejected
    assert _codes(result) == ("training_policy.randomness_forbidden",)
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")


@pytest.mark.parametrize(
    "purpose_id",
    ("actual_draw", "realized_draw", "draw_id", "draw_identity"),
)
def test_training_purpose_cannot_carry_draw_identity(tmp_path, purpose_id):
    fixture = make_compile_fixture(tmp_path)
    assembly_ref = fixture.assembly.to_ref()
    catalog_ref = fixture.catalog.to_ref(candidate_assembly=fixture.assembly)
    sampling_entry = next(
        entry
        for entry in fixture.catalog.entries
        if entry.surface_id == "fixture_sampling_level"
    )
    lever = sampling_entry.training_lever_binding
    forbidden_lever = replace(
        lever,
        randomness_purposes=(
            replace(lever.randomness_purposes[0], purpose_id=purpose_id),
        ),
    )
    forbidden_entry = replace(
        sampling_entry,
        training_lever_binding=forbidden_lever,
    )
    forbidden_entries = tuple(
        forbidden_entry if entry is sampling_entry else entry
        for entry in fixture.catalog.entries
    )

    with pytest.raises(ConstructionValidationError) as caught:
        replace(fixture.catalog, entries=forbidden_entries)
    assert caught.value.code == "construction.training_randomness_authority_forbidden"

    object.__setattr__(fixture.catalog, "entries", forbidden_entries)
    result = _compile_with_exact_refs(fixture, assembly_ref, catalog_ref)

    assert type(result) is CompileRejected
    assert _codes(result) == ("training_policy.randomness_forbidden",)
    assert not hasattr(result, "training_policy")
    assert not hasattr(result, "construction_plan")
