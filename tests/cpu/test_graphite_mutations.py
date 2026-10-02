"""GRAPHITE-01 mutation checks: disabling each protection fails its test.

The pattern of `test_agent_campaign_mutations.py`: each case switches one
protection off with monkeypatch and runs the test that guards it. The guard
passes with the protection in place and must fail without it; if it still
passed, that test would not exercise the protection.
"""

from __future__ import annotations

import pytest
import test_graphite_boundaries as tb
import test_graphite_harness as th
import test_graphite_ladder as tl

from carbon.agent_campaign.graphite import ladder as gl
from carbon.agent_campaign.graphite import provider as gp
from carbon.agent_campaign.graphite import tools as gt
from carbon.development_session.model_provider import ENGY_LADDER
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tools import PREFIX

_CAPS = gp.GraphiteProvider.caps
_READ_EV4 = tb.test_requests_for_protected_material_are_refused_typed.pytestmark[
    0
].args[1][0]

MUTATIONS = {
    # The session record is re-verified against the role before resuming.
    "session_record_verified": (
        lambda m: m.setattr(gp, "_verify", lambda *args: None),
        lambda tmp: th.test_a_tampered_session_record_refuses_to_resume(
            tmp, ("role", "prompt_digest"), "sha256:" + "0" * 64, "role_changed"
        ),
    ),
    # A tool outside the role's manifest is refused, whatever the model asks.
    "tool_manifest_closed": (
        lambda m: m.setattr(gt.GraphiteToolbox, "_offered", lambda self, name: True),
        lambda tmp: tb.test_instructions_inside_tool_output_never_change_role_tools_or_budget(
            tmp
        ),
    ),
    # A request naming confirmation or official material is refused.
    "protected_material_refused": (
        lambda m: m.setattr(gt, "protected", lambda value: False),
        lambda tmp: tb.test_requests_for_protected_material_are_refused_typed(
            tmp, *_READ_EV4
        ),
    ),
    # A result carrying protected material is withheld from the model.
    "protected_result_withheld": (
        lambda m: m.setattr(gt, "protected", lambda value: False),
        lambda tmp: tb.test_a_result_carrying_protected_material_is_withheld(tmp),
    ),
    # A role runs only under its own campaign role.
    "role_boundary": (
        lambda m: m.setattr(gp, "_check_role", lambda role, spec: None),
        lambda tmp: th.test_an_unregistered_brief_or_wrong_role_opens_nothing(tmp),
    ),
    # Escalation moves one rung, never two.
    "one_rung_only": (
        lambda m: m.setattr(gl, "_next_rung", lambda current: current + 2),
        lambda tmp: tl.test_rungs_are_never_skipped(tmp),
    ),
    # Nothing escalates above the top rung.
    "ladder_ceiling": (
        lambda m: m.setattr(gl, "TOP", len(ENGY_LADDER) + 5),
        lambda tmp: tl.test_the_top_rung_is_a_ceiling(tmp),
    ),
    # Escalation needs a recorded failure of this role, consumed once.
    "failure_required": (
        lambda m: m.setattr(
            gl.Ladder, "_consumable", staticmethod(lambda db, role, failure: None)
        ),
        lambda tmp: tl.test_no_escalation_without_a_recorded_failure(tmp),
    ),
    # Cancellation is observed at the loop's next checkpoint.
    "cancellation_checkpoint": (
        lambda m: m.setattr(gp.GraphiteLedger, "checkpoint", CampaignLedger.checkpoint),
        lambda tmp: th.test_cancellation_mid_run_stops_before_the_next_call(tmp),
    ),
    # A run's money is capped at the controller's reservation for it.
    "per_run_money_cap": (
        lambda m: m.setattr(
            gp.GraphiteProvider,
            "caps",
            lambda self, role=None: {**_CAPS(self, role), "provider_nanodollars": None},
        ),
        lambda tmp: th.test_the_per_run_money_cap_is_the_controllers_reservation(tmp),
    ),
}


def test_the_guarded_protected_request_is_the_ev4_read():
    name, arguments = _READ_EV4
    assert name == PREFIX + "start_research_task"
    assert "ev4" in arguments["arguments_json"]


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(tmp_path / "mutated")
