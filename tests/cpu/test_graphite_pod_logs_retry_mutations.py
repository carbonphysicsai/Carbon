"""Mutation checks for the R2 run-4 fixes (GRAPHITE-POD-LOGS-RETRY-01).

The pattern of `test_graphite_phase3_mutations.py`: each case switches one
guard off with monkeypatch and runs the test that guards it. The guard passes
with the protection in place and must fail without it.
"""

from __future__ import annotations

import pytest
import test_graphite_pod_logs_retry as t

from carbon.agent_campaign.graphite import baseline_retry, pod_logs
from carbon.agent_campaign.graphite import experiment as ex

ASSERTION = (AssertionError, pytest.fail.Exception)


def _with_monkeypatch(test):
    """Run a guard test that itself takes `monkeypatch`."""

    def run(tmp):
        with pytest.MonkeyPatch.context() as patch:
            test(tmp, patch)

    return run


MUTATIONS = {
    # Fix 2: only a run that did not score keeps its logs.
    "logs_kept_for_unscored_runs_only": (
        lambda m: m.setattr(pod_logs, "kept_for", lambda status: True),
        t.test_a_scored_pods_logs_are_not_kept,
        ASSERTION,
    ),
    # A kept log matches the digest the pod listed.
    "log_matches_the_pods_listing": (
        lambda m: m.setattr(pod_logs, "digest_matches", lambda body, listed: True),
        t.test_a_log_that_does_not_match_the_pods_listing_is_a_digest_mismatch,
        ASSERTION,
    ),
    # A log naming protected material is withheld.
    "protected_log_withheld": (
        lambda m: m.setattr(pod_logs, "names_protected", lambda text: False),
        lambda tmp: t.test_a_log_naming_protected_material_is_withheld_with_its_digest(
            tmp, b"loading official_seed from the pack\n"
        ),
        ASSERTION,
    ),
    # Each kept log is bounded to its head and tail.
    "log_bounded_per_file": (
        lambda m: m.setattr(
            pod_logs, "_bounded", lambda body, allowance: (body, b"", 0)
        ),
        lambda tmp: (
            t.test_a_failed_pods_logs_are_kept_bounded_with_the_truncation_recorded(
                tmp, t.L0
            )
        ),
        ASSERTION,
    ),
    # The proposal's total allowance bounds its logs.
    "log_total_allowance": (
        lambda m: m.setattr(pod_logs, "allowance_left", lambda allowance: True),
        _with_monkeypatch(t.test_a_spent_allowance_withholds_the_log),
        ASSERTION,
    ),
    # A log too large to scan is never stored.
    "log_scanned_whole": (
        lambda m: m.setattr(pod_logs, "scannable", lambda body: True),
        _with_monkeypatch(t.test_a_log_too_large_to_scan_is_withheld),
        ASSERTION,
    ),
    # Fix 3: a candidate-attributed baseline is never retried.
    "no_retry_on_candidate_failure": (
        lambda m: m.setattr(baseline_retry, "retryable", lambda first, policy: True),
        t.test_no_retry_when_the_baseline_failed_as_the_candidate,
        ASSERTION,
    ),
    # Nor a launch the gate refused.
    "no_retry_on_a_launch_gate_refusal": (
        lambda m: m.setattr(baseline_retry, "retryable", lambda first, policy: True),
        t.test_no_retry_when_the_launch_gate_refused_the_baseline,
        ASSERTION,
    ),
    # The policy allows one retry.
    "one_retry_by_policy": (
        lambda m: m.setattr(baseline_retry, "retry_left", lambda used, policy: True),
        lambda tmp: (
            t.test_the_decision_is_a_pure_function_of_the_record_and_the_limits()
        ),
        ASSERTION,
    ),
    # The decision is made once: re-deciding conflicts with the recorded one.
    "decided_once": (
        lambda m: m.setattr(ex.Experiment, "baseline_retry", lambda self: None),
        t.test_no_second_retry,
        (*ASSERTION, ValueError),
    ),
    # The retry is held to the pod limit and the run's money cap.
    "retry_within_the_budget": (
        lambda m: m.setattr(ex.Experiment, "_retry_budget", lambda self, pods: None),
        lambda tmp: t.test_no_retry_when_the_budget_cannot_cover_it(
            tmp, lambda: {"max_pods": 2}, "not_retried:session_pod_limit_reached"
        ),
        ASSERTION,
    ),
    # And to the remaining elapsed time.
    "retry_within_the_time": (
        lambda m: m.setattr(ex.Experiment, "_fits_time", lambda self, pods: True),
        t.test_no_retry_when_its_pods_cannot_finish_in_the_remaining_time,
        ASSERTION,
    ),
    # A retry that scores is the session's baseline.
    "retried_baseline_is_the_sessions": (
        lambda m: m.setattr(ex.Experiment, "baseline_id", lambda self: "baseline"),
        t.test_a_baseline_failed_as_infrastructure_is_retried_once_and_becomes_the_baseline,
        ASSERTION,
    ),
    # A policy may not make a launch-gate refusal retryable.
    "policy_refuses_launch_gate_retries": (
        lambda m: m.setattr(baseline_retry, "NEVER_REASONS", frozenset()),
        lambda tmp: t.test_an_unsafe_registered_policy_is_refused(
            tmp, lambda d: d["retry_on_reasons"].append("launch_refused")
        ),
        ASSERTION,
    ),
    # The dry run's failure-path check fails when the retry is off.
    "dry_run_check_sees_the_retry": (
        lambda m: m.setattr(ex.Experiment, "_retry_baseline", lambda self: None),
        t.test_the_failure_path_check_is_ok_and_fails_when_a_fix_is_off,
        ASSERTION,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_guard_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard, failure = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the guard in place
    disable(monkeypatch)
    with pytest.raises(failure):
        guard(tmp_path / "mutated")
