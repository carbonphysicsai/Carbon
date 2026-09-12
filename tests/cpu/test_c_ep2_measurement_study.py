"""C-EP2 observation, accounting, and detached replay checks."""

from __future__ import annotations

import copy
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_c01_durable_execution import _binding
from test_c_ep1_evaluation_packs import _pack_service
from test_net3_candidates import setup, signed

from carbon.evaluation_packs.study import (
    DiagnosticTraceRecorder,
    EvidenceLayer,
    ModelQuantity,
    Observation,
    ReplayJob,
    ReplayOutcome,
    StudyFailure,
    compare_variants,
    simulate_variant_a,
    simulate_variant_b,
    summarize_observations,
    validate_finite_number,
)
from carbon.execution import (
    DurableExecutionQueue,
    ExecutionCode,
    ExecutionFailure,
    ExecutionState,
)
from carbon.fees import AdmissionKind
from scripts.dev.run_c_ep2_study import DEFAULT_CONFIG, run_study


def _quantity(value: int | None, reason: str | None = None) -> ModelQuantity:
    return ModelQuantity(value, missing_reason=reason)


def _job(
    name: str,
    *,
    admitted: int = 0,
    challenge: str = "challenge-a",
    compatible: str | None = "same",
    candidate: int = 10,
    reference: int = 20,
    closure: int = 5,
    outcome: ReplayOutcome = ReplayOutcome.COMPLETED,
) -> ReplayJob:
    return ReplayJob(
        name,
        challenge,
        admitted,
        compatible,
        _quantity(candidate),
        _quantity(reference),
        _quantity(closure),
        outcome,
    )


def _observed(
    sequence: int,
    *,
    start: int | None = 10,
    end: int | None = 20,
    process: int | None = 7,
    unit: str = "nanoseconds",
    work: int | None = 1,
    reason: str | None = None,
    parent: int | None = None,
    chargeable: bool = True,
) -> Observation:
    return Observation(
        "carbon.c-ep2.observation.v1",
        "run",
        sequence,
        "private-association",
        1,
        "owner",
        "operation",
        "completed boundary",
        "perf_counter_ns/process_time_ns" if start is not None else "UNAVAILABLE",
        start,
        end,
        process,
        unit,
        work,
        "COMPLETED" if start is not None else "NOT_IMPLEMENTED",
        EvidenceLayer.OBSERVED_DEVELOPMENT_EXECUTION,
        "revision",
        missing_reason=reason,
        parent_sequence=parent,
        chargeable=chargeable,
        durability="COMPLETED_CALL_BOUNDARY" if start is not None else "NOT_OBSERVED",
    )


def test_observation_privacy_and_diagnostic_sink_noninterference() -> None:
    calls = 0

    def fail_sink(_record):
        raise OSError("diagnostic sink unavailable")

    recorder = DiagnosticTraceRecorder(
        run_id="run", source_revision="revision", sink=fail_sink
    )

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "scientific-result"

    assert (
        recorder.measure(
            operation,
            association_ref="private-association",
            attempt_number=1,
            owner="owner",
            operation="operation",
            boundary="completed call",
        )
        == "scientific-result"
    )
    assert calls == 1
    assert recorder.sink_failures == 1
    assert not recorder.usable
    public = recorder.records[0].public_safe()
    assert "association_ref" not in public
    assert "start_ns" not in public
    assert "end_ns" not in public
    assert public["evidence_layer"] == "OBSERVED_DEVELOPMENT_EXECUTION"


def test_disabled_observer_executes_once_without_trace() -> None:
    calls = 0
    recorder = DiagnosticTraceRecorder(
        run_id="run", source_revision="revision", enabled=False
    )

    def operation() -> bytes:
        nonlocal calls
        calls += 1
        return b"unchanged"

    assert (
        recorder.measure(
            operation,
            association_ref=None,
            attempt_number=None,
            owner="owner",
            operation="operation",
            boundary="completed call",
        )
        == b"unchanged"
    )
    assert calls == 1
    assert recorder.records == []


