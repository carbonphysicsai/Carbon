from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_DIRECTORY = ROOT / "docs/development/d_qual_prep_01"
SPEC = importlib.util.spec_from_file_location(
    "d_qual_prep_01_runner", CAMPAIGN_DIRECTORY / "run_campaign.py"
)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


@pytest.fixture(scope="module")
def records():
    return RUNNER.build_records(CAMPAIGN_DIRECTORY / "protocol_v1.json")


def _walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def test_exact_source_case_and_environment_identity(records) -> None:
    protocol = json.loads(
        (CAMPAIGN_DIRECTORY / "protocol_v1.json").read_text(encoding="ascii")
    )
    primary = records["primary_reference_evidence.json"]
    witness = records["witness_refinement_evidence.json"]
    assert protocol["source_revision"] == "ed6047d03cf60db6ce52f03e63040d95c1ea78e4"
    assert [case["cell"] for case in primary["cases"]] == list(range(12))
    assert [case["cell"] for case in witness["cases"]] == list(range(12))
    assert len({case["case_digest"] for case in primary["cases"]}) == 12
    assert all(
        case["request_digest"].startswith("sha256:") for case in primary["cases"]
    )
    assert (
        RUNNER.runtime_environment_digest()
        == protocol["upstream_identities"]["c04_environment_digest"]
    )


def test_no_threshold_invention_or_automatic_qualification(records) -> None:
    for record in records.values():
        for key, value in _walk(record):
            if "threshold" in key or "scientific_limit" in key:
                assert value is None
            if key in {
                "scientifically_qualified",
                "score_eligible",
                "protected_execution_eligible",
                "can_mint_qualification",
                "can_activate_scoring",
                "d05_can_proceed_to_qualification",
            }:
                assert value is False


def test_independence_matrix_is_complete_without_percentage(records) -> None:
    matrix = records["independence_matrix.json"]
    assert [row["dimension"] for row in matrix["rows"]] == [
        "mathematical_formulation",
        "discretization",
        "time_integration",
        "representation",
        "code",
        "libraries",
        "generator",
        "environment",
        "personnel",
        "validation_data",
    ]
    assert {row["classification"] for row in matrix["rows"]} <= set(
        matrix["allowed_classes"]
    )
    assert matrix["independence_percentage"] is None


def test_case_level_convergence_and_nonconvergence_slots_are_preserved(records) -> None:
    primary = records["primary_reference_evidence.json"]
    witness = records["witness_refinement_evidence.json"]
    assert len(primary["cases"]) == len(witness["cases"]) == 12
    assert all(len(case["convergence_history"]) == 4 for case in primary["cases"])
    assert all(
        len(case["spatial_refinement_history"]) == 4 for case in witness["cases"]
    )
    assert all(
        row["outcome"] in {"SUPPORTED", "NUMERICAL_FAILURE"}
        for case in primary["cases"]
        for row in case["convergence_history"]
    )


def test_failed_history_entry_is_retained(monkeypatch) -> None:
    protocol = json.loads(
        (CAMPAIGN_DIRECTORY / "protocol_v1.json").read_text(encoding="ascii")
    )
    case = RUNNER._case(protocol, 0)
    request = RUNNER._request(
        case,
        RUNNER.BurgersReferenceRole.CANDIDATE_PRIMARY,
        protocol["query"]["time_over_characteristic_time"],
        RUNNER.runtime_environment_digest(),
    )
    real = RUNNER._cole_hopf

    def fail_one(candidate, *, internal_grid_points=None):
        if internal_grid_points == 512:
            raise FloatingPointError("retained negative control")
        return real(candidate, internal_grid_points=internal_grid_points)

    monkeypatch.setattr(RUNNER, "_cole_hopf", fail_one)
    history = RUNNER._primary_history(request, [512, 1024])
    assert len(history) == 2
    assert history[0]["outcome"] == "NUMERICAL_FAILURE"
    assert history[0]["failure_reason"] == "FloatingPointError"
    assert history[1]["outcome"] == "SUPPORTED"


def test_identical_or_unsupported_controls_are_not_refinement_levels() -> None:
    for grids in ([256, 256], [1024, 512], [64, 8192]):
        with pytest.raises(ValueError, match="distinct, strictly increasing"):
            RUNNER._validate_refinement_grids(grids, "test")


