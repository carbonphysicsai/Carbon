"""The signed score feed's file: its bytes, signature check, read and write
(VALIDATOR-29).

Kept apart from `score_feed` on purpose. The validator's door (the battery
intake, which miner surfaces reach) serves the feed file through this module
alone, so the door's import closure never reaches the feed builder's science
(the design showcase, the quiz and tuning code) or anything beyond it
(`tests/invariants/test_attack_store_unreachable.py`). Standard library and
`cryptography` only.

**Signed bytes:** `FEED_DOMAIN` followed by the feed without its `signature`
field, as `json.dumps(sort_keys=True, separators=(",", ":"), allow_nan=False,
ensure_ascii=True)` encoded UTF-8.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FEED_SCHEMA = "carbon.validator.score-feed.v1"
FEED_DOMAIN = b"carbon.validator.score-feed.v1\x00"


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True
    )


def verify_feed(feed, pinned_key=None):
    """Whether a feed's signature is its feed key's, over the document without
    the signature. With `pinned_key` (the key a reader configured out of
    band), the feed must name exactly that key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        if pinned_key is not None and feed["validator"]["feed_key"] != pinned_key:
            return False
        body = {k: v for k, v in feed.items() if k != "signature"}
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(feed["validator"]["feed_key"])
        ).verify(
            bytes.fromhex(feed["signature"]), FEED_DOMAIN + canonical(body).encode()
        )
    except (InvalidSignature, KeyError, TypeError, ValueError):
        return False
    return True


def write_feed(path, feed):
    """Write the signed feed atomically for the door to serve."""
    path = Path(path)
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    with os.fdopen(fd, "w") as handle:
        json.dump(feed, handle, sort_keys=True)
    os.replace(temporary, path)


def read_feed(path, challenge_id):
    """The signed feed at `path` for `challenge_id`, or None: unreadable,
    another Challenge's, or not verified by its own feed key."""
    try:
        feed = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    if (
        type(feed) is not dict
        or feed.get("schema") != FEED_SCHEMA
        or (feed.get("challenge") or {}).get("id") != challenge_id
        or not verify_feed(feed)
    ):
        return None
    return feed


__all__ = [
    "FEED_DOMAIN",
    "FEED_SCHEMA",
    "canonical",
    "read_feed",
    "verify_feed",
    "write_feed",
]
