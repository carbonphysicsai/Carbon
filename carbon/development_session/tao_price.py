"""The approximate TAO/USD price for the "Fund your wallet" step
(OWNER-TAO-USD-PRICE-SOURCE-01, 342f5ab7f; Validator funding-door correction).

TAO stays the authoritative amount. This adds "about $X" from CoinGecko's free
public price, labelled approximate with the time it was fetched:

- one fetch per request, never cached: no stale price is ever shown;
- the request names only the coin and the currency: no address, hotkey or any
  miner data, and it is a separate call from the chain read;
- when the price can't be fetched, there is no USD at all (TAO only), never
  an invented figure;
- no score, weight, KOTH or Ladder code loads this
  (`tests/invariants/test_funding_unreachable.py`).
"""

from __future__ import annotations

import datetime
import json
import urllib.request
from decimal import Decimal, InvalidOperation

SOURCE = "CoinGecko"
URL = "https://api.coingecko.com/api/v3/simple/price?ids=bittensor&vs_currencies=usd"
LABEL = "approximate"
#: Read bound: the answer is one number.
MAX_BYTES = 4096


def fetch(*, timeout=5.0, opener=urllib.request.urlopen, now=None):
    """`{"usd_per_tao": Decimal, "fetched_at": ISO time}`, or None when the
    price can't be fetched or read."""
    try:
        with opener(URL, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None
        value = json.loads(raw)["bittensor"]["usd"]
        if type(value) not in (int, float) or isinstance(value, bool):
            return None
        price = Decimal(repr(value))
        if not price.is_finite() or price <= 0:
            return None
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation):
        return None
    moment = now() if now is not None else datetime.datetime.now(datetime.UTC)
    return {
        "usd_per_tao": price,
        "fetched_at": moment.replace(microsecond=0).isoformat(),
    }


def about(rao, price):
    """`rao` at `price` as "about $1,234.56"."""
    usd = (Decimal(rao) / Decimal(10**9) * price["usd_per_tao"]).quantize(
        Decimal("0.01")
    )
    return f"about ${usd:,}"
