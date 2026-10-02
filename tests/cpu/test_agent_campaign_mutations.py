"""Mutation checks: disabling each critical protection makes its test fail.

Each case switches one protection off with monkeypatch and runs the test that
guards it. The guarding test must fail; if it passes, that test does not
actually exercise the protection.
"""

from __future__ import annotations

import pytest
import test_agent_campaign_boundaries as tb
import test_agent_campaign_controller as tc
import test_design_search_commitment as ts

from carbon.agent_campaign import boundaries
from carbon.agent_campaign.controller import CampaignController
from carbon.battery.value import search_commitment as sc

MUTATIONS = {
    "dispatch_halts": (
        lambda m: m.setattr(CampaignController, "_halts", lambda self, db: []),
        lambda tmp: tc.test_unknown_usage_stops_dispatch(tmp),
    ),
    "worst_case_reservation": (
        lambda m: m.setattr(
            CampaignController, "_committed", staticmethod(lambda row: 0)
        ),
        lambda tmp: tc.test_worst_case_spend_is_reserved_before_launch(tmp),
    ),
    "cross_session_boundary": (
        lambda m: m.setattr(
            CampaignController, "_check_session", staticmethod(lambda s, c: None)
        ),
        lambda tmp: tc.test_a_task_cannot_reach_another_sessions_workspace(tmp),
    ),
    "verified_worker_stop": (
        lambda m: m.setattr(
            CampaignController,
            "_stopped",
            staticmethod(lambda status: status.state.value == "cancelled"),
        ),
        lambda tmp: tc.test_cancel_is_verified_and_incomplete_cleanup_is_actionable(
            tmp
        ),
    ),
    "finding_blocks_expansion": (
        lambda m: m.setattr(
            CampaignController, "_expansion_blocked", staticmethod(lambda db: False)
        ),
        lambda tmp: tc.test_existing_battery_findings_stop_expansion(tmp),
    ),
    "canary_scan": (
        lambda m: m.setattr(boundaries, "exposed", lambda body, canaries: []),
        lambda tmp: tc.test_canary_exposure_is_a_finding_and_halts_dispatch(tmp),
    ),
    "checkout_denylist": (
        lambda m: m.setattr(boundaries, "_denied", lambda relative: False),
        lambda tmp: tb.test_denied_and_escaping_paths_are_refused(
            "docs/development/evidence/ev2-2026-10-01/results.json"
        ),
    ),
    "ev4_material_guard": (
        lambda m: m.setattr(sc, "_protected", lambda: (lambda t, s: False)),
        lambda tmp: ts.test_ev4_material_is_refused((24.0, 0.33)),
    ),
    "query_budget": (
        lambda m: m.setattr(sc.Oracle, "used", property(lambda self: 0)),
        lambda tmp: ts.test_oracle_enforces_budget_and_declared_points(),
    ),
    "commitment_before_reference": (
        lambda m: m.setattr(sc, "_load_committed", lambda c: getattr(c, "document", c)),
        lambda tmp: ts.test_a_raw_commitment_document_is_refused(tmp),
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(tmp_path / "mutated")
