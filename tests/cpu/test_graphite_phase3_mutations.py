"""GRAPHITE-01 phase 3 mutation checks: disabling each protection fails its test.

The pattern of `test_graphite_mutations.py`: each case switches one phase-3
protection off with monkeypatch and runs the test that guards it. The guard
passes with the protection in place and must fail without it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import test_graphite_phase3 as t3
from graphite_phase3_fixtures import BASELINE, UNREBUILDABLE

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import miner_path, phase3, pod_phase
from carbon.agent_campaign.graphite.provider import GraphiteLedger

_ADMIT = ex.admit


def _lax_admit(strategy, seed, root=ex.REPOSITORY):
    """Admission that never refuses: anything unrebuildable becomes the baseline."""
    try:
        return _ADMIT(strategy, seed, root)
    except ex.Unrebuildable:
        return _ADMIT(BASELINE, seed, root)


def _settle_unknown_as_zero(self, pid, handle):
    charge = self.pods.charge(handle)
    self.ledger.append(
        "pod_settled",
        intent_id=handle.intent_id,
        proposal=pid,
        charge_usd=str(charge if charge is not None else 0),
        basis="mutated",
    )


MUTATIONS = {
    # A proposal Carbon cannot rebuild is refused and never run.
    "reconstruction_gate": (
        lambda m: m.setattr(ex, "admit", _lax_admit),
        lambda tmp: t3.test_an_unrebuildable_proposal_is_refused_recorded_and_never_run(
            tmp, UNREBUILDABLE, "contract_refused"
        ),
    ),
    # What the pod built is checked against what Carbon computed.
    "independent_rebuild_check": (
        lambda m: m.setattr(ex, "rebuild_differences", lambda expected, built: []),
        lambda tmp: t3.test_a_pod_build_that_differs_from_carbons_is_a_finding_and_never_scored(
            tmp
        ),
    ),
    # Tokens count against the same run cap as pods.
    "combined_token_and_pod_cap": (
        lambda m: m.setattr(
            phase3.Phase3Provider, "_tokens_usd", lambda self, run_id: Decimal(0)
        ),
        lambda tmp: t3.test_tokens_plus_pods_share_one_run_cap(tmp),
    ),
    # A model call is held to the same run cap as the pods.
    "model_calls_held_to_combined_cap": (
        lambda m: m.setattr(phase3.Phase3Ledger, "_reserve", GraphiteLedger._reserve),
        lambda tmp: t3.test_a_model_call_is_refused_when_pods_have_used_the_run_cap(
            tmp
        ),
    ),
    # Cancellation terminates the running pod.
    "terminate_on_cancel": (
        lambda m: m.setattr(ex.Experiment, "_terminate", lambda self, pid, h: False),
        lambda tmp: t3.test_cancellation_terminates_the_running_pod_and_stops_the_run(
            tmp
        ),
    ),
    # A resume after a process death terminates the pod it left.
    "reconcile_after_crash": (
        lambda m: m.setattr(ex.Experiment, "reconcile", lambda self: []),
        lambda tmp: t3.test_a_crash_leaves_no_pod_after_resume_and_never_pays_twice(
            tmp, "wait"
        ),
    ),
    # An unknown charge keeps the full reservation.
    "unknown_keeps_reservation": (
        lambda m: m.setattr(ex.Experiment, "_settle", _settle_unknown_as_zero),
        lambda tmp: t3.test_an_unknown_pod_charge_keeps_its_full_reservation(tmp),
    ),
    # Five non-improving attempts record the stall observation.
    "stall_limit": (
        lambda m: m.setattr(ex, "CONSTRUCTOR_STALL_ATTEMPTS", 6),
        lambda tmp: t3.test_five_non_improving_attempts_record_the_stall_and_escalate_one_rung(
            tmp
        ),
    ),
    # The recorded stall escalates the Constructor one rung.
    "stall_escalates": (
        lambda m: m.setattr(
            phase3.Phase3Provider,
            "_escalate_on_stall",
            lambda self, run_id, experiment: None,
        ),
        lambda tmp: t3.test_five_non_improving_attempts_record_the_stall_and_escalate_one_rung(
            tmp
        ),
    ),
    # A Constructor session gets its own 150-call cap (GRAPHITE-D26); without
    # it the session falls back to the shared 48.
    "constructor_session_turns": (
        lambda m: m.setattr(phase3, "CONSTRUCTOR_SESSION_TURNS", None),
        lambda tmp: t3.test_a_constructor_session_makes_up_to_150_model_calls(tmp),
    ),
    # The 150-call cap bounds the session; it does not run past it.
    "constructor_session_turns_bound": (
        lambda m: m.setattr(phase3, "CONSTRUCTOR_SESSION_TURNS", 151),
        lambda tmp: t3.test_a_constructor_session_makes_up_to_150_model_calls(tmp),
    ),
    # A turn with several tool calls runs the first and refuses the rest
    # (GRAPHITE-D33); without the rule it ends the run harness_error.
    "constructor_parallel_rule": (
        lambda m: m.setattr(phase3, "PARALLEL_RULES", {}),
        lambda tmp: t3.test_a_turn_with_several_tool_calls_runs_the_first_and_refuses_the_rest(
            tmp
        ),
    ),
    # The pod runs only the build Carbon pinned.
    "pod_runs_only_the_pinned_build": (
        lambda m: m.setattr(pod_phase, "pinned", lambda record, expected: True),
        lambda tmp: t3.test_the_pod_phase_runs_the_pinned_build_and_refuses_another(
            tmp
        ),
    ),
    # A phase-3 brief serves the battery development Challenge only.
    "battery_development_only": (
        lambda m: m.setattr(phase3, "check_observation", lambda observation: None),
        lambda tmp: t3.test_a_brief_for_other_or_protected_material_is_refused(tmp),
    ),
    # The miner path attaches to a battery development campaign only.
    "miner_path_battery_only": (
        lambda m: m.setattr(
            miner_path,
            "check_battery_development",
            lambda manifest: (manifest or {}).get("challenge"),
        ),
        lambda tmp: t3.test_the_miner_path_attaches_only_to_battery_development(),
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(tmp_path / "mutated")
