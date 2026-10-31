"""The signed launch board's file, as the receiver's door serves it:
``GET /carbon/v1/feed/<challenge_id>`` (OWNER-DASHBOARD-LIVE-SWITCH-01).

The validator operator builds and signs the board on the validator host
(`launch_board`, `scripts/dev/launch_board_operator.py`) and writes it to a file.
This module is the door's whole involvement: it reads that file and returns the
document only when it can be served, else None. **The door never holds the feed
key.** It verifies; it does not sign.

A board is served only when all of these hold:

- the file is a readable JSON object of at most `MAX_BYTES`;
- it is the closed launch-board shape (`launch_board.check`): no field outside the
  allow-lists, so nothing finer than the Ladder's rounded totals, the king document
  and counts can appear;
- it is this Challenge's board (`challenge.id`);
- its signature verifies under `launch_board.BOARD_DOMAIN` with the feed key it names,
  and with ``pinned_key`` (64 hex, the key the operator configured) when one is given;
- every total it shows is exactly on the Ladder step of its own margin: none is finer than
  a miner sees;
- the key is not the dashboard's public fixture key: a fixture-signed board is never
  served, and the dashboard refuses it too.

The Worker still pins the validator's key out of band and verifies for itself; a door
that served a bad file would be refused there, and this module refuses first.

DEVELOPMENT / TESTNET only: display data, no score, weight or reward authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

#: A launch board is at most 512 ladder rows; this is far above a real one.
MAX_BYTES = 262144
#: The seed of the dashboard's public fixture key (`carbon.dashboard.fixtures`).
_FIXTURE_SEED = hashlib.sha256(b"carbon.dashboard.fixture-key.v1").digest()


def fixture_public_key():
    """The public half of the dashboard's fixture key (64 hex)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return (
        Ed25519PrivateKey.from_private_bytes(_FIXTURE_SEED)
        .public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )


def read_board(path, challenge_id, pinned_key=None):
    """The signed launch board at ``path`` for ``challenge_id``, or None: unreadable,
    oversized, not the closed shape, another Challenge's, signed by the fixture key or
    by another key than ``pinned_key``, or not verified by its signature."""
    from . import launch_board

    try:
        file = Path(path)
        if file.stat().st_size > MAX_BYTES:
            return None
        board = json.loads(file.read_text(encoding="utf-8"))
        if (
            type(board) is not dict
            or board.get("schema") != launch_board.SCHEMA
            or (board.get("challenge") or {}).get("id") != challenge_id
        ):
            return None
        key = board["validator"]["feed_key"]
        if key == fixture_public_key() or (
            pinned_key is not None and key != pinned_key
        ):
            return None
        launch_board.verify(board, key)
        if not _on_the_ladder_step(board):
            return None
    except (OSError, ValueError, KeyError, TypeError, launch_board.BoardRefused):
        return None
    return board


def _on_the_ladder_step(board):
    """Whether every total the board shows (the king's and each ladder row's) is exactly
    on the Ladder step of the board's own margin, so no total is finer than a miner sees
    (`grade_feedback.floor_to_step`). A failing check is a refusal to serve, never a
    rounding."""
    from carbon.scoring import grade_feedback as gf

    noise = board["king"]["margin"]
    totals = [row["total"] for row in board["ladder"] if row["total"] is not None]
    if board["king"]["king"] is not None:
        totals.append(board["king"]["king"]["total"])
    return all(gf.floor_to_step(total, noise) == total for total in totals)


__all__ = ["MAX_BYTES", "fixture_public_key", "read_board"]
