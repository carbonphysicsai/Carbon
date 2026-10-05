"""Mutation checks for GRAPHITE-CONDITIONAL-EXPLORATION-01: switching off each
guard makes the test that guards it fail.

Each case disables one guard with monkeypatch and runs its guarding test,
which must pass with the guard in place and fail without it. The citation
check is disabled once and shown to fail the test of every site that cites
evidence.
"""

from __future__ import annotations

import pytest
import test_conditional_evidence as t

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.controller import CampaignController
from carbon.challenge_readiness import admission
from carbon.challenge_readiness import conditional_evidence as ce

_TAG = ce.tag
_EXPANSIONS = admission._expansions


def _lenient_expansions(entries):
    """Accept development keys on a LOCK entry by dropping them first."""
    drop = {"kind", *ce.TAG_KEYS}
    return _EXPANSIONS([{k: v for k, v in e.items() if k not in drop} for e in entries])


def _let_tagged_pass(m):
    m.setattr(ce, "conditional_on", lambda value: [])


MUTATIONS = {
    "lock_refused_after_finding_on_the_controller": (
        lambda m: m.setattr(
            CampaignController, "_expansion_blocked", staticmethod(lambda db: False)
        ),
        t.test_lock_is_still_refused_with_an_open_finding_on_the_controller,
    ),
    "lock_refused_after_finding_on_the_admission_path": (
        lambda m: m.setattr(
            admission, "_findings", lambda entries, expansions, root: None
        ),
        t.test_lock_is_still_refused_with_an_open_finding_on_the_admission_path,
    ),
    "lock_ledger_refuses_development_entries": (
        lambda m: m.setattr(admission, "_expansions", _lenient_expansions),
        t.test_a_development_entry_never_enters_a_lock,
    ),
    "development_expansion_is_tagged": (
        lambda m: m.setattr(
            ce, "tag", lambda found, policy=ce.POLICY: _TAG([], policy)
        ),
        t.test_a_development_expansion_proceeds_and_is_tagged,
    ),
    "controller_results_are_tagged": (
        lambda m: m.setattr(ctl, "RESULT_KINDS", frozenset()),
        t.test_every_controller_result_recorded_while_a_finding_is_open_is_tagged,
    ),
    "climb_report_is_tagged": (
        lambda m: m.setattr(
            ce, "tag", lambda found, policy=ce.POLICY: _TAG([], policy)
        ),
        lambda tmp: t.test_a_climb_report_carries_the_tag(),
    ),
    "repair_releases_its_finding": (
        lambda m: m.setattr(
            CampaignController, "_repaired", lambda self, db, finding_id: False
        ),
        t.test_a_repaired_finding_leaves_later_development_expansions_untagged,
    ),
    "recurrence_reopens_a_repaired_finding": (
        lambda m: m.setattr(CampaignController, "_recur", lambda *args: None),
        t.test_a_repaired_finding_that_recurs_is_open_again,
    ),
    "citation_ladder_tested": (
        _let_tagged_pass,
        lambda tmp: t.test_the_ladder_refuses_conditional_level_evidence(
            tmp, "TESTED", "json"
        ),
    ),
    "citation_ladder_frozen": (
        _let_tagged_pass,
        lambda tmp: t.test_the_ladder_refuses_conditional_level_evidence(
            tmp, "FROZEN", "jsonl"
        ),
    ),
    "citation_accepted_proposal": (
        _let_tagged_pass,
        lambda tmp: t.test_an_accepted_proposal_cannot_be_conditional(),
    ),
    "citation_admission_report": (
        _let_tagged_pass,
        lambda tmp: t.test_admission_evidence_and_the_lock_refuse_a_conditional_result(
            tmp, "engineering_value"
        ),
    ),
    "citation_lock": (
        _let_tagged_pass,
        t.test_the_lock_refuses_conditional_evidence_it_binds,
    ),
    "citation_frozen_run": (
        _let_tagged_pass,
        t.test_a_frozen_run_cannot_cite_conditional_evidence,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_guard_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    intact, mutated = tmp_path / "intact", tmp_path / "mutated"
    intact.mkdir()
    mutated.mkdir()
    guard(intact)  # passes with the guard in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(mutated)
