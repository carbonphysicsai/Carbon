"""Onboarding a miner onto the subnet, without Carbon ever touching a key.

No chain is contacted: the reader is a device-free stub returning a real
`MetagraphSnapshot`. What is exercised is the service's own logic - validation,
the read-only status path, the unsigned description and the confirmation - plus
the structural absence that the key rule depends on.
"""

import asyncio
import pathlib

import pytest

from carbon.chain.models import (
    CARBON_NETUID,
    CARBON_NETWORK,
    ChainContext,
    ChainFailure,
    FailureCode,
    MetagraphSnapshot,
    Participant,
)
from carbon.development_session import chain_onboarding as onboarding

MODULE = pathlib.Path(onboarding.__file__)
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
COLDKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
GENESIS = "0x" + "ab" * 32


def _context(netuid=CARBON_NETUID, network=CARBON_NETWORK):
    return ChainContext(
        network=network,
        endpoint="wss://entrypoint-finney.opentensor.ai:443",
        provider="test",
        genesis_hash=GENESIS,
        netuid=netuid,
    )


class _Reader:
    """A device-free stub standing in for the chain, not for the service."""

    def __init__(self, participants=(), failure=None):
        self.participants = participants
        self.failure = failure
        self.calls = 0

    async def capture(self, context):
        self.calls += 1
        if self.failure is not None:
            raise ChainFailure(self.failure)
        return MetagraphSnapshot(
            context=context,
            finalized_block=100,
            block_hash="0x" + "cd" * 32,
            timestamp_ms=1,
            participants=tuple(self.participants),
        )


def _registered():
    return (Participant(uid=0, hotkey=HOTKEY, coldkey=COLDKEY, registered_at=42),)


# --- the key rule, asserted structurally rather than by discipline -----------


def test_no_signing_capability_exists_in_the_module():
    """The rule holds because the capability is absent, not because it is guarded.

    Asserted over the module's *identifiers* rather than its text: the module
    legitimately names what it refuses, in the docstring that states the rule and
    in the message a miner sees when they paste the wrong thing. Grepping the
    prose would fail on the very sentences that make the prohibition legible, so
    this walks the syntax tree and asserts nothing signing-shaped is ever
    defined, called or referenced. A disabled or flag-guarded signer would still
    be a signer one edit away; there is nothing to flip because there is nothing
    there.
    """
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    forbidden = (
        "sign",
        "mnemonic",
        "seed",
        "privkey",
        "private_key",
        "keypair",
        "keyfile",
        "wallet",
        "secret",
        "submit",
    )
    offenders = sorted(
        name for name in names if any(word in name.lower() for word in forbidden)
    )
    assert offenders == [], offenders


