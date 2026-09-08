"""Offline-only executable pieces of the proposed B-E4 pilot contract.

Nothing in this module can contact a provider, approve the proposal, authorize
execution, or create gauntlet evidence.  It exists so interaction, deadline,
payload, and synthetic-task semantics can be tested before owner review.
"""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from carbon.toy.physics import (
    FixtureModelConfiguration,
    construct_fixture_model,
    evaluate_fixture_reference,
)

from .model import AgentProfile


class PilotContractError(ValueError):
    pass


class PilotPhase(str, Enum):
    READY_FOR_PROPOSAL = "READY_FOR_PROPOSAL"
    AWAITING_PRACTICE = "AWAITING_PRACTICE"
    READY_FOR_SELECTION = "READY_FOR_SELECTION"
    TERMINAL = "TERMINAL"


class PilotEvent(str, Enum):
    VALID_PROPOSAL = "VALID_PROPOSAL"
    INVALID_STRATEGY = "INVALID_STRATEGY"
    SCHEMA_INVALID_OR_MALFORMED_OUTPUT = "SCHEMA_INVALID_OR_MALFORMED_OUTPUT"
    REFUSAL = "REFUSAL"
    TRUNCATED_OR_OUTPUT_BUDGET_EXHAUSTED = "TRUNCATED_OR_OUTPUT_BUDGET_EXHAUSTED"
    EXPLICIT_AGENT_STOP = "EXPLICIT_AGENT_STOP"
    VERIFIED_EXTERNAL_PROVIDER_FAILURE = "VERIFIED_EXTERNAL_PROVIDER_FAILURE"
    AMBIGUOUS_TIMEOUT = "AMBIGUOUS_TIMEOUT"
    PRACTICE_SUCCESS = "PRACTICE_SUCCESS"
    PRACTICE_FAILURE = "PRACTICE_FAILURE"
    FINAL_SELECTION_OR_STOP = "FINAL_SELECTION_OR_STOP"
    RUN_OR_CAMPAIGN_BUDGET_EXHAUSTED = "RUN_OR_CAMPAIGN_BUDGET_EXHAUSTED"


@dataclass(frozen=True, slots=True)
class PilotInteractionState:
    profile: AgentProfile
    phase: PilotPhase
    proposal_attempts: int
    provider_requests: int
    provider_retries_for_current_call: int
    feedback_results: int
    admissible_ancestor_ids: tuple[str, ...]
    pending_candidate_id: str | None
    selected_ancestor_id: str | None
    termination_reason: str | None
    unknown_billing_reservation: bool

    @property
    def maximum_proposal_attempts(self) -> int:
        return 1 if self.profile is AgentProfile.MINIMALIST else 4


def initial_pilot_interaction(profile: AgentProfile) -> PilotInteractionState:
    if type(profile) is not AgentProfile:
        raise TypeError("pilot state requires an exact profile")
    return PilotInteractionState(
        profile,
        PilotPhase.READY_FOR_PROPOSAL,
        0,
        0,
        0,
        0,
        (),
        None,
        None,
        None,
        False,
    )


def _terminal(
    state: PilotInteractionState,
    reason: str,
    *,
    proposal_delta: int = 0,
    request_delta: int = 0,
    unknown_billing: bool = False,
    selected: str | None = None,
) -> PilotInteractionState:
    return PilotInteractionState(
        state.profile,
        PilotPhase.TERMINAL,
        state.proposal_attempts + proposal_delta,
        state.provider_requests + request_delta,
        state.provider_retries_for_current_call,
        state.feedback_results,
        state.admissible_ancestor_ids,
        None,
        selected,
        reason,
        unknown_billing,
    )


