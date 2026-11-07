"""R89: the direct door's request buckets per verified funder group (Validator-2 6 Nov 09:16 option b;
Release Architect 11:31 + Validator-2 11:32: one `group()` for R89 and OWNER-PROBING-COUNTERS-01 (a)).

Today the direct door serves loopback only, so the shared intake's peer bucket sees one address and every
miner's POST shares one bucket. With a `request_buckets` block configured, a POST is charged instead to:

- the GUARD (one, shared): before the body is read, for a POST that cannot be attributed (no or malformed
  signing header, or a claimed hotkey not registered in the latest snapshot); and after verification, for
  every POST that failed it (bad signature, stale or replayed nonce, wrong context);
- its GROUP's request bucket: only after the request verified over a fresh nonce, so a forged or replayed
  request naming a member's hotkey charges the guard and never the group;
- its GROUP's chunk bucket, for a verified continuation chunk (`stage_research_source` at offset > 0), so an
  upload never takes the tokens a submit needs.

Before the body is read, a POST that names a registered hotkey is only PEEKED: if neither of its group's
buckets holds a token it is refused at once (what the real hotkey would be told anyway); nothing is charged.

The values are the owner's (decision #10, with the security acceptance). None is defaulted here: a block
with any value missing, null, "HUMAN_INPUT", non-numeric or not positive refuses to start the door.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict

KINDS = ("guard", "group", "chunks")
#: At most this many keyed buckets per kind; the least recently seen is evicted (as `PeerLimits`). Keys are
#: verified funder groups, which cost a registration each, so eviction is not a cheap reset.
MAX_KEYS = 4096
GUARD_KEY = "guard"


HOTKEY_HEADER = "x-bittensor-hotkey"


def claimed_hotkey(headers):
    """The hotkey a request's signing header CLAIMS (unverified), or None when absent, repeated or malformed."""
    if not hasattr(headers, "items"):
        return None
    found = [v for k, v in headers.items() if type(k) is str and k.lower() == HOTKEY_HEADER]
    if len(found) != 1 or type(found[0]) is not str:
        return None
    value = found[0]
    return value if 1 <= len(value) <= 64 and value.isascii() and value.isalnum() else None


class RequestBucketsUnset(ValueError):
    """The configured block does not carry every value the owner sets."""

    code = "direct_intake_request_buckets_unset"


def _rate(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _burst(value):
    return type(value) is int and value >= 1


def values(block):
    """The validated `{kind: (rate_per_s, burst)}` of a configured block, or `RequestBucketsUnset`."""
    if type(block) is not dict or set(block) != set(KINDS):
        raise RequestBucketsUnset("request_buckets needs exactly: " + ", ".join(KINDS))
    out = {}
    for kind in KINDS:
        entry = block[kind]
        if (
            type(entry) is not dict
            or set(entry) != {"rate_per_s", "burst"}
            or not _rate(entry["rate_per_s"])
            or not _burst(entry["burst"])
        ):
            raise RequestBucketsUnset(f"request_buckets.{kind}: rate_per_s > 0 and burst >= 1 are owner values")
        out[kind] = (float(entry["rate_per_s"]), entry["burst"])
    return out


class _Buckets:
    """Token buckets by key, bounded, least recently seen evicted."""

    def __init__(self, rate, burst, clock):
        self.rate, self.burst, self.clock = rate, burst, clock
        self._buckets = OrderedDict()

    def _tokens(self, key, now):
        tokens, then = self._buckets.pop(key, (self.burst, now))
        return min(self.burst, tokens + (now - then) * self.rate)

    def _store(self, key, tokens, now):
        self._buckets[key] = (tokens, now)
        while len(self._buckets) > MAX_KEYS:
            self._buckets.popitem(last=False)

    def take(self, key):
        now = self.clock()
        tokens = self._tokens(key, now)
        allowed = tokens >= 1
        self._store(key, tokens - 1 if allowed else tokens, now)
        return allowed

    def peek(self, key):
        now = self.clock()
        tokens = self._tokens(key, now)
        self._store(key, tokens, now)
        return tokens >= 1


class RequestBuckets:
    """The guard, group and chunk buckets of one door. Thread-safe; every call is O(1)."""

    def __init__(self, configured, *, clock=time.monotonic):
        checked = values(configured)
        self._lock = threading.Lock()
        self._kinds = {kind: _Buckets(*checked[kind], clock) for kind in KINDS}

    def charge_guard(self):
        """Charge the shared guard; False when it is empty (refuse 429 `rate`)."""
        with self._lock:
            return self._kinds["guard"].take(GUARD_KEY)

    def peek_group(self, group):
        """Before the body: may a POST of this group still be admitted by either of its buckets? Charges nothing."""
        with self._lock:
            return self._kinds["group"].peek(group) or self._kinds["chunks"].peek(group)

    def charge_group(self, group, *, chunk):
        """After verification: charge the group's chunk bucket (a continuation chunk) or its request bucket."""
        with self._lock:
            return self._kinds["chunks" if chunk else "group"].take(group)
