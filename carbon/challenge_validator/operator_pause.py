"""Operator pause switch for crown changes and weight publication.

One operator-owned flag file, ``operator-pause.json``, in the validator state directory, read at decision time:
``{"crowns_paused": true, "weights_paused": true}``. Absent means running. A file that exists but is not a
private regular file of this user, or does not parse as exactly those two booleans, pauses both: an unreadable switch
never leaves the validator running. The flag changes no grade and no score; it only withholds a crown change or a
weight publication until the operator removes it.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

FLAG_NAME = "operator-pause.json"
CROWNS_PAUSED = "crowns_paused"
WEIGHTS_PAUSED = "weights_paused"


def flag_path(state_dir) -> Path:
    return Path(state_dir) / FLAG_NAME


def read(state_dir) -> dict:
    """The pause state in `state_dir`: both keys, False when the flag file is absent."""
    if state_dir is None:  # a store with no directory (a test double) has no flag
        return {CROWNS_PAUSED: False, WEIGHTS_PAUSED: False}
    path = flag_path(state_dir)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return {CROWNS_PAUSED: False, WEIGHTS_PAUSED: False}
    except OSError:
        return _paused()
    owner = getattr(os, "geteuid", lambda: info.st_uid)()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != owner:
        return _paused()
    try:
        body = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return _paused()
    if type(body) is not dict or set(body) - {CROWNS_PAUSED, WEIGHTS_PAUSED}:
        return _paused()
    if any(type(value) is not bool for value in body.values()):
        return _paused()
    return {
        CROWNS_PAUSED: body.get(CROWNS_PAUSED, False),
        WEIGHTS_PAUSED: body.get(WEIGHTS_PAUSED, False),
    }


def _paused() -> dict:
    return {CROWNS_PAUSED: True, WEIGHTS_PAUSED: True}


def crowns_paused(state_dir) -> bool:
    return read(state_dir)[CROWNS_PAUSED]


def weights_paused(state_dir) -> bool:
    return read(state_dir)[WEIGHTS_PAUSED]
