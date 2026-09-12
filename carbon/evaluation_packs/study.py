"""Closed DEVELOPMENT measurement and detached counterfactual replay tools.

This module observes the existing Variant-A fixture lifecycle.  It does not
evaluate a Strategy, expose private evaluation material, or implement sharing.
"""

from __future__ import annotations

import math
import statistics
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from enum import Enum
from typing import TypeVar

_T = TypeVar("_T")
_TRACE_UNITS = frozenset({"nanoseconds", "operation_count", "unknown"})
_MODEL_UNIT = "normalized_work_units"


class StudyFailure(ValueError):
    """Stable local-study validation failure."""


class EvidenceLayer(str, Enum):
    OBSERVED_DEVELOPMENT_EXECUTION = "OBSERVED_DEVELOPMENT_EXECUTION"
    OBSERVED_PUBLIC_NUMERICAL_PROBE = "OBSERVED_PUBLIC_NUMERICAL_PROBE"
    COUNTERFACTUAL_MODEL = "COUNTERFACTUAL_MODEL"


class ReplayOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class Observation:
    schema_version: str
    run_id: str
    sequence: int
    association_ref: str | None
    attempt_number: int | None
    owner: str
    operation: str
    boundary: str
    clock: str
    start_ns: int | None
    end_ns: int | None
    process_elapsed_ns: int | None
    unit: str
    work_count: int | None
    outcome: str
    evidence_layer: EvidenceLayer
    source_revision: str
    missing_reason: str | None = None
    parent_sequence: int | None = None
    chargeable: bool = True
    durability: str = "COMPLETED_CALL_BOUNDARY"

    def __post_init__(self) -> None:
        if (
            self.schema_version != "carbon.c-ep2.observation.v1"
            or type(self.run_id) is not str
            or not self.run_id
            or type(self.sequence) is not int
            or self.sequence < 1
            or (
                self.association_ref is not None
                and (type(self.association_ref) is not str or not self.association_ref)
            )
            or (
                self.attempt_number is not None
                and (type(self.attempt_number) is not int or self.attempt_number < 1)
            )
            or any(
                type(value) is not str or not value
                for value in (
                    self.owner,
                    self.operation,
                    self.boundary,
                    self.clock,
                    self.outcome,
                    self.source_revision,
                    self.durability,
                )
            )
            or self.unit not in _TRACE_UNITS
            or type(self.evidence_layer) is not EvidenceLayer
            or type(self.chargeable) is not bool
            or (
                self.parent_sequence is not None
                and (
                    type(self.parent_sequence) is not int
                    or self.parent_sequence < 1
                    or self.parent_sequence >= self.sequence
                )
            )
        ):
            raise StudyFailure("invalid observation")
        missing = self.start_ns is None or self.end_ns is None
        if missing:
            if (
                self.start_ns is not None
                or self.end_ns is not None
                or self.process_elapsed_ns is not None
                or self.work_count is not None
                or type(self.missing_reason) is not str
                or not self.missing_reason
                or self.unit != "unknown"
                or self.chargeable
            ):
                raise StudyFailure("invalid missing observation")
            return
        if (
            type(self.start_ns) is not int
            or type(self.end_ns) is not int
            or self.start_ns < 0
            or self.end_ns < self.start_ns
            or type(self.process_elapsed_ns) is not int
            or self.process_elapsed_ns < 0
            or type(self.work_count) is not int
            or self.work_count < 0
            or self.missing_reason is not None
            or self.unit != "nanoseconds"
        ):
            raise StudyFailure("invalid observed span")

    @property
    def wall_elapsed_ns(self) -> int | None:
        if self.start_ns is None or self.end_ns is None:
            return None
        return self.end_ns - self.start_ns

    def public_safe(self) -> dict[str, object]:
        """Return a fixture-safe record without private association or clocks."""
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "sequence": self.sequence,
            "attempt_number": self.attempt_number,
            "owner": self.owner,
            "operation": self.operation,
            "boundary": self.boundary,
            "wall_elapsed_ns": self.wall_elapsed_ns,
            "process_elapsed_ns": self.process_elapsed_ns,
            "unit": self.unit,
            "work_count": self.work_count,
            "outcome": self.outcome,
            "evidence_layer": self.evidence_layer.value,
            "source_revision": self.source_revision,
            "missing_reason": self.missing_reason,
            "parent_sequence": self.parent_sequence,
            "chargeable": self.chargeable,
            "durability": self.durability,
        }


