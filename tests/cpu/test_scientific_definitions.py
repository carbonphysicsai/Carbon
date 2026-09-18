"""Shared definitions preserve native physics, lineage and disclosure boundaries."""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError, replace

import pytest

from carbon.authoring.refs import CanonicalChallengeCaseRef
from carbon.development_session.contracts import authored_contracts
from carbon.generators.burgers_dynamics import DOMAIN_LENGTH, CandidateQuery
from carbon.scientific_tasks.definitions import (
    Audience,
    AuthoringBinding,
    Custody,
    PeriodicDefinition,
    Template,
    bind_authoring,
    from_public_burgers_query,
    template_projection,
)


def definition(**changes):
    values = {
        "template": Template.BURGERS,
        "custody": Custody.PUBLIC_DEVELOPMENT,
        "domain_length": DOMAIN_LENGTH,
        "initial_field": (0.0, 1.0, 0.0, -1.0),
        "requested_times": (0.2, 0.0, 0.1, 0.2),
        "parameter": 0.02,
        "unit_system": "carbon_burgers_native_v1",
        "source_lineage": "synthetic-contract-verification-only",
    }
    return PeriodicDefinition(**(values | changes))


def test_public_burgers_adapter_preserves_existing_query_without_generator_state():
    query = CandidateQuery((0.0, 1.0, 0.0, -1.0), 0.02, (0.2, 0.0, 0.1))
    value = from_public_burgers_query(query, source_lineage="public-fixture")
    view = value.project(Audience.MINER)
    assert view["inputs"]["initial_field"] == query.payload()["initial_field"]
    assert view["inputs"]["requested_times"] == [0.2, 0.0, 0.1]
    assert view["inputs"]["parameters"] == {"viscosity": 0.02}
    assert view["inputs"]["domain_length"] == DOMAIN_LENGTH
    assert view["equation"] == "u_t + d_x(u^2/2) = nu*u_xx"
    assert view["positions"] == [0.0, math.pi / 2, math.pi, 3 * math.pi / 2]
    assert view["shapes"]["solution"] == [3, 4]
    assert view["requested_horizon"] == 0.2
    assert (
        not {"seed", "cell", "ordinal", "draw_index", "parent_id"}
        & view["inputs"].keys()
    )
    with pytest.raises(ValueError, match="exact public"):
        from_public_burgers_query(query.payload(), source_lineage="cannot-coerce")


def test_second_template_reuses_layout_without_claiming_solver_or_challenge_support():
    value = definition(
        template=Template.ADVECTION_CONTROL,
        unit_system="carbon_advection_definition_native_v1",
        parameter=-1.0,
    )
    view = value.project(Audience.WORKBENCH)
    assert view["equation"] == "u_t + c*u_x = 0"
    assert view["variables"]["u"]["unit"] == "Q"
    assert view["parameters"]["transport_velocity"]["unit"] == "L/T"
    assert view["availability"] == "DEFINITION_ONLY_NOT_EXECUTABLE"
    assert view["qualification"] == "UNASSESSED_NOT_QUALIFIED"
    assert view["shapes"] == definition().project(Audience.MINER)["shapes"]
    assert view["encoding"] == {
        "dtype": "float64",
        "array_order": "C",
        "index_origin": 0,
    }
    assert view["inputs"]["authoring"] is None


@pytest.mark.parametrize("audience", tuple(Audience))
def test_public_metadata_has_no_case_values_or_private_identities(audience):
    projection = template_projection(Template.BURGERS, audience)
    assert projection["audience"] == audience.value
    assert (
        not {"inputs", "content_digest", "source_lineage", "authoring"}
        & projection.keys()
    )
    assert "role_boundary" in projection
    json.dumps(projection, allow_nan=False)


@pytest.mark.parametrize(
    "custody, permitted",
    (
        (Custody.PUBLIC_DEVELOPMENT, tuple(Audience)),
        (Custody.VALIDATOR_INTERNAL, (Audience.VALIDATOR,)),
        (Custody.WORKBENCH_PRIVATE, (Audience.WORKBENCH,)),
    ),
)
def test_case_projections_are_allowlisted_by_trusted_custody(custody, permitted):
    value = definition(custody=custody, source_lineage="private-canary")
    assert "private-canary" not in repr(value)
    for audience in Audience:
        if audience in permitted:
            assert (
                value.project(audience)["inputs"]["source_lineage"] == "private-canary"
            )
        else:
            with pytest.raises(PermissionError, match="custody") as error:
                value.project(audience)
            assert "private-canary" not in str(error.value)
            assert value.content_digest not in str(error.value)


