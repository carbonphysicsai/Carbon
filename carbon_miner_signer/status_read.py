"""The signer's one read-only request kind: a ``battery_status`` read (LA-F18).

``status_read`` is how the Launchpad's observe asks a validator intake for the
verdict of a submission the miner already made. Unlike ``sign``, which sees
only the ``btauth/1`` payload and so only the hash of the body it covers, a
``status_read`` request carries the body too. The signer signs it only when
that body is exactly one ``battery_status`` request for one submission id:

- the payload passes every check ``sign`` makes (``refusal_for``: this
  hotkey, a fresh nonce, the receiver allow-list) for the MCP request target
  only, never the answer-key fetch;
- the payload's body hash is the sha256 of the body sent beside it;
- the body is the canonical form of a Carbon request
  (``carbon.transport.models.message``): exactly its fields, protocol
  ``carbon.mcp.hotkey.v1``, tool ``battery_status``, and fields exactly
  ``{"submission_id": "bsub-<32 hex>"}``.

So it can never sign a submission (``battery_submit``, an admission), a
Level 4 envelope part, any other tool, or anything that is not a ``btauth/1``
request: never a commitment or any other chain extrinsic, which is ``commit``
alone, with its own confirmation. It never reads the commitment policy, the
commitment ledger or the auto-confirm allow-list, and never asks the
terminal: a status read changes nothing at the validator and spends nothing,
as the status polls ``sign`` already signs unasked. The intake answers a
status read only for the signing hotkey's own submissions.

This module imports nothing from ``carbon``: the request shape is written out
here, and the tests hold it against Carbon's own builder.
"""

from __future__ import annotations

import hashlib
import json
import re

OP = "status_read"
#: `carbon.transport.models.PROTOCOL`.
BODY_PROTOCOL = "carbon.mcp.hotkey.v1"
#: `carbon.battery.intake.STATUS_TOOL`.
STATUS_TOOL = "battery_status"
#: The fields of every Carbon request body (`carbon.transport.models.message`).
BODY_FIELDS = frozenset(
    {
        "protocol",
        "network",
        "genesis",
        "netuid",
        "challenge_id",
        "challenge_version",
        "snapshot",
        "session",
        "request",
        "tool",
        "fields",
    }
)
#: A battery submission id (`carbon.battery.daemon.submission_identity`).
SUBMISSION_ID = re.compile(r"bsub-[0-9a-f]{32}")
#: Far above any status read's body, far below the signer's request bound.
MAX_BODY_BYTES = 2048


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def status_read_id(payload: bytes, body: bytes) -> str | None:
    """The submission id when ``body`` is one ``battery_status`` read that
    ``payload`` (already checked by ``refusal_for``) covers; None otherwise."""
    if type(body) is not bytes or not 0 < len(body) <= MAX_BODY_BYTES:
        return None
    lines = payload.decode("ascii").split("\n")
    if hashlib.sha256(body).hexdigest() != lines[4]:
        return None
    try:
        document = json.loads(body, object_pairs_hook=_no_duplicates)
        if type(document) is not dict or _canonical(document) != body:
            return None
    except (ValueError, UnicodeError, RecursionError):
        return None
    if set(document) != BODY_FIELDS:
        return None
    if document["protocol"] != BODY_PROTOCOL or document["tool"] != STATUS_TOOL:
        return None
    fields = document["fields"]
    if type(fields) is not dict or set(fields) != {"submission_id"}:
        return None
    found = fields["submission_id"]
    if type(found) is not str or not SUBMISSION_ID.fullmatch(found):
        return None
    return found