class DiagnosticTraceRecorder:
    """In-memory diagnostic recorder that cannot change lifecycle outcomes."""

    def __init__(
        self,
        *,
        run_id: str,
        source_revision: str,
        enabled: bool = True,
        sink: Callable[[Observation], None] | None = None,
        wall_clock: Callable[[], int] = time.perf_counter_ns,
        process_clock: Callable[[], int] = time.process_time_ns,
    ) -> None:
        if (
            type(run_id) is not str
            or not run_id
            or type(source_revision) is not str
            or not source_revision
            or type(enabled) is not bool
            or (sink is not None and not callable(sink))
            or not callable(wall_clock)
            or not callable(process_clock)
        ):
            raise StudyFailure("invalid recorder")
        self.run_id = run_id
        self.source_revision = source_revision
        self.enabled = enabled
        self._sink = sink
        self._wall_clock = wall_clock
        self._process_clock = process_clock
        self.records: list[Observation] = []
        self.sink_failures = 0

    @property
    def usable(self) -> bool:
        return self.sink_failures == 0

    def _retain(self, record: Observation) -> None:
        self.records.append(record)
        if self._sink is not None:
            try:
                self._sink(record)
            except Exception:  # noqa: BLE001 - diagnostic sink cannot alter science.
                self.sink_failures += 1

    def measure(
        self,
        function: Callable[[], _T],
        *,
        association_ref: str | None,
        attempt_number: int | None,
        owner: str,
        operation: str,
        boundary: str,
        outcome: str = "COMPLETED",
        parent_sequence: int | None = None,
        chargeable: bool = True,
        durability: str = "COMPLETED_CALL_BOUNDARY",
    ) -> _T:
        if not self.enabled:
            return function()
        start = self._wall_clock()
        process_start = self._process_clock()
        try:
            value = function()
        except BaseException:
            end = self._wall_clock()
            process_end = self._process_clock()
            self._retain(
                Observation(
                    "carbon.c-ep2.observation.v1",
                    self.run_id,
                    len(self.records) + 1,
                    association_ref,
                    attempt_number,
                    owner,
                    operation,
                    boundary,
                    "perf_counter_ns/process_time_ns",
                    start,
                    end,
                    process_end - process_start,
                    "nanoseconds",
                    1,
                    "RAISED",
                    EvidenceLayer.OBSERVED_DEVELOPMENT_EXECUTION,
                    self.source_revision,
                    parent_sequence=parent_sequence,
                    chargeable=chargeable,
                    durability=durability,
                )
            )
            raise
        end = self._wall_clock()
        process_end = self._process_clock()
        self._retain(
            Observation(
                "carbon.c-ep2.observation.v1",
                self.run_id,
                len(self.records) + 1,
                association_ref,
                attempt_number,
                owner,
                operation,
                boundary,
                "perf_counter_ns/process_time_ns",
                start,
                end,
                process_end - process_start,
                "nanoseconds",
                1,
                outcome,
                EvidenceLayer.OBSERVED_DEVELOPMENT_EXECUTION,
                self.source_revision,
                parent_sequence=parent_sequence,
                chargeable=chargeable,
                durability=durability,
            )
        )
        return value

    def missing(
        self,
        *,
        owner: str,
        operation: str,
        boundary: str,
        reason: str,
        evidence_layer: EvidenceLayer,
    ) -> None:
        if not self.enabled:
            return
        self._retain(
            Observation(
                "carbon.c-ep2.observation.v1",
                self.run_id,
                len(self.records) + 1,
                None,
                None,
                owner,
                operation,
                boundary,
                "UNAVAILABLE",
                None,
                None,
                None,
                "unknown",
                None,
                "NOT_IMPLEMENTED",
                evidence_layer,
                self.source_revision,
                missing_reason=reason,
                chargeable=False,
                durability="NOT_OBSERVED",
            )
        )


def _distribution(values: Iterable[int]) -> dict[str, int | None]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "minimum": None, "median": None, "maximum": None}
    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "median": int(statistics.median(ordered)),
        "maximum": ordered[-1],
    }


