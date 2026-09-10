"""Focused C-AUTH1 authoring and Burgers development-law tests."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from carbon.authoring.cli import main
from carbon.authoring.goals import (
    GOAL_AUTHORING_SCHEMA,
    GoalAuthoringCode,
    GoalAuthoringError,
    ProposalWriteDisposition,
    compile_goal_intake,
    load_goal_document,
    write_compiled_proposal,
)
from carbon.generators.burgers_dynamics import (
    CANDIDATE_PAYLOAD_KEYS,
    REYNOLDS_EDGES,
    BurgersCaseCoordinates,
    BurgersDevelopmentError,
    PublicDevelopmentRole,
    candidate_query,
    evaluate_initial_field,
    generate_development_case,
    public_development_coordinates,
)
from carbon.registry import ChallengeKey
from carbon.seeding import (
    EvaluationBinding,
    MockContext,
    MockEntropy,
    SeedPin,
)


def _intake() -> dict[str, object]:
    return {
        "assets_rights": "SYNTHETIC_INTERNAL",
        "budget": {
            "local_wall_seconds": 1800.0,
            "max_candidate_trajectories": 2400,
            "max_reference_trajectories": 420,
            "official_evaluations": 0,
            "provider_calls": 0,
        },
        "challenge_id": "burgers-dynamics-v1",
        "claim": {
            "allowed_evidence": "PUBLIC_DEVELOPMENT_ONLY",
            "exclusions": [
                "No continuum-wide or universal generalization proof",
                "No real industrial or customer validation",
                "No official Carbon score, payment, network or scientific qualification",
                "No neural-operator capability claim from kernel or conventional controls",
            ],
            "maximum_failure_probability": 0.05,
            "simultaneous_alpha": 0.05,
            "tail_quantile": 0.9,
            "target": "Public numerical development diagnostics of accuracy, engineering QoIs and physics consistency on the declared periodic viscous Burgers population.",
        },
        "generator_recipe": "goal_burgers_12cell_v1",
        "goals": [
            {
                "compression_weight": 1.0 / 6.0,
                "dissipation_weight": 1.0 / 6.0,
                "field_weight": 0.5,
                "half_time_weight": 1.0 / 6.0,
                "intended_decision": "Predict the complete evolution while resolving compression and dissipation without sacrificing a declared regime.",
                "name": "Dynamics",
            }
        ],
        "intended_use": "Develop reconstructable surrogates for periodic nonlinear transport, viscous front evolution and dissipation across a declared synthetic population. Engineering analogies explain the task; this is not a calibrated industrial digital twin.",
        "mandatory_physics": "IC_PERIODIC_MEAN_MAXIMUM_ENERGY_WEAK_PDE",
        "physical_scope": "PERIODIC_UNFORCED_POSITIVE_VISCOSITY_FINITE_FOURIER_INPUT",
        "runtime_status": "NOT_INTEGRATED_WITH_CARBON_OR_JAX",
        "sampling": {
            "cell_mass": [1.0 / 12.0] * 12,
            "curriculum": "MATCHED_FULL_SUPPORT",
            "independent_learning_builds": 2,
            "learning_per_cell_per_build": 3,
            "performance_per_cell": 4,
            "reliability_per_cell": 10,
            "roles": "TRAIN_EVAL_STRESS_DISJOINT",
        },
        "schema_version": "goal-authoring/1",
        "score_policy": "HALF_MEAN_HALF_WORST_CELL_CVAR_PROPOSAL",
        "sponsor_type": "INTERNAL",
        "template": "periodic_viscous_burgers_1d_v1",
        "title": "Burgers Dynamics V1",
        "tolerances": {
            "basis": "One-percent field RMS and five-percent dimensionless QoI tolerances are explicit internal authoring choices for a discriminating development benchmark. They are not customer-validated requirements and were fixed before this numerical cohort.",
            "compression_relative_with_floor": 0.05,
            "dissipation_relative_with_floor": 0.05,
            "field_over_initial_rms": 0.01,
            "half_time_over_characteristic_time": 0.05,
            "origin": "INTERNAL_DEVELOPMENT_PROPOSAL",
            "reference_budget_fraction": 0.1,
        },
    }


def _workbench_digest(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(b"carbon-authoring-v1\0" + payload).hexdigest()


def _package() -> dict[str, object]:
    intake = _intake()
    package: dict[str, object] = {
        "intake": intake,
        "intake_digest": _workbench_digest(intake),
        "status": "DEVELOPMENT_ONLY",
    }
    package["package_digest"] = _workbench_digest(package)
    return package


def _mock_context(material: bytes = b"m" * 32) -> MockContext:
    pin = SeedPin(
        ChallengeKey("burgers-dynamics-v1", "1.0"),
        "1.0",
        "sha256:" + "1" * 64,
        "1.0",
        "sha256:" + "2" * 64,
        EvaluationBinding(b"e" * 32),
    )
    return MockContext(MockEntropy(material), pin)


def _other_context() -> MockContext:
    pin = SeedPin(
        ChallengeKey("other-challenge", "1.0"),
        "1.0",
        "sha256:" + "1" * 64,
        "1.0",
        "sha256:" + "2" * 64,
        EvaluationBinding(b"e" * 32),
    )
    return MockContext(MockEntropy(b"m" * 32), pin)


def test_raw_intake_compiles_one_competition_and_four_goal_reports() -> None:
    proposal = compile_goal_intake(_intake())
    document = proposal.document()
    assert document["schema_version"] == GOAL_AUTHORING_SCHEMA
    assert document["challenge"]["competition_count"] == 1
    reports = document["goal_reports"]
    assert [report["name"] for report in reports] == [
        "Dynamics",
        "Transport",
        "Front Resolution",
        "Dissipation",
    ]
    assert reports[0]["activation"] == "PRIMARY_CHALLENGE"
    assert all(
        report["activation"] == "PREPARED_SPECIALIST_INACTIVE" for report in reports[1:]
    )
    assert reports[0]["weights"]["field"] == {"denominator": 2, "numerator": 1}
    assert document["source"]["document_kind"] == "RAW_INTAKE"
    assert document["source"]["package_digest"] is None


def test_proposal_keeps_science_network_and_evidence_boundaries_closed() -> None:
    document = compile_goal_intake(_intake()).document()
    assert set(document["capabilities"].values()) == {False}
    assert document["evidence_boundary"]["allowed_role"] == "PUBLIC_DEVELOPMENT_ONLY"
    assert document["evidence_boundary"]["protected_evaluation_eligible"] is False
    assert document["score_proposal"]["status"] == (
        "NEW_DEVELOPMENT_SCORE_PROPOSAL_NOT_A5_ACTIVATION"
    )
    assert document["training_adapter"]["jax_source_status"] == "UNAVAILABLE"
    assert [candidate["role"] for candidate in document["reference_candidates"]] == [
        "PRIMARY_DEVELOPMENT_CANDIDATE",
        "INDEPENDENT_DEVELOPMENT_WITNESS",
    ]
    assert all(
        candidate["status"] == "NOT_QUALIFIED"
        for candidate in document["reference_candidates"]
    )
    assert document["measurement_proposal"]["point_query_rule"].startswith(
        "EVALUATE_PERIODIC_TRIGONOMETRIC_REPRESENTATION_AT_REQUESTED_POINTS"
    )
    assert document["measurement_proposal"]["uncertainty_gate"] == {
        "fail": "defect-uncertainty>limit",
        "indeterminate": "otherwise",
        "pass": "defect+uncertainty<=limit",
    }


def test_verified_package_digest_is_checked_and_bound() -> None:
    package = _package()
    proposal = compile_goal_intake(package).document()
    assert proposal["source"]["document_kind"] == "VERIFIED_WORKBENCH_PACKAGE"
    assert proposal["source"]["package_digest"] == package["package_digest"]
    package["status"] = "TAMPERED"
    with pytest.raises(GoalAuthoringError) as caught:
        compile_goal_intake(package)
    assert caught.value.code is GoalAuthoringCode.DIGEST_MISMATCH


@pytest.mark.parametrize(
    ("path", "value", "code"),
    [
        (("template",), "arbitrary_python", GoalAuthoringCode.UNSUPPORTED_TEMPLATE),
        (("runtime_status",), "READY", GoalAuthoringCode.SEMANTIC_MISMATCH),
        (("sampling", "performance_per_cell"), 5, GoalAuthoringCode.SEMANTIC_MISMATCH),
    ],
)
def test_closed_semantics_reject_changes(
    path: tuple[str, ...], value: object, code: GoalAuthoringCode
) -> None:
    intake = _intake()
    target = intake
    for field in path[:-1]:
        target = target[field]  # type: ignore[assignment,index]
    target[path[-1]] = value
    with pytest.raises(GoalAuthoringError) as caught:
        compile_goal_intake(intake)
    assert caught.value.code is code


def test_content_addressed_write_is_idempotent_and_conflicts_fail_closed(
    tmp_path: Path,
) -> None:
    proposal = compile_goal_intake(_intake())
    assert (
        write_compiled_proposal(tmp_path, proposal) is ProposalWriteDisposition.CREATED
    )
    assert (
        write_compiled_proposal(tmp_path, proposal)
        is ProposalWriteDisposition.ALREADY_PRESENT
    )
    (tmp_path / "proposal.json").write_text("conflict", encoding="utf-8")
    with pytest.raises(GoalAuthoringError) as caught:
        write_compiled_proposal(tmp_path, proposal)
    assert caught.value.code is GoalAuthoringCode.OUTPUT_CONFLICT


def test_json_loader_rejects_duplicate_keys(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.json"
    source.write_text('{"template":"one","template":"two"}', encoding="utf-8")
    with pytest.raises(GoalAuthoringError):
        load_goal_document(source)


def test_cli_emits_stable_result_and_exact_replay(
    tmp_path: Path, capsys: object
) -> None:
    source = tmp_path / "input.json"
    output = tmp_path / "output"
    source.write_text(json.dumps(_package()), encoding="utf-8")
    assert main(["compile-goal", str(source), str(output)]) == 0
    first = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert first["disposition"] == "CREATED"
    assert main(["compile-goal", str(source), str(output)]) == 0
    second = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert second["disposition"] == "ALREADY_PRESENT"
    assert first["content_digest"] == second["content_digest"]


def test_public_plan_has_exact_role_counts_and_disjoint_coordinates() -> None:
    coordinates = public_development_coordinates()
    assert len(coordinates) == 240
    assert len(set(coordinates)) == 240
    assert len({(item.role, item.draw_index) for item in coordinates}) == 240
    assert sum(item.role is PublicDevelopmentRole.TRAIN for item in coordinates) == 72
    assert sum(item.role is PublicDevelopmentRole.EVAL for item in coordinates) == 48
    assert sum(item.role is PublicDevelopmentRole.STRESS for item in coordinates) == 120


def test_all_cells_preserve_declared_burgers_parameter_law() -> None:
    context = _mock_context()
    for cell in range(12):
        case = generate_development_case(
            context,
            BurgersCaseCoordinates(PublicDevelopmentRole.STRESS, cell, 0),
        )
        coefficient_energy = sum(
            a * a + b * b
            for a, b in zip(
                case.cosine_coefficients, case.sine_coefficients, strict=True
            )
        )
        assert math.sqrt(coefficient_energy / 2.0) == pytest.approx(case.amplitude)
        assert 0.15 <= case.amplitude < 0.35
        assert -case.amplitude <= case.mean < case.amplitude
        assert (
            REYNOLDS_EDGES[cell % 4]
            <= case.reynolds_number
            < REYNOLDS_EDGES[cell % 4 + 1]
        )
        assert case.viscosity == pytest.approx(
            case.amplitude / (case.reynolds_number * case.k_rms)
        )
        assert case.horizon == pytest.approx(4.0 * case.characteristic_time)
        assert case.development_only is True
        assert case.protected_evaluation_eligible is False


def test_generation_is_deterministic_role_separated_and_mock_only() -> None:
    context = _mock_context()
    train = BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN, 0, 0)
    evaluation = BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, 0, 0)
    assert generate_development_case(context, train) == generate_development_case(
        context, train
    )
    assert (
        generate_development_case(context, train).parent_id
        != generate_development_case(context, evaluation).parent_id
    )
    with pytest.raises(BurgersDevelopmentError):
        generate_development_case(object(), train)  # type: ignore[arg-type]
    with pytest.raises(BurgersDevelopmentError):
        generate_development_case(_other_context(), train)


def test_candidate_query_is_allow_listed_and_point_exact() -> None:
    case = generate_development_case(
        _mock_context(), BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN, 0, 0)
    )
    query = candidate_query(case, grid_points=32, intervals_per_phase=2)
    assert set(query.payload()) == CANDIDATE_PAYLOAD_KEYS
    assert query.requested_times[0] == 0.0
    assert query.requested_times[-1] == case.horizon
    assert all(
        earlier < later
        for earlier, later in zip(
            query.requested_times, query.requested_times[1:], strict=False
        )
    )
    assert evaluate_initial_field(case, (0.0,))[0] == pytest.approx(
        case.mean + sum(case.cosine_coefficients)
    )


def test_coordinate_and_query_bounds_are_closed() -> None:
    with pytest.raises(BurgersDevelopmentError):
        BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN, 12, 0)
    with pytest.raises(BurgersDevelopmentError):
        BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, 0, 4)
    case = generate_development_case(
        _mock_context(), BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN, 0, 0)
    )
    with pytest.raises(BurgersDevelopmentError):
        candidate_query(case, grid_points=31)
