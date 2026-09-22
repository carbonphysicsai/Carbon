"""What a miner is told about their own spending.

The decision is that Carbon does not control a miner's spending. The part of it
that can go quietly wrong is not the enforcement but the *reporting*: a surface
that fills in a number where the miner set no cap has invented a limit they
never chose, and it will read as Carbon's limit to everyone who sees it after.

So these assert the absence. Where there is no budget there is no figure - not
a large one, not a zero, not the old development ceiling - and Carbon's own
service capacity is reported under its own name so the two can never be read as
one thing.
"""

import json

import pytest

from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DIMENSIONS,
    NO_BUDGET,
    SERVICE_LIMITS,
    VERSION,
    CampaignLedger,
)

OWNER = "alice"


def campaign(tmp_path, *, ceilings=None, elapsed_seconds=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    ledger = CampaignLedger(tmp_path)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": ceilings,
            "elapsed_seconds": elapsed_seconds,
            "campaign_id": "test-only",
            "implementation": "fixture",
            "objective": "balanced-v2",
            "sampling": "test-only",
            "control": "test-only",
            "selection": "test-only",
            "replica_policy": "three",
            "provider": "test-only",
            "owner": OWNER,
        }
    )
    return ledger


def test_no_budget_reports_no_figure(tmp_path):
    """A miner who set no budget is told they set none, not told a number."""
    status = campaign(tmp_path).status(owner=OWNER)
    assert status["budget"] is None
    assert status["elapsed_limit_seconds"] is None


def test_carbon_service_capacity_is_reported_under_its_own_name(tmp_path):
    """Carbon's infrastructure and the miner's money are different things.

    Named separately so a service limit can never be read as a cap on what the
    miner may spend, which is the confusion the decision exists to prevent.
    """
    status = campaign(tmp_path).status(owner=OWNER)
    assert status["carbon_service_limits"] == SERVICE_LIMITS
    assert "reference_invocations" not in (status["budget"] or {})


def test_a_budget_the_miner_set_is_reported_exactly_as_they_set_it(tmp_path):
    chosen = {"provider_nanodollars": 5_000_000, "research_trials": 3}
    status = campaign(tmp_path, ceilings=chosen).status(owner=OWNER)
    assert status["budget"] == chosen


def test_the_old_development_ceilings_never_appear_as_a_miner_budget(tmp_path):
    """The specific regression: development fixtures leaking in as product limits.

    The provider ceiling was one dollar and the wall clock was eight hours.
    Those bound Carbon's own experiments and must never describe a miner.
    """
    status = campaign(tmp_path).status(owner=OWNER)
    rendered = json.dumps(status, default=str)
    assert str(DEVELOPMENT_CEILINGS["provider_nanodollars"]) not in rendered
    assert status["budget"] != DEVELOPMENT_CEILINGS


def test_an_uncapped_dimension_has_no_remaining_figure(tmp_path):
    """There is nothing remaining *of* a cap that does not exist."""
    from carbon.development_session.research_report import render_status

    value = render_status(campaign(tmp_path), owner=OWNER)
    assert set(value["remaining"].values()) == {None}


def test_remaining_is_a_number_once_the_miner_sets_a_budget(tmp_path):
    from carbon.development_session.research_report import render_status

    value = render_status(
        campaign(tmp_path, ceilings={"research_trials": 9}), owner=OWNER
    )
    assert value["remaining"]["research_trials"] == 9


def test_the_sentinel_cannot_be_mistaken_for_a_limit():
    """A stand-in number would read as a limit to the next person.

    Asserted on the type rather than on a value: `NO_BUDGET` answers no
    comparison and no truth test, so a forgotten skip fails at the mistake.
    """
    with pytest.raises(TypeError):
        _ = 1 > NO_BUDGET
    with pytest.raises(TypeError):
        _ = NO_BUDGET > 1
    with pytest.raises(TypeError):
        bool(NO_BUDGET)
    assert not isinstance(NO_BUDGET, int)


def test_a_budget_is_whatever_number_the_miner_chose(tmp_path):
    """No floor and no ceiling: not Carbon's call, in either direction.

    A cap far above every former development ceiling is accepted, and so is a
    very small one. Carbon has no opinion about either.
    """
    huge = DEVELOPMENT_CEILINGS["provider_nanodollars"] * 1000
    assert campaign(tmp_path / "huge", ceilings={"provider_nanodollars": huge}).status(
        owner=OWNER
    )["budget"] == {"provider_nanodollars": huge}
    assert campaign(tmp_path / "tiny", ceilings={"provider_nanodollars": 1}).status(
        owner=OWNER
    )["budget"] == {"provider_nanodollars": 1}


def test_an_incoherent_budget_is_still_refused(tmp_path):
    """Declining to cap a miner is not declining to validate input."""
    for bad in ({"provider_nanodollars": -1}, {"not_a_resource": 5}):
        with pytest.raises(ValueError):
            campaign(tmp_path / str(abs(hash(str(bad)))), ceilings=bad)


