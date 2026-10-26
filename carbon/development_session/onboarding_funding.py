"""The "Fund your wallet" step's one read: a coldkey's balance and the joining
cost, read fresh from the chain (Validator funding-door ruling, 2026-10-23).

The owner's 10-21 onboarding decision asked for very easy TAO buying, so the
page shows whether the miner's coldkey holds enough to register. Conditions:

- a fresh finalized read on every request (`carbon.chain.funding_read`),
  never cached or stored; the reply names the block it was read at;
- the cost is the wallet's to state at signing: the note says so, word for
  word, and `enough` is "at block N, before transaction fees". No fee
  estimate. TAO is the authoritative amount; "about $X" beside it comes from
  a separate, address-free price fetch (`tao_price`,
  OWNER-TAO-USD-PRICE-SOURCE-01), labelled approximate with its time, and is
  absent when the price can't be fetched;
- the address travels only in the request body to the configured chain
  reader: never in a URL, a log or to anyone else;
- on a test network (testnet, localnet) the coin is test TAO: it is free, comes from
  the faucet or from Carbon, has no price, and no dollar figure is fetched or shown
  (`test_network` in the reply tells the page which wording to use);
- the miner's local Launchpad serves it, never Carbon's public intake;
- no score, weight, KOTH, Ladder or receiver code imports this
  (`tests/invariants/test_funding_unreachable.py`).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
from types import MappingProxyType

SCHEMA = "carbon.onboarding.funding.v1"
#: One TAO in rao.
RAO = 10**9
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")
#: The owner's label for the figure (U-c decision, via the Lead).
LABEL = "current estimate; your wallet confirms the exact amount when you sign"
NOTE = (
    "Read at block {block}. Your wallet shows the cost again when you sign; "
    "that figure is the one that counts."
)


class FundingRefused(ValueError):
    """Why there is no reading, closed: a code, its HTTP status, a next step."""

    STEPS = MappingProxyType(
        {
            "address_invalid": (
                400,
                "Paste your coldkey's address (starts with 5, 47 or 48 characters).",
            ),
            "chain_not_configured": (
                409,
                "Finish Setup's network step so this machine knows which chain to read.",
            ),
            "chain_read_failed_infra": (
                503,
                "The chain couldn't be read just now; try again shortly.",
            ),
        }
    )

    def __init__(self, code):
        super().__init__(code)
        self.code = code
        self.status, self.next_step = self.STEPS[code]

    def body(self):
        return {"error": self.code, "next_step": self.next_step}


def tao(rao):
    """`rao` as a TAO amount string with all nine decimals, exactly."""
    whole, part = divmod(rao, RAO)
    return f"{whole}.{part:09d}"


def is_test_network(network):
    """Whether ``network`` is a test network, whose TAO has no price."""
    return type(network) is str and (
        "test" in network.lower() or network.lower() == "localnet"
    )


def funding(context, address, *, fetch=None, price=None):
    """The reply for `address` on `context`'s subnet, or `FundingRefused`."""
    from carbon.chain.models import ChainContext

    if type(address) is not str or not _SS58.fullmatch(address):
        raise FundingRefused("address_invalid")
    if type(context) is not ChainContext:
        raise FundingRefused("chain_not_configured")
    if fetch is None:
        from carbon.chain.funding_read import read_funding as fetch
    try:
        # A private event loop in a worker thread, as `chain.permits` reads.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            reading = pool.submit(asyncio.run, fetch(context, address)).result()
        block = reading["block"]
        balance = max(reading["free_rao"] - reading["frozen_rao"], 0)
        cost = reading["burn_rao"]
        if not all(type(v) is int and v >= 0 for v in (block, balance, cost)):
            raise ValueError
    except Exception:  # noqa: BLE001 - any provider failure is infrastructure
        raise FundingRefused("chain_read_failed_infra") from None
    return {
        "schema": SCHEMA,
        "network": context.network,
        "test_network": is_test_network(context.network),
        "netuid": context.netuid,
        "address": address,
        "balance_rao": balance,
        "balance_tao": tao(balance),
        "joining_cost_rao": cost,
        "joining_cost_tao": tao(cost),
        "enough": balance >= cost,
        "enough_words": (
            f"{'Enough' if balance >= cost else 'Not enough'} to join, at block "
            f"{block}, before transaction fees."
        ),
        "read_at_block": block,
        "label": LABEL,
        "note": NOTE.format(block=block),
        "usd": None if is_test_network(context.network) else _usd(balance, cost, price),
    }


def _usd(balance, cost, price):
    """The approximate USD amounts, or None (TAO only) when no price was
    fetched for this request. The price fetch carries no miner data."""
    from carbon.development_session import tao_price

    quote = tao_price.fetch() if price is None else price()
    if quote is None:
        return None
    return {
        "balance": tao_price.about(balance, quote),
        "joining_cost": tao_price.about(cost, quote),
        "usd_per_tao": str(quote["usd_per_tao"]),
        "fetched_at": quote["fetched_at"],
        "source": tao_price.SOURCE,
        "label": tao_price.LABEL,
    }
