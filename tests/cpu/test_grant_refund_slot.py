"""A run that fails as infrastructure before any pod exists releases its run SLOT only.

The weekly window keeps the reported model charge and any pod reservation; a refund is
single-use, written under both locks, and refused for anything the ledger or the
controller cannot positively show. Injected clocks only: no network, no spend.
"""

from __future__ import annotations

import json
import threading
from decimal import Decimal

import pytest
from test_agent_campaign_controller import Clock, register, spec
from test_grant_weekly_budget import T0, claim, grant, store

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign import grant_runs as gr
from carbon.agent_campaign.fake import FakeProvider
from carbon.agent_campaign.provider import RunState


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    directory = tmp_path / "host-ledger"
    monkeypatch.setenv(gr.ENV, str(directory))
    return directory


def refund(g, number, key, cost="0.30", pending="0", **kw):
    return gr.refund(g, store(number), key, cost, pending_usd=pending, **kw)


def test_a_refund_frees_the_run_slot():
    g = grant(runs=1)
    claim(g, 1, "k1", T0)
    with pytest.raises(gr.SharedRunsError) as full:
        claim(g, 1, "k2", T0 + 1)
    assert full.value.code == gr.LIMIT
    refund(g, 1, "k1")
    assert gr.count(g.grant_id) == 0
    claim(g, 1, "k2", T0 + 2)  # the slot is free again
    assert gr.count(g.grant_id) == 1


def test_the_model_charge_and_pod_reservation_stay_in_the_weekly_window():
    g = grant(cost="20.00", runs=1)
    claim(g, 1, "k1", T0)
    refund(g, 1, "k1", cost="4.42", pending="3.92")
    report = gr.weekly_report(clock=lambda: T0 + 1)
    assert report["spent_usd"] == "4.42"  # not zero, and not the worst case
    assert report["pod_reservation_unresolved_usd"] == "3.92"


def test_a_double_refund_is_refused():
    g = grant(runs=2)
    claim(g, 1, "k1", T0)
    refund(g, 1, "k1")
    with pytest.raises(gr.SharedRunsError, match="already refunded"):
        refund(g, 1, "k1")
    assert gr.count(g.grant_id) == 0


def test_a_settled_run_cannot_be_refunded():
    g = grant(runs=2)
    claim(g, 1, "k1", T0)
    gr.settle(g, store(1), "k1", "1.00")
    with pytest.raises(gr.SharedRunsError, match="already settled"):
        refund(g, 1, "k1")
    assert gr.count(g.grant_id) == 1


def test_a_claim_never_made_or_only_seeded_cannot_be_refunded():
    g = grant(runs=3)
    with pytest.raises(gr.SharedRunsError, match="not a launch claimed here"):
        refund(g, 1, "nope")
    gr.claim_seeds(g, store(1), ["old"], runs=[("old", T0 - 10, Decimal("1.00"))])
    with pytest.raises(gr.SharedRunsError, match="not a launch claimed here"):
        refund(g, 1, "old")
    assert gr.count(g.grant_id) == 1


def test_an_unknown_reason_or_cost_is_refused():
    g = grant(runs=2)
    claim(g, 1, "k1", T0)
    with pytest.raises(gr.SharedRunsError):
        refund(g, 1, "k1", reason="because")
    with pytest.raises(gr.SharedRunsError):
        refund(g, 1, "k1", cost="unknown")
    with pytest.raises(gr.SharedRunsError):
        refund(g, 1, "k1", cost="1.00", pending="2.00")
    assert gr.count(g.grant_id) == 1  # nothing was released


def test_a_refunded_claim_cannot_be_claimed_again_and_seeds_do_not_resurrect_it():
    g = grant(runs=2)
    claim(g, 1, "k1", T0)
    refund(g, 1, "k1")
    with pytest.raises(gr.SharedRunsError, match="refunded"):
        claim(g, 1, "k1", T0 + 5)
    # a later claim that lists the refunded key among its store runs does not
    # take the slot back
    gr.claim(g, store(1), "k2", seed_keys=["k1"], clock=lambda: T0 + 6)
    assert gr.count(g.grant_id) == 1
    gr.claim_seeds(g, store(1), ["k1"])
    assert gr.count(g.grant_id) == 1


