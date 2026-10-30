"""Own-agent avenue on rc50 (Test Runner 01:57Z, Lead 02:13Z): on Motor the summary said
eligible=false (gate motoring_mean_nonnegative) while practice_dual said eligible=true, and on
Cooling the reverse; an agent had to reconcile two truths. The exam's own gate verdict
(practice_dual) AND the summary's own must both pass (A4): each stays beside it."""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.scoring import practice_dual
from scripts.dev.miner_launchpad import campaign_view

ROOT = Path(__file__).resolve().parents[2]


def _dual(eligible, available=True):
    return {"available": available, "eligible": eligible, "schema": "x"}


@pytest.mark.parametrize(
    ("summary_says", "dual_says", "expected"),
    [
        (
            False,
            True,
            False,
        ),  # A4: the dual passes but the summary lists a gate failure
        (True, False, False),  # the reverse, seen on Cooling
        (True, True, True),
        (False, False, False),
    ],
)
def test_eligible_needs_both_the_dual_and_the_summary(
    summary_says, dual_says, expected
):
    out = practice_dual.reconcile_eligibility(
        {"eligible": summary_says, "score": 0.45}, _dual(dual_says)
    )
    assert out["eligible"] is expected
    assert out["summary_gate_eligible"] is summary_says
    assert out["dual_gate_eligible"] is dual_says
    assert out["score"] == 0.45 and "AND" in out["eligible_basis"]


def test_the_a4_motor_case_lists_a_gate_failure_and_is_not_eligible():
    """Motor: one public practice case fails motoring_mean_nonnegative, so the summary is ineligible and lists it,
    while the dual measurement on the practice grid alone says eligible. The merged result must say false.
    """
    summary = {
        "eligible": False,
        "n_gate_failed": 1,
        "gate_failures": {"motoring_mean_nonnegative": 1},
        "score": 0.2,
    }
    out = practice_dual.reconcile_eligibility(summary, _dual(True))
    assert out["eligible"] is False
    assert out["gate_failures"] == {"motoring_mean_nonnegative": 1}
    assert out["dual_gate_eligible"] is True and out["summary_gate_eligible"] is False


def test_the_cooling_shape_goes_through_the_same_function():
    """Cooling's catalog practice calls the same reconcile_eligibility: a failing cold-plate gate in the summary
    cannot be hidden by a passing dual block either."""
    summary = {
        "eligible": False,
        "n_gate_failed": 2,
        "gate_failures": {"peak_bounds_profile": 2},
    }
    assert (
        practice_dual.reconcile_eligibility(summary, _dual(True))["eligible"] is False
    )
    clean = {"eligible": True, "n_gate_failed": 0, "gate_failures": {}}
    assert practice_dual.reconcile_eligibility(clean, _dual(True))["eligible"] is True


def test_without_a_usable_dual_the_summary_is_unchanged():
    summary = {"eligible": False, "score": 1.0}
    for dual in (None, {"available": False}, {"available": True}, _dual("yes")):
        assert practice_dual.reconcile_eligibility(summary, dual) is summary
    assert practice_dual.reconcile_eligibility(None, _dual(True)) is None


def test_a_summary_without_its_own_verdict_gains_only_the_dual_one():
    out = practice_dual.reconcile_eligibility({"score": 0.3}, _dual(True))
    assert out["eligible"] is True and "summary_gate_eligible" not in out
    assert out["dual_gate_eligible"] is True


def test_the_page_reader_needs_every_verdict_it_carries():
    dual = {
        "schema": "carbon.practice.dual-feedback.v2",
        "available": True,
        "eligible": True,
        "gates": {},
    }
    run = {"summary": {"eligible": False}, "practice_dual": dual}
    assert (
        campaign_view.run_eligible(run) is False
    )  # A4: the summary's failure is not compensated
    both_true = {"summary": {"eligible": True}, "practice_dual": dual}
    assert campaign_view.run_eligible(both_true) is True
    # an older stored result: `eligible` was the dual's verdict and the summary's own was kept beside it
    older = {
        "summary": {"eligible": True, "summary_gate_eligible": False},
        "practice_dual": dual,
    }
    assert campaign_view.run_eligible(older) is False
    only_dual = {"practice_dual": dual}
    assert campaign_view.run_eligible(only_dual) is True
    # No dual: the summary's verdict stands; neither: unknown.
    assert campaign_view.run_eligible({"summary": {"eligible": False}}) is False
    assert campaign_view.run_eligible({"summary": {}}) is None


@pytest.mark.parametrize(
    "path",
    ["carbon/motor/catalog_practice.py", "carbon/cold_plate/catalog_practice.py"],
)
def test_motor_and_cooling_practice_write_the_reconciled_summary(path):
    source = (ROOT / path).read_text(encoding="utf-8")
    assert "reconcile_eligibility" in source
    assert source.index("reconcile_eligibility") < source.index(
        "ResearchWorkspace(self.ledger, self.owner).put"
    )


def test_campaign_busy_tells_a_new_launch_to_wait():
    """Test Runner 01:57Z: the first practice call right after a launch got campaign_busy while
    the launch run was still queued; the next step now says to wait."""
    from scripts.dev.miner_launchpad import supervisor

    step = supervisor.NEXT_ACTIONS["campaign_busy"]
    assert "carbon_wait" in step and "QUEUED" in step and "READY" in step
    assert "carbon_detach_campaign" in step  # the other cause is still named
