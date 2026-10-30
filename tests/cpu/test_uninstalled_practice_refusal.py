"""A practice on a catalog entry that is not installed here is refused in the call itself, in the miner's own
numbers, and the plain text no longer promises a list that is not there (launch A2 and L1b).
"""

from types import SimpleNamespace

import pytest

from carbon.development_session import research_campaign as campaign
from carbon.development_session import research_tools

STRATEGY = {"challenge": {"id": "electric-motor-magnetics", "version": "1.4"}}


class Practice:
    construction_mode = "direct"

    def __init__(self, installed):
        self.installed = installed

    def backend_refusal(self, strategy):
        return self.installed


def _prepared(practice):
    return SimpleNamespace(
        composition=SimpleNamespace(executor=SimpleNamespace(practice=practice))
    )


def test_an_uninstalled_entry_is_refused_in_the_call_with_the_miners_own_count():
    with pytest.raises(campaign.PracticeNotRun) as refused:
        campaign._refuse_uninstalled_entry(
            _prepared(Practice(("v2.motor.prior_krr", "v2.motor.jno.bcat"))), STRATEGY
        )
    assert refused.value.code == "catalog_entry_not_installed"
    step = refused.value.next_step
    assert "Installed here: 2 of " in step and "retry later" in step
    assert "Nothing started" in step


def test_nothing_installed_is_its_own_code_and_an_installed_entry_passes():
    with pytest.raises(campaign.PracticeNotRun) as refused:
        campaign._refuse_uninstalled_entry(_prepared(Practice(())), STRATEGY)
    assert refused.value.code == "catalog_not_installed"
    assert (
        campaign._refuse_uninstalled_entry(_prepared(Practice(None)), STRATEGY) is None
    )


def test_a_practice_that_is_not_a_catalog_one_is_left_to_its_own_checks():
    practice = Practice(("x",))
    practice.construction_mode = "scaffold"
    assert campaign._refuse_uninstalled_entry(_prepared(practice), STRATEGY) is None


def test_the_plain_text_names_no_list_that_is_not_there():
    text = research_tools.TASK_CORRECTIONS["catalog_entry_not_installed"]
    assert "listed below" not in text
    assert text.startswith(
        "This catalog entry is not installed on this machine, so it cannot practise here. "
        "Choose an installed one, or have the miner install this one once, outside the campaign:"
    )