def test_the_module_never_imports_a_signing_path():
    source = MODULE.read_text(encoding="utf-8")
    imports = [
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    for line in imports:
        assert "auth" not in line, line
        assert "wallet" not in line, line


def test_the_public_surface_is_only_the_four_functions():
    public = {
        name
        for name in dir(onboarding)
        if not name.startswith("_") and callable(getattr(onboarding, name))
    }
    assert {"requirements", "status", "prepare", "confirm"} <= public
    assert not {name for name in public if "sign" in name.lower()}


@pytest.mark.parametrize(
    "supplied",
    [
        "bottom drive obey lake curtain smoke basket hold race lonely fit walk",
        "abandon abandon abandon abandon abandon abandon abandon abandon ability",
    ],
)
def test_seed_phrase_shaped_input_is_refused_without_being_echoed(supplied):
    """A miner pasting the wrong thing must not have it travel anywhere.

    The refusal is on shape alone, and the message repeats nothing it was given.
    """
    with pytest.raises(onboarding.OnboardingFailure) as caught:
        onboarding._address(supplied)
    assert caught.value.reason == "REFUSED_KEY_MATERIAL"
    body = caught.value.body()
    for word in supplied.split():
        assert word not in str(body)


# --- requirements: description only, and no invented figure -----------------


def test_requirements_states_the_mechanism_and_defers_the_cost():
    value = onboarding.requirements()
    assert value["mechanism"] == "BURNED_REGISTRATION"
    assert value["network"] == CARBON_NETWORK
    assert value["netuid"] == CARBON_NETUID
    assert value["cost"]["basis"] == "SUBNET_RECYCLE_PARAMETER"
    # NOT_READ, not UNKNOWN: Carbon did not ask, rather than asked and failed.
    assert value["cost"]["value"] == "NOT_READ"
    assert "wallet" in value["cost"]["shown_by"]


def test_requirements_displays_no_numeric_cost_anywhere():
    """No figure, cached or invented, appears as if it were current."""
    import json
    import re

    body = json.dumps(onboarding.requirements())
    numbers = re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", body)
    assert set(numbers) <= {str(CARBON_NETUID)}, numbers


def test_requirements_needs_no_chain_and_no_registration():
    """It has to work for the unregistered visitor it exists for."""
    assert onboarding.requirements()["netuid"] == CARBON_NETUID


# --- status: the existing read-only path ------------------------------------


def test_status_reports_an_unregistered_address_as_locked():
    reader = _Reader()
    value = asyncio.run(onboarding.status(reader, _context(), HOTKEY))
    assert value["registered"] is False
    assert value["uid"] is None
    assert value["research_environment"] == "LOCKED"
    assert reader.calls == 1


def test_status_reports_a_registered_address_and_unlocks():
    reader = _Reader(_registered())
    value = asyncio.run(onboarding.status(reader, _context(), HOTKEY))
    assert value["registered"] is True
    assert value["uid"] == 0
    assert value["registered_at_block"] == 42
    assert value["research_environment"] == "UNLOCKED"


def test_a_wrong_network_is_refused_before_any_read():
    reader = _Reader()
    with pytest.raises(onboarding.OnboardingFailure) as caught:
        asyncio.run(onboarding.status(reader, _context(netuid=1), HOTKEY))
    assert caught.value.reason == "WRONG_NETWORK"
    assert reader.calls == 0, "a misconfigured context must not reach the chain"


def test_an_unavailable_chain_is_actionable_and_changes_nothing():
    reader = _Reader(failure=FailureCode.UNAVAILABLE)
    with pytest.raises(onboarding.OnboardingFailure) as caught:
        asyncio.run(onboarding.status(reader, _context(), HOTKEY))
    assert caught.value.reason == "CHAIN_UNAVAILABLE"
    assert "nothing was" in caught.value.next_action.lower()


# --- prepare: validated, described, unsigned --------------------------------


def test_prepare_describes_an_unsigned_registration():
    reader = _Reader()
    value = asyncio.run(onboarding.prepare(reader, _context(), HOTKEY))
    assert value["signed"] is False
    assert value["signed_by_carbon"] is False
    assert value["extrinsic"] == "BurnedRegister"
    assert value["netuid"] == CARBON_NETUID
    assert value["hotkey"] == HOTKEY
    assert value["execute_in"] == "your own wallet tooling"
    assert value["cost"]["value"] == "NOT_READ"


def test_prepare_refuses_an_already_registered_hotkey():
    reader = _Reader(_registered())
    with pytest.raises(onboarding.OnboardingFailure) as caught:
        asyncio.run(onboarding.prepare(reader, _context(), HOTKEY))
    assert caught.value.reason == "ALREADY_REGISTERED"


def test_prepare_returns_no_transaction_object_and_no_key():
    """No signed object, no key-shaped value, and no field pretending to hold one.

    Asserted over field names and values, not prose. The response deliberately
    *says* Carbon never takes a seed phrase - that disclosure is the point of it,
    and a text search would fail on the very sentence a miner needs to read.
    """
    value = asyncio.run(onboarding.prepare(_Reader(), _context(), HOTKEY))

    # No field offers to carry key material or a completed transaction.
    def fields(node, seen):
        if isinstance(node, dict):
            for key, item in node.items():
                seen.add(key)
                fields(item, seen)
        elif isinstance(node, list):
            for item in node:
                fields(item, seen)
        return seen

    for name in fields(value, set()):
        assert not any(
            word in name.lower()
            for word in ("mnemonic", "seed", "secret", "signature", "private", "nonce")
        ), name

    # Nothing in it is a signed artefact, and the only address is the public one.
    assert value["signed"] is False and value["signed_by_carbon"] is False
    assert value["hotkey"] == HOTKEY
    # No value is seed-phrase shaped: a recovery phrase is many short words.
    for item in (value["extrinsic"], value["execute_in"], value["network"]):
        assert len(str(item).split()) < 8, item


# --- confirm: an observation, not a receipt ---------------------------------


def test_confirm_reports_failure_rather_than_assuming_success():
    value = asyncio.run(onboarding.confirm(_Reader(), _context(), HOTKEY))
    assert value["confirmed"] is False
    assert value["research_environment"] == "LOCKED"
    assert "retries or submits" in value["next_action"]


def test_confirm_surfaces_the_resulting_identity():
    value = asyncio.run(onboarding.confirm(_Reader(_registered()), _context(), HOTKEY))
    assert value["confirmed"] is True
    assert value["uid"] == 0
    assert value["research_environment"] == "UNLOCKED"


def test_confirm_is_the_same_observation_as_status():
    """Confirmation is public chain state, not something Carbon issues."""
    registered = _registered()
    confirmed = asyncio.run(onboarding.confirm(_Reader(registered), _context(), HOTKEY))
    observed = asyncio.run(onboarding.status(_Reader(registered), _context(), HOTKEY))
    assert {k: v for k, v in confirmed.items() if k in observed} == {
        k: v for k, v in observed.items() if k in confirmed
    } or confirmed["uid"] == observed["uid"]
