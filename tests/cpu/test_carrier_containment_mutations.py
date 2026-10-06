"""Mutation checks for the carrier containment check
(GRAPHITE-CARRIER-CONTAINMENT-01).

The pattern of `test_graphite_phase3_mutations.py`: each case switches one
guard off with monkeypatch and runs the test that guards it. The guard passes
with the protection in place and must fail without it.
"""

from __future__ import annotations

import pytest
import test_carrier_containment as t

from carbon.development_session import containment_check as cc

ASSERTION = (AssertionError, pytest.fail.Exception)


def _with_monkeypatch(test):
    """Run a guard test that itself takes `monkeypatch`."""

    def run(tmp):
        with pytest.MonkeyPatch.context() as patch:
            test(tmp, patch)

    return run


MUTATIONS = {
    # A canary that was read is treated as contained.
    "canary_read_treated_as_pass": (
        lambda m: m.setattr(cc, "_denied_or_absent", lambda observation: True),
        t.test_a_canary_read_fails_its_probe,
        ASSERTION,
    ),
    # The host's own PID 1 is accepted as the container's init.
    "host_proc1_comm_accepted": (
        lambda m: m.setattr(
            cc,
            "_own_init",
            lambda container, host: type(container) is str and bool(container),
        ),
        t.test_the_hosts_own_init_fails_its_probe,
        ASSERTION,
    ),
    # A network attempt that succeeded is accepted.
    "network_success_accepted": (
        lambda m: m.setattr(cc, "_failed", lambda observation: True),
        t.test_a_network_success_fails_its_probe,
        ASSERTION,
    ),
    # The canary is left on the host (and reported removed).
    "no_cleanup": (
        lambda m: m.setattr(cc, "remove_canary", lambda directory: True),
        _with_monkeypatch(t.test_the_canary_is_removed_even_when_the_run_fails),
        ASSERTION,
    ),
    # The same, on an interrupted check.
    "no_cleanup_on_interrupt": (
        lambda m: m.setattr(cc, "remove_canary", lambda directory: True),
        _with_monkeypatch(t.test_the_canary_is_removed_when_the_check_is_interrupted),
        ASSERTION,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_guard_fails_without_its_protection(tmp_path, monkeypatch, name):
    mutate, guard, expected = MUTATIONS[name]
    mutate(monkeypatch)
    with pytest.raises(expected):
        guard(tmp_path)


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_guard_passes_with_its_protection(tmp_path, name):
    _, guard, _ = MUTATIONS[name]
    guard(tmp_path)
