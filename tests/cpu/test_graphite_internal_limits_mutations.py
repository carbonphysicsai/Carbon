"""Internal Graphite session-limits mutation checks (OWNER-GRAPHITE-MINER-01 §6).

The pattern of `test_graphite_mutations.py`: each case switches one
protection of the session-limits rule off with monkeypatch and runs the test
that guards it. The guard passes with the protection in place and must fail
without it.
"""

from __future__ import annotations

import pytest
import test_graphite_internal_limits as t6

from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite import provider as gp

_CAPS = phase3.Phase3Provider.caps


def _changed_compaction(block):
    block["compaction"].update(trigger_fraction=0.5)


MUTATIONS = {
    # A new session has no call cap: given the historical 150 it stops there,
    # not at its money cap.
    "v2_no_call_cap": (
        lambda m: m.setattr(
            gp.GraphiteProvider,
            "_loop_limits",
            lambda self, opened: {"max_provider_calls": 150},
        ),
        lambda tmp: t6.test_a_v2_constructor_session_runs_past_150_until_its_money_cap(
            tmp
        ),
    ),
    # The money cap binds a new session: without the token share as its
    # ledger ceiling the run goes on until the script runs out.
    "v2_money_cap_binds": (
        lambda m: m.setattr(
            phase3.Phase3Provider,
            "caps",
            lambda self, rule=None: {**_CAPS(self, rule), "provider_nanodollars": None},
        ),
        lambda tmp: t6.test_a_v2_constructor_session_runs_past_150_until_its_money_cap(
            tmp
        ),
    ),
    # The loop receives the count-free limits and compaction, never a cap.
    "v2_loop_limits_passed": (
        lambda m: m.setattr(gp.GraphiteProvider, "_loop_limits", lambda self, o: {}),
        lambda tmp: _loop_guard(tmp),
    ),
    # The new rule's record freezes the money cap and the elapsed limit.
    "v2_record_states_the_bounds": (
        lambda m: m.setattr(
            phase3.Phase3Provider,
            "session_limits_record",
            lambda self, task: {
                **gp.GraphiteProvider.session_limits_record(self, task),
                "money_cap_nanodollars": None,
            },
        ),
        lambda tmp: t6.test_a_new_session_freezes_the_v2_rule_with_its_money_and_time_bounds(
            tmp
        ),
    ),
    # A money stop still bundles the session's best improvement.
    "v2_money_stop_bundles": (
        lambda m: m.setattr(
            phase3.Phase3Provider,
            "_close_at_limit",
            lambda self, run_id, experiment: self._escalate_on_stall(
                run_id, experiment
            ),
        ),
        lambda tmp: t6.test_a_money_stop_still_bundles_the_best_improvement(tmp),
    ),
    # An operator's call-cap stop closes the session's work too.
    "v2_operator_cap_stop_bundles": (
        lambda m: m.setattr(
            phase3.Phase3Provider,
            "_close_at_limit",
            lambda self, run_id, experiment: None,
        ),
        lambda tmp: t6.test_an_operator_call_cap_still_narrows_a_v2_run(tmp),
    ),
    # A money stop still applies the stall rule's one-rung escalation.
    "v2_money_stop_escalates": (
        lambda m: m.setattr(
            phase3.Phase3Provider,
            "_escalate_on_stall",
            lambda self, run_id, experiment: None,
        ),
        lambda tmp: t6.test_a_stall_then_a_money_stop_escalates_one_rung(tmp),
    ),
    # Delivery runs no ablation pod that cannot finish within the elapsed
    # limit: without the time-bound view the ablation runs past it.
    "v2_ablation_pods_fit_the_time": (
        lambda m: m.setattr(
            phase3.Phase3Provider,
            "_delivery_view",
            lambda self, run_id, experiment: experiment,
        ),
        lambda tmp: t6.test_an_elapsed_stop_bundles_with_no_pod_past_the_limit(tmp),
    ),
    # A proposal whose pods cannot finish in time is refused before any pod.
    "v2_proposal_pods_fit_the_time": (
        lambda m: m.setattr(phase3.Phase3Tools, "_no_time", lambda self: None),
        lambda tmp: t6.test_a_first_proposal_needs_time_for_its_pod_and_the_baselines(
            tmp
        ),
    ),
    # A proposal after the baseline counts its own pod only, not the baseline's.
    "v2_late_proposal_refused": (
        lambda m: m.setattr(phase3.Phase3Tools, "_no_time", lambda self: None),
        lambda tmp: t6.test_a_late_proposal_is_refused_and_delivery_runs_no_late_ablation(
            tmp
        ),
    ),
    # An elapsed stop still applies the stall rule.
    "v2_elapsed_stop_escalates": (
        lambda m: m.setattr(
            phase3.Phase3Provider,
            "_close_at_limit",
            lambda self, run_id, experiment: None,
        ),
        lambda tmp: t6.test_an_elapsed_stop_still_applies_the_stall_rule(tmp),
    ),
    # The record names the engine tool the model is offered beyond its
    # manifest.
    "v2_engine_tools_recorded": (
        lambda m: m.setattr(gp, "ENGINE_TOOLS_V2", ()),
        lambda tmp: t6.test_a_new_session_freezes_the_v2_rule_with_its_money_and_time_bounds(
            tmp
        ),
    ),
    # A resumed record's rule must match the epoch plan it already wrote.
    "v2_started_plan_checked": (
        lambda m: m.setattr(
            gp.GraphiteProvider,
            "_check_started_plan",
            lambda self, run_id, opened: None,
        ),
        lambda tmp: t6.test_a_record_whose_rule_no_longer_matches_its_started_plan_is_refused(
            tmp, gp.SESSION_LIMITS_V2
        ),
    ),
    # Only the v2 rule closes a capped session; v1 is unchanged.
    "v1_cap_closes_nothing": (
        lambda m: m.setattr(phase3, "SESSION_LIMITS_V2", gp.SESSION_LIMITS_V1),
        lambda tmp: t6.test_a_v1_session_closes_nothing_at_a_cap_as_before(tmp),
    ),
    # A v1 record resumes under v1, byte-identically, whatever rule the
    # resuming provider opens new sessions under.
    "v1_records_keep_v1": (
        lambda m: m.setattr(
            gp.GraphiteProvider,
            "_loop_limits",
            lambda self, opened: {"limits": gp.LOOP_LIMITS},
        ),
        lambda tmp: t6.test_a_v1_plan_is_byte_identical_to_the_one_written_before_the_change(
            tmp
        ),
    ),
    # A v1 session's ledger keeps the historical cap; without it its record
    # would no longer match the one written before the change.
    "v1_caps_keep_the_historical_cap": (
        lambda m: m.setattr(phase3.Phase3Provider, "HISTORICAL_SESSION_TURNS", None),
        lambda tmp: t6.test_a_v1_plan_is_byte_identical_to_the_one_written_before_the_change(
            tmp
        ),
    ),
    # A resume under a changed rule is refused before any call.
    "v2_rule_verified_on_resume": (
        lambda m: m.setattr(
            gp.GraphiteProvider,
            "_expected_limits",
            lambda self, opened: {
                "grant": self._grant_record(),
                "caps": opened["caps"],
                "session_limits": opened.get("session_limits"),
            },
        ),
        lambda tmp: t6.test_a_resume_under_a_changed_rule_is_refused(
            tmp, _changed_compaction, "session_limits_changed"
        ),
    ),
    # A v2 record cannot be downgraded to v1 by dropping its block.
    "v2_record_not_downgraded": (
        lambda m: m.setattr(
            gp.GraphiteProvider,
            "_expected_limits",
            lambda self, opened: {
                "grant": self._grant_record(),
                "caps": opened["caps"],
                "session_limits": opened.get("session_limits"),
            },
        ),
        lambda tmp: t6.test_a_v2_constructor_record_cannot_be_turned_into_a_v1_one(tmp),
    ),
}


def _loop_guard(tmp):
    """The loop-arguments guard with its recorder installed for this run only
    (the guard's fixture is not injected outside pytest)."""
    with pytest.MonkeyPatch.context() as patch:
        recorder = t6.LoopRecorder(gp.run_epoch)
        patch.setattr(gp, "run_epoch", recorder)
        patch.setattr(phase3, "run_epoch", recorder)
        t6.test_the_loop_gets_count_free_limits_and_compaction_never_a_call_cap(
            tmp, recorder
        )


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(tmp_path / "mutated")
