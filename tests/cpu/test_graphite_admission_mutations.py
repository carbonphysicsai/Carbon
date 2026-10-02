"""Mutation checks for GRAPHITE-ADMISSION-01: disabling each new protection
makes the test that guards it fail.

Each case switches one protection off with monkeypatch and runs its guarding
test. The guarding test must fail; if it passes, it does not exercise the
protection.
"""

from __future__ import annotations

import pytest
import test_agent_campaign_study as tstudy
import test_graphite_level_planner as tlp

from carbon.agent_campaign import study
from carbon.agent_campaign.graphite import closed_task
from carbon.agent_campaign.graphite import level_planner as lp


def _rejection(name):
    return lambda tmp: tlp.test_a_reply_outside_the_rules_is_rejected_and_recorded(
        tmp, name
    )


MUTATIONS = {
    "planner_sources_resolve_to_the_brief": (
        lambda m: m.setattr(lp, "_resolves", lambda source, document: "card"),
        _rejection("unresolved_source"),
    ),
    "planner_reply_is_closed": (
        lambda m: m.setattr(lp, "_closed_reply", lambda value, level: True),
        _rejection("status_in_reply"),
    ),
    "planner_level0_records_the_difference": (
        lambda m: m.setattr(lp, "_level0_gaps", lambda c, left, document: []),
        _rejection("level0_missing_citation"),
    ),
    "planner_refuses_an_unplaced_dimension": (
        lambda m: m.setattr(
            lp,
            "planning_level",
            lambda s, capability_id: s.ladder.get(capability_id.partition(".")[0], 0),
        ),
        lambda tmp: tlp.test_an_unplaced_dimension_refuses_the_session_before_any_call(
            tmp
        ),
    ),
    "planner_refuses_protected_results": (
        lambda m: m.setattr(lp, "protected", lambda value: False),
        lambda tmp: tlp.test_protected_or_malformed_results_are_refused(
            (
                {
                    "result_id": "dev-1",
                    "summary": "EV4 confirmation margins",
                    "ref": "x",
                },
            ),
            "result_names_protected_material",
        ),
    ),
    "closed_task_needs_a_grant": (
        lambda m: m.setattr(closed_task, "check_grant", lambda g, model, now: None),
        lambda tmp: tlp.test_a_session_needs_an_exact_unexpired_graphite_grant(
            tmp, None, "spending_grant_required"
        ),
    ),
    "unmapped_capability_is_refused": (
        lambda m: m.setattr(
            study,
            "planning_level",
            lambda s, capability_id: s.ladder.get(capability_id.partition(".")[0], 0),
        ),
        lambda tmp: tstudy.test_an_unmapped_capability_is_refused_not_defaulted(),
    ),
    "adapter_is_checked": (
        lambda m: m.setattr(study, "_checked", lambda s: (s, s.contract())),
        lambda tmp: tstudy.test_a_malformed_adapter_is_refused(
            {"ladder": {"model_family": 6}}, "ladder_map_malformed"
        ),
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(tmp_path / "mutated")