def test_definition_immutable_views_independent_and_relevant_edits_change_identity():
    value = definition()
    with pytest.raises(FrozenInstanceError):
        value.parameter = 0.5
    view = value.project(Audience.MINER)
    view["inputs"]["initial_field"][0] = 999.0
    assert value.initial_field[0] == 0.0
    assert value.project(Audience.MINER)["inputs"]["initial_field"][0] == 0.0
    assert value.content_digest == definition().content_digest
    for changes in (
        {"parameter": 0.03},
        {"domain_length": 1.0},
        {"initial_field": (0.0, 0.5, 0.0, -0.5)},
        {"requested_times": (0.0, 0.1, 0.2)},
        {"source_lineage": "different-source"},
        {"custody": Custody.WORKBENCH_PRIVATE},
    ):
        assert definition(**changes).content_digest != value.content_digest
    with pytest.raises(TypeError):
        definition(display_title="display edits are not physical inputs")


@pytest.mark.parametrize(
    "changes",
    (
        {"template": "periodic_viscous_burgers_1d_v1"},
        {"custody": "PUBLIC_DEVELOPMENT"},
        {"domain_length": True},
        {"domain_length": 0.0},
        {"domain_length": float("inf")},
        {"domain_length": 5e-324},
        {"parameter": 0.0},
        {"parameter": -0.1},
        {"parameter": float("nan")},
        {"parameter": 1},
        {"unit_system": "SI"},
        {"initial_field": [0.0, 1.0]},
        {"initial_field": (0.0,)},
        {"initial_field": (True, 0.0)},
        {"initial_field": (1.0j, 0.0)},
        {"initial_field": (0.0, float("nan"))},
        {"requested_times": ()},
        {"requested_times": (-0.1,)},
        {"requested_times": ("0.1",)},
        {"source_lineage": ""},
        {"authoring": {}},
    ),
)
def test_ambiguous_invalid_or_unrepresentable_inputs_rejected(changes):
    with pytest.raises(ValueError):
        definition(**changes)


def test_existing_authoring_binding_uses_actual_exact_contracts_and_layout():
    physical, candidate, _ = authored_contracts()
    binding = bind_authoring(physical, candidate)
    assert binding.physical_system == physical.to_ref()
    assert binding.candidate_output == candidate.to_ref()
    value = definition(
        initial_field=tuple(0.0 for _ in range(64)),
        requested_times=tuple(float(i) for i in range(13)),
        authoring=binding,
    )
    assert (
        value.project(Audience.MINER)["inputs"]["authoring"]["physical_system_digest"]
        == physical.to_ref().content_digest
    )
    with pytest.raises(ValueError, match="domain/layout"):
        definition(authoring=binding)
    with pytest.raises(ValueError, match="unsupported physical"):
        AuthoringBinding(
            replace(physical.to_ref(), content_digest="sha256:" + "0" * 64),
            candidate.to_ref(),
            None,
        )
    with pytest.raises(ValueError, match="canonical-case"):
        bind_authoring(physical, candidate, object())
    with pytest.raises(ValueError, match="exact authored"):
        bind_authoring(physical.to_ref(), candidate.to_ref())
    with pytest.raises(ValueError, match="no registered"):
        definition(
            template=Template.ADVECTION_CONTROL,
            unit_system="carbon_advection_definition_native_v1",
            authoring=binding,
        )


def test_unknown_audience_cannot_select_a_view():
    with pytest.raises(ValueError, match="exact audience"):
        definition().project("validator")
    with pytest.raises(ValueError, match="exact template"):
        template_projection("burgers", Audience.MINER)


def test_canonical_case_binding_cannot_be_downgraded_to_public_or_workbench():
    physical, candidate, _ = authored_contracts()
    ref = physical.to_ref()
    case_ref = CanonicalChallengeCaseRef(
        ref.challenge_key,
        "verification_case",
        "1.0",
        ref.schema_version,
        ref.canonicalization_profile,
        "sha256:" + "a" * 64,
        "PROTECTED",
    )
    binding = AuthoringBinding(ref, candidate.to_ref(), case_ref)
    inputs = {
        "initial_field": tuple(0.0 for _ in range(64)),
        "requested_times": tuple(float(i) for i in range(13)),
        "authoring": binding,
    }
    for custody in (Custody.PUBLIC_DEVELOPMENT, Custody.WORKBENCH_PRIVATE):
        with pytest.raises(ValueError, match="validator internal"):
            definition(custody=custody, **inputs)
    value = definition(custody=Custody.VALIDATOR_INTERNAL, **inputs)
    assert (
        value.project(Audience.VALIDATOR)["inputs"]["authoring"][
            "canonical_case_digest"
        ]
        == case_ref.content_digest
    )