def test_observation_rejects_clock_unit_nonfinite_and_missing_errors() -> None:
    with pytest.raises(StudyFailure):
        _observed(1, end=9)
    with pytest.raises(StudyFailure):
        _observed(1, unit="seconds")
    with pytest.raises(StudyFailure):
        _observed(
            1,
            start=None,
            end=None,
            process=None,
            unit="unknown",
            work=None,
            reason=None,
            chargeable=False,
        )
    for value in (True, float("inf"), float("nan"), -1):
        with pytest.raises(StudyFailure):
            validate_finite_number(value)


def test_root_span_accounting_does_not_double_charge_nested_or_precommit() -> None:
    root = _observed(1, start=0, end=100, process=80)
    nested = _observed(2, start=10, end=60, process=40, parent=1)
    summary = summarize_observations((root, nested))
    assert summary["chargeable_root_wall_ns"] == 100
    assert summary["chargeable_root_process_ns"] == 80
    assert summary["nested_or_precommit_records_charged"] == 1


def test_unknown_model_quantity_remains_unknown() -> None:
    unknown = _quantity(None, "backend phase not implemented")
    assert unknown.value is None
    with pytest.raises(StudyFailure):
        ModelQuantity(None)


def test_hand_computable_singleton_and_replay_dedup_accounting() -> None:
    result = simulate_variant_a((_job("one"), _job("two")))
    assert result["offered_distinct_jobs"] == 2
    assert result["reference_attempts"] == 2
    assert result["total_work_units"] == 70
    assert result["eligible_completions"] == 2
    assert len(result["groups"]) == 2


def test_b_reduces_to_a_when_compatibility_is_unavailable() -> None:
    jobs = (_job("one", compatible=None), _job("two", compatible=None))
    a = simulate_variant_a(jobs)
    b = simulate_variant_b(jobs, group_bound=3, group_overhead=_quantity(0))
    assert b["total_work_units"] == a["total_work_units"]
    assert [group["group_size"] for group in b["groups"]] == [1, 1]


def test_b_groups_only_ready_compatible_same_challenge_jobs() -> None:
    jobs = (
        _job("a", challenge="one"),
        _job("b", challenge="one"),
        _job("c", challenge="two"),
        _job("future", admitted=100, challenge="one"),
    )
    b = simulate_variant_b(jobs, group_bound=2, group_overhead=_quantity(0))
    assert [group["members"] for group in b["groups"]] == [
        ["a", "b"],
        ["c"],
        ["future"],
    ]
    assert not b["groups_use_future_information"]
    assert max(group["group_size"] for group in b["groups"]) == 2


def test_shared_closure_waits_for_slow_or_unresolved_member_without_global_barrier() -> (
    None
):
    jobs = (
        _job("fast", candidate=1),
        _job("slow", candidate=50),
        _job("blocked", challenge="two", outcome=ReplayOutcome.UNRESOLVED),
        _job("independent", admitted=200, challenge="three"),
    )
    b = simulate_variant_b(jobs, group_bound=3, group_overhead=_quantity(0))
    assert b["jobs"]["fast"]["shared_pack_closure_delay"] > 50
    assert b["jobs"]["blocked"]["summary_at"] is None
    assert b["jobs"]["independent"]["summary_at"] is not None


def test_unknown_b_overhead_prevents_unconditional_savings_claim() -> None:
    comparison = compare_variants(
        (_job("one"), _job("two")),
        group_bound=2,
        group_overhead=_quantity(None, "membership implementation absent"),
    )
    assert comparison["variant_b"]["total_work_units"] is None
    assert comparison["variant_b"]["eligible_completions"] == 2
    assert comparison["variant_b"]["jobs"]["one"]["summary_at"] is None
    assert (
        comparison["variant_b"]["jobs"]["one"]["summary_at_without_unknown_overhead"]
        is not None
    )
    assert comparison["supported_savings_units"] is None
    assert not comparison["unconditional_savings_supported"]
    assert not comparison["reference_sharing_implemented"]


