"""GRAPHITE-01 phase 3 literature follow-up: mutation checks (GRAPHITE-D28-D31).

The pattern of `test_graphite_phase3_mutations.py`: each case switches one
protection off (or plants the widening it guards against) with monkeypatch
and runs the test that guards it. The guard passes with the protection in
place and must fail without it. A guard may fail by assertion or, where the
next layer refuses fail closed, by that layer's typed refusal.
"""

from __future__ import annotations

import pytest
import test_graphite_phase3_literature as tl

from carbon.agent_campaign.graphite import literature as lit
from carbon.agent_campaign.graphite import method_cards as mc
from carbon.agent_campaign.graphite import next_level, phase3
from carbon.agent_campaign.graphite import provider as gp
from carbon.agent_campaign.graphite import tools as gt
from carbon.reconstruction import expansion_record

_WRITE = next_level.ProposalStore.write


def _widening_write(self, record):
    """A planted widening: writing a proposal also records an expansion."""
    path = _WRITE(self, record)
    expansion_record.record("battery-fastcharge-ageing-development-v1", "widened")
    return path


MUTATIONS = {
    # Only cards a person checked CORRECT are offered by default.
    "checked_only_filter": (
        lambda m: m.setattr(mc, "_offered", lambda status, allow_unchecked: True),
        tl.test_checked_only_offers_only_cards_a_person_checked_correct,
    ),
    # An unchecked card is marked UNCHECKED in tool results.
    "unchecked_marking": (
        lambda m: m.setattr(
            lit.OfferedLiterature,
            "status",
            lambda self, card_id: "HUMAN_CHECKED_CORRECT",
        ),
        tl.test_unchecked_cards_are_offered_only_on_opt_in_and_marked,
    ),
    # The provider refuses a resume whose pinned literature changed.
    "digest_pinning_provider": (
        lambda m: m.setattr(gp, "_literature_changed", lambda recorded, current: False),
        tl.test_the_provider_refuses_to_resume_a_session_whose_literature_changed,
    ),
    # The runner refuses that resume before anything is touched.
    "digest_pinning_runner": (
        lambda m: m.setattr(phase3, "check_resume", lambda provider, number: None),
        tl.test_a_resume_with_another_snapshot_or_policy_is_refused_before_it_runs,
    ),
    # A capability the recorded contract already rebuilds is not next level.
    "proposal_cites_outside_the_contract": (
        lambda m: m.setattr(
            next_level, "_cited", lambda capability_id, dimension, live: "research_only"
        ),
        tl.test_a_planner_proposal_is_validated_written_and_listed,
    ),
    # Writing a proposal never widens: a planted widening is caught.
    "proposal_never_widens": (
        lambda m: m.setattr(next_level.ProposalStore, "write", _widening_write),
        tl.test_a_proposal_never_changes_the_contract_permissions_or_score,
    ),
    # Only the Planner's manifest offers the proposal tool.
    "proposal_tool_planner_only": (
        lambda m: m.setattr(gt.GraphiteToolbox, "_offered", lambda self, name: True),
        tl.test_the_constructor_cannot_write_a_proposal,
    ),
}


def _guard(test, tmp, monkeypatch, capsys):
    names = test.__code__.co_varnames[: test.__code__.co_argcount]
    kwargs = {}
    for name in names:
        if name == "tmp_path":
            tmp.mkdir(parents=True, exist_ok=True)
            kwargs[name] = tmp
        elif name == "monkeypatch":
            kwargs[name] = monkeypatch
        elif name == "capsys":
            kwargs[name] = capsys
    return test(**kwargs)


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch, capsys):
    disable, guard = MUTATIONS[name]
    with pytest.MonkeyPatch.context() as intact:
        _guard(guard, tmp_path / "intact", intact, capsys)  # passes with it in place
    disable(monkeypatch)
    refused = (AssertionError, pytest.fail.Exception, lit.LiteratureError)
    with pytest.raises(refused), pytest.MonkeyPatch.context() as mutated:
        _guard(guard, tmp_path / "mutated", mutated, capsys)
