"""The standing testnet testing budget: a rolling seven-day spend cap that fails closed.

OWNER-TESTNET-WEEKLY-BUDGET-01: one hundred fifty US dollars per rolling seven days, pods
plus model charges, enforced beside the per-grant run counts in the host-level ledger.
Injected clocks only: no real sleeping, no network, no spend.
"""

from __future__ import annotations

import json
import re
import threading
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_agent_campaign_controller import grant_document

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign import grant_runs as gr
from carbon.agent_campaign.grant import SpendingGrant

DAY = 24 * 3600
REPOSITORY = Path(__file__).resolve().parents[2]
T0 = 1_800_000_000.0


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    directory = tmp_path / "host-ledger"
    monkeypatch.setenv(gr.ENV, str(directory))
    # These tests pin the raw USD 300 rolling-week mechanics. The held reserves
    # (`gr.HELD_RESERVES`, which every claim also honours) are tested on their own in
    # test_grant_runs_pod_jobs.py.
    monkeypatch.setattr(gr, "HELD_RESERVES", {})
    return directory


def grant(cost="20.00", runs=100, grant_id="g1", **extra):
    return SpendingGrant.from_document(
        grant_document(
            grant_id=grant_id,
            worst_case_run_cost=cost,
            permitted_runs=runs,
            monetary_ceiling="1000.00",
            **extra,
        )
    )


def store(number):
    return f"{number:032x}"


def claim(g, number, key, at):
    return gr.claim(g, store(number), key, clock=lambda: at)


def test_the_cap_is_three_hundred_us_dollars_and_fifty_per_run():
    assert gr.WEEKLY_CAP_USD == Decimal(300) and gr.WEEK_SECONDS == 7 * DAY
    assert gr.PER_RUN_CAP_USD == Decimal(50)


def test_both_figures_match_the_committed_decision_record():
    """The figures in code are the record's own words, so neither can drift."""
    text = (REPOSITORY / gr.CAP_RECORD).read_text(encoding="utf-8")
    weekly = re.search(r"The figure is USD (\d+) per rolling seven days", text)
    per_run = re.search(r"Per-run safety cap: USD (\d+)", text)
    assert weekly and per_run, "the record no longer states the figures"
    assert Decimal(weekly[1]) == gr.WEEKLY_CAP_USD
    assert Decimal(per_run[1]) == gr.PER_RUN_CAP_USD
    assert "OWNER-TEST-GRANT-01" in text and "OWNER-TEST-GRANT-01" in gr.CAP_DECISION


def test_a_run_above_the_per_run_cap_is_refused_without_taking_a_slot_or_budget():
    g = grant(cost="50.01")
    with pytest.raises(gr.SharedRunsError) as refused:
        claim(g, 1, "k", T0)
    assert refused.value.code == gr.PER_RUN_LIMIT
    assert gr.count("g1") == 0
    assert gr.weekly_report(clock=lambda: T0)["runs"] == 0
    claim(grant(cost="50.00", grant_id="g2"), 1, "k", T0)  # exactly 50 is allowed


def test_an_unreadable_worst_case_cost_refuses_not_zero_or_the_cap():
    class Unknown:
        grant_id, currency, permitted_runs = "g9", "USD", 5
        worst_case_run_cost = "not-a-number"

    with pytest.raises(gr.SharedRunsError) as refused:
        gr.claim(Unknown(), store(1), "k", clock=lambda: T0)
    assert refused.value.code == gr.UNAVAILABLE


def test_claims_up_to_the_cap_succeed_and_the_next_is_refused_without_taking_a_run_slot():
    g = grant()
    for index in range(15):  # 15 x 20 = 300 of 300
        claim(g, 1, f"k{index}", T0 + index)
    with pytest.raises(gr.SharedRunsError) as refused:
        claim(g, 2, "k-over", T0 + 20)  # 320 > 300
    assert refused.value.code == gr.WEEKLY_LIMIT
    assert gr.count("g1") == 15  # the refused launch took no run slot
    report = gr.weekly_report(clock=lambda: T0 + 20)
    assert report["spent_usd"] == "300.00" and report["remaining_usd"] == "0.00"