def test_d05_blocks_without_d02_and_retained_measurement_matrix(records) -> None:
    generator = records["generator_dependency.json"]
    measurement = records["measurement_floor_sensitivity.json"]
    assert generator["d02_state"] == "FUTURE_RESERVED_UNSELECTED_UNSTARTED"
    assert generator["d05_readiness_disposition"] == "BLOCKED_INPUT"
    assert generator["d05_can_proceed_to_qualification"] is False
    assert measurement["campaign_shape"]["retained_result_matrix_path"] is None
    assert measurement["readiness_disposition"] == "BLOCKED_INPUT"
    assert measurement["score_input"] is None


def test_development_evidence_and_workbench_cannot_mint_authority(records) -> None:
    projection = records["workbench_projection_status.json"]
    assert projection["projection_eligible"] is False
    assert projection["status"] == "MANUAL_ATTACHMENT_ONLY"
    assert projection["import_record"] is None
    assert projection["supported_reader"] == (
        "carbon.c05.burgers-measurement-result.v1"
    )
    assert projection["dqual_readiness_schema_supported"] is False
    assert projection["manual_handoff_supported"] is True
    assert projection["can_mint_qualification"] is False
    assert projection["can_activate_scoring"] is False
    assert all(
        record.get("scientifically_qualified") is False
        for record in records.values()
        if "scientifically_qualified" in record
    )


def test_retained_coverage_and_accounting_do_not_expand_from_cell_count() -> None:
    readiness = json.loads(
        (CAMPAIGN_DIRECTORY / "readiness_record.json").read_text(encoding="ascii")
    )
    accounting = readiness["evidence_accounting"]
    coverage = readiness["coverage"]
    assert accounting["distinct_physical_cases"] == 12
    assert accounting["source_request_executions"] == 48
    assert accounting["numerical_method_evaluations"] == 168
    assert accounting["distinct_case_role_method_settings_queries"] == 120
    assert coverage["time_over_characteristic_time"] == [0.0, 0.1, 0.25]
    assert coverage["time_scope"] == "EARLY_TIME_THREE_SAMPLE_PROBE_NOT_FULL_TRAJECTORY"
    assert "full trajectory" in coverage["unsupported_extensions"]
    assert len(coverage["unobserved_c05_measurements"]) == 4
    assert coverage["unobserved_c05_physics_diagnostics_count"] == 6


def test_unavailable_measurement_matrix_cannot_be_completed_by_counts_or_fill() -> None:
    measurement = json.loads(
        (CAMPAIGN_DIRECTORY / "measurement_floor_sensitivity.json").read_text(
            encoding="ascii"
        )
    )
    audit = measurement["matrix_evidence_audit"]
    assert audit["status"] == "EXECUTION_NOT_ESTABLISHED"
    assert audit["specified_member_count"] == 72
    assert audit["retained_member_count"] == 0
    assert audit["executed_matrix_receipt_count"] == 0
    assert len(audit["expected_member_ids"]) == 72
    assert len(set(audit["expected_member_ids"])) == 72
    assert audit["retained_member_ids"] == []
    assert audit["conflicting_member_ids"] == []
    assert all(not row["matrix_compatible"] for row in audit["nonmatrix_evidence"])


def test_historical_wait_and_scoped_readiness_remain_distinct() -> None:
    readiness = json.loads(
        (CAMPAIGN_DIRECTORY / "readiness_record.json").read_text(encoding="ascii")
    )
    assert readiness["historical_campaign_recommendation"] == (
        "WAIT_FOR_D02_GENERATOR_CONFORMANCE"
    )
    axes = {row["axis"]: row for row in readiness["readiness_axes"]}
    assert axes["application_delivery"]["qualification_or_customer_use_effect"] == (
        "NONE"
    )
    assert axes["measurement_campaign_data"]["evidence_state"] == "UNRESOLVED"
    assert readiness["workflow"]["packet_state"] == (
        "EXPORTED_NOT_ACKNOWLEDGED_NOT_APPROVED"
    )
    assert readiness["authority"]["wave_d_selected"] is False
    assert readiness["authority"]["scientific_thresholds"] is None


def test_exact_replay_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    protocol = CAMPAIGN_DIRECTORY / "protocol_v1.json"
    RUNNER.run_campaign(protocol, first)
    RUNNER.run_campaign(protocol, second)
    names = (*RUNNER.OUTPUT_FILES, "readiness_record.json")
    assert all(
        (first / name).read_bytes() == (second / name).read_bytes() for name in names
    )
