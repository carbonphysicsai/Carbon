"""The networks Carbon may bind to: one exact row per network (F4, Chain Auditor 5 Nov; TE scope 5 Nov): testnet
(``CARBON_NETUID``) and finney (netuid 116).

A process binds to EXACTLY one row. A context is accepted only when every field equals that row: its name, chain id,
genesis hash, netuid and one of its registered endpoints (or the host's own loopback node). A mixed context
(finney's genesis with the testnet netuid, or the reverse), an unknown network or an unregistered endpoint is refused by
name. The genesis read at connect is the real identity check, so a URL alone never selects a network.

`models.CARBON_NETWORK` / `CARBON_NETUID` are the process's row (``CARBON_CHAIN_NETWORK``; testnet when unset), so
nothing moves without a configuration that names another row. Binding a row grants no authority: a finney publish still needs OWNER-WEIGHTS-AUTHORITY-01 (enforced by
`rewards.winner_decay`), the owner's signature and the Validator's D1-D4 receipts (chain prep, 5 Nov).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .models import _NETUIDS, CARBON_NETWORK

#: Public reads (Chain Auditor, 5 Nov; read again by TE 5 Nov): test.finney's genesis is the operator's long-standing
#: pin; finney's genesis is the main chain's ("Bittensor"). Both chains ran runtime spec 488 on 5 Nov.
TESTNET_GENESIS = "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105"
FINNEY_GENESIS = "0x2f0555cc76fc2840a25a6ea3b9637146806f1f44b090c175ffde2a7e5ab36c03"


class NetworkRefused(ValueError):
    """A context that is not exactly one registered row; ``code`` names why."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class NetworkRow:
    network: str
    chain_id: str
    genesis_hash: str
    netuid: int
    #: The PUBLIC endpoints a context of this network may name. The host's own node (a lite node with RPC on
    #: localhost only, chain prep §3) is accepted on every row as a loopback ``ws``/``wss`` URL (`own_node`).
    endpoints: tuple[str, ...]
    #: The operator profile's stage label for this network: the winner publication's own stage for it
    #: (`rewards.testnet_winner_publication.STAGES`, held equal by a test). None = not set, refused.
    stage: str | None


NETWORKS: dict[str, NetworkRow] = {
    "testnet": NetworkRow(
        network="testnet",
        chain_id="bittensor-official-test",
        genesis_hash=TESTNET_GENESIS,
        netuid=_NETUIDS["testnet"],
        endpoints=("wss://test.finney.opentensor.ai:443",),
        stage="PUBLIC_TESTNET_DEVELOPMENT",
    ),
    "finney": NetworkRow(
        network="finney",
        chain_id="bittensor-official-finney",
        genesis_hash=FINNEY_GENESIS,
        netuid=_NETUIDS["finney"],
        endpoints=("wss://entrypoint-finney.opentensor.ai:443",),
        stage="PUBLIC_MAINNET",
    ),
}

#: The row THIS process binds (`models.CARBON_NETWORK`, from ``CARBON_CHAIN_NETWORK``; testnet when unset).
BOUND = NETWORKS[CARBON_NETWORK]
#: The row the code was written against, and the binding when nothing is set.
DEFAULT = NETWORKS["testnet"]


def row(network: object) -> NetworkRow:
    """The registered row named ``network``; anything else is refused (``network_unregistered``)."""
    if type(network) is not str or network not in NETWORKS:
        raise NetworkRefused("network_unregistered")
    return NETWORKS[network]


def row_of_netuid(netuid: object) -> NetworkRow:
    """The one row whose netuid is ``netuid``; anything else is refused (``netuid_unregistered``)."""
    found = [r for r in NETWORKS.values() if type(netuid) is int and r.netuid == netuid]
    if len(found) != 1:
        raise NetworkRefused("netuid_unregistered")
    return found[0]


def own_node(endpoint: object) -> bool:
    """A loopback ``ws``/``wss`` endpoint with an explicit port: the host's own node, never a remote one."""
    if type(endpoint) is not str:
        return False
    try:
        url = urlsplit(endpoint)
        port = url.port
    except ValueError:
        return False
    return (
        url.scheme in ("ws", "wss")
        and url.hostname in ("127.0.0.1", "localhost", "::1")
        and port is not None
        and not url.username
        and not url.password
        and url.path in ("", "/")
        and not url.query
        and not url.fragment
    )


def check_context(
    *,
    network: object,
    chain_id: object = None,
    genesis_hash: object = None,
    netuid: object = None,
    endpoint: object = None,
) -> NetworkRow:
    """The row ``network`` names, when every given field equals it; a field passed as None is not compared (a caller
    that holds it must pass it). Refusals: ``network_unregistered``, ``network_chain_id_differs``,
    ``network_genesis_differs``, ``network_netuid_differs`` (a mixed row), ``network_endpoint_unregistered``.
    """
    bound = row(network)
    if chain_id is not None and chain_id != bound.chain_id:
        raise NetworkRefused("network_chain_id_differs")
    if genesis_hash is not None and genesis_hash != bound.genesis_hash:
        raise NetworkRefused("network_genesis_differs")
    if netuid is not None and (type(netuid) is not int or netuid != bound.netuid):
        raise NetworkRefused("network_netuid_differs")
    if (
        endpoint is not None
        and endpoint not in bound.endpoints
        and not own_node(endpoint)
    ):
        raise NetworkRefused("network_endpoint_unregistered")
    return bound


def check_genesis_at_connect(bound: NetworkRow, observed_genesis: object) -> None:
    """The connect-time identity check: the chain the endpoint answers for must be the bound row's."""
    if observed_genesis != bound.genesis_hash:
        raise NetworkRefused("network_genesis_mismatch_at_connect")
