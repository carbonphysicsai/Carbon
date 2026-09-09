from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

FUTURE_TICKET_MARKERS = {
    "C-02_real_reconstruction.md": (
        "repeated-build identities",
        "protected official case material",
    ),
    "C-04_protected_reference_runtime.md": (
        "typed `ReferenceRunOutcome`",
        "no mock, weaker solver, averaging",
    ),
    "C-05_production_measurement.md": (
        "numerical/reference floors",
        "cannot enter lean scientific scoring",
    ),
    "C-06_signed_evidence_ledger.md": (
        "SamplingPlan",
        "positive allow-lists",
    ),
    "C-07_official_evaluation_orchestration.md": (
        "no duplicate compiler",
        "no direct chain access",
    ),
    "C-10_independent_reexecution.md": (
        "typed contested record",
        "cannot finalize, settle",
    ),
    "D-02_generator_conformance.md": (
        "intended-versus-realized population",
        "human generator qualification",
    ),
    "D-03_cole_hopf_qualification.md": (
        "quadrature/transform sensitivity",
        "not itself truth admission",
    ),
    "D-04_independent_numerical_witness.md": (
        "conservation diagnostics",
        "false independence claims",
    ),
    "D-05_measurement_qualification.md": (
        "post-result threshold tuning",
        "No measurement, gate, weight, or score threshold",
    ),
    "D-06_reconstruction_whole_case_experiment.md": (
        "dependence-aware intervals",
        "pseudo-replication cannot create false precision",
    ),
    "D-08_adversarial_candidates.md": (
        "candidate-specific evidence depth",
        "does not recreate B-E4",
    ),
}


@pytest.mark.parametrize(("filename", "markers"), FUTURE_TICKET_MARKERS.items())
def test_future_science_ticket_has_ticket_local_acceptance(
    filename: str, markers: tuple[str, str]
) -> None:
    ticket = (ROOT / ".agent/tickets" / filename).read_text(encoding="utf-8")
    assert "**Status:** `future_reserved`; unselected and unstarted" in ticket
    assert "Definition of Done" in ticket
    for marker in markers:
        assert marker in ticket


def test_current_wave_b_closeout_has_no_research_or_review_alias() -> None:
    board = (ROOT / ".agent/WAVE_B.md").read_text(encoding="utf-8")
    build_out = (ROOT / "Design_Specs/Build_Out.md").read_text(encoding="utf-8")
    research_contract = (
        ROOT / "Design_Specs/Miner_MCP_Wave_B_Research_Contract.md"
    ).read_text(encoding="utf-8")

    closeout = board.split("## 8. Wave B closeout", maxsplit=1)[1]
    assert "optional/deferred/non-blocking" in closeout
    assert "requires no human approval, GPT receipt, repeated" in closeout
    assert "failure or indeterminacy blocks Wave B closeout" not in build_out
    assert "indeterminate result also blocks Wave B closeout" not in research_contract


def test_b_gate_shipping_correctness_receipts_remain_present() -> None:
    required_tests = {
        "tests/cpu/test_b07f_resolved_fixture_adapter.py": (
            "test_a7_to_plan_to_fixture_to_a5_to_publication",
            "test_b07c_practice_and_b07f_share_exact_compiled_meaning",
            "test_unresolved_b07e_forecast_cannot_gate_or_change_fixture_result",
        ),
        "tests/cpu/test_b07g_research_service.py": (
            "test_complete_non_prior_domain_operation_path_uses_real_owners",
            "test_provider_failures_are_isolated_and_redacted",
            "test_official_v1_and_b07f_paths_never_dispatch",
        ),
        "tests/cpu/test_be1_reproducibility_harness.py": (
            "test_crossed_graph_is_full_factorial_stratified_and_dependency_explicit",
            "test_missing_censored_and_unresolved_anchor_evidence_fail_closed",
            "test_scientific_sequential_stopping_is_qualified_and_typed",
        ),
        "tests/cpu/test_be2_reference_failure_boundary.py": (
            "test_disagreement_stays_contested_and_has_no_combined_artifact",
            "test_no_failure_path_manufactures_truth_candidate_or_economic_authority",
        ),
        "tests/invariants/test_a12_invariants.py": (
            "test_a12_r05_live_requires_complete_exact_qualification",
            "test_a12_r07_infrastructure_cannot_be_scored_as_science",
        ),
    }
    for relative_path, test_names in required_tests.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        for test_name in test_names:
            assert f"def {test_name}" in source
