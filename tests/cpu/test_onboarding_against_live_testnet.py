"""The onboarding door against real finalized chain state.

Opt-in, and skipped by default: CI must not depend on whether testnet answers,
and a test whose result turns on someone else's uptime reports on their
availability rather than on this code. Enable with

    CARBON_LIVE_TESTNET_READ=1

These assert refusals and identities, never balances. Public chain reads only -
nothing here signs, submits, or constructs a wallet, and no private key, seed
phrase or mnemonic is involved in any path it touches.

**What made this worth writing.** The registration flow had only ever been
exercised against fixtures, and a fixture proves the code agrees with the
fixture. An audit of subnet 567 on 23 September 2026 established that the
recorded miner hotkey still holds UID 1 - registered at block 8,013,851 and
still present at 8,065,348, so not pruned - which means `prepare` has a real
ALREADY_REGISTERED case to refuse rather than a synthetic one. That turned the
end-to-end path from blocked-pending-a-registration into testable without one,
and no transaction was needed to get there.
"""

import asyncio
import os

import pytest

from carbon.development_session.chain_onboarding import (
    OnboardingFailure,
    carbon_testnet_context,
    prepare,
    status,
)

#: Public, and already published in this repository's development documents.
#: Recorded at UID 1 on netuid 567; its balance is deliberately never read here.
REGISTERED_HOTKEY = "5HmVzauSQMjErYSAzPFiKXi7uN9vM1TMLLVrjdVDJxYdPTxY"

#: A well-formed address that holds no UID on this subnet.
UNREGISTERED_HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"

live = pytest.mark.skipif(
    os.environ.get("CARBON_LIVE_TESTNET_READ") != "1",
    reason="live testnet read is opt-in; set CARBON_LIVE_TESTNET_READ=1",
)


def reader():
    from carbon.chain.sdk import BittensorReader

    return BittensorReader()


@live
def test_a_registered_hotkey_reads_as_registered_and_unlocked():
    """Observed 2026-09-23: UID 1, UNLOCKED, at finalized block 8,065,348."""
    observed = asyncio.run(
        status(reader(), carbon_testnet_context(), REGISTERED_HOTKEY)
    )
    assert observed["registered"] is True
    assert observed["uid"] == 1
    assert observed["research_environment"] == "UNLOCKED"


@live
def test_prepare_refuses_a_hotkey_that_already_holds_a_uid():
    """The refusal that made a registration unnecessary.

    Worth asserting against the chain rather than a fixture: this is the case
    that decides whether anyone spends. A door that offered to prepare a second
    registration for a key already holding a UID would invite a miner to burn
    real funds for nothing, and a fixture asserting that could agree with itself
    while the live behaviour differed.
    """
    with pytest.raises(OnboardingFailure) as raised:
        asyncio.run(prepare(reader(), carbon_testnet_context(), REGISTERED_HOTKEY))
    assert raised.value.reason == "ALREADY_REGISTERED"
    assert "Nothing to prepare" in raised.value.next_action


@live
def test_an_unregistered_hotkey_stays_locked():
    """LOCKED as a gate, against real state rather than a stubbed roster."""
    observed = asyncio.run(
        status(reader(), carbon_testnet_context(), UNREGISTERED_HOTKEY)
    )
    assert observed["registered"] is False
    assert observed["research_environment"] == "LOCKED"
    assert observed.get("uid") is None


@live
def test_the_live_context_is_the_settled_one():
    """The door reads the chain the operator config validates against.

    Guards the divergence this context exists to prevent: if these ever named
    two different chains, every other assertion here would still pass while
    describing somewhere else.
    """
    from carbon.chain.models import CARBON_NETUID
    from carbon.development_testnet.operator import DEFAULT_ENDPOINT, TESTNET_GENESIS

    context = carbon_testnet_context()
    assert context.netuid == CARBON_NETUID == 567
    assert context.endpoint == DEFAULT_ENDPOINT
    assert context.genesis_hash == TESTNET_GENESIS

    snapshot = asyncio.run(reader().capture(context))
    assert snapshot.context.genesis_hash == TESTNET_GENESIS
    assert snapshot.finalized_block > 8_013_851, "UID 1's registration block"