def test_the_window_boundary_is_exactly_seven_days_on_the_injected_clock():
    g = grant()
    for index in range(15):
        claim(g, 1, f"k{index}", T0)
    with pytest.raises(gr.SharedRunsError):
        claim(g, 2, "early", T0 + gr.WEEK_SECONDS - 1)  # the old runs still count
    assert claim(g, 2, "on-time", T0 + gr.WEEK_SECONDS) >= 1  # they have just left


def test_a_reported_cost_replaces_the_worst_case_reservation():
    g = grant(cost="40.00")
    for index in range(7):  # 7 x 40 = 280 of 300
        claim(g, 1, f"k{index}", T0 + index)
    with pytest.raises(gr.SharedRunsError):
        claim(g, 2, "before-settle", T0 + 50)  # 320 > 300
    assert gr.settle(g, store(1), "k0", "1.00") is True  # ran for 1.00, not 40.00
    claim(g, 2, "after-settle", T0 + 100)  # 280 - 39 + 40 fits again
    assert gr.weekly_report(clock=lambda: T0 + 100)["spent_usd"] == "281.00"
    # An unknown run settles nothing; a bad cost raises and leaves the reservation.
    assert gr.settle(g, store(9), "nope", "1.00") is False
    with pytest.raises(gr.SharedRunsError):
        gr.settle(g, store(1), "k1", "not-a-number")
    assert gr.weekly_report(clock=lambda: T0 + 100)["spent_usd"] == "281.00"


def test_the_cap_is_shared_across_grants_and_roots():
    first = grant(cost="40.00", grant_id="g1")
    second = grant(cost="40.00", grant_id="g2")
    for index in range(4):
        claim(first, 1, f"a{index}", T0 + index)
    for index in range(3):
        claim(second, 2, f"b{index}", T0 + 10 + index)
    with pytest.raises(gr.SharedRunsError) as refused:
        claim(second, 3, "c", T0 + 20)
    assert refused.value.code == gr.WEEKLY_LIMIT
    report = gr.weekly_report(clock=lambda: T0 + 20)
    assert report["by_grant"] == {"g1": "160.00", "g2": "120.00"}
    assert report["runs"] == 7


def test_a_relaunch_of_the_same_key_is_not_counted_twice():
    g = grant()
    claim(g, 1, "k", T0)
    claim(g, 1, "k", T0 + 5)
    assert gr.weekly_report(clock=lambda: T0 + 5)["spent_usd"] == "20.00"


def test_an_unknown_cost_refuses_not_zero():
    with pytest.raises(gr.SharedRunsError) as refused:
        gr.claim(grant(currency="EUR"), store(1), "k", clock=lambda: T0)
    assert refused.value.code == gr.UNAVAILABLE
    assert gr.weekly_report(clock=lambda: T0)["runs"] == 0


def test_a_corrupt_or_unreadable_weekly_ledger_refuses_every_claim(ledger):
    g = grant()
    claim(g, 1, "k0", T0)
    path = ledger / gr.WEEKLY_FILE
    good = path.read_bytes()
    for bad in (
        good + b"not json\n",
        good + b'{"entry":"%s","grant":"g","at":1,"cost_usd":"NaN"}\n' % (b"0" * 64),
        good + b'{"entry":"short","grant":"g","at":1,"cost_usd":"1"}\n',
        good + b'{"settle":"%s","cost_usd":"1"}\n' % (b"1" * 64),
    ):
        path.write_bytes(bad)
        with pytest.raises(gr.SharedRunsError) as refused:
            claim(g, 1, "k-next", T0 + 1)
        assert refused.value.code == gr.UNAVAILABLE
        with pytest.raises(gr.SharedRunsError):
            gr.weekly_report(clock=lambda: T0 + 1)
    assert gr.count("g1") == 1  # no refused claim took a run slot


