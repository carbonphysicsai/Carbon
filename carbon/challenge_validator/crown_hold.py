"""The coded crown HOLD of a menu-D version (Validator-2B 7 Nov; Carbon Validator-B 7 Nov (2)).

A version that registers a pool ``menu`` block is graded on D by the sealed menu (`carbon.scoring.pool_menu`). Until
the crown-side re-score on stored predictions (E2, and Carbon Validator-B's mean of 3 keyed draws for a close change)
is built, a crown change on such a version is never made automatically:

- `bank_promotion.consider_private` returns UNAVAILABLE with the reason `CROWN_HELD` where a crown would change, before
  any repeat or rebuild is spent; the sitting king keeps the crown (status quo);
- the caller files the contender like a paused one (`lean_recipe_retention._file_if_paused`), so it keeps its place in
  admission order (`crown_pause_sweep`), and the miner's grade shows only the closed code;
- the operator releases ONE held contender by naming it in the private file `menu-crown-release.json` in the validator
  state directory (``{"released": [submission_id, ...]}``); the sweep then decides it as normal, and its resolution
  is written once in the pool store (the record of the release). A file that is not a private regular file of this
  user, or does not parse as exactly that, releases nothing (fail closed: held).

`install` turns the hold on at receiver start when the served Challenge version's registration carries a ``menu``
block (read from the raw registration, so a version whose other constants are still HUMAN_INPUT is held too). Every
other version is unchanged: the hold is never on for it.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

#: The closed reason code of a held crown change (the miner sees this code only).
CROWN_HELD = "crown_held_for_review"
RELEASE_NAME = "menu-crown-release.json"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}")

#: True while the served version registers a menu (set by `install` at receiver start).
ACTIVE = False


def menu_registered(challenge_id, version, *, path=None) -> bool:
    """Whether the version's raw registration carries a ``menu`` block (no other constant is read or checked)."""
    from carbon.scoring import pool_version

    try:
        document = json.loads(Path(path or pool_version.CONSTANTS).read_bytes())
        entry = document["versions"].get(f"{challenge_id} {version}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # an unreadable registration cannot show the version is NOT a menu version: hold (fail closed)
        return True
    return type(entry) is dict and "menu" in entry


def install(cfg):
    """Hold crowns for the served Challenge version when it registers a menu; off for every other version."""
    global ACTIVE
    selected = cfg.get("challenge") if type(cfg) is dict else None
    if type(selected) is not dict or set(selected) != {"id", "version"}:
        ACTIVE = False
        return
    ACTIVE = menu_registered(selected["id"], selected["version"])


def released(state_dir, submission_id) -> bool:
    """Whether the operator's private release file names this contender."""
    if state_dir is None or type(submission_id) is not str:
        return False
    path = Path(state_dir) / RELEASE_NAME
    try:
        info = os.lstat(path)
    except OSError:
        return False
    owner = getattr(os, "geteuid", lambda: info.st_uid)()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != owner:
        return False
    try:
        body = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return False
    if (
        type(body) is not dict
        or set(body) != {"released"}
        or type(body["released"]) is not list
        or not all(type(x) is str and _ID.fullmatch(x) for x in body["released"])
    ):
        return False
    return submission_id in body["released"]


def held(state_dir, submission_id, *, active=None) -> bool:
    """Whether this contender's crown change is held: the hold is on and the operator has not released it."""
    on = ACTIVE if active is None else active
    return bool(on) and not released(state_dir, submission_id)