def test_the_refund_line_carries_the_reason_and_the_claim_id(ledger):
    g = grant()
    claim(g, 1, "k1", T0)
    refund(g, 1, "k1", clock=lambda: T0 + 3)
    lines = [
        json.loads(line)
        for line in next(ledger.glob("g1.*.jsonl")).read_text().splitlines()
    ]
    refund_line = lines[-1]
    assert refund_line["reason"] == gr.REFUND_FAILED_INFRA
    assert refund_line["refund"] == gr.entry_id(store(1), "k1")
    assert set(refund_line) == {"refund", "reason", "store", "at"}


def test_a_refund_line_without_its_claim_makes_the_ledger_unusable(ledger):
    g = grant()
    claim(g, 1, "k1", T0)
    path = next(ledger.glob("g1.*.jsonl"))
    with path.open("a") as stream:
        stream.write(
            json.dumps({"refund": "0" * 64, "reason": gr.REFUND_FAILED_INFRA}) + "\n"
        )
    with pytest.raises(gr.SharedRunsError) as refused:
        gr.count(g.grant_id)
    assert refused.value.code == gr.UNAVAILABLE


def test_concurrent_refunds_of_one_claim_release_one_slot_once():
    g = grant(runs=1)
    claim(g, 1, "k1", T0)
    outcomes = []

    def attempt():
        try:
            refund(g, 1, "k1")
            outcomes.append("refunded")
        except gr.SharedRunsError:
            outcomes.append("refused")

    threads = [threading.Thread(target=attempt) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count("refunded") == 1 and outcomes.count("refused") == 5
    assert gr.count(g.grant_id) == 0


# -- the controller: only what it can prove --------------------------------------------------
def failed_run(tmp_path, evidence, *, runs=1):
    """A live controller whose provider reports `evidence` and whose run FAILED."""
    provider = FakeProvider(cost_per_run="0.30")
    if evidence is not None:
        provider.refund_evidence = evidence
    controller = ctl.CampaignController(
        root=tmp_path / "a",
        provider=provider,
        grant=grant(cost="20.00", runs=runs, max_concurrency=10),
        operator="carbon-operator",
        clock=Clock(),
        shared_runs=True,
    )
    register(controller, ceiling="900.00")
    controller.launch(spec(), "a1")
    provider.finish("fake-run-0001", RunState.FAILED)
    assert controller.poll("a1") == "failed"
    return controller


def proved(**changes):
    body = {
        "failed_infra": True,
        "pod_record_readable": True,
        "pods_created": 0,
        "pods_uncertain": 0,
    }
    body.update(changes)
    return lambda run_id: body


def test_a_proved_infrastructure_failure_before_any_pod_frees_the_slot(tmp_path):
    controller = failed_run(tmp_path, proved())
    assert gr.count("g1") == 0
    # the charge it reported stays in the window
    report = gr.weekly_report(clock=lambda: controller.clock().timestamp())
    assert report["spent_usd"] == "0.30"
    controller.launch(spec(), "a2")  # the freed slot is usable
    assert gr.count("g1") == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"failed_infra": False},
        {"pod_record_readable": False},
        {"pods_created": 1},
        {"pods_uncertain": 1},
        {"pods_created": None},
        {"pods_uncertain": "0"},
        {"pods_created": True},
    ],
)
def test_anything_not_proved_keeps_the_slot_consumed(tmp_path, changes):
    failed_run(tmp_path, proved(**changes))
    assert gr.count("g1") == 1


def test_a_provider_that_cannot_state_the_evidence_keeps_the_slot_consumed(tmp_path):
    failed_run(tmp_path, None)
    assert gr.count("g1") == 1


def test_a_provider_whose_evidence_raises_keeps_the_slot_consumed(tmp_path):
    def broken(run_id):
        raise OSError("unreadable")

    failed_run(tmp_path, broken)
    assert gr.count("g1") == 1


def test_a_run_that_did_not_fail_is_never_refunded(tmp_path):
    provider = FakeProvider(cost_per_run="0.30")
    provider.refund_evidence = proved()
    controller = ctl.CampaignController(
        root=tmp_path / "a",
        provider=provider,
        grant=grant(cost="20.00", runs=1, max_concurrency=10),
        operator="carbon-operator",
        clock=Clock(),
        shared_runs=True,
    )
    register(controller, ceiling="900.00")
    controller.launch(spec(), "a1")
    provider.finish("fake-run-0001")
    assert controller.poll("a1") == "completed"
    assert gr.count("g1") == 1