def advance_pilot_interaction(
    state: PilotInteractionState,
    event: PilotEvent,
    *,
    candidate_id: str | None = None,
) -> PilotInteractionState:
    """Apply one v2 transition and its exact research/provider counters."""

    if type(state) is not PilotInteractionState or type(event) is not PilotEvent:
        raise TypeError("pilot transitions require exact closed values")
    if state.phase is PilotPhase.TERMINAL:
        raise PilotContractError("terminal pilot state cannot transition")
    if event is PilotEvent.RUN_OR_CAMPAIGN_BUDGET_EXHAUSTED:
        return _terminal(state, event.value)
    if event is PilotEvent.EXPLICIT_AGENT_STOP:
        if state.phase is not PilotPhase.READY_FOR_PROPOSAL:
            raise PilotContractError("agent stop is only a proposal-call response")
        return _terminal(state, event.value, request_delta=1)
    if event is PilotEvent.VERIFIED_EXTERNAL_PROVIDER_FAILURE:
        if state.phase not in (
            PilotPhase.READY_FOR_PROPOSAL,
            PilotPhase.READY_FOR_SELECTION,
        ):
            raise PilotContractError("provider retry cannot replace practice")
        if state.provider_retries_for_current_call >= 1:
            return _terminal(
                state, "VERIFIED_PROVIDER_FAILURE_RETRY_EXHAUSTED", request_delta=1
            )
        return PilotInteractionState(
            state.profile,
            state.phase,
            state.proposal_attempts,
            state.provider_requests + 1,
            1,
            state.feedback_results,
            state.admissible_ancestor_ids,
            state.pending_candidate_id,
            state.selected_ancestor_id,
            None,
            False,
        )
    if event is PilotEvent.AMBIGUOUS_TIMEOUT:
        if state.phase not in (
            PilotPhase.READY_FOR_PROPOSAL,
            PilotPhase.READY_FOR_SELECTION,
        ):
            raise PilotContractError("ambiguous timeout has no dispatched call")
        proposal_delta = int(state.phase is PilotPhase.READY_FOR_PROPOSAL)
        return _terminal(
            state,
            event.value,
            proposal_delta=proposal_delta,
            request_delta=1,
            unknown_billing=True,
        )
    if event in (
        PilotEvent.INVALID_STRATEGY,
        PilotEvent.SCHEMA_INVALID_OR_MALFORMED_OUTPUT,
        PilotEvent.REFUSAL,
        PilotEvent.TRUNCATED_OR_OUTPUT_BUDGET_EXHAUSTED,
    ):
        if state.phase is not PilotPhase.READY_FOR_PROPOSAL:
            raise PilotContractError("invalid output requires a proposal call")
        attempts = state.proposal_attempts + 1
        if attempts >= state.maximum_proposal_attempts:
            if state.profile is AgentProfile.MINIMALIST:
                return _terminal(state, event.value, proposal_delta=1, request_delta=1)
            phase = PilotPhase.READY_FOR_SELECTION
        else:
            phase = PilotPhase.READY_FOR_PROPOSAL
        return PilotInteractionState(
            state.profile,
            phase,
            attempts,
            state.provider_requests + 1,
            0,
            state.feedback_results,
            state.admissible_ancestor_ids,
            None,
            None,
            None,
            False,
        )
    if event is PilotEvent.VALID_PROPOSAL:
        if (
            state.phase is not PilotPhase.READY_FOR_PROPOSAL
            or type(candidate_id) is not str
            or not candidate_id
            or state.proposal_attempts >= state.maximum_proposal_attempts
        ):
            raise PilotContractError("valid proposal is not admissible in this state")
        return PilotInteractionState(
            state.profile,
            PilotPhase.AWAITING_PRACTICE,
            state.proposal_attempts + 1,
            state.provider_requests + 1,
            0,
            state.feedback_results,
            state.admissible_ancestor_ids,
            candidate_id,
            None,
            None,
            False,
        )
    if event in (PilotEvent.PRACTICE_SUCCESS, PilotEvent.PRACTICE_FAILURE):
        if state.phase is not PilotPhase.AWAITING_PRACTICE:
            raise PilotContractError("practice result has no pending proposal")
        ancestors = state.admissible_ancestor_ids
        if event is PilotEvent.PRACTICE_SUCCESS:
            assert state.pending_candidate_id is not None
            ancestors = (*ancestors, state.pending_candidate_id)
        feedback = state.feedback_results + 1
        if state.profile is AgentProfile.MINIMALIST:
            return _terminal(
                PilotInteractionState(
                    state.profile,
                    state.phase,
                    state.proposal_attempts,
                    state.provider_requests,
                    0,
                    feedback,
                    ancestors,
                    state.pending_candidate_id,
                    None,
                    None,
                    False,
                ),
                "MINIMALIST_ONE_ATTEMPT_COMPLETE",
                selected=(ancestors[0] if ancestors else None),
            )
        next_phase = (
            PilotPhase.READY_FOR_SELECTION
            if state.proposal_attempts >= 4
            else PilotPhase.READY_FOR_PROPOSAL
        )
        return PilotInteractionState(
            state.profile,
            next_phase,
            state.proposal_attempts,
            state.provider_requests,
            0,
            feedback,
            ancestors,
            None,
            None,
            None,
            False,
        )
    if event is PilotEvent.FINAL_SELECTION_OR_STOP:
        if (
            state.profile is AgentProfile.MINIMALIST
            or state.phase is not PilotPhase.READY_FOR_SELECTION
            or (
                candidate_id is not None
                and candidate_id not in state.admissible_ancestor_ids
            )
        ):
            raise PilotContractError(
                "selection may only choose an existing admissible ancestor or stop"
            )
        return _terminal(
            state,
            "FINAL_SELECTION" if candidate_id is not None else "FINAL_STOP",
            request_delta=1,
            selected=candidate_id,
        )
    raise PilotContractError("unsupported pilot transition")


