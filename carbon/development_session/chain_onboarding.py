"""Getting a miner registered on the subnet, without ever touching their key.

A miner arrives with no Carbon account, no registration and whatever compute
they have. Registration is the gate for Carbon's research environment, so this
is the first thing they meet - and it has to work for someone who is not
registered yet, which is exactly who it is for.

Four functions, modelled on `carbon.reconstruction.onboarding`, whose rules this
follows rather than restates: describing a host is not authorizing it, and the
tool never mints authority. Applied to chain identity that means:

``requirements``  what registration is and what it needs. Description only.
``status``        is this address registered, and as which UID.
``prepare``       a validated, fully described, UNSIGNED registration.
``confirm``       re-query, and report the identity that resulted.

**Carbon never holds, transmits, stores, logs or requests a private key, seed
phrase or mnemonic.** Not in a browser field, not in a tool argument, not in a
log, not in an export, not temporarily. The rule is enforced structurally rather
than by discipline: there is no function here that signs, and none that accepts
key material. Not a disabled one, not a guarded one - the capability is absent,
so a reviewer can confirm the rule by grepping for what is not here.

`prepare` therefore returns a description of a transaction the miner executes in
their own tooling. Carbon states what it would be; the miner decides whether it
happens, and their wallet is the only thing that ever sees a key.

Testnet only. Mainnet enablement is a separate owner decision and no path here
anticipates one.
"""

from __future__ import annotations

from typing import Self

from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK

SCHEMA = "carbon.chain-onboarding.v1"

#: How registration happens on this subnet.
#:
#: Burned registration: the SDK's `BurnedRegister` extrinsic, whose cost is the
#: subnet's recycle parameter. Carbon does not read that parameter and does not
#: display a figure - see `COST_BASIS` for why that is a deliberate absence
#: rather than a gap.
MECHANISM = "BURNED_REGISTRATION"

#: Why no number appears anywhere in this module.
#:
#: The cost is a live chain parameter. Carbon could read it, but a figure
#: fetched here would be a second source of truth for a number the miner's own
#: wallet shows them at the moment they sign - and a stale or cached one is
#: worse than none, because it looks current. So the projection reports the
#: basis and defers the amount.
#:
#: `NOT_READ` is a different claim from `UNKNOWN` and the distinction is
#: deliberate. `UNKNOWN` says Carbon looked and could not tell, which implies a
#: query that failed. `NOT_READ` says Carbon did not ask. Only the second is
#: true here, and a reader deciding how much to trust this surface should be
#: able to tell them apart.
COST_BASIS = "SUBNET_RECYCLE_PARAMETER"
COST_VALUE = "NOT_READ"


class OnboardingFailure(Exception):
    """Closed, actionable failure. Never carries a provider message or a key."""

    def __init__(self, reason: str, *, next_action: str):
        super().__init__(reason)
        self.reason = reason
        self.next_action = next_action

    def body(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "ok": False,
            "reason": self.reason,
            "next_action": self.next_action,
        }


