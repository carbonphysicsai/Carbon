"""GRAPHITE-01 phase 2 mutation checks: disabling each protection fails its test.

The pattern of `test_graphite_mutations.py`: each case switches one protection
off with monkeypatch and runs the test that guards it. The guard passes with
the protection in place and must fail without it.
"""

from __future__ import annotations

import pytest
import test_graphite_ladder as tl
import test_graphite_literature_fetch as tf
import test_graphite_method_cards as tm

from carbon.agent_campaign.graphite import ladder as gl
from carbon.agent_campaign.graphite import literature_fetch as lf
from carbon.agent_campaign.graphite import method_cards as mc
from carbon.agent_campaign.graphite import triage as tr

_CEILINGS = tr.ceilings
_PUT_CARD = mc.CardStore.put_card

MUTATIONS = {
    # The model's reply must have exactly the card fields: an injected
    # status, model or budget field rejects the extraction.
    "extraction_fields_closed": (
        lambda m: m.setattr(mc, "_closed", lambda value: type(value) is dict),
        lambda tmp: tm.test_injection_inside_an_abstract_is_data(tmp),
    ),
    # A backfill needs an exact, unexpired spending grant for Graphite.
    "grant_required": (
        lambda m: m.setattr(tr, "check_grant", lambda grant, model, now: None),
        lambda tmp: tm.test_a_backfill_refuses_without_an_exact_grant(tmp),
    ),
    # A run's money is capped at the grant's worst case.
    "run_money_cap": (
        lambda m: m.setattr(
            tr,
            "ceilings",
            lambda grant, calls: {
                **_CEILINGS(grant, calls),
                "provider_nanodollars": None,
            },
        ),
        lambda tmp: tm.test_the_spend_cap_stops_the_run_mid_backfill(tmp),
    ),
    # arXiv requests are at least 3 s apart.
    "arxiv_rate_limit": (
        lambda m: m.setattr(lf.ArxivClient, "_wait", lambda self, at_least=0.0: None),
        lambda tmp: tf.test_requests_are_at_least_three_seconds_apart(),
    ),
    # Only a card written UNCHECKED is stored.
    "cards_written_unchecked": (
        lambda m: m.setattr(
            mc.CardStore,
            "put_card",
            lambda self, card: _PUT_CARD(self, {**card, "status": mc.UNCHECKED})
            and None,
        ),
        lambda tmp: tm.test_the_agent_path_cannot_mark_a_card_checked(tmp),
    ),
    # A human check needs the person to type the card id back.
    "human_confirmation": (
        lambda m: m.setattr(mc, "_confirmed", lambda confirm, cid: True),
        lambda tmp: tm.test_a_check_needs_the_person_to_type_the_card_id(tmp),
    ),
    # An agent or model name cannot be the checker.
    "checker_not_an_agent": (
        lambda m: m.setattr(mc, "_agent_name", lambda checker: False),
        lambda tmp: tm.test_an_agent_or_model_cannot_be_the_checker(
            tmp, "graphite-reader"
        ),
    ),
    # A card naming protected material is withheld from the snapshot.
    "protected_cards_withheld": (
        lambda m: m.setattr(mc, "_withheld", lambda card: False),
        lambda tmp: tm.test_cards_that_name_protected_material_are_withheld(tmp),
    ),
    # A stall needs the registered five attempts (OWNER-GRAPHITE-02).
    "constructor_stall_limit": (
        lambda m: m.setattr(gl, "_stalled", lambda attempts: True),
        lambda tmp: tl.test_the_constructor_stall_limit_is_the_registered_five_attempts(
            tmp
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