def bounded_provider_deadline_seconds(
    *,
    requested_call_seconds: float,
    remaining_run_seconds: float,
    remaining_stage_seconds: float,
    remaining_campaign_seconds: float,
) -> float:
    """Return one nested deadline without granting a retry fresh time."""

    values = (
        requested_call_seconds,
        remaining_run_seconds,
        remaining_stage_seconds,
        remaining_campaign_seconds,
    )
    if any(type(value) is not float or value <= 0.0 for value in values):
        raise PilotContractError("no provider call fits the remaining deadlines")
    return float(min(values))


_PAYLOAD_FIELDS = frozenset(
    {
        "frozen_system_and_profile_policy",
        "agent_visible_synthetic_task_description",
        "current_arm_permitted_prior_material",
        "current_run_permitted_practice_feedback",
        "public_resource_facts",
        "current_run_existing_candidate_ids",
    }
)
_FORBIDDEN_CANARIES = frozenset(
    {
        "evaluator_seed",
        "hidden_case",
        "private_reference",
        "shadow_data",
        "scorer_internal",
        "credential",
        "other_arm_transcript",
        "other_run_transcript",
    }
)
_NORMALIZED_FORBIDDEN_CANARIES = frozenset(
    "".join(character for character in item if character.isalnum())
    for item in _FORBIDDEN_CANARIES
)


def build_offline_provider_payload(values: Mapping[str, object]) -> dict[str, object]:
    """Construct the exact allow-listed payload; this performs no disclosure."""

    if type(values) is not dict or set(values) != _PAYLOAD_FIELDS:
        raise PilotContractError("provider payload is not the exact allow-listed shape")

    def inspect(value: object) -> None:
        if type(value) is str:
            normalized = "".join(
                character for character in value.lower() if character.isalnum()
            )
            if any(canary in normalized for canary in _NORMALIZED_FORBIDDEN_CANARIES):
                raise PilotContractError("provider payload contains a forbidden canary")
            return
        if type(value) in (int, float, bool, type(None)):
            return
        if type(value) in (tuple, list):
            for item in value:
                inspect(item)
            return
        if type(value) is dict:
            for key, item in value.items():
                inspect(key)
                inspect(item)
            return
        raise PilotContractError("provider payload contains an unsupported value")

    for item in values.values():
        inspect(item)
    return dict(values)


