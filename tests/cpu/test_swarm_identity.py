"""Many agents, one miner: what parallel sessions may and may not do.

The swarm model in one line: distinct agents working for the same miner share
that miner's budget and ledger, different miners are isolated from each other,
and running more sessions multiplies nothing.

The last of those is the one worth testing hardest, because it is the one a
miner would only discover was false by being billed for it. Concurrency is a
way to get work done, not a way to get more allowance, and nothing about
opening a second connection should change what the first one was entitled to.

Section 9 case 7 of the owner handoff. `BoundPrincipal` already makes the
recorded identity structural - it is derivable only from an owner-bound adapter
and cannot be built from a string - so what these add is the *accounting*
behaviour across sessions rather than the identity itself.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_standard_mcp_adapter import make_adapter

from carbon.development_session.research_ledger import (
    VERSION,
    CampaignLedger,
)
from carbon.miner_mcp.serving import BoundPrincipal

OWNER = "alice"


def campaign(root, *, owner=OWNER, ceilings=None):
    root.mkdir(parents=True, exist_ok=True)
    ledger = CampaignLedger(root)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": ceilings,
            "elapsed_seconds": None,
            "campaign_id": "swarm-test",
            "implementation": "fixture",
            "objective": "balanced-v2",
            "sampling": "test-only",
            "control": "test-only",
            "selection": "test-only",
            "replica_policy": "three",
            "provider": "test-only",
            "owner": owner,
        }
    )
    return ledger


def spend(ledger, identity, *, owner=OWNER, trials=1):
    return ledger.reserve(
        identity,
        owner=owner,
        phase="research",
        request={"hypothesis": "h"},
        resources={"research_trials": trials},
    )


def test_two_agents_for_one_miner_share_one_ledger(tmp_path):
    """Distinct sessions, one accounting record.

    Two agents reaching the same campaign root see one another's consumption,
    because the budget belongs to the miner and not to the connection.
    """
    first = campaign(tmp_path / "shared")
    second = CampaignLedger(tmp_path / "shared")

    spend(first, "agent-one-operation")
    spend(second, "agent-two-operation")

    assert first.status(owner=OWNER)["used"]["research_trials"] == 2
    assert second.status(owner=OWNER)["used"]["research_trials"] == 2


def test_a_second_session_does_not_multiply_the_budget(tmp_path):
    """The property a miner would otherwise discover by being billed for it.

    A budget of three trials is three trials, however many agents are working.
    Asserted by exhausting it from one session and finding the other refused,
    rather than by inspecting a number - a shared counter that is read
    consistently but enforced per session would pass the weaker check.
    """
    first = campaign(tmp_path / "bounded", ceilings={"research_trials": 3})
    second = CampaignLedger(tmp_path / "bounded")

    spend(first, "op-1")
    spend(first, "op-2")
    spend(second, "op-3")

    with pytest.raises(ValueError, match="miner budget: research_trials"):
        spend(second, "op-4")
    with pytest.raises(ValueError, match="miner budget: research_trials"):
        spend(first, "op-5")


def test_replaying_an_operation_charges_once(tmp_path):
    """Retry is not a second purchase.

    An agent that loses its answer and retries with the same operation_id must
    be told what happened the first time, not charged again for it.
    """
    ledger = campaign(tmp_path / "replay", ceilings={"research_trials": 2})
    assert spend(ledger, "same-operation")["dispatch"] is True

    other_session = CampaignLedger(tmp_path / "replay")
    assert spend(other_session, "same-operation")["dispatch"] is False
    assert ledger.status(owner=OWNER)["used"]["research_trials"] == 1

    # Positive control: the refusal above is about the repeated identity, not
    # about second calls generally. A genuinely new operation still charges,
    # so a ledger that simply stopped accounting would fail here.
    assert spend(other_session, "a-different-operation")["dispatch"] is True
    assert ledger.status(owner=OWNER)["used"]["research_trials"] == 2


def test_a_different_miner_cannot_consume_another_campaign(tmp_path):
    """Different principals stay isolated.

    Not merely unable to read: unable to spend. The owner check sits on the
    reservation itself, so a second miner reaching the same root is refused
    rather than quietly accounted against the first.
    """
    ledger = campaign(tmp_path / "isolated")
    spend(ledger, "alices-operation")

    with pytest.raises(ValueError):
        spend(ledger, "alices-operation", owner="bob")

    assert ledger.status(owner="bob")["operations"] == []
    assert ledger.status(owner=OWNER)["used"]["research_trials"] == 1


def test_the_recorded_identity_is_the_campaign_owner_not_the_session(tmp_path):
    """Two adapters, one principal, one recorded identity.

    `BoundPrincipal` is derived from the adapter rather than supplied, and each
    adapter re-verifies its own owner binding, so two sessions for the same
    miner cannot record themselves as two different callers.
    """
    _first_sdk, first = make_adapter()
    _second_sdk, second = make_adapter()

    assert BoundPrincipal(first) == BoundPrincipal(second) == OWNER
    assert type(BoundPrincipal(first)) is BoundPrincipal


def test_a_second_miner_gets_a_different_bound_identity():
    _sdk, other = make_adapter(owner="bob")
    _sdk2, mine = make_adapter()
    assert BoundPrincipal(other) != BoundPrincipal(mine)
