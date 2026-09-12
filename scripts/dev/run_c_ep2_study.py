#!/usr/bin/env python3
"""Run the bounded C-EP2 Variant-A study and detached Variant-B replay."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import sys
import tempfile
import time
import uuid
from collections import defaultdict
from dataclasses import asdict
from enum import Enum
from functools import partial
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "cpu"))

from test_c01_durable_execution import _binding
from test_c_ep1_evaluation_packs import PASSING_FIXTURE
from test_net3_candidates import setup, signed
from test_traineval_stub import (
    _a7_service,
    _provider,
    _service,
    _strategy,
    _valid_material,
)

from carbon.evaluation_packs import (
    DevelopmentEvaluationPackLedger,
    DevelopmentEvaluationPackService,
    PackCode,
    PackFailure,
    PackState,
)
from carbon.evaluation_packs.study import (
    DiagnosticTraceRecorder,
    EvidenceLayer,
    ModelQuantity,
    ReplayJob,
    ReplayOutcome,
    compare_variants,
    model_job_dict,
    summarize_observations,
)
from carbon.execution import DurableExecutionQueue, ExecutionState
from carbon.fees import AdmissionKind
from carbon.traineval import FixtureStubBackend, FixtureTrainEvalService
from carbon.traineval.model import (
    InfrastructureCause,
    InfrastructureFailedRun,
    InfrastructureRetryClass,
)
from carbon.transport.models import canonical, digest

DEFAULT_CONFIG = ROOT / ".agent/preregistrations/C-EP2_measurement_study_v1.json"


def _memory_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError):
        return None


def _fixture_uuid(value: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-4000-8000-{value:012d}")


def _owners(root: Path, identity_index: int):
    root.mkdir(parents=True, exist_ok=True)
    journal, gate = setup(root)
    pack_ids = iter(
        _fixture_uuid(identity_index * 100 + value) for value in range(1, 50)
    )
    ledger = DevelopmentEvaluationPackLedger(journal, id_factory=lambda: next(pack_ids))
    submissions = _a7_service(root / "science")
    submission_ids = iter(
        _fixture_uuid(identity_index * 10_000 + value) for value in range(1, 50)
    )
    submissions._store.uuid_factory = lambda: next(submission_ids)
    executions = DurableExecutionQueue(root / "execution.sqlite3")
    service = DevelopmentEvaluationPackService(
        ledger,
        submissions,
        _service(provider=_provider(PASSING_FIXTURE)),
        executions,
    )
    return journal, gate, ledger, service


def _event_timings(ledger: DevelopmentEvaluationPackLedger) -> dict[str, list[int]]:
    with sqlite3.connect(ledger.journal.receipts.path) as db:
        values: dict[str, list[int]] = defaultdict(list)
        for kind, elapsed in db.execute(
            "SELECT kind,elapsed_ns FROM candidate_pack_event_v1 ORDER BY sequence"
        ):
            values[kind].append(elapsed)
    return dict(values)


def _extend_timings(target: dict[str, list[int]], source: dict[str, list[int]]) -> None:
    for kind, values in source.items():
        target[kind].extend(values)


def _distribution(values: list[int]) -> dict[str, int | None]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "minimum": None, "median": None, "maximum": None}
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) // 2
    )
    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "median": median,
        "maximum": ordered[-1],
    }


def _semantic_value(value):
    if isinstance(value, Enum):
        return value.value
    if type(value) is dict:
        return {key: _semantic_value(child) for key, child in value.items()}
    if type(value) in (list, tuple):
        return [_semantic_value(child) for child in value]
    if type(value) is bytes:
        return value.hex()
    return value


def _semantic_snapshot(ledger, service, candidate, card) -> str:
    assignment = ledger.internal_assignment(candidate)
    with ledger.journal.receipts.transaction() as db:
        attempts = db.execute(
            "SELECT attempt_number,materialization,materialization_digest "
            "FROM candidate_pack_attempt_v1 WHERE candidate=? ORDER BY attempt_number",
            (candidate.identity,),
        ).fetchall()
        rewards = db.execute(
            "SELECT count(*) FROM candidate_reward_batch_v1 WHERE candidate=?",
            (candidate.identity,),
        ).fetchone()[0]
        event_counts = db.execute(
            "SELECT kind,count(*) FROM candidate_pack_event_v1 "
            "WHERE candidate=? GROUP BY kind ORDER BY kind",
            (candidate.identity,),
        ).fetchall()
    with sqlite3.connect(service.executions.path) as db:
        execution_states = db.execute(
            "SELECT attempt_number,state FROM execution_attempt_v1 ORDER BY sequence"
        ).fetchall()
    return digest(
        canonical(
            _semantic_value(
                {
                    "candidate": candidate.identity,
                    "pack": assignment.pack.identity,
                    "status": asdict(service.status(candidate)),
                    "card": asdict(card),
                    "attempts": [list(row) for row in attempts],
                    "event_counts": [list(row) for row in event_counts],
                    "execution_states": [list(row) for row in execution_states],
                    "reward_rows": rewards,
                }
            )
        )
    )


def _measure_expected_failure(recorder, function, **fields) -> PackFailure:
    try:
        recorder.measure(function, **fields)
    except PackFailure as failure:
        return failure
    raise AssertionError("expected pack failure")


def _evaluate_fixture_success(service, candidate):
    with patch.object(
        FixtureStubBackend,
        "_execute_fixture",
        lambda self, **kwargs: _valid_material(),
    ):
        return service.evaluate(candidate)


def _ordinary_blocks(config, root, recorder, ledger_timings, reconciliation):
    blocks = config["repetitions"]["ordinary_blocks"]
    for index in range(blocks):
        association = f"ordinary-{index + 1:02d}"
        owners = recorder.measure(
            partial(_owners, root / association, 100 + index),
            association_ref=None,
            attempt_number=None,
            owner="C-EP1/C-01/NET-3",
            operation="startup_and_store_open",
            boundary="completed fixture-owner construction",
        )
        journal, gate, ledger, service = owners
        first_signed = signed(gate, 1)
        first = recorder.measure(
            partial(journal.commit, *first_signed),
            association_ref=association + "-a",
            attempt_number=None,
            owner="NET-3 CandidateJournal",
            operation="admit_distinct_job",
            boundary="completed candidate commit",
        )
        second_signed = signed(
            gate, 2, strategy=_strategy(parameters={"n": index + 100})
        )
        second = recorder.measure(
            partial(journal.commit, *second_signed),
            association_ref=association + "-b",
            attempt_number=None,
            owner="NET-3 CandidateJournal",
            operation="admit_distinct_job",
            boundary="completed candidate commit",
        )
        first_card = recorder.measure(
            partial(_evaluate_fixture_success, service, first),
            association_ref=association + "-a",
            attempt_number=1,
            owner="C-EP1 DevelopmentEvaluationPackService",
            operation="cold_variant_a_job",
            boundary="submission through post-closure summary",
        )
        second_card = recorder.measure(
            partial(_evaluate_fixture_success, service, second),
            association_ref=association + "-b",
            attempt_number=1,
            owner="C-EP1 DevelopmentEvaluationPackService",
            operation="warm_distinct_variant_a_job",
            boundary="submission through post-closure summary",
        )
        before_replay = ledger.trace_counts()
        copied_signed = signed(gate, 3, hotkey="validator")
        copied = recorder.measure(
            partial(journal.commit, *copied_signed),
            association_ref=association + "-a",
            attempt_number=None,
            owner="NET-3 CandidateJournal",
            operation="duplicate_candidate_commit",
            boundary="completed duplicate resolution",
        )
        if copied != first:
            raise AssertionError("duplicate changed CandidateRef")
        replay_card = recorder.measure(
            partial(service.evaluate, copied),
            association_ref=association + "-a",
            attempt_number=1,
            owner="C-EP1 DevelopmentEvaluationPackService",
            operation="idempotent_completed_job_replay",
            boundary="completed replay",
        )
        read_card = recorder.measure(
            partial(service.read_summary, first),
            association_ref=association + "-a",
            attempt_number=1,
            owner="C-EP1 DevelopmentEvaluationPackService",
            operation="read_only_summary_replay",
            boundary="completed summary read",
        )
        if replay_card != first_card or read_card != first_card:
            raise AssertionError("replay changed summary")
        if first_card.status != "SCORED" or second_card.status != "SCORED":
            raise AssertionError("ordinary fixture did not pass")
        if before_replay != ledger.trace_counts():
            raise AssertionError("replay consumed lifecycle events")
        _extend_timings(ledger_timings, _event_timings(ledger))
        reconciliation["admitted_distinct_jobs"] += 2
        reconciliation["deduplicated_requests"] += 1
        reconciliation["completed_fixture_outcomes"] += 2
        reconciliation["scored_fixture_results"] += 2
        reconciliation["pack_assignments"] += 2
        reconciliation["fresh_packs"] += 2
        reconciliation["execution_attempts"] += 2
        reconciliation["reconstruction_obligations"] += 2
        reconciliation["result_records"] += 2
        reconciliation["summary_records"] += 2


def _observer_parity(config, root, source_revision):
    pairs = config["repetitions"]["observer_parity_pairs"]
    overhead: list[int] = []
    for index in range(pairs):
        enabled = DiagnosticTraceRecorder(
            run_id=f"parity-enabled-{index}", source_revision=source_revision
        )
        j1, g1, l1, s1 = _owners(root / f"parity-enabled-{index}", 500 + index)
        c1 = j1.commit(*signed(g1, 1))
        card1 = enabled.measure(
            partial(_evaluate_fixture_success, s1, c1),
            association_ref="parity",
            attempt_number=1,
            owner="C-EP1 DevelopmentEvaluationPackService",
            operation="observer_parity_job",
            boundary="completed Variant-A call",
        )
        enabled_elapsed = enabled.records[0].wall_elapsed_ns

        disabled = DiagnosticTraceRecorder(
            run_id=f"parity-disabled-{index}",
            source_revision=source_revision,
            enabled=False,
        )
        j2, g2, l2, s2 = _owners(root / f"parity-disabled-{index}", 500 + index)
        c2 = j2.commit(*signed(g2, 1))
        started = time.perf_counter_ns()
        card2 = disabled.measure(
            partial(_evaluate_fixture_success, s2, c2),
            association_ref="parity",
            attempt_number=1,
            owner="C-EP1 DevelopmentEvaluationPackService",
            operation="observer_parity_job",
            boundary="completed Variant-A call",
        )
        disabled_elapsed = time.perf_counter_ns() - started
        if enabled.records == [] or disabled.records != []:
            raise AssertionError("observer enablement contract changed")
        if _semantic_snapshot(l1, s1, c1, card1) != _semantic_snapshot(
            l2, s2, c2, card2
        ):
            raise AssertionError("observer changed lifecycle semantics")
        if enabled_elapsed is None:
            raise AssertionError("enabled observation missing")
        overhead.append(enabled_elapsed - disabled_elapsed)
    return {
        "pairs": pairs,
        "semantic_mismatches": 0,
        "paired_enabled_minus_disabled_wall_ns": _distribution(overhead),
        "interpretation": "diagnostic paired difference; host noise prevents causal speed claims",
    }


def _fault_blocks(config, root, recorder, ledger_timings, reconciliation):
    repeats = config["repetitions"]["fault_blocks_each"]
    original_run = FixtureTrainEvalService.run_fixture

    for index in range(repeats):
        journal, gate, ledger, service = _owners(
            root / f"mandatory-{index}", 700 + index
        )
        candidate = journal.commit(*signed(gate, 1))
        with patch.object(
            FixtureStubBackend,
            "_execute_fixture",
            lambda self, **kwargs: _valid_material(gate_error=1.25),
        ):
            card = recorder.measure(
                partial(service.evaluate, candidate),
                association_ref=f"mandatory-{index}",
                attempt_number=1,
                owner="C-EP1/A8/A5",
                operation="mandatory_fixture_result",
                boundary="completed mandatory-gate fixture lifecycle",
            )
        if card.status != "MANDATORY_GATE_FAILED":
            raise AssertionError("mandatory outcome collapsed")
        _extend_timings(ledger_timings, _event_timings(ledger))
        reconciliation["admitted_distinct_jobs"] += 1
        reconciliation["completed_fixture_outcomes"] += 1
        reconciliation["pack_assignments"] += 1
        reconciliation["fresh_packs"] += 1
        reconciliation["execution_attempts"] += 1
        reconciliation["reconstruction_obligations"] += 1
        reconciliation["result_records"] += 1
        reconciliation["summary_records"] += 1
        reconciliation["mandatory_fixture_results"] += 1

    for index in range(repeats):
        journal, gate, ledger, service = _owners(
            root / f"terminal-infra-{index}", 800 + index
        )
        candidate = journal.commit(*signed(gate, 1))

        def terminal_failure(owner, envelope):
            del owner
            return InfrastructureFailedRun(
                envelope.handle,
                InfrastructureRetryClass.NON_RETRYABLE,
                InfrastructureCause.CONFIGURATION_UNAVAILABLE,
            )

        with patch.object(FixtureTrainEvalService, "run_fixture", terminal_failure):
            failure = _measure_expected_failure(
                recorder,
                partial(service.evaluate, candidate),
                association_ref=f"terminal-infra-{index}",
                attempt_number=1,
                owner="C-EP1/C-01/A8",
                operation="terminal_infrastructure_failure",
                boundary="typed terminal fixture lifecycle",
            )
        if (
            failure.code is not PackCode.STATE
            or ledger.status(candidate).state is not PackState.INCOMPLETE_CLOSED
        ):
            raise AssertionError("terminal infrastructure failure changed")
        _extend_timings(ledger_timings, _event_timings(ledger))
        reconciliation["admitted_distinct_jobs"] += 1
        reconciliation["incomplete_terminal_jobs"] += 1
        reconciliation["pack_assignments"] += 1
        reconciliation["fresh_packs"] += 1
        reconciliation["execution_attempts"] += 1
        reconciliation["reconstruction_obligations"] += 1

    for index in range(repeats):
        journal, gate, ledger, service = _owners(root / f"retry-{index}", 900 + index)
        candidate = journal.commit(*signed(gate, 1))
        calls = 0

        def retry_once(owner, envelope):
            nonlocal calls
            calls += 1
            if calls == 1:
                return InfrastructureFailedRun(
                    envelope.handle,
                    InfrastructureRetryClass.RETRYABLE,
                    InfrastructureCause.EXECUTION_TIMEOUT,
                )
            return original_run(owner, envelope)

        with patch.object(FixtureTrainEvalService, "run_fixture", retry_once):
            recorder.measure(
                partial(service.evaluate, candidate),
                association_ref=f"retry-{index}",
                attempt_number=1,
                owner="C-EP1/C-01/A7/A8",
                operation="retryable_infrastructure_successor",
                boundary="completed lifecycle after one successor",
            )
        if calls != 2:
            raise AssertionError("retry count changed")
        _extend_timings(ledger_timings, _event_timings(ledger))
        reconciliation["admitted_distinct_jobs"] += 1
        reconciliation["completed_fixture_outcomes"] += 1
        reconciliation["pack_assignments"] += 1
        reconciliation["fresh_packs"] += 1
        reconciliation["execution_attempts"] += 2
        reconciliation["infrastructure_retries"] += 1
        reconciliation["reconstruction_obligations"] += 2
        reconciliation["result_records"] += 1
        reconciliation["summary_records"] += 1

    for index in range(repeats):
        journal, gate, ledger, service = _owners(
            root / f"restart-{index}", 1000 + index
        )
        candidate = journal.commit(*signed(gate, 1))

        def crash_after_fixture(owner, envelope):
            original_run(owner, envelope)
            raise RuntimeError("injected post-fixture crash")

        with patch.object(FixtureTrainEvalService, "run_fixture", crash_after_fixture):
            failure = _measure_expected_failure(
                recorder,
                partial(service.evaluate, candidate),
                association_ref=f"restart-{index}",
                attempt_number=1,
                owner="C-EP1/C-01/A8",
                operation="ambiguous_restart",
                boundary="raised after fixture before durable result",
            )
        restarted = DurableExecutionQueue(service.executions.path)
        if (
            failure.code is not PackCode.INDETERMINATE
            or ledger.status(candidate).state is not PackState.RECONCILIATION_REQUIRED
        ):
            raise AssertionError("ambiguous restart was hidden")
        if restarted.claim_next("replacement-worker") is not None:
            raise AssertionError("restart silently redispatched")
        _extend_timings(ledger_timings, _event_timings(ledger))
        reconciliation["admitted_distinct_jobs"] += 1
        reconciliation["pending_jobs"] += 1
        reconciliation["pack_assignments"] += 1
        reconciliation["fresh_packs"] += 1
        reconciliation["execution_attempts"] += 1
        reconciliation["reconstruction_obligations"] += 1
        reconciliation["reconciliation_required"] += 1

    for index in range(repeats):
        journal, gate, ledger, service = _owners(
            root / f"result-replay-{index}", 1100 + index
        )
        candidate = journal.commit(*signed(gate, 1))
        original_close = ledger.close
        calls = 0

        def crash_close(*args, _original_close=original_close, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("injected post-result crash")
            return _original_close(*args, **kwargs)

        with patch.object(ledger, "close", crash_close):
            failure = _measure_expected_failure(
                recorder,
                partial(service.evaluate, candidate),
                association_ref=f"result-replay-{index}",
                attempt_number=1,
                owner="C-EP1/C-01",
                operation="crash_after_result_before_closure",
                boundary="raised after durable result association",
            )
            if (
                failure.code is not PackCode.INDETERMINATE
                or ledger.status(candidate).state is not PackState.RESULT_RECORDED
            ):
                raise AssertionError("result recovery state changed")
            recorder.measure(
                partial(service.evaluate, candidate),
                association_ref=f"result-replay-{index}",
                attempt_number=1,
                owner="C-EP1/C-01",
                operation="post_result_closure_replay",
                boundary="closure without redispatch",
            )
        _extend_timings(ledger_timings, _event_timings(ledger))
        reconciliation["admitted_distinct_jobs"] += 1
        reconciliation["completed_fixture_outcomes"] += 1
        reconciliation["pack_assignments"] += 1
        reconciliation["fresh_packs"] += 1
        reconciliation["execution_attempts"] += 1
        reconciliation["reconstruction_obligations"] += 1
        reconciliation["result_records"] += 1
        reconciliation["summary_records"] += 1
        reconciliation["post_result_replays"] += 1

    for index in range(repeats):
        journal, gate, ledger, service = _owners(
            root / f"summary-replay-{index}", 1200 + index
        )
        candidate = journal.commit(*signed(gate, 1))
        original_deliver = ledger.deliver_summary
        calls = 0

        def crash_deliver(value, _original_deliver=original_deliver):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("injected post-closure crash")
            return _original_deliver(value)

        with patch.object(ledger, "deliver_summary", crash_deliver):
            failure = _measure_expected_failure(
                recorder,
                partial(service.evaluate, candidate),
                association_ref=f"summary-replay-{index}",
                attempt_number=1,
                owner="C-EP1",
                operation="crash_after_closure_before_summary",
                boundary="raised after durable closure",
            )
            if (
                failure.code is not PackCode.INDETERMINATE
                or ledger.status(candidate).state is not PackState.CLOSED
            ):
                raise AssertionError("summary recovery state changed")
            recorder.measure(
                partial(service.evaluate, candidate),
                association_ref=f"summary-replay-{index}",
                attempt_number=1,
                owner="C-EP1",
                operation="post_closure_summary_replay",
                boundary="idempotent summary delivery",
            )
        _extend_timings(ledger_timings, _event_timings(ledger))
        reconciliation["admitted_distinct_jobs"] += 1
        reconciliation["completed_fixture_outcomes"] += 1
        reconciliation["pack_assignments"] += 1
        reconciliation["fresh_packs"] += 1
        reconciliation["execution_attempts"] += 1
        reconciliation["reconstruction_obligations"] += 1
        reconciliation["result_records"] += 1
        reconciliation["summary_records"] += 1
        reconciliation["post_closure_replays"] += 1


def _queued_work_probe(root, recorder, ledger_timings, reconciliation):
    journal, gate, ledger, service = _owners(root / "queued-work", 1300)
    unrelated = _binding(kind=AdmissionKind.FIXTURE)
    service.executions.admit(unrelated)
    candidate = journal.commit(*signed(gate, 1))
    recorder.measure(
        lambda: service.evaluate(candidate),
        association_ref="queued-work-intended",
        attempt_number=1,
        owner="C-EP1/C-01",
        operation="exact_claim_with_unrelated_work_queued",
        boundary="intended attempt only",
    )
    unrelated_status = service.executions.status(
        unrelated.ref, unrelated.requester_identity
    )
    if unrelated_status.state is not ExecutionState.QUEUED:
        raise AssertionError("unrelated queued job was claimed")
    _extend_timings(ledger_timings, _event_timings(ledger))
    reconciliation["admitted_distinct_jobs"] += 1
    reconciliation["completed_fixture_outcomes"] += 1
    reconciliation["pack_assignments"] += 1
    reconciliation["fresh_packs"] += 1
    reconciliation["execution_attempts"] += 1
    reconciliation["reconstruction_obligations"] += 1
    reconciliation["result_records"] += 1
    reconciliation["summary_records"] += 1
    return {"unrelated_attempt_state": unrelated_status.state.value}


def _replay(config, source_revision):
    output = []
    replay_config = config["replay"]
    unknown = ModelQuantity(
        None, missing_reason=replay_config["unknown_group_overhead_reason"]
    )
    for scenario in replay_config["scenarios"]:
        jobs = tuple(
            ReplayJob(
                job_id=row[0],
                challenge=row[1],
                admitted_at=row[2],
                compatibility_key=row[3],
                candidate_work=ModelQuantity(row[4]),
                reference_work=ModelQuantity(row[5]),
                closure_work=ModelQuantity(row[6]),
                outcome=ReplayOutcome(row[7]),
            )
            for row in scenario["jobs"]
        )
        comparison = compare_variants(
            jobs,
            group_bound=replay_config["group_bound"],
            group_overhead=unknown,
        )
        sensitivities = []
        for overhead in replay_config["overhead_sensitivity_units"]:
            value = compare_variants(
                jobs,
                group_bound=replay_config["group_bound"],
                group_overhead=ModelQuantity(overhead),
            )
            sensitivities.append(
                {
                    "group_overhead_units": overhead,
                    "assumption_conditioned_savings_units": value[
                        "assumption_conditioned_savings_units"
                    ],
                    "modeled_savings_positive_under_declared_assumptions": value[
                        "modeled_savings_positive_under_declared_assumptions"
                    ],
                    "empirical_savings_supported": value["empirical_savings_supported"],
                }
            )
        output.append(
            {
                "scenario_id": scenario["id"],
                "offered_requests": scenario["offered_requests"],
                "deduplicated_requests": scenario["deduplicated_requests"],
                "jobs": [model_job_dict(job) for job in jobs],
                "comparison_with_unknown_b_overhead": comparison,
                "overhead_sensitivity": sensitivities,
            }
        )
    return {
        "schema_version": "carbon.c-ep2.replay-bundle.v2",
        "source_revision": source_revision,
        "evidence_layer": EvidenceLayer.COUNTERFACTUAL_MODEL.value,
        "calibration": {
            "status": "UNCALIBRATED_FOR_REFERENCE_AND_CANDIDATE_WORK",
            "reason": "C-EP1 A8 is a scalar stub with no observed physical phases and model units are normalized assumptions",
        },
        "scenarios": output,
        "reference_sharing_implemented": False,
        "scientific_score_reuse": False,
        "supersedes_reporting_semantics": (
            "carbon.c-ep2.replay-bundle.v1 lower-bound labels only; "
            "the frozen v1 observations remain historical evidence"
        ),
    }


def run_study(
    config: dict[str, object],
    output_dir: Path,
    source_revision: str,
    *,
    public_output_dir: Path | None = None,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    recorder = DiagnosticTraceRecorder(
        run_id="c-ep2-frozen-study-v1", source_revision=source_revision
    )
    ledger_timings: dict[str, list[int]] = defaultdict(list)
    reconciliation = defaultdict(int)
    with tempfile.TemporaryDirectory(prefix="carbon-c-ep2-") as directory:
        root = Path(directory)
        _ordinary_blocks(config, root, recorder, ledger_timings, reconciliation)
        parity = _observer_parity(config, root, source_revision)
        _fault_blocks(config, root, recorder, ledger_timings, reconciliation)
        queued_probe = _queued_work_probe(
            root, recorder, ledger_timings, reconciliation
        )

    recorder.missing(
        owner="C-02/C-04/C-07",
        operation="physical_reconstruction_reference_inference",
        boundary="authorized real scientific vertical",
        reason="authorized real backend/reference/orchestrator not implemented",
        evidence_layer=EvidenceLayer.OBSERVED_DEVELOPMENT_EXECUTION,
    )
    recorder.missing(
        owner="C-04 public research adapter",
        operation="public_numerical_reference_probe",
        boundary="standalone numerical fixture",
        reason="no eligible pinned public numerical fixture selected in this revision",
        evidence_layer=EvidenceLayer.OBSERVED_PUBLIC_NUMERICAL_PROBE,
    )
    observed_summary = summarize_observations(recorder.records)
    ledger_summary = {
        kind: _distribution(values) for kind, values in sorted(ledger_timings.items())
    }
    admitted = reconciliation["admitted_distinct_jobs"]
    accounted = (
        reconciliation["completed_fixture_outcomes"]
        + reconciliation["incomplete_terminal_jobs"]
        + reconciliation["pending_jobs"]
    )
    if admitted != accounted:
        raise AssertionError("job reconciliation failed")
    reconciliation["reconciliation_equation_holds"] = True
    reconciliation["actual_physical_reference_cases"] = None
    reconciliation["actual_reference_attempts"] = None
    reconciliation["actual_candidate_inference"] = None
    reconciliation["accelerator_time_ns"] = None
    reconciliation["missing_physical_reason"] = (
        "A8 executes synthetic scalar derivation only"
    )

    environment = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "memory_bytes": _memory_bytes(),
        "gpu_used": False,
        "validator_count": 1,
        "concurrency": 1,
        "clock": "perf_counter_ns/process_time_ns",
    }
    observed = {
        "schema_version": "carbon.c-ep2.variant-a-observations.v1",
        "source_revision": source_revision,
        "evidence_layer": EvidenceLayer.OBSERVED_DEVELOPMENT_EXECUTION.value,
        "environment": environment,
        "configuration_digest": digest(canonical(config)),
        "trace_summary": observed_summary,
        "ledger_internal_precommit_timings": ledger_summary,
        "ledger_timing_limitation": (
            "C-EP1 event elapsed values stop before final event INSERT/commit and are not separately chargeable"
        ),
        "observer_parity": parity,
        "queued_work_probe": queued_probe,
        "work_reconciliation": dict(reconciliation),
        "numerical_probe": {
            "status": "NOT_RUN",
            "evidence_layer": EvidenceLayer.OBSERVED_PUBLIC_NUMERICAL_PROBE.value,
            "reason": "no eligible pinned public numerical fixture selected",
        },
        "claims": {
            "neural_training_measured": False,
            "physical_reference_measured": False,
            "candidate_inference_measured": False,
            "cfd_measured": False,
            "throughput_forecast": False,
            "scientific_qualification": False,
            "security_qualification": False,
        },
    }
    replay = _replay(config, source_revision)
    profiler = {
        "schema_version": "carbon.c-ep2.profiler-study-summary.v1",
        "source_revision": source_revision,
        "current_implemented_variant": "A_FRESH_PACK_PER_ADMITTED_JOB",
        "hypothetical_variant": "B_ZERO_FILL_WAIT_ALREADY_ADMITTED_ONLY",
        "observed": {
            "evidence_class": EvidenceLayer.OBSERVED_DEVELOPMENT_EXECUTION.value,
            "components": [
                "fixture receipt/admission and deduplication",
                "SQLite owner startup/open",
                "C-EP1 aggregate singleton lifecycle",
                "C-01 retry/restart/result state",
                "pack closure and summary replay",
            ],
        },
        "modeled": {
            "evidence_class": EvidenceLayer.COUNTERFACTUAL_MODEL.value,
            "components": [
                "already-admitted compatibility grouping",
                "normalized reference/candidate/control work",
                "last-member closure delay",
                "assumption-conditioned B overhead scenarios",
            ],
        },
        "upfront_qualification_burden": "UNKNOWN_AND_SEPARATE_FROM_RECURRING_WORK",
        "shareable_reference_fraction": None,
        "shareable_reference_fraction_reason": (
            "no authorized reconstruction/reference backend or observed physical reference phase"
        ),
        "missing_evidence": [
            "authorized C-02 reconstruction observations",
            "eligible C-04 reference-cost and witness observations",
            "C-07 integrated resource occupancy",
            "representative admitted compatible workload",
            "B membership/control/recovery overhead",
            "common-comparison and TRAIN/EVAL randomness policy",
        ],
        "scientific_and_protection_blockers": [
            "AT-09",
            "AT-16",
            "AT-19",
            "AT-22",
            "AT-30",
        ],
        "recommendation": "COLLECT MISSING INPUTS FIRST",
        "smallest_next_investment": (
            "run this observation protocol on an authorized C-02/C-04/C-07 path and declared hardware, plus a bounded representative admitted-workload trace, without implementing sharing"
        ),
        "variant_b_implementation_authorized": False,
        "qualification_created": False,
    }

    private_rows = []
    for record in recorder.records:
        value = asdict(record)
        value["evidence_layer"] = record.evidence_layer.value
        value["wall_elapsed_ns"] = record.wall_elapsed_ns
        private_rows.append(value)
    public_rows = [record.public_safe() for record in recorder.records]
    files = {
        "private_trace_v1.jsonl": "\n".join(
            json.dumps(value, sort_keys=True) for value in private_rows
        )
        + "\n",
        "public_safe_trace_v1.jsonl": "\n".join(
            json.dumps(value, sort_keys=True) for value in public_rows
        )
        + "\n",
        "variant_a_observations_v1.json": json.dumps(observed, indent=2, sort_keys=True)
        + "\n",
        "variant_b_replay_correction_v2.json": json.dumps(
            replay, indent=2, sort_keys=True
        )
        + "\n",
        "profiler_summary_v1.json": json.dumps(profiler, indent=2, sort_keys=True)
        + "\n",
        "environment_manifest_v1.json": json.dumps(
            {
                "schema_version": "carbon.c-ep2.environment-manifest.v1",
                "source_revision": source_revision,
                "environment": environment,
                "configuration_digest": digest(canonical(config)),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }
    for name, body in files.items():
        (output_dir / name).write_text(body, encoding="utf-8")
    if public_output_dir is not None:
        public_output_dir.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            if name != "private_trace_v1.jsonl":
                (public_output_dir / name).write_text(body, encoding="utf-8")
    return observed, replay, profiler


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--public-output-dir", type=Path)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--replay-correction-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.replay_correction_only:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        replay = _replay(config, args.source_revision)
        name = "variant_b_replay_correction_v2.json"
        body = json.dumps(replay, indent=2, sort_keys=True) + "\n"
        (args.output_dir / name).write_text(body, encoding="utf-8")
        if args.public_output_dir is not None:
            args.public_output_dir.mkdir(parents=True, exist_ok=True)
            (args.public_output_dir / name).write_text(body, encoding="utf-8")
        print(
            json.dumps(
                {
                    "source_revision": args.source_revision,
                    "output": str(args.output_dir / name),
                    "recommendation": "COLLECT MISSING INPUTS FIRST",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    observed, _replay_output, profiler = run_study(
        config,
        args.output_dir,
        args.source_revision,
        public_output_dir=args.public_output_dir,
    )
    print(
        json.dumps(
            {
                "source_revision": args.source_revision,
                "recommendation": profiler["recommendation"],
                "jobs": observed["work_reconciliation"],
                "output_dir": str(args.output_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