@dataclass(frozen=True, slots=True)
class SyntheticPilotTaskCell:
    cell_id: str
    resource_regime: str
    noise_id: str
    noise_amplitude: int
    transfer_id: str
    transfer_x: tuple[int, int]
    target_degree: int
    training_x: tuple[int, ...]
    candidate_fixture_units: int


@dataclass(frozen=True, slots=True)
class SyntheticPilotTaskRealization:
    cell: SyntheticPilotTaskCell
    seed_digest: str
    training_observations: tuple[tuple[int, int], ...]
    heldout_observations: tuple[tuple[int, int], ...]
    transfer_observations: tuple[tuple[int, int], ...]


def proposed_synthetic_task_cells() -> tuple[SyntheticPilotTaskCell, ...]:
    """Return the twelve concrete, arm-neutral v2 fixture recipes."""

    resources = (
        ("DATA_SCARCE", (1, 2), 11),
        ("BALANCED", (1, 2, 3, 4), 17),
        ("COMPUTE_SCARCE", (1, 2, 3, 4), 29),
    )
    noises = (("LOW_NOISE", 1), ("HIGH_NOISE", 4))
    transfers = (("NEAR_TRANSFER", (5, 6)), ("FAR_TRANSFER", (9, 12)))
    cells = []
    for ordinal, (resource, noise, transfer) in enumerate(
        itertools.product(resources, noises, transfers)
    ):
        resource_id, training_x, units = resource
        noise_id, amplitude = noise
        transfer_id, transfer_x = transfer
        target_degree = 1 + ordinal % 2
        cells.append(
            SyntheticPilotTaskCell(
                f"be4-pilot-v2-{ordinal:02d}",
                resource_id,
                noise_id,
                amplitude,
                transfer_id,
                transfer_x,
                target_degree,
                training_x,
                units,
            )
        )
    return tuple(cells)


def realize_synthetic_task(
    cell: SyntheticPilotTaskCell, *, evaluator_seed: bytes
) -> SyntheticPilotTaskRealization:
    """Evaluator-only deterministic recipe used by offline inclusion checks."""

    if type(cell) is not SyntheticPilotTaskCell or type(evaluator_seed) is not bytes:
        raise TypeError("task realization requires exact fixture values")
    if not evaluator_seed:
        raise PilotContractError("task seed must not be empty")
    digest = hashlib.sha256(
        b"carbon.be4.pilot-task-realization.v2\x00"
        + cell.cell_id.encode("ascii")
        + b"\x00"
        + evaluator_seed
    ).digest()
    training = tuple(
        (
            x,
            x**cell.target_degree
            + cell.noise_amplitude * (1 if digest[index] & 1 else -1),
        )
        for index, x in enumerate(cell.training_x)
    )
    heldout = tuple((x, x**cell.target_degree) for x in (3, 4))
    transfer = tuple((x, x**cell.target_degree) for x in cell.transfer_x)
    return SyntheticPilotTaskRealization(
        cell,
        "sha256:" + hashlib.sha256(evaluator_seed).hexdigest(),
        training,
        heldout,
        transfer,
    )


@dataclass(frozen=True, slots=True)
class SyntheticInclusionAudit:
    cell_count: int
    generation_attempts: int
    candidate_checks: int
    fixture_units: int
    unique_endpoint_counts: tuple[int, ...]
    all_candidates_reconstructed: bool
    all_families_causally_active: bool
    endpoint_ranges_nonzero: bool
    no_single_candidate_dominates_all_cells: bool
    arm_neutral_baselines_checked: bool
    within_cell_saturation_recorded: bool
    qualifying_execution_ready: bool = False