def summarize_observations(records: Iterable[Observation]) -> dict[str, object]:
    records = tuple(records)
    if any(type(record) is not Observation for record in records):
        raise StudyFailure("invalid trace")
    sequences = [record.sequence for record in records]
    if sequences != list(range(1, len(records) + 1)):
        raise StudyFailure("non-contiguous trace")
    operations: dict[str, dict[str, int | None]] = {}
    for operation in sorted({record.operation for record in records}):
        operations[operation] = _distribution(
            record.wall_elapsed_ns
            for record in records
            if record.operation == operation and record.wall_elapsed_ns is not None
        )
    roots = [
        record
        for record in records
        if record.chargeable and record.parent_sequence is None
    ]
    return {
        "schema_version": "carbon.c-ep2.observation-summary.v1",
        "evidence_layer": EvidenceLayer.OBSERVED_DEVELOPMENT_EXECUTION.value,
        "record_count": len(records),
        "missing_count": sum(record.wall_elapsed_ns is None for record in records),
        "chargeable_root_wall_ns": sum(record.wall_elapsed_ns or 0 for record in roots),
        "chargeable_root_process_ns": sum(
            record.process_elapsed_ns or 0 for record in roots
        ),
        "nested_or_precommit_records_charged": sum(
            record.chargeable and record.parent_sequence is not None
            for record in records
        ),
        "operations": operations,
    }


@dataclass(frozen=True, slots=True)
class ModelQuantity:
    value: int | None
    unit: str = _MODEL_UNIT
    evidence_layer: EvidenceLayer = EvidenceLayer.COUNTERFACTUAL_MODEL
    missing_reason: str | None = None

    def __post_init__(self) -> None:
        if (
            self.unit != _MODEL_UNIT
            or self.evidence_layer is not EvidenceLayer.COUNTERFACTUAL_MODEL
            or (
                self.value is not None
                and (type(self.value) is not int or self.value < 0)
            )
            or (
                self.value is None
                and (type(self.missing_reason) is not str or not self.missing_reason)
            )
            or (self.value is not None and self.missing_reason is not None)
        ):
            raise StudyFailure("invalid modeled quantity")


@dataclass(frozen=True, slots=True)
class ReplayJob:
    job_id: str
    challenge: str
    admitted_at: int
    compatibility_key: str | None
    candidate_work: ModelQuantity
    reference_work: ModelQuantity
    closure_work: ModelQuantity
    outcome: ReplayOutcome = ReplayOutcome.COMPLETED

    def __post_init__(self) -> None:
        if (
            type(self.job_id) is not str
            or not self.job_id
            or type(self.challenge) is not str
            or not self.challenge
            or type(self.admitted_at) is not int
            or self.admitted_at < 0
            or (
                self.compatibility_key is not None
                and (
                    type(self.compatibility_key) is not str
                    or not self.compatibility_key
                )
            )
            or any(
                type(value) is not ModelQuantity
                for value in (
                    self.candidate_work,
                    self.reference_work,
                    self.closure_work,
                )
            )
            or type(self.outcome) is not ReplayOutcome
        ):
            raise StudyFailure("invalid replay job")


def _known(value: ModelQuantity) -> int:
    if value.value is None:
        raise StudyFailure("unknown modeled work")
    return value.value


