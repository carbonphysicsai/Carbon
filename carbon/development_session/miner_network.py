"""The network a miner's campaign talks to, without an operator file (C-MLP-04).

A campaign needs two public facts about the network: the chain context
(Carbon's testnet and its subnet, `CARBON_NETUID`) and the publisher hotkey its signed requests
are bound to. Until C-MLP-04 both came from the operator configuration
(`carbon.development_testnet.operator`), a document only Carbon's operator can
write: it also names the publisher's coldkey, wallet, execution digests and
retention. A miner has none of that, so a miner could not finish setup.

This module gives a miner the two facts on their own:

- the chain context is `carbon_testnet_context()`, the settled constants the
  onboarding doors already read;
- the publisher is the hotkey at UID 0 of the subnet in a finalized metagraph
  snapshot. UID 0 is the subnet owner's, the publisher's (the testnet runbook
  names the publisher UID 0), and the burn UID weights go to under OD-4a.

Setup reads them once, after the miner's registration is confirmed, and
writes `miner-network.json` (owner-only) beside the profile. A campaign then
loads either that file or, where an operator runs one, the operator
configuration, through `binding`, so both paths reach the same two facts.
Nothing here holds or asks for a key.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from carbon.chain.models import CARBON_NETUID, ChainContext, identifier

SCHEMA = "carbon.miner-network.v1"
#: The UID whose hotkey publishes for the subnet: the owner's.
PUBLISHER_UID = 0


class NetworkUnavailable(ValueError):
    """The network facts could not be read or do not match Carbon's testnet."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class NetworkBinding:
    context: ChainContext
    publisher_hotkey: str
    netuid: int


def _context():
    from carbon.development_session.chain_onboarding import carbon_testnet_context

    return carbon_testnet_context()


def resolve(reader) -> tuple[NetworkBinding, int]:
    """Read the publisher from a finalized snapshot of Carbon's subnet.

    Returns the binding and the finalized block it was read at.
    """
    context = _context()
    snapshot = asyncio.run(reader.capture(context))
    owners = [p for p in snapshot.participants if p.uid == PUBLISHER_UID]
    if len(owners) != 1:
        raise NetworkUnavailable("publisher_not_on_chain")
    return (
        NetworkBinding(context, owners[0].hotkey, context.netuid),
        snapshot.finalized_block,
    )


def document(binding: NetworkBinding, block: int) -> dict:
    context = binding.context
    return {
        "schema": SCHEMA,
        "context": {
            "network": context.network,
            "endpoint": context.endpoint,
            "provider": context.provider,
            "genesis_hash": context.genesis_hash,
            "netuid": context.netuid,
        },
        "publisher_hotkey": binding.publisher_hotkey,
        "publisher_uid": PUBLISHER_UID,
        "observed_block": block,
    }


def load(path: Path) -> NetworkBinding:
    """A miner network file, checked against Carbon's own testnet constants."""
    try:
        raw = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        raise NetworkUnavailable("miner_network_unreadable") from None
    expected = _context()
    if (
        type(raw) is not dict
        or raw.get("schema") != SCHEMA
        or raw.get("publisher_uid") != PUBLISHER_UID
        or raw.get("context")
        != {
            "network": expected.network,
            "endpoint": expected.endpoint,
            "provider": expected.provider,
            "genesis_hash": expected.genesis_hash,
            "netuid": expected.netuid,
        }
    ):
        raise NetworkUnavailable("miner_network_not_carbon_testnet")
    publisher = raw.get("publisher_hotkey")
    try:
        identifier(publisher)
    except Exception:  # noqa: BLE001 - any malformed value is one refusal
        raise NetworkUnavailable("miner_network_not_carbon_testnet") from None
    return NetworkBinding(expected, publisher, expected.netuid)


def binding(*, operator_config=None, miner_network=None) -> NetworkBinding:
    """The campaign's network: the operator configuration where an operator
    runs one, otherwise the miner's own network file. Exactly one is given."""
    if (operator_config is None) == (miner_network is None):
        raise NetworkUnavailable("network_binding_required")
    if operator_config is not None:
        from carbon.development_testnet.operator import load_config

        config = load_config(Path(operator_config))
        bound = NetworkBinding(config.context, config.publisher_hotkey, config.netuid)
    else:
        bound = load(Path(miner_network))
    if bound.netuid != CARBON_NETUID:
        raise NetworkUnavailable("network_not_carbon_subnet")
    return bound


def binding_for(args) -> NetworkBinding:
    """`binding` from a campaign's arguments (either attribute may be absent)."""
    return binding(
        operator_config=getattr(args, "operator_config", None),
        miner_network=getattr(args, "miner_network", None),
    )