def run_offline_synthetic_inclusion_audit(
    *, evaluator_seed: bytes
) -> SyntheticInclusionAudit:
    """Bounded 12x8 structural check; never selects on a prior-arm outcome."""

    cells = proposed_synthetic_task_cells()
    configurations = tuple(
        FixtureModelConfiguration(*values)
        for values in itertools.product((1, 2), repeat=3)
    )
    best_by_cell: list[set[FixtureModelConfiguration]] = []
    family_active = [False, False, False]
    endpoint_ranges = []
    unique_endpoint_counts = []
    candidate_counts = []
    reconstructed = True
    for cell in cells:
        realized = realize_synthetic_task(cell, evaluator_seed=evaluator_seed)
        results: dict[FixtureModelConfiguration, tuple[str, float, float]] = {}
        for configuration in configurations:
            try:
                coefficient, identity = construct_fixture_model(
                    realized.training_observations,
                    configuration.sampling_level,
                    hashlib.sha256(
                        evaluator_seed + cell.cell_id.encode("ascii")
                    ).digest(),
                    curriculum_emphasis=configuration.curriculum_emphasis,
                    feature_degree=configuration.feature_degree,
                )
                heldout = evaluate_fixture_reference(
                    coefficient,
                    realized.heldout_observations,
                    feature_degree=configuration.feature_degree,
                )
                transfer = evaluate_fixture_reference(
                    coefficient,
                    realized.transfer_observations,
                    feature_degree=configuration.feature_degree,
                )
            except ArithmeticError:
                reconstructed = False
                continue
            results[configuration] = (identity, heldout, transfer)
        unique_count = len({(value[1], value[2]) for value in results.values()})
        unique_endpoint_counts.append(unique_count)
        endpoint_ranges.append(unique_count > 1)
        candidate_counts.append(len(results))
        for family_index in range(3):
            for left in configurations:
                right_values = [
                    left.sampling_level,
                    left.curriculum_emphasis,
                    left.feature_degree,
                ]
                right_values[family_index] = 3 - right_values[family_index]
                right = FixtureModelConfiguration(*right_values)
                if (
                    left in results
                    and right in results
                    and results[left] != results[right]
                ):
                    family_active[family_index] = True
                    break
        minimum = min(value[1] + value[2] for value in results.values())
        best_by_cell.append(
            {
                config
                for config, value in results.items()
                if value[1] + value[2] == minimum
            }
        )
    common_best = set(configurations)
    for winners in best_by_cell:
        common_best &= winners
    baseline_configurations = {
        FixtureModelConfiguration(1, 1, 1),
        FixtureModelConfiguration(2, 1, 1),
        FixtureModelConfiguration(1, 2, 1),
        FixtureModelConfiguration(1, 1, 2),
    }
    fixture_units = sum(
        cell.candidate_fixture_units * len(configurations) for cell in cells
    )
    return SyntheticInclusionAudit(
        len(cells),
        len(cells),
        len(cells) * len(configurations),
        fixture_units,
        tuple(unique_endpoint_counts),
        reconstructed
        and all(count == len(configurations) for count in candidate_counts),
        all(family_active),
        all(endpoint_ranges),
        not common_best,
        baseline_configurations <= set(configurations),
        len(unique_endpoint_counts) == len(cells)
        and all(1 < count <= len(configurations) for count in unique_endpoint_counts),
    )


__all__ = (
    "PilotContractError",
    "PilotEvent",
    "PilotInteractionState",
    "PilotPhase",
    "SyntheticInclusionAudit",
    "SyntheticPilotTaskCell",
    "SyntheticPilotTaskRealization",
    "advance_pilot_interaction",
    "bounded_provider_deadline_seconds",
    "build_offline_provider_payload",
    "initial_pilot_interaction",
    "proposed_synthetic_task_cells",
    "realize_synthetic_task",
    "run_offline_synthetic_inclusion_audit",
)
