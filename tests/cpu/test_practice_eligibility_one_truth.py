"""Own-agent avenue on rc50 (Test Runner 01:57Z, Lead 02:13Z): on Motor the summary said
eligible=false (gate motoring_mean_nonnegative) while practice_dual said eligible=true, and on
Cooling the reverse; an agent had to reconcile two truths. The exam's own gate verdict
(practice_dual) is the practice's `eligible`; the summary's stays beside it."""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.scoring import practice_dual
from scripts.dev.miner_launchpad import campaign_view

ROOT = Path(__file__).resolve().parents[2]


def _dual(eligible, available=True):
    return {"available": available, "eligible": eligible, "schema": "x"}


@pytest.mark.parametrize(
    ("summary_says", "dual_says"), [(False, True), (True, False), (True, True), (False, False)]
)
def test_the_dual_verdict_is_the_practices_eligible(summary_says, dual_says):
    out = practice_dual.reconcile_eligibility(
        {"eligible": summary_says, "score": 0.45}, _dual(dual_says)
    )
    assert out["eligible"] is dual_says
    assert out["summary_gate_eligible"] is summary_says
    assert out["score"] == 0.45 and "exam's own gates" in out["eligible_basis"]


def test_without_a_usable_dual_the_summary_is_unchanged():
    summary = {"eligible": False, "score": 1.0}
    for dual in (None, {"available": False}, {"available": True}, _dual("yes")):
        assert practice_dual.reconcile_eligibility(summary, dual) is summary
    assert practice_dual.reconcile_eligibility(None, _dual(True)) is None


def test_a_summary_without_its_own_verdict_gains_only_the_dual_one():
    out = practice_dual.reconcile_eligibility({"score": 0.3}, _dual(True))
    assert out["eligible"] is True and "summary_gate_eligible" not in out


def test_the_page_reader_prefers_the_dual_verdict_too():
    dual = {
        "schema": "carbon.practice.dual-feedback.v2",
        "available": True,
        "eligible": True,
        "gates": {},
    }
    run = {"summary": {"eligible": False}, "practice_dual": dual}
    assert campaign_view.run_eligible(run) is True
    # No dual: the summary's verdict stands; neither: unknown.
    assert campaign_view.run_eligible({"summary": {"eligible": False}}) is False
    assert campaign_view.run_eligible({"summary": {}}) is None


@pytest.mark.parametrize(
    "path", ["carbon/motor/catalog_practice.py", "carbon/cold_plate/catalog_practice.py"]
)
def test_motor_and_cooling_practice_write_the_reconciled_summary(path):
    source = (ROOT / path).read_text(encoding="utf-8")
    assert "reconcile_eligibility" in source
    assert source.index("reconcile_eligibility") < source.index("ResearchWorkspace(self.ledger, self.owner).put")


def test_campaign_busy_tells_a_new_launch_to_wait():
    """Test Runner 01:57Z: the first practice call right after a launch got campaign_busy while
    the launch run was still queued; the next step now says to wait."""
    from scripts.dev.miner_launchpad import supervisor

    step = supervisor.NEXT_ACTIONS["campaign_busy"]
    assert "carbon_wait" in step and "QUEUED" in step and "READY" in step
    assert "carbon_detach_campaign" in step  # the other cause is still named