def test_storage_is_the_miners_to_cap_and_not_carbons_to_limit():
    """The comment in SERVICE_LIMITS, written as a check instead of prose.

    `check_storage` measures the campaign root on the executing host - the
    miner's own machine or their rented box - and no retained byte is accounted
    against Carbon anywhere. So storage is miner-side, and adding it back to
    Carbon's service capacity would silently reintroduce a cap on their own
    disk. That belongs in a test rather than in a sentence someone has to read.
    """
    assert "retained_bytes" not in SERVICE_LIMITS
    assert "retained_bytes" in DIMENSIONS


def test_a_miner_can_still_cap_their_own_storage(tmp_path):
    """Removing Carbon's cap is not removing the miner's.

    Someone running unattended overnight may well want "stop at 50GB", and it
    would be arbitrary if they could bound dollars and hours but not disk. So
    storage is an ordinary dimension: uncapped by default, binding when set.
    """
    ledger = campaign(tmp_path / "capped", ceilings={"retained_bytes": 4096})
    assert ledger.status(owner=OWNER)["budget"] == {"retained_bytes": 4096}
    with pytest.raises(ValueError, match="miner budget: retained_bytes"):
        ledger.check_storage(1024**3)

    # And an uncapped campaign is not quietly held to some other number.
    campaign(tmp_path / "uncapped").check_storage(1024**4)


def test_dispatch_without_a_campaign_refuses_with_a_next_action(tmp_path):
    """Dispatch needs a campaign. It does not need a budget.

    The distinction is the whole tier model: registration opens the research
    environment, a campaign is what work is accounted against, and a budget is
    optional and blocks nothing. So the refusal names the campaign, offers the
    next usable step, and says plainly that a budget is not what is missing -
    because a miner who reads "no envelope" will go and set a budget and still
    be stuck.
    """
    import asyncio
    from types import SimpleNamespace

    from carbon.development_session.research_tools import PREFIX, ResearchMinerTools

    sdk = ResearchMinerTools(
        connection=object(),
        wrapper=object(),
        composition=SimpleNamespace(executor=SimpleNamespace(owner=OWNER)),
        ledger=None,
        owner=OWNER,
    )
    from carbon.development_session.research_tools import PreDispatchRefusal

    # Moved with the contract. This asserted a ValueError carrying everything in
    # its message; the refusal is now a distinct type so the transport can tell
    # "nothing was dispatched" from "something might have been", and the next
    # action is a field rather than prose to be parsed back out.
    with pytest.raises(PreDispatchRefusal) as raised:
        asyncio.run(
            sdk.call(
                PREFIX + "start_research_task",
                {"kind": "practice"},
                "operation-without-a-campaign",
            )
        )
    assert raised.value.reason == "NO_CAMPAIGN"
    # It names no tool, because no operation creates a campaign. An instruction
    # the caller cannot follow is worse than saying so.
    assert "creates one" in raised.value.next_action
    assert "budget is optional" in raised.value.next_action.lower()


def test_refused_feedback_is_journalled_only_when_a_campaign_exists(tmp_path):
    """A journal entry belongs to a campaign; the feedback belongs to the miner.

    Someone registered but not yet running a campaign can still learn why a
    request was refused. Losing the durable copy is correct - there is nothing
    to write it to - but losing the answer would not be.
    """
    from types import SimpleNamespace

    from carbon.development_session.research_tools import ResearchMinerTools

    sdk = ResearchMinerTools(
        connection=object(),
        wrapper=object(),
        composition=SimpleNamespace(executor=SimpleNamespace(owner=OWNER)),
        ledger=None,
        owner=OWNER,
    )
    result = sdk.rejected(
        "start_research_task",
        {"hypothesis": "h", "expected_effect": "e"},
        "identity-1",
    )
    assert result["status"] == "REJECTED_BEFORE_DISPATCH"
    assert result["reason"] == "contract_incompatibility"


def test_only_an_agent_can_reach_the_no_campaign_refusal():
    """The refusal is written for an agent because only an agent gets there.

    A human filling the launch wizard receives a campaign as a consequence of
    launching; they never meet it as a separate object. So if the browser path
    could produce "no campaign", the surface would have offered dispatch before
    the thing dispatch requires, and the message would be papering over a flow
    bug rather than reporting a state.

    Pinned structurally: `ResearchMinerTools` is entered only through the MCP
    adapter, and the browser's runner never touches the sdk. Asserted over the
    source of both doors, so a future edit that wires the browser straight into
    the sdk fails here and has to decide what a person should be told.
    """
    from pathlib import Path

    runner = Path("scripts/dev/miner_launchpad/runner.py").read_text()
    controller = Path("scripts/dev/miner_launchpad/controller.py").read_text()
    for door in (runner, controller):
        assert "ResearchMinerTools" not in door
        assert "research_tools" not in door

    adapter = Path("carbon/miner_mcp/standard.py").read_text()
    assert "_sdk.call(" in adapter, "the MCP door is the one that does reach it"