def _simulate(
    jobs: Iterable[ReplayJob],
    *,
    group_bound: int,
    group_overhead: ModelQuantity,
    sharing: bool,
) -> dict[str, object]:
    ordered = sorted(jobs, key=lambda item: (item.admitted_at, item.job_id))
    if (
        not ordered
        or len({job.job_id for job in ordered}) != len(ordered)
        or type(group_bound) is not int
        or group_bound < 1
        or type(group_overhead) is not ModelQuantity
    ):
        raise StudyFailure("invalid replay")
    for job in ordered:
        _known(job.candidate_work)
        _known(job.reference_work)
        _known(job.closure_work)
    pending = list(ordered)
    current = 0
    overhead_known = group_overhead.value is not None
    scenario_overhead = group_overhead.value if overhead_known else 0
    groups: list[dict[str, object]] = []
    completions: dict[str, dict[str, int | str | None]] = {}
    base_work = 0
    reference_attempts = 0
    while pending:
        current = max(current, pending[0].admitted_at)
        ready = [job for job in pending if job.admitted_at <= current]
        first = ready[0]
        group = [first]
        if sharing and first.compatibility_key is not None:
            group.extend(
                job
                for job in ready[1:]
                if job.challenge == first.challenge
                and job.compatibility_key == first.compatibility_key
                and len(group) < group_bound
            )
        for job in group:
            pending.remove(job)
        if sharing and len(group) > 1:
            reference_requirements = {
                (job.reference_work.value, job.reference_work.unit) for job in group
            }
            if len(reference_requirements) != 1:
                raise StudyFailure(
                    "shared group has inconsistent reference requirements"
                )
        dispatch_at = current
        reference_cost = _known(first.reference_work)
        if not sharing:
            reference_cost = sum(_known(job.reference_work) for job in group)
        reference_attempts += 1 if sharing else len(group)
        current += reference_cost
        reference_ready_at = current
        base_work += reference_cost
        member_finish: dict[str, int] = {}
        member_start: dict[str, int] = {}
        for job in group:
            work = _known(job.candidate_work)
            member_start[job.job_id] = current
            current += work
            base_work += work
            member_finish[job.job_id] = current
        last_member_finish = current
        closure_cost = sum(_known(job.closure_work) for job in group)
        current += closure_cost
        base_work += closure_cost
        current += scenario_overhead
        unresolved = any(job.outcome is ReplayOutcome.UNRESOLVED for job in group)
        scenario_group_close = None if unresolved else current
        group_close = scenario_group_close if overhead_known else None
        for job in group:
            summary_at = (
                group_close
                if group_close is not None and job.outcome is ReplayOutcome.COMPLETED
                else None
            )
            scenario_summary_at = (
                scenario_group_close
                if scenario_group_close is not None
                and job.outcome is ReplayOutcome.COMPLETED
                else None
            )
            completions[job.job_id] = {
                "outcome": job.outcome.value,
                "ordinary_queue_wait": (
                    dispatch_at - job.admitted_at if overhead_known else None
                ),
                "ordinary_queue_wait_scenario": dispatch_at - job.admitted_at,
                "intentional_fill_wait": 0,
                "reference_ready_at": reference_ready_at if overhead_known else None,
                "reference_ready_at_scenario": reference_ready_at,
                "candidate_started_at": (
                    member_start[job.job_id] if overhead_known else None
                ),
                "candidate_started_at_scenario": member_start[job.job_id],
                "candidate_execution_work": _known(job.candidate_work),
                "candidate_finished_at": (
                    member_finish[job.job_id] if overhead_known else None
                ),
                "candidate_finished_at_scenario": member_finish[job.job_id],
                "required_evidence_closure_work": _known(job.closure_work),
                "waiting_for_other_pack_members": (
                    last_member_finish - member_finish[job.job_id]
                    if overhead_known
                    else None
                ),
                "waiting_for_other_pack_members_scenario": (
                    last_member_finish - member_finish[job.job_id]
                ),
                "summary_at": summary_at,
                "summary_at_scenario": scenario_summary_at,
                "submission_to_summary": (
                    None if summary_at is None else summary_at - job.admitted_at
                ),
                "submission_to_summary_scenario": (
                    None
                    if scenario_summary_at is None
                    else scenario_summary_at - job.admitted_at
                ),
                "shared_pack_closure_delay": (
                    None
                    if summary_at is None
                    else summary_at - member_finish[job.job_id]
                ),
                "shared_pack_closure_delay_scenario": (
                    None
                    if scenario_summary_at is None
                    else scenario_summary_at - member_finish[job.job_id]
                ),
            }
        groups.append(
            {
                "dispatch_at": dispatch_at if overhead_known else None,
                "dispatch_at_scenario": dispatch_at,
                "members": [job.job_id for job in group],
                "group_size": len(group),
                "compatibility_key": first.compatibility_key,
                "closed_at": group_close,
                "closed_at_scenario": scenario_group_close,
            }
        )
    scenario_work = base_work + scenario_overhead * len(groups)
    scenario_completed = sum(
        value["summary_at_scenario"] is not None for value in completions.values()
    )
    return {
        "schema_version": "carbon.c-ep2.replay-result.v2",
        "evidence_layer": EvidenceLayer.COUNTERFACTUAL_MODEL.value,
        "policy": "B_HYPOTHETICAL" if sharing else "A_SINGLETON",
        "intentional_fill_wait": 0,
        "group_bound": group_bound,
        "groups": groups,
        "jobs": completions,
        "offered_distinct_jobs": len(ordered),
        "eligible_completions": scenario_completed if overhead_known else None,
        "eligible_completions_scenario": scenario_completed,
        "unfinished_or_nonpositive": (
            len(ordered) - scenario_completed if overhead_known else None
        ),
        "unfinished_or_nonpositive_scenario": len(ordered) - scenario_completed,
        "reference_attempts": reference_attempts if overhead_known else None,
        "reference_attempts_scenario": reference_attempts,
        "base_work_units_in_scenario": base_work,
        "group_overhead_units": group_overhead.value,
        "group_overhead_missing_reason": group_overhead.missing_reason,
        "scenario_overhead_units_applied": scenario_overhead,
        "scenario_kind": (
            "DECLARED_OVERHEAD_DYNAMIC_GROUPING"
            if overhead_known
            else "ZERO_OVERHEAD_COUNTERFACTUAL_DYNAMIC_GROUPING"
        ),
        "scenario_work_units": scenario_work,
        "total_work_units": scenario_work if overhead_known else None,
        "scenario_is_universal_bound": False,
        "groups_use_future_information": False,
        "one_validator": True,
    }