#: The base58 alphabet an ss58 address is written in. Excludes 0, O, I and l,
#: which is why a validator can be positive rather than merely "not obviously
#: wrong": anything outside this set is not an address, whatever else it is.
BASE58 = frozenset("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def _phrase_shaped(value: str) -> bool:
    """Does this look like a recovery phrase, however it was separated?

    Checked on separators generally rather than on spaces alone. A miner pastes
    what their wallet showed them, and wallets render phrases space-separated,
    newline-separated, comma-separated and numbered. Only the first was caught
    before, and the rest fell through to the generic refusal - which is the path
    least likely to be handled carefully downstream, and the one a logger would
    most naturally record its input on.

    Deliberately shape-only: no dictionary, no entropy check, no attempt to
    decide whether it is a *valid* phrase. The question is whether to refuse it
    untouched, and word-shaped input in an address field earns that either way.
    """
    import re

    words = [w for w in re.split(r"[^A-Za-z]+", value) if w]
    return len(words) >= 4 and all(3 <= len(w) <= 8 for w in words)


class PublicAddress(str):
    """An ss58 address that has been validated. Construction *is* validation.

    A distinct type rather than a string plus a flag, for the same reason a
    verification-only type beats a boolean: a flag is a convention that survives
    until someone constructs the object differently, while a type that cannot be
    built from unvalidated input fails at the point of the mistake with nothing
    to flip.

    That is what makes `call_record` structural. It requires this type, so an
    unvalidated string is not merely rejected - it is not the right kind of
    thing, and the error lands where the mistake was made rather than wherever
    the value eventually gets written.

    It subclasses `str` so that everything downstream - the metagraph lookup,
    the JSON response - keeps treating it as the address it is, while the one
    place that must not accept a bare string can still tell the difference.
    """

    __slots__ = ()

    def __new__(cls, value: object) -> Self:
        if type(value) not in (str, cls):
            raise OnboardingFailure(
                "INVALID_ADDRESS",
                next_action=(
                    "Supply the ss58 address of the hotkey you want registered."
                ),
            )
        if not 46 <= len(value) <= 50 or any(
            character not in BASE58 for character in value
        ):
            raise OnboardingFailure(
                "INVALID_ADDRESS",
                next_action=(
                    "Supply the ss58 address of the hotkey you want registered."
                ),
            )
        return super().__new__(cls, value)


def _address(value: object) -> PublicAddress:
    """An ss58 address is public. Anything key-shaped is refused on sight.

    Phrase shape is checked first so that a pasted recovery phrase earns the
    specific refusal rather than the generic one. Everything that survives that
    is handed to `PublicAddress`, whose construction is the validation - so a
    value returned from here is a public address by construction, and it is the
    only thing anything downstream is ever given.

    No branch echoes its input.
    """
    if type(value) is str and _phrase_shaped(value):
        raise OnboardingFailure(
            "REFUSED_KEY_MATERIAL",
            next_action=(
                "That looks like a recovery phrase. Carbon never accepts one, "
                "and it has not been stored or logged. Supply only the public "
                "ss58 address of your hotkey."
            ),
        )
    return PublicAddress(value)


def call_record(operation: str, *, address: PublicAddress | None, outcome: str) -> dict:
    """The per-call record for an onboarding call, safe by construction.

    Written before the logging surface that will consume it exists.
    Retrofitting redaction onto a log that already captures arguments is how
    secrets end up in retained records - the log is written, the arguments look
    innocuous, and the one caller who pasted the wrong thing is already
    persisted by the time anyone looks.

    So the contract is not "redact the bad values" but "only validated values
    are recordable", and it is enforced by the type rather than by a re-check
    here. A bare string is refused because it is the wrong kind of thing, not
    because this function inspected it and disapproved.

    A refused call records its reason code and no input at all: there is nothing
    about the input worth keeping and something about it worth never keeping.
    """
    if address is not None and type(address) is not PublicAddress:
        raise OnboardingFailure(
            "UNRECORDABLE",
            next_action=(
                "Only a validated public address is recordable. Pass the value "
                "returned by validation, not the caller's input."
            ),
        )
    return {
        "schema": SCHEMA,
        "operation": operation,
        "address": str(address) if address is not None else None,
        "outcome": outcome,
        "arguments": "NOT_RECORDED",
    }


def requirements() -> dict[str, object]:
    """What registration is, what it needs, and where the cost is visible.

    Description only: reading this registers nothing and grants nothing.
    """
    return {
        "schema": SCHEMA,
        "network": CARBON_NETWORK,
        "netuid": CARBON_NETUID,
        "mechanism": MECHANISM,
        "cost": {
            "basis": COST_BASIS,
            "value": COST_VALUE,
            "shown_by": "your own wallet tooling, at the moment you sign",
            "note": (
                "Carbon does not query or display the current amount. NOT_READ "
                "means Carbon did not ask, which is not the same as being "
                "unable to find out."
            ),
        },
        "you_need": [
            "a wallet you control, with a hotkey and a coldkey",
            "enough balance on the coldkey to cover the recycle amount",
        ],
        "carbon_never": [
            "holds, transmits, stores, logs or requests a private key",
            "holds, transmits, stores, logs or requests a seed phrase or mnemonic",
            "signs a transaction on your behalf",
            "submits on behalf of someone who is not registered",
        ],
        "you_sign": "in your own tooling. Carbon prepares and describes; you decide.",
        "gate": (
            "Registration is the gate for Carbon's research environment. Off-platform "
            "research with any tools and compute you choose, and submitting a strategy "
            "you arrived at that way, are unaffected by it."
        ),
    }


async def status(reader, context, address: object) -> dict[str, object]:
    """Is this address registered on the subnet, and as which UID.

    Read-only, on public chain state, through the existing reader. No new query
    is introduced and nothing is written.
    """
    from carbon.chain.models import ChainFailure

    hotkey = _address(address)
    if context.netuid != CARBON_NETUID or context.network != CARBON_NETWORK:
        raise OnboardingFailure(
            "WRONG_NETWORK",
            next_action=(
                f"Point the operator configuration at {CARBON_NETWORK} "
                f"subnet {CARBON_NETUID}."
            ),
        )
    try:
        observed = await reader.capture(context)
    except ChainFailure as failure:
        raise OnboardingFailure(
            "CHAIN_UNAVAILABLE",
            next_action=(
                "The chain could not be read just now. Retry; nothing was "
                "changed and no registration was attempted."
            ),
        ) from failure
    participant = observed.resolve(hotkey)
    if participant is None:
        return {
            "schema": SCHEMA,
            "ok": True,
            "registered": False,
            "network": CARBON_NETWORK,
            "netuid": CARBON_NETUID,
            "hotkey": hotkey,
            "uid": None,
            "research_environment": "LOCKED",
            "next_action": (
                "Not registered on this subnet. Call prepare to get the exact "
                "registration to execute in your own tooling."
            ),
        }
    return {
        "schema": SCHEMA,
        "ok": True,
        "registered": True,
        "network": CARBON_NETWORK,
        "netuid": CARBON_NETUID,
        "hotkey": hotkey,
        "uid": participant.uid,
        "registered_at_block": participant.registered_at,
        "observed_block": observed.finalized_block,
        "research_environment": "UNLOCKED",
        "next_action": "Registered. Choose your research compute.",
    }


async def prepare(reader, context, address: object) -> dict[str, object]:
    """Describe the registration to execute. Unsigned, and never signed here.

    Returns what the transaction *is* - extrinsic, network, subnet, hotkey - so
    the miner can execute exactly that in their own tooling and recognise it
    when their wallet shows it. Carbon builds no transaction object, holds no
    key and submits nothing.

    Validated first: an address already registered does not need this, and a
    misconfigured network would describe a registration on the wrong subnet.
    """
    current = await status(reader, context, address)
    if current["registered"]:
        raise OnboardingFailure(
            "ALREADY_REGISTERED",
            next_action=(
                f"This hotkey already holds UID {current['uid']} on subnet "
                f"{CARBON_NETUID}. Nothing to prepare."
            ),
        )
    return {
        "schema": SCHEMA,
        "ok": True,
        "signed": False,
        "signed_by_carbon": False,
        "extrinsic": "BurnedRegister",
        "network": CARBON_NETWORK,
        "netuid": CARBON_NETUID,
        "hotkey": current["hotkey"],
        "cost": {
            "basis": COST_BASIS,
            "value": COST_VALUE,
            "shown_by": "your wallet, before you confirm",
        },
        "execute_in": "your own wallet tooling",
        "carbon_did_not": [
            "sign this",
            "hold or request any key, seed phrase or mnemonic",
            "submit anything to the chain",
        ],
        "next_action": (
            "Execute this registration in your own tooling, then call confirm."
        ),
    }


async def confirm(reader, context, address: object) -> dict[str, object]:
    """Re-query after the miner has executed, and report what resulted.

    Deliberately the same read as `status`: confirmation is an observation of
    public chain state, not a receipt Carbon issues. If the registration did not
    land, this says so rather than reporting success optimistically.
    """
    current = await status(reader, context, address)
    if not current["registered"]:
        return {
            **current,
            "confirmed": False,
            "next_action": (
                "No registration is visible for this hotkey yet. If you have "
                "just executed it, the chain may not have finalised the block; "
                "retry shortly. Nothing here retries or submits for you."
            ),
        }
    return {
        **current,
        "confirmed": True,
        "next_action": "Registered. The research environment is unlocked.",
    }
