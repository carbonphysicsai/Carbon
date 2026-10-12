"""The weekly cap's cost basis: pod reservation plus model charge, seeded from earlier roots.

Pods never settle at the provider (`pod_charge_unresolved`), so an unresolved pod stays
counted at its reservation, and runs that predate the ledger enter the rolling window at
their own start time and committed cost. A root whose store cannot be read is refused,
never skipped. Injected clocks only: no network, no spend.
"""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_agent_campaign_controller import Clock, grant_document, register, spec
from test_grant_weekly_budget import T0, claim, grant, store

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign import grant_runs as gr
from carbon.agent_campaign.fake import FakeProvider


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    directory = tmp_path / "host-ledger"
    monkeypatch.setenv(gr.ENV, str(directory))
    return directory


def old_root(
    tmp_path, name, *, settled, usage_known=1, phase="completed", keys=("o1",)
):
    """A controller root that predates the ledger, with its runs' cost basis set in the
    store the way a controller leaves it."""
    controller = ctl.CampaignController(
        root=tmp_path / name,
        provider=FakeProvider(),
        grant=grant(cost="20.00", runs=10, max_concurrency=10),
        operator="carbon-operator",
        clock=Clock(),
    )
    register(controller, ceiling="900.00")
    for key in keys:
        controller.launch(spec(), key)
    controller.close()
    database = sqlite3.connect(tmp_path / name / "campaign.sqlite3")
    with database:
        database.execute(
            "UPDATE runs SET settled=?, usage_known=?, phase=?",
            (settled, usage_known, phase),
        )
    database.close()
    return tmp_path / name


def started(root):
    database = sqlite3.connect(root / "campaign.sqlite3")
    try:
        (text,) = database.execute("SELECT started_at FROM runs LIMIT 1").fetchone()
    finally:
        database.close()
    return gr.run_start(text)


def test_an_unresolved_pod_stays_counted_at_its_reservation():
    g = grant(cost="20.00")
    claim(g, 1, "k", T0)
    # 0.50 of model charge plus a 3.92 pod the provider never settled: 4.42, not 0.50.
    assert gr.settle(g, store(1), "k", "4.42", pending_usd="3.92")
    report = gr.weekly_report(clock=lambda: T0 + 1)
    assert report["spent_usd"] == "4.42"
    assert report["pod_reservation_unresolved_usd"] == "3.92"
    assert report["worst_case_not_yet_settled_usd"] == "0.00"


def test_an_unsettled_run_stays_at_its_worst_case_and_is_reported_so():
    claim(grant(cost="20.00"), 1, "k", T0)
    report = gr.weekly_report(clock=lambda: T0 + 1)
    assert report["spent_usd"] == "20.00"
    assert report["worst_case_not_yet_settled_usd"] == "20.00"


def test_pending_cannot_exceed_the_reported_cost():
    g = grant()
    claim(g, 1, "k", T0)
    with pytest.raises(gr.SharedRunsError):
        gr.settle(g, store(1), "k", "1.00", pending_usd="2.00")
    assert gr.weekly_report(clock=lambda: T0 + 1)["spent_usd"] == "20.00"


def test_the_controller_records_the_unresolved_pod_part(tmp_path):
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
        "a1", SimpleNamespace(settled=Decimal("0.50"), pending=Decimal("3.92"))
    )
    report = gr.weekly_report(clock=lambda: controller.clock().timestamp())
    assert report["spent_usd"] == "4.42"
    assert report["pod_reservation_unresolved_usd"] == "3.92"


def test_the_seed_command_imports_each_runs_cost_with_its_start_time(tmp_path):
    root = old_root(tmp_path, "old", settled="4.42", keys=("o1", "o2"))
    document = tmp_path / "grant.json"
    document.write_text(json.dumps(grant_document(grant_id="g1", permitted_runs=10)))
    assert gr.main(["seed", "--grant", str(document), "--root", str(root)]) == 0
    at = started(root)
    report = gr.weekly_report(clock=lambda: at + 60)
    assert report["spent_usd"] == "8.84"  # two runs at 4.42 each
    assert report["seeded_runs"] == 2 and report["seeded_usd"] == "8.84"
    # re-seeding changes nothing
    assert gr.main(["seed", "--grant", str(document), "--root", str(root)]) == 0
    assert gr.weekly_report(clock=lambda: at + 60)["spent_usd"] == "8.84"


def test_a_root_counted_by_an_earlier_seed_gains_its_costs_on_reseed(tmp_path):
    root = old_root(tmp_path, "old", settled="4.42")
    g = grant()
    store_id, runs = gr.read_store(root)
    gr.claim_seeds(g, store_id, [r[0] for r in runs])  # the old count-only seed
    at = started(root)
    assert gr.weekly_report(clock=lambda: at + 60)["spent_usd"] == "0.00"
    gr.seed_root(g, root)
    assert gr.weekly_report(clock=lambda: at + 60)["spent_usd"] == "4.42"
    assert gr.count("g1") == 1


def test_seeded_spend_rolls_off_at_its_own_start_time(tmp_path):
    root = old_root(tmp_path, "old", settled="4.42")
    gr.seed_root(grant(), root)
    at = started(root)
    inside = gr.weekly_report(clock=lambda: at + gr.WEEK_SECONDS - 1)
    outside = gr.weekly_report(clock=lambda: at + gr.WEEK_SECONDS + 1)
    assert inside["spent_usd"] == "4.42" and outside["spent_usd"] == "0.00"