def simulate_variant_a(jobs: Iterable[ReplayJob]) -> dict[str, object]:
    return _simulate(
        jobs,
        group_bound=1,
        group_overhead=ModelQuantity(0),
        sharing=False,
    )


def simulate_variant_b(
    jobs: Iterable[ReplayJob],
    *,
    group_bound: int,
    group_overhead: ModelQuantity,
) -> dict[str, object]:
    return _simulate(
        jobs,
        group_bound=group_bound,
        group_overhead=group_overhead,
        sharing=True,
    )


def compare_variants(
    jobs: Iterable[ReplayJob],
    *,
    group_bound: int,
    group_overhead: ModelQuantity,
) -> dict[str, object]:
    jobs = tuple(jobs)
    variant_a = simulate_variant_a(jobs)
    variant_b = simulate_variant_b(
        jobs, group_bound=group_bound, group_overhead=group_overhead
    )
    a_work = variant_a["total_work_units"]
    b_base = variant_b["base_work_units_in_scenario"]
    if type(a_work) is not int or type(b_base) is not int:
        raise StudyFailure("invalid replay accounting")
    break_even_total_overhead = a_work - b_base
    b_work = variant_b["total_work_units"]
    conditioned_savings = a_work - b_work if type(b_work) is int else None
    return {
        "schema_version": "carbon.c-ep2.variant-comparison.v2",
        "evidence_layer": EvidenceLayer.COUNTERFACTUAL_MODEL.value,
        "variant_a": variant_a,
        "variant_b": variant_b,
        "assumption_conditioned_savings_units": conditioned_savings,
        "modeled_savings_positive_under_declared_assumptions": (
            type(conditioned_savings) is int and conditioned_savings > 0
        ),
        "fixed_membership_break_even_total_b_overhead_units": max(
            0, break_even_total_overhead
        ),
        "fixed_membership_break_even_assumption": (
            "membership fixed to this run's zero/declaration-overhead grouping; "
            "not a bound for endogenous regrouping"
        ),
        "empirical_savings_supported": False,
        "scientific_score_comparison_supported": False,
        "reference_sharing_implemented": False,
    }


def validate_finite_number(value: object) -> float:
    """Reject nonfinite or Boolean scenario inputs before replay accounting."""
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise StudyFailure("invalid finite number")
    return float(value)


def model_job_dict(job: ReplayJob) -> dict[str, object]:
    value = asdict(job)
    value["outcome"] = job.outcome.value
    for key in ("candidate_work", "reference_work", "closure_work"):
        value[key]["evidence_layer"] = EvidenceLayer.COUNTERFACTUAL_MODEL.value
    return value


__all__ = (
    "DiagnosticTraceRecorder",
    "EvidenceLayer",
    "ModelQuantity",
    "Observation",
    "ReplayJob",
    "ReplayOutcome",
    "StudyFailure",
    "compare_variants",
    "model_job_dict",
    "simulate_variant_a",
    "simulate_variant_b",
    "summarize_observations",
    "validate_finite_number",
)
