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


def _address(value: object) -> str:
    """An ss58 address is public. Anything key-shaped is refused on sight.

    The length and alphabet bounds are ordinary input validation. The mnemonic
    check is not: it exists so that a miner who pastes the wrong thing into the
    wrong box gets a refusal instead of having their seed phrase travel into a
    request, a log or an error message. It refuses on shape alone and never
    echoes what it saw.
    """
    if type(value) is not str:
        raise OnboardingFailure(
            "INVALID_ADDRESS",
            next_action="Supply the ss58 address of the hotkey you want registered.",
        )
    # Shape-checked before the length bound, deliberately. A recovery phrase is
    # longer than an address, so checking length first would answer a pasted
    # seed phrase with a generic "invalid address" - and the specific refusal is
    # the entire point of this branch.
    if len(value.split()) > 1:
        raise OnboardingFailure(
            "REFUSED_KEY_MATERIAL",
            next_action=(
                "That looks like a seed phrase. Carbon never accepts one. "
                "Supply only the public ss58 address."
            ),
        )
    if not 32 <= len(value) <= 64 or not value.isalnum():
        raise OnboardingFailure(
            "INVALID_ADDRESS",
            next_action="Supply the ss58 address of the hotkey you want registered.",
        )
    return value


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