def test_seeded_spend_counts_against_a_new_launch(tmp_path):
    root = old_root(tmp_path, "old", settled="290.00")
    gr.seed_root(grant(), root)
    at = started(root)
    with pytest.raises(gr.SharedRunsError) as refused:
        gr.claim(grant(cost="20.00"), store(9), "new", clock=lambda: at + 60)
    assert refused.value.code == gr.WEEKLY_LIMIT


def test_unknown_usage_a_missing_settlement_or_an_open_run_count_at_the_reservation(
    tmp_path,
):
    unknown = old_root(tmp_path, "u", settled="0.10", usage_known=0)
    assert gr.read_store(unknown)[1][0][2] == Decimal("20.00")
    never = old_root(tmp_path, "n", settled=None)
    assert gr.read_store(never)[1][0][2] == Decimal("20.00")
    open_run = old_root(tmp_path, "o", settled="0.10", phase="dispatched")
    assert gr.read_store(open_run)[1][0][2] == Decimal("20.00")


def test_a_live_controllers_first_claim_seeds_its_existing_costs(tmp_path):
    root = old_root(tmp_path, "old", settled="4.42")
    clock = Clock()
    controller = ctl.CampaignController(
        root=root,
        provider=FakeProvider(),
        grant=grant(cost="20.00", runs=10, max_concurrency=10),
        operator="carbon-operator",
        clock=clock,
        shared_runs=True,
    )
    controller.launch(spec(), "new")
    report = gr.weekly_report(clock=lambda: clock().timestamp())
    assert report["spent_usd"] == "24.42"  # 4.42 seeded + 20.00 reserved
    assert report["seeded_runs"] == 1


@pytest.mark.parametrize(
    "damage", ["no-store-id", "no-database", "bad-cost", "bad-time"]
)
def test_a_root_whose_store_cannot_be_read_refuses_the_seed(tmp_path, damage):
    root = old_root(tmp_path, "old", settled="4.42")
    if damage == "no-store-id":
        (root / ctl.STORE_ID_FILE).unlink()
    elif damage == "no-database":
        (root / "campaign.sqlite3").unlink()
    else:
        database = sqlite3.connect(root / "campaign.sqlite3")
        with database:
            if damage == "bad-cost":
                database.execute("UPDATE runs SET settled='not-a-number'")
            else:
                database.execute("UPDATE runs SET started_at='yesterday'")
        database.close()
    with pytest.raises(gr.SharedRunsError) as refused:
        gr.seed_root(grant(), root)
    assert refused.value.code == gr.UNAVAILABLE
    assert gr.weekly_report(clock=lambda: T0)["runs"] == 0  # nothing partly imported


def test_the_report_line_states_the_basis_and_the_headroom():
    claim(grant(), 1, "k", T0)
    line = gr.weekly_line(gr.weekly_report(clock=lambda: T0 + 1))
    assert "headroom" in line and "pod reservation" in line and "unresolved" in line


def pod_ledger(tmp_path):
    from carbon.agent_campaign.graphite import experiment as ex

    ledger = ex.PodLedger(tmp_path / "pod-ledger.jsonl", clock=lambda: 0.0)
    for event, body in (
        ("pod_reserved", {"reserved_usd": "0.25", "minutes": 10}),
        ("pod_launch_requested", {}),
        ("pod_created", {"pod_id": "p", "rate_usd_per_hr": "0.49"}),
        ("pod_terminated_verified", {"pod_id": "p"}),
        ("pod_charge_unresolved", {"note": "no provider-reported charge"}),
    ):
        ledger.append(event, intent_id="i1", proposal="p-1", **body)
    return ledger


def test_a_created_pod_with_no_reported_charge_is_counted_at_its_reservation(tmp_path):
    ledger = pod_ledger(tmp_path)
    assert ledger.committed() == (Decimal(0), Decimal("0.25"))


def test_a_duplicate_pod_with_no_reported_charge_is_counted_at_the_reservation(
    tmp_path,
):
    ledger = pod_ledger(tmp_path)
    ledger.append(
        "pod_duplicates_counted",
        intent_id="i1",
        proposal="p-1",
        count=2,
        charged_usd="0",
        unknown_charges=2,
    )
    # the pod itself plus two duplicates whose charge is unknown: never zero
    assert ledger.committed() == (Decimal(0), Decimal("0.75"))


def test_a_duplicate_with_a_reported_charge_adds_that_charge_only(tmp_path):
    ledger = pod_ledger(tmp_path)
    ledger.append(
        "pod_duplicates_counted",
        intent_id="i1",
        proposal="p-1",
        count=1,
        charged_usd="0.07",
        unknown_charges=0,
    )
    assert ledger.committed() == (Decimal("0.07"), Decimal("0.25"))


def test_a_pod_that_was_never_dispatched_or_found_absent_costs_nothing(tmp_path):
    from carbon.agent_campaign.graphite import experiment as ex

    ledger = ex.PodLedger(tmp_path / "pod-ledger.jsonl", clock=lambda: 0.0)
    ledger.append(
        "pod_reserved", intent_id="i2", proposal="p-2", reserved_usd="0.25", minutes=10
    )
    ledger.append(
        "pod_settled",
        intent_id="i2",
        proposal="p-2",
        charge_usd="0",
        basis="reserved_never_dispatched",
    )
    assert ledger.committed() == (Decimal(0), Decimal(0))
