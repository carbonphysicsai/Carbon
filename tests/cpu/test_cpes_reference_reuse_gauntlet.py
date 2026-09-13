"""Detached EXAM-PROTECT-01 reuse-gauntlet tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev.cpes_reference_reuse_gauntlet import (
    ATTACKS,
    ORIGINAL_BLOCKED,
    EconomicJob,
    ResearchLedger,
    ResearchRejected,
    adaptive_bank_exploit,
    attack_dispositions,
    run,
    run_operating_grid,
    run_persistent_probes,
    scenario_jobs,
    simulate_operating_policy,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "docs/development/cpes_reference_reuse_gauntlet_protocol_v2.json"


def _job(name: str, arrival: int, *, compatible: str | None = "same") -> EconomicJob:
    return EconomicJob(name, "challenge", compatible, arrival, 10, 1, 1)


def test_protocol_is_frozen_research_only_and_covers_four_arms() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert (
        config["schema_version"] == "carbon.cpes-reference-reuse-gauntlet.protocol.v2"
    )
    assert config["source_revision"] == "d94a22bb3c09089e01402db9e7ebf6eb3c662966"
    assert config["runtime_integration_authorized"] is False
    assert set(config["variants"]) == {"A", "B", "C", "D"}


def test_all_original_attack_ids_and_blockers_are_preserved(tmp_path: Path) -> None:
    probes = run_persistent_probes(tmp_path / "prototype")
    bank = adaptive_bank_exploit(20260914)
    rows = attack_dispositions(probes, bank)
    assert set(ATTACKS) == {f"AT-{index:02d}" for index in range(1, 31)}
    assert {row["attack_id"] for row in rows} == set(ATTACKS)
    assert {
        row["attack_id"] for row in rows if row["current_disposition"] == "BLOCKED"
    } == ORIGINAL_BLOCKED
    assert all(
        {
            "attacker_permissions",
            "entry_point",
            "input_history",
            "observations",
            "attempted_manipulation",
            "implementation_layer",
            "expected_result",
            "observed_result",
            "counterexample_trace",
            "limitation",
        }.issubset(row)
        for row in rows
    )


def test_persistent_negative_controls_exploit_and_guards_reject(tmp_path: Path) -> None:
    result = run_persistent_probes(tmp_path / "prototype")
    assert result["expected_guards"] == {
        "late_membership": "MEMBERSHIP_CLOSED",
        "retirement": "ANSWER_DEPENDENT_OPPORTUNITY_OPEN",
        "forged_authority": "UNVERIFIED_AUTHORITY",
        "early_summary": "PACK_CLOSURE_REQUIRED",
        "stale_write_after_restart": "PACK_CLOSED",
        "answer_publication": "ANSWER_PUBLICATION_NOT_AUTHORIZED",
        "changed_prediction": "PREDICTION_CONFLICT",
        "open_retry_closure": "ANSWER_DEPENDENT_OPPORTUNITY_OPEN",
    }
    assert set(result["negative_control_exploits"]) == {
        "late_membership_guard_removed",
        "retirement_guard_removed",
        "authority_evidence_guard_removed",
    }
    assert result["assignment_race_results"] == ["ASSIGNED", "INELIGIBLE_MEMBER"]


def test_duplicate_identity_gets_no_second_job_or_pack(tmp_path: Path) -> None:
    ledger = ResearchLedger(tmp_path / "ledger.sqlite3")
    first = ledger.submit("first", "challenge", {"recipe": 1}, "compatible", 1)
    copy = ledger.submit("copy", "challenge", {"recipe": 1}, "compatible", 2)
    assert first == copy == "first"
    assert ledger.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    ledger.lock_pack(
        "pack", "challenge", "compatible", ("first",), cutoff=2, case_identity="case"
    )
    assert ledger.db.execute("SELECT COUNT(*) FROM packs").fetchone()[0] == 1


def test_cache_binding_rejects_every_scientific_identity_mismatch(
    tmp_path: Path,
) -> None:
    ledger = ResearchLedger(tmp_path / "ledger.sqlite3")
    binding = {
        "challenge": "challenge",
        "physical_inputs": "inputs",
        "output_request": "output",
        "units_scaling": "units",
        "solver_config": "solver",
        "environment": "environment",
        "policy": "policy",
        "evidence_depth": "depth",
    }
    exact = ledger.put_reference(binding, {"array": [1]}, complete=True)
    assert ledger.lookup_reference(binding) == exact
    for field in binding:
        changed = dict(binding)
        changed[field] += "-changed"
        with pytest.raises(ResearchRejected, match="CACHE_BINDING_MISMATCH"):
            ledger.lookup_reference(changed)
    with pytest.raises(ResearchRejected, match="INCOMPLETE_CACHE_BINDING"):
        ledger.put_reference({"challenge": "challenge"}, {}, complete=True)


def test_adaptive_exact_feedback_reconstructs_reused_bank_not_holdout() -> None:
    result = adaptive_bank_exploit(20260914)
    assert result["queries"] == 33
    assert result["recovered_bank_exactly"] is True
    assert result["reused_bank_accuracy"] == 1.0
    assert result["independent_holdout_accuracy"] < 1.0
    assert result["evidence_class"] == "SYNTHETIC_ADAPTIVE_NEGATIVE_CONTROL"


def test_b_reduces_to_a_when_compatibility_is_absent() -> None:
    jobs = (_job("a", 0, compatible=None), _job("b", 0, compatible=None))
    a = simulate_operating_policy(
        jobs, variant="A", group_bound=3, fill_wait=0, group_overhead=0
    )
    b = simulate_operating_policy(
        jobs, variant="B", group_bound=3, fill_wait=0, group_overhead=0
    )
    assert b["total_recurring_work"] == a["total_recurring_work"]
    assert b["unique_reference_cases"] == a["unique_reference_cases"] == 2


def test_endogenous_grouping_recomputed_for_each_overhead() -> None:
    jobs = tuple(
        _job(name, arrived)
        for name, arrived in (("a", 0), ("b", 13), ("c", 14), ("d", 15))
    )
    zero = simulate_operating_policy(
        jobs, variant="B", group_bound=3, fill_wait=0, group_overhead=0
    )
    four = simulate_operating_policy(
        jobs, variant="B", group_bound=3, fill_wait=0, group_overhead=4
    )
    assert [group["members"] for group in zero["groups"]] == [["a"], ["b"], ["c", "d"]]
    assert zero["total_recurring_work"] == 38
    assert zero["jobs"]["c"]["summary_at"] == 39
    assert [group["members"] for group in four["groups"]] == [["a"], ["b", "c", "d"]]
    assert four["total_recurring_work"] == 36
    assert four["jobs"]["c"]["summary_at"] == 36


def test_c_charges_fill_wait_and_compares_incrementally_with_b() -> None:
    jobs = scenario_jobs("cheap_sparse")
    b = simulate_operating_policy(
        jobs, variant="B", group_bound=3, fill_wait=0, group_overhead=4
    )
    c = simulate_operating_policy(
        jobs, variant="C", group_bound=3, fill_wait=4, group_overhead=4
    )
    assert all(group["fill_wait"] == 0 for group in b["groups"])
    assert any(group["fill_wait"] > 0 for group in c["groups"])
    assert c["mean_feedback_delay"] > b["mean_feedback_delay"]


def test_slow_unresolved_member_blocks_only_its_pack_summary() -> None:
    result = simulate_operating_policy(
        scenario_jobs("slow_or_unresolved_member"),
        variant="B",
        group_bound=3,
        fill_wait=0,
        group_overhead=4,
    )
    assert result["jobs"]["fast"]["summary_at"] is None
    assert result["jobs"]["slow"]["summary_at"] is None
    assert result["jobs"]["unresolved"]["summary_at"] is None
    assert result["jobs"]["independent"]["summary_at"] is not None


def test_duplicate_flood_does_not_add_scientific_work() -> None:
    jobs = scenario_jobs("duplicate_flood")
    result = simulate_operating_policy(
        jobs, variant="B", group_bound=3, fill_wait=0, group_overhead=4
    )
    assert result["offered_requests"] == 13
    assert result["deduplicated_requests"] == 8
    assert result["admitted_distinct_jobs"] == 5


def test_group_reference_requirements_must_match() -> None:
    jobs = (_job("a", 0), replace_reference(_job("b", 0), 11))
    with pytest.raises(ResearchRejected, match="INCONSISTENT_REFERENCE_REQUIREMENTS"):
        simulate_operating_policy(
            jobs, variant="B", group_bound=3, fill_wait=0, group_overhead=0
        )


def replace_reference(job: EconomicJob, value: int) -> EconomicJob:
    return EconomicJob(
        job.job_id,
        job.challenge,
        job.compatibility_key,
        job.arrival,
        value,
        job.candidate_work,
        job.evidence_work,
        job.outcome,
        job.duplicate_of,
    )


def test_operating_grid_keeps_unknown_real_inputs_unknown() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    result = run_operating_grid(config)
    assert result["actual_b_overhead"] is None
    assert result["compatible_miner_demand"] is None
    assert result["scientifically_adequate_reference_cost"] is None
    assert result["unconditional_savings_supported"] is False
    assert result["membership_recomputed_per_overhead"] is True
    assert len(result["rows"]) == 45
    assert all(
        row["total_recurring_work"] == sum(row["work"].values())
        and row["uses_future_information"] is False
        for row in result["rows"]
    )


def test_complete_harness_is_single_use_and_non_authoritative(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    summary = run(config_path=CONFIG, output_dir=output, original_bundle=None)
    assert summary["blocked_attack_ids"] == sorted(ORIGINAL_BLOCKED)
    assert summary["production_authority"] is False
    assert summary["runtime_sharing_implemented"] is False
    assert summary["recommendation"] == "RETAIN_A"
    assert (output / "attack_dispositions_v2.json").exists()
    with pytest.raises(ResearchRejected, match="OUTPUT_DIRECTORY_ALREADY_EXISTS"):
        run(config_path=CONFIG, output_dir=output, original_bundle=None)
