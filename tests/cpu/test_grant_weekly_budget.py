"""The standing testnet testing budget: a rolling seven-day spend cap that fails closed.

OWNER-TESTNET-WEEKLY-BUDGET-01: one hundred fifty US dollars per rolling seven days, pods
plus model charges, enforced beside the per-grant run counts in the host-level ledger.
Injected clocks only: no real sleeping, no network, no spend.
"""

from __future__ import annotations

import json
import threading
from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_agent_campaign_controller import grant_document

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign import grant_runs as gr
from carbon.agent_campaign.grant import SpendingGrant

DAY = 24 * 3600
T0 = 1_800_000_000.0


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    directory = tmp_path / "host-ledger"
    monkeypatch.setenv(gr.ENV, str(directory))
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


def test_the_cap_is_one_hundred_fifty_us_dollars():
    assert gr.WEEKLY_CAP_USD == Decimal(150) and gr.WEEK_SECONDS == 7 * DAY


def test_claims_up_to_the_cap_succeed_and_the_next_is_refused_without_taking_a_run_slot():
    g = grant()
    for index in range(7):  # 7 x 20 = 140 of 150
        claim(g, 1, f"k{index}", T0 + index)
    with pytest.raises(gr.SharedRunsError) as refused:
        claim(g, 2, "k-over", T0 + 10)  # 160 > 150
    assert refused.value.code == gr.WEEKLY_LIMIT
    assert gr.count("g1") == 7  # the refused launch took no run slot
    report = gr.weekly_report(clock=lambda: T0 + 10)
    assert report["spent_usd"] == "140.00" and report["remaining_usd"] == "10.00"


def test_the_window_boundary_is_exactly_seven_days_on_the_injected_clock():
    g = grant()
    for index in range(7):
        claim(g, 1, f"k{index}", T0)
    with pytest.raises(gr.SharedRunsError):
        claim(g, 2, "early", T0 + gr.WEEK_SECONDS - 1)  # the old runs still count
    assert claim(g, 2, "on-time", T0 + gr.WEEK_SECONDS) >= 1  # they have just left


def test_a_reported_cost_replaces_the_worst_case_reservation():
    g = grant()
    for index in range(7):
        claim(g, 1, f"k{index}", T0 + index)
    assert gr.settle(g, store(1), "k0", "1.00") is True  # ran for 1.00, not 20.00
    claim(g, 2, "after-settle", T0 + 100)  # 140 - 19 + 20 fits again
    assert gr.weekly_report(clock=lambda: T0 + 100)["spent_usd"] == "141.00"
    # An unknown run settles nothing; a bad cost raises and leaves the reservation.
    assert gr.settle(g, store(9), "nope", "1.00") is False
    with pytest.raises(gr.SharedRunsError):
        gr.settle(g, store(1), "k1", "not-a-number")
    assert gr.weekly_report(clock=lambda: T0 + 100)["spent_usd"] == "141.00"


def test_the_cap_is_shared_across_grants_and_roots():
    first, second = grant(grant_id="g1"), grant(grant_id="g2")
    for index in range(4):
        claim(first, 1, f"a{index}", T0 + index)
    for index in range(3):
        claim(second, 2, f"b{index}", T0 + 10 + index)
    with pytest.raises(gr.SharedRunsError) as refused:
        claim(second, 3, "c", T0 + 20)
    assert refused.value.code == gr.WEEKLY_LIMIT
    report = gr.weekly_report(clock=lambda: T0 + 20)
    assert report["by_grant"] == {"g1": "80.00", "g2": "60.00"} and report["runs"] == 7


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
    g = grant(cost="50.00")  # exactly three fit in 150
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
    assert results.count("claimed") == 3 and results.count(gr.WEEKLY_LIMIT) == 5
    assert gr.weekly_report(clock=lambda: T0)["spent_usd"] == "150.00"


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
        "Testnet testing budget, rolling 7 days: USD 20.00 of 150.00 used, "
        "USD 130.00 headroom, 1 runs (0 seeded from earlier roots). "
        f"Basis: {gr.BASIS}."
    )
    assert gr.main(["weekly"]) == 0
    assert "Testnet testing budget, rolling 7 days: USD 20.00 of 150.00 used" in (
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
            grant=grant(cost="60.00", runs=10, max_concurrency=10),
            operator="carbon-operator",
            clock=clock,
            shared_runs=True,
        )
        register(controller, ceiling="900.00")
        return controller

    first, second = live("a"), live("b")
    first.launch(spec(), "a1")
    second.launch(spec(), "b1")
    with pytest.raises(ctl.ControllerError, match="weekly_budget_reached"):
        first.launch(spec(), "a2")  # 180 > 150
    clock.advance(gr.WEEK_SECONDS + 1)
    first.launch(spec(), "a2")  # the week has rolled


def test_the_controller_settles_a_live_runs_reported_cost(tmp_path):
    from test_agent_campaign_controller import Clock, register, spec

    from carbon.agent_campaign.fake import FakeProvider

    controller = ctl.CampaignController(
        root=tmp_path / "a",
        provider=FakeProvider(),
        grant=grant(cost="60.00", runs=10, max_concurrency=10),
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
