"""Mutation checks for the GPU probe and pod-attribution-v2 (GRAPHITE-POD-GPU-PROBE-01).

The pattern of `test_graphite_pod_logs_retry_mutations.py`: each case
switches one guard off with monkeypatch and runs the test that guards it. The
guard passes with the protection in place and must fail without it. One case
per Test Lead condition and per Carbon Validator constraint.
"""

from __future__ import annotations

import pytest
import test_graphite_pod_gpu_probe as t

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import pod_logs, pod_outcome, pod_phase, pods
from carbon.agent_campaign.graphite.protected_material import PROTECTED_MARKERS

ASSERTION = (AssertionError, pytest.fail.Exception)


def _with_monkeypatch(test):
    def run(tmp):
        with pytest.MonkeyPatch.context() as patch:
            test(tmp, patch)

    return run


def _monkeypatch_only(test):
    def run(_tmp):
        with pytest.MonkeyPatch.context() as patch:
            test(patch)

    return run


def _probe_after_program(m):
    """The probe reports success first and runs only after the program."""
    real_probe, real_python = pod_phase.probe_environment, pod_phase._python
    deferred = []

    def late_probe(code=None):
        deferred.append(code)
        return {
            "schema": pod_phase.PROBE_SCHEMA,
            "before_program": True,
            "exit": 0,
            "seconds": 0.0,
            "ok": True,
        }

    def python_then_probe(code, args, **kwargs):
        result = real_python(code, args, **kwargs)
        while deferred:
            real_probe(deferred.pop())
        return result

    m.setattr(pod_phase, "probe_environment", late_probe)
    m.setattr(pod_phase, "_python", python_then_probe)


def _load_ignores_version(m):
    real = pod_outcome.load_policy
    m.setattr(
        pod_outcome,
        "load_policy",
        lambda version=None, directory=None: real(None, directory),
    )


def _leaky_classes(m):
    m.setattr(
        pod_logs,
        "withheld_classes",
        lambda text: sorted(x for x in PROTECTED_MARKERS if x in text.lower()),
    )


def _environment_blamed_policy(tmp):
    t.test_a_v2_policy_cannot_blame_the_environment_or_loop(
        tmp,
        ("admissible", "environment"),
        ["CANDIDATE_FAILED", "environment"],
    )


MUTATIONS = {
    # Test Lead 1: the probe runs before any candidate code.
    "probe_runs_after_the_program": (
        _probe_after_program,
        _with_monkeypatch(t.test_the_probe_runs_before_any_candidate_code),
    ),
    # Test Lead 1: the candidate cannot write the environment claim (pod
    # side: the phase rewrites its claim and report after the program).
    "candidate_writes_the_environment_claim": (
        lambda m: m.setattr(pod_phase, "_ended", lambda *a, **k: None),
        _with_monkeypatch(t.test_a_candidate_cannot_write_the_environment_claim),
    ),
    # Test Lead 1 / Validator 3: an environment claim from a pod whose
    # program started is never accepted (host side).
    "environment_claim_accepted_whatever_the_export": (
        lambda m: m.setattr(pod_outcome, "environment_consistent", lambda e: True),
        t.test_an_inconsistent_environment_claim_is_a_signal_never_a_free_retry,
    ),
    # Test Lead 1: the environment stage is never typed as the candidate's.
    "environment_typed_as_the_candidates": (
        lambda m: m.setattr(pod_outcome, "never_the_candidates", lambda o: True),
        _environment_blamed_policy,
    ),
    # Test Lead 3 / Validator 5: one counter for every infrastructure retry.
    "no_relaunch_cap": (
        lambda m: m.setattr(pod_outcome, "retry_left", lambda a, p: True),
        t.test_the_retry_counter_never_resets_between_timeouts_and_relaunches,
    ),
    # Test Lead 3: the attempt loop is bounded whatever a verdict asks.
    "no_attempt_bound": (
        lambda m: m.setattr(ex, "pod_attempts", lambda policy: 10),
        _with_monkeypatch(t.test_the_attempt_loop_is_bounded_whatever_the_policy_asks),
    ),
    # Test Lead 3 / Validator 5: a second environment failure stops it.
    "repeated_environment_does_not_stop": (
        lambda m: m.setattr(ex.Experiment, "_stop_session", lambda *a: None),
        t.test_a_second_environment_failure_stops_the_session_failed_infra,
    ),
    # Test Lead 3: the baseline does not use both the relaunch and the retry.
    "baseline_uses_relaunch_and_retry": (
        lambda m: m.setattr(ex.Experiment, "relaunched", lambda self, pid: False),
        t.test_a_baseline_environment_failure_does_not_also_use_the_baseline_retry,
    ),
    # Test Lead 4: a withheld log never carries the marker text.
    "marker_text_leaks": (
        _leaky_classes,
        t.test_a_withheld_log_names_the_marker_class_never_the_marker,
    ),
    # Validator 1: v1 stays registered and replays unchanged.
    "v1_replayed_under_v2": (
        _load_ignores_version,
        lambda tmp: t.test_v1_typed_evidence_replays_unchanged(),
    ),
    # Validator 2: admissible only where Carbon writes the claim.
    "environment_trusted_at_every_level": (
        lambda m: m.setattr(pod_outcome, "trusted_writer", lambda level, p: True),
        t.test_a_level4_environment_claim_is_evidence_only_and_never_relaunched,
    ),
    # Validator 4: host timing outranks the claim.
    "host_timing_ignored": (
        lambda m: m.setattr(
            pod_outcome, "host_ran_full_allowance", lambda timing, work: False
        ),
        t.test_an_environment_claim_the_host_contradicts_is_a_signal,
    ),
    # Validator 6: the probe's result goes into the supervisor report...
    "no_supervisor_report": (
        lambda m: m.setattr(pod_phase, "_report", lambda *a, **k: None),
        _with_monkeypatch(t.test_the_probe_runs_before_any_candidate_code),
    ),
    # ...which a separated image makes admissible at Levels 4-5.
    "separated_report_ignored": (
        lambda m: m.setattr(pod_outcome, "admissible_stage", lambda r, i: None),
        _monkeypatch_only(
            t.test_a_separated_images_probe_report_is_admissible_at_level4
        ),
    ),
    # Validator 7 / Test Lead 2: every create sends the derived versions.
    "no_allowed_cuda_versions": (
        lambda m: m.setattr(pods, "allowed_cuda_versions", lambda repository=None: ()),
        t.test_the_real_path_sends_the_derived_cuda_versions,
    ),
    # Test Lead 5: the Attacker's pod-attribution attacks hold only while the
    # boundary checks the export.
    "attacker_probe_boundary_trusts_the_claim": (
        lambda m: m.setattr(pod_outcome, "environment_consistent", lambda e: True),
        lambda tmp: t.test_the_attacker_probe_holds_and_its_specimen_fires(),
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_guard_fails_its_test(name, tmp_path, monkeypatch):
    mutate, guard = MUTATIONS[name]
    # The guard passes with the protection in place...
    guard(tmp_path / "intact")
    # ...and fails without it.
    mutate(monkeypatch)
    with pytest.raises(ASSERTION):
        guard(tmp_path / "mutated")
