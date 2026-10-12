"""Pod jobs under the standing weekly test grant (CLOUD-FIRST-COMPUTE-01 item 2):
the USD 50 per-run cap, the USD 300 rolling week less the held CONFIRM-02 reserve,
and every run in the weekly summary. No pod, no provider, no spend."""

from __future__ import annotations

from decimal import Decimal

import pytest

from carbon.agent_campaign import grant_runs as gr

DAY = 24 * 3600


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv(gr.ENV, str(tmp_path / "grant-runs"))
    clock = {"now": 1_800_000_000.0}
    return lambda: clock["now"], clock


def refused(code, fn, *args, **kwargs):
    with pytest.raises(gr.SharedRunsError) as caught:
        fn(*args, **kwargs)
    assert caught.value.code == code


def test_the_per_run_cap_is_fifty_dollars(ledger):
    clock, _ = ledger
    assert gr.claim_pod_job("job-50", "50", clock=clock).worst_case_run_cost == 50
    refused(gr.PER_RUN_LIMIT, gr.claim_pod_job, "job-big", "50.01", clock=clock)
    refused(gr.UNAVAILABLE, gr.claim_pod_job, "job-zero", "0", clock=clock)
    refused(gr.UNAVAILABLE, gr.claim_pod_job, "job/../x", "5", clock=clock)


def test_the_week_is_three_hundred_less_the_held_reserve(ledger):
    clock, _ = ledger
    assert gr.pod_job_weekly_cap() == Decimal(260)
    assert gr.HELD_RESERVES == {"OWNER-SCORE-PROOF-CONFIRM-02-GRANT": Decimal(40)}
    for n in range(5):
        gr.claim_pod_job(f"job-{n}", "50", clock=clock)  # 250 reserved
    # The reserve holds: 250 + 50 > 260, though it would fit under 300.
    refused(gr.WEEKLY_LIMIT, gr.claim_pod_job, "job-5", "50", clock=clock)
    gr.claim_pod_job("job-6", "10", clock=clock)  # exactly 260
    refused(gr.WEEKLY_LIMIT, gr.claim_pod_job, "job-7", "0.01", clock=clock)
    # A claim again under a claimed id is the same claim, not a new run.
    gr.claim_pod_job("job-0", "50", clock=clock)
    # Released reserves (none held) give the full cap back.
    gr.claim_pod_job("job-8", "40", clock=clock, reserves={})
    refused(
        gr.WEEKLY_LIMIT, gr.claim_pod_job, "job-9", "0.01", clock=clock, reserves={}
    )


def test_settling_and_the_rolling_week_free_the_budget(ledger):
    clock, state = ledger
    for n in range(5):
        gr.claim_pod_job(f"job-{n}", "50", clock=clock)
    refused(gr.WEEKLY_LIMIT, gr.claim_pod_job, "late", "50", clock=clock)
    # A job settles at its reported cost, with any unresolved pod reservation kept.
    assert gr.settle_pod_job("job-0", "12.50", pending_usd="2.50")
    gr.claim_pod_job("late", "40", clock=clock)
    # Seven days on, the window is empty again.
    state["now"] += 7 * DAY + 1
    gr.claim_pod_job("next-week", "50", clock=clock)


def test_every_pod_job_is_in_the_weekly_summary(ledger):
    clock, _ = ledger
    gr.claim_pod_job("job-a", "20", clock=clock)
    gr.claim_pod_job("job-b", "15", clock=clock)
    gr.settle_pod_job("job-b", "3")
    report = gr.weekly_report(clock=clock)
    assert report["runs"] == 2
    assert report["by_grant"] == {gr.POD_JOB_GRANT_ID: "23.00"}
    assert "OWNER-TEST-GRANT-01" in report["cap_decision"]
    assert len(gr.POD_JOB_STORE) == 32 and int(gr.POD_JOB_STORE, 16) >= 0


class _Grant:
    currency = "USD"

    def __init__(self, grant_id, cost, runs=1):
        self.grant_id, self.worst_case_run_cost, self.permitted_runs = (
            grant_id,
            cost,
            runs,
        )


def test_the_reserve_binds_every_claim_not_only_pod_jobs(ledger):
    """One rule everywhere (the Test Lead, 2026-10-12): a Graphite grant's claim,
    e.g. the hunt's, also waits at USD 260 while CONFIRM-02's USD 40 is held."""
    clock, _ = ledger
    assert gr.effective_weekly_cap() == Decimal(260)
    for n in range(5):  # USD 250 of hunt-sized runs
        gr.claim(
            _Grant(f"GRAPHITE-GRANT-HUNT-X{n}", Decimal(50)),
            "a" * 32,
            f"r{n}",
            clock=clock,
        )
    refused(gr.WEEKLY_LIMIT, gr.claim, _Grant("GRAPHITE-GRANT-HUNT-X5", Decimal("14.94")),
            "a" * 32, "r5", clock=clock)  # fmt: skip
    refused(gr.WEEKLY_LIMIT, gr.claim_pod_job, "job-x", "10.01", clock=clock)
    gr.claim_pod_job("job-y", "10", clock=clock)  # exactly 260, shared across kinds


def test_removing_the_reserve_once_confirm02_settles_frees_the_headroom(
    ledger, monkeypatch
):
    clock, _ = ledger
    for n in range(5):
        gr.claim_pod_job(f"job-{n}", "50", clock=clock)
    gr.claim_pod_job("job-5", "10", clock=clock)  # at 260
    refused(gr.WEEKLY_LIMIT, gr.claim_pod_job, "job-6", "40", clock=clock)
    # The reviewed change after CONFIRM-02 settles removes its entry.
    monkeypatch.setattr(gr, "HELD_RESERVES", {})
    assert gr.effective_weekly_cap() == Decimal(300)
    gr.claim_pod_job("job-6", "40", clock=clock)  # the USD 40 is free again
    refused(gr.WEEKLY_LIMIT, gr.claim_pod_job, "job-7", "0.01", clock=clock)
