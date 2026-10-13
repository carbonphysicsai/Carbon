"""Graphite's pod backend waits in full under a slewed wall clock (the operator
layer's ambiguous-create reconcile gap; Data Collection, 2026-10-13)."""

from __future__ import annotations

import time

from carbon.agent_campaign.graphite import pods


def test_a_wait_that_wakes_early_is_topped_up_until_the_clock_agrees():
    now = {"t": 100.0}
    calls = []

    def clock():
        return now["t"]

    def sleep(seconds):
        calls.append(seconds)
        # The first wake comes 5 ms short of the requested time (a slewed clock).
        now["t"] += seconds - (0.005 if len(calls) == 1 else 0)

    pods.full_wait(clock, sleep)(30)
    assert now["t"] >= 130.0
    assert calls[0] == 30 and len(calls) == 2 and calls[1] >= 0.005


def test_the_top_ups_are_bounded():
    calls = []
    pods.full_wait(lambda: 0.0, calls.append, rounds=3)(5)  # a clock that never moves
    assert len(calls) == 1 + 3


def test_only_the_real_sleep_and_clock_are_wrapped():
    assert pods._wall_sleep(time.time, time.sleep) is not time.sleep
    fake = lambda _seconds: None
    assert pods._wall_sleep(time.time, fake) is fake
    assert pods._wall_sleep(lambda: 0.0, time.sleep) is time.sleep