def test_concurrent_claimants_cannot_overspend_the_week():
    g = grant(cost="50.00")  # exactly six fit in 300
    results, barrier = [], threading.Barrier(8)

    def claimant(number):
        barrier.wait()
        try:
            gr.claim(g, store(number), f"k{number}", clock=lambda: T0)
            results.append("claimed")
        except gr.SharedRunsError as error:
            results.append(error.code)

    threads = [threading.Thread(target=claimant, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("claimed") == 6 and results.count(gr.WEEKLY_LIMIT) == 2
    assert gr.weekly_report(clock=lambda: T0)["spent_usd"] == "300.00"


def test_the_ledger_holds_ids_costs_and_times_only(ledger):
    claim(grant(), 1, "k", T0)
    text = (ledger / gr.WEEKLY_FILE).read_text()
    row = json.loads(text.splitlines()[0])
    assert set(row) == {"entry", "grant", "at", "cost_usd"}
    for forbidden in ("account", "balance", "test-account", "granted_by", "provider"):
        assert forbidden not in text


def test_the_weekly_report_line_and_command(capsys):
    g = grant()
    claim(g, 1, "k", T0)
    line = gr.weekly_line(gr.weekly_report(clock=lambda: T0 + 1))
    assert line == (
        "Testnet testing budget, rolling 7 days: USD 20.00 of 300.00 used, "
        "USD 280.00 headroom, 1 runs (0 seeded from earlier roots). "
        "Cap: USD 300.00 per rolling 7 days and USD 50.00 per run "
        f"({gr.CAP_DECISION}). Basis: {gr.BASIS}."
    )
    assert gr.main(["weekly"]) == 0
    assert "Testnet testing budget, rolling 7 days: USD 20.00 of 300.00 used" in (
        capsys.readouterr().out
    )


def test_a_live_controller_is_held_to_the_weekly_cap(tmp_path):
    from test_agent_campaign_controller import Clock, register, spec

    from carbon.agent_campaign.fake import FakeProvider

    clock = Clock()

    def live(name):
        controller = ctl.CampaignController(
            root=tmp_path / name,
            provider=FakeProvider(),
            grant=grant(cost="50.00", runs=10, max_concurrency=10),
            operator="carbon-operator",
            clock=clock,
            shared_runs=True,
        )
        register(controller, ceiling="900.00")
        return controller

    first, second = live("a"), live("b")
    for index in range(3):  # 6 x 50 = 300 of 300
        first.launch(spec(), f"a{index}")
        second.launch(spec(), f"b{index}")
    with pytest.raises(ctl.ControllerError, match="weekly_budget_reached"):
        first.launch(spec(), "a-over")  # 350 > 300
    clock.advance(gr.WEEK_SECONDS + 1)
    first.launch(spec(), "a-over")  # the week has rolled


def test_the_controller_settles_a_live_runs_reported_cost(tmp_path):
    from test_agent_campaign_controller import Clock, register, spec

    from carbon.agent_campaign.fake import FakeProvider

    controller = ctl.CampaignController(
        root=tmp_path / "a",
        provider=FakeProvider(),
        grant=grant(cost="50.00", runs=10, max_concurrency=10),
        operator="carbon-operator",
        clock=Clock(),
        shared_runs=True,
    )
    register(controller, ceiling="900.00")
    controller.launch(spec(), "a1")
    controller._weekly_settle(
        "a1", SimpleNamespace(settled=Decimal("4.00"), pending=Decimal("1.00"))
    )
    assert (
        gr.weekly_report(clock=lambda: controller.clock().timestamp())["spent_usd"]
        == "5.00"
    )
    controller._weekly_settle("a1", None)  # unknown usage keeps the reservation
    assert (
        gr.weekly_report(clock=lambda: controller.clock().timestamp())["spent_usd"]
        == "5.00"
    )