def test_exact_attempt_claim_does_not_select_unrelated_queued_work(tmp_path) -> None:
    queue = DurableExecutionQueue(tmp_path / "queue.sqlite3")
    first = _binding(
        submission="00000000-0000-4000-8000-000000000101",
        kind=AdmissionKind.FIXTURE,
    )
    second = _binding(
        submission="00000000-0000-4000-8000-000000000102",
        kind=AdmissionKind.FIXTURE,
    )
    queue.admit(first)
    queue.admit(second)
    claim = queue.claim(second.ref, "worker", claim_id="claim-second")
    assert claim.binding == second
    assert (
        queue.status(first.ref, first.requester_identity).state is ExecutionState.QUEUED
    )
    assert queue.claim(second.ref, "worker", claim_id="claim-second") == claim
    with pytest.raises(ExecutionFailure) as captured:
        queue.claim(first.ref, "worker", claim_id="claim-second")
    assert captured.value.code is ExecutionCode.CONFLICT


def test_exact_attempt_claim_race_has_one_effect(tmp_path) -> None:
    path = tmp_path / "queue.sqlite3"
    binding = _binding(kind=AdmissionKind.FIXTURE)
    DurableExecutionQueue(path).admit(binding)
    owners = (DurableExecutionQueue.attach(path), DurableExecutionQueue.attach(path))

    def claim(owner):
        try:
            return owner.claim(binding.ref, "worker")
        except ExecutionFailure as failure:
            return failure.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = tuple(workers.map(claim, owners))
    assert sum(not isinstance(result, ExecutionCode) for result in results) == 1
    assert sum(result is ExecutionCode.STATE for result in results) == 1


def test_c_ep1_service_leaves_unrelated_queued_attempt_untouched(tmp_path) -> None:
    journal, gate = setup(tmp_path)
    candidate = journal.commit(*signed(gate, 1))
    ledger, service = _pack_service(
        tmp_path,
        journal,
        ids=(uuid.UUID("00000000-0000-0000-0000-000000009999"),),
    )
    unrelated = _binding(
        submission="00000000-0000-4000-8000-000000009998",
        kind=AdmissionKind.FIXTURE,
    )
    service.executions.admit(unrelated)
    card = service.evaluate(candidate)
    assert card.result_id
    assert (
        service.executions.status(unrelated.ref, unrelated.requester_identity).state
        is ExecutionState.QUEUED
    )
    assert ledger.trace_counts()["PACK_ASSIGNED"] == 1


def test_frozen_harness_accounts_failure_retry_restart_and_keeps_layers_distinct(
    tmp_path,
) -> None:
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    reduced = copy.deepcopy(config)
    reduced["repetitions"] = {
        "ordinary_blocks": 1,
        "observer_parity_pairs": 1,
        "fault_blocks_each": 1,
    }
    observed, replay, profiler = run_study(
        reduced,
        tmp_path / "private",
        "test-revision",
        public_output_dir=tmp_path / "public",
    )
    work = observed["work_reconciliation"]
    assert work["reconciliation_equation_holds"]
    assert work["infrastructure_retries"] == 1
    assert work["reconciliation_required"] == 1
    assert work["scored_fixture_results"] == 2
    assert work["actual_physical_reference_cases"] is None
    assert observed["numerical_probe"]["status"] == "NOT_RUN"
    assert replay["evidence_layer"] == EvidenceLayer.COUNTERFACTUAL_MODEL.value
    assert profiler["recommendation"] == "COLLECT MISSING INPUTS FIRST"
    assert not profiler["variant_b_implementation_authorized"]
    assert not (tmp_path / "public/private_trace_v1.jsonl").exists()
    assert (tmp_path / "private/private_trace_v1.jsonl").exists()
