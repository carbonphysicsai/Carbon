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

`install` turns the hold on at receiver start when the Challenge version the receiver actually serves (its material's
challenge key) has a registration carrying a ``menu``
block (read from the raw registration, so a version whose other constants are still HUMAN_INPUT is held too). Every
other version is unchanged: the hold is never on for it.

The hold can be registered OFF for one exact exam of one version (the owner's ruling, 13 Nov: once a version's floor,
noise and margin_N are registered its crowns change by the coded rule, with no daily human release). That is a registry
entry in `scripts/validator_host_classes/crown_hold.json` (host-read data, outside `carbon/`, like the noise, margin and
floor registries): ``{"challenge", "version", "menu_epoch", "evaluation_pack_digest", "hold": "off", "authority": <digest
of the owner's typed line>}``. The registry is read ONCE, at `install` (a change goes through commit, push and a door
roll, never an in-place edit), and the result is logged. The hold is off only WHILE the entry's pack digest equals the
sealed evaluation pack this receiver serves (`bind_pack`) AND its menu epoch equals the registered menu epoch of the
version: a re-pack or a rotation to another epoch re-engages the hold. ``ACTIVE`` keeps its meaning (the served version
is a menu version: the menu re-check still runs); only the HOLD is off. No entry, an unreadable or malformed registry,
an unbound pack, or any other version: the hold is exactly what it was (fail closed). The operator's pause flag
(`operator_pause`) is checked before the hold and still stops every crown change.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

#: The registered hold-off entries (`holding`): outside `carbon/`, so registering one never moves the worker image id.
REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "crown_hold.json"
)
REGISTRY_SCHEMA = "carbon.crown.hold-registry.v1"
_ENTRY = {
    "challenge",
    "version",
    "menu_epoch",
    "evaluation_pack_digest",
    "hold",
    "authority",
}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")

#: The closed reason code of a held crown change (the miner sees this code only).
CROWN_HELD = "crown_held_for_review"
RELEASE_NAME = "menu-crown-release.json"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}")

#: True while the served version registers a menu (set by `install` at receiver start).
ACTIVE = False
#: ``(challenge_id, version)`` the receiver serves, set by `install` (None until then).
SERVED = None
#: The registry's off entry for the served version, read once by `install`: ``{"menu_epoch", "evaluation_pack_digest"}``
#: or None. It takes effect only while `PACK` and `EPOCH` equal it (`off_in_force`).
OFF = None
#: The sealed evaluation pack digest the receiver serves (`bind_pack`) and the version's registered menu epoch
#: (`install`); None until set.
PACK = None
EPOCH = None


def menu_registered(challenge_id, version, *, path=None) -> bool:
    """Whether the version's raw registration carries a ``menu`` block (no other constant is read or checked)."""
    # an unreadable registration cannot show the version is NOT a menu version: hold (fail closed)
    return _reason(challenge_id, version, path=path) != "off"


def _say(line, log):
    if log is None:
        import sys

        print(line, file=sys.stderr, flush=True)
    else:
        log(line)


def _registered_epoch(challenge_id, version):
    """The version's registered menu epoch, or None when it cannot be read (fail closed)."""
    try:
        from carbon.scoring import pool_version

        rule = pool_version.registered_menu(challenge_id, version)
        return rule.epoch if rule is not None and type(rule.epoch) is str else None
    except Exception:  # noqa: BLE001 - unreadable: the hold stays (fail closed)
        return None


def install(challenge_id, version, *, log=None):
    """Hold crowns when the version this receiver ACTUALLY serves (its material's challenge key, never the cfg's
    selection: Validator-2B 7 Nov must-fix 2) registers a menu; off for every other version. Reads the registry's hold-off
    entry ONCE and says what it found. Logs, last, ``crown_hold_active=<bool> reason=<menu|unreadable|off>`` (Ops Watch).
    The off entry takes effect only once `bind_pack` names the served pack and only while its epoch is the registered one.
    """
    global ACTIVE, SERVED, OFF, PACK, EPOCH
    reason = _reason(challenge_id, version)
    ACTIVE = reason != "off"
    SERVED = (challenge_id, version)
    PACK = None
    OFF = registered_off(challenge_id, version) if ACTIVE else None
    EPOCH = _registered_epoch(challenge_id, version) if ACTIVE else None
    if ACTIVE:
        if OFF is None:
            _say("crown_hold_registry_off=false (no entry for this version)", log)
        else:
            _say(
                "crown_hold_registry_off=true"
                f" pack={OFF['evaluation_pack_digest'][:23]} epoch={OFF['menu_epoch']}"
                f" registered_epoch={EPOCH} (in force only while both match the served pack)",
                log,
            )
    _say(f"crown_hold_active={str(ACTIVE).lower()} reason={reason}", log)
    return ACTIVE


def bind_pack(evaluation_pack_digest, *, log=None):
    """Name the sealed evaluation pack this receiver serves (called once the pack is attached). Returns whether the
    registered hold-off is in force for it, and says so when an entry exists."""
    global PACK
    PACK = evaluation_pack_digest if type(evaluation_pack_digest) is str else None
    if OFF is not None:
        _say(f"crown_hold_off_in_force={str(off_in_force()).lower()}", log)
    return off_in_force()


def off_in_force() -> bool:
    """Whether the registry's hold-off entry applies now: it exists for the served version and BOTH its pack digest and
    its menu epoch equal the served sealed pack and the registered menu epoch. Anything else stays held.
    """
    return (
        OFF is not None
        and PACK is not None
        and EPOCH is not None
        and OFF["evaluation_pack_digest"] == PACK
        and OFF["menu_epoch"] == EPOCH
    )


def _reason(challenge_id, version, *, path=None):
    from carbon.scoring import pool_version

    try:
        document = json.loads(Path(path or pool_version.CONSTANTS).read_bytes())
        entry = document["versions"].get(f"{challenge_id} {version}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return "unreadable"
    return "menu" if type(entry) is dict and "menu" in entry else "off"


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


def registered_off(challenge_id, version, *, path=None):
    """The registry's hold-off entry for exactly this version (``{"menu_epoch", "evaluation_pack_digest"}``), or None.
    Anything unreadable or malformed, a version the Challenge does not register, a duplicate, an unknown field, a value
    other than "off", a pack that is not a digest, an empty epoch or an authority that is not a digest makes the WHOLE
    registry read as "no entry": the hold stays on (fail closed)."""
    try:
        document = json.loads(Path(REGISTRY if path is None else path).read_bytes())
        if (
            type(document) is not dict
            or set(document) != {"schema", "holds"}
            or document["schema"] != REGISTRY_SCHEMA
            or type(document["holds"]) is not list
        ):
            return None
        from carbon.challenge_kit import version_registry
        from carbon.challenge_validator.exam_cap import registered_challenges

        known = registered_challenges()
        found = {}
        for entry in document["holds"]:
            if (
                type(entry) is not dict
                or set(entry) != _ENTRY
                or entry["challenge"] not in known
                or type(entry["version"]) is not str
                or version_registry.find(entry["challenge"], entry["version"]) is None
                or entry["hold"] != "off"
                or type(entry["menu_epoch"]) is not str
                or not entry["menu_epoch"]
                or type(entry["evaluation_pack_digest"]) is not str
                or not _DIGEST.fullmatch(entry["evaluation_pack_digest"])
                or type(entry["authority"]) is not str
                or not _DIGEST.fullmatch(entry["authority"])
            ):
                return None
            key = (entry["challenge"], entry["version"])
            if key in found:
                return None
            found[key] = {
                "menu_epoch": entry["menu_epoch"],
                "evaluation_pack_digest": entry["evaluation_pack_digest"],
            }
        return found.get((challenge_id, version))
    except Exception:  # noqa: BLE001 - unreadable: the hold stays (fail closed)
        return None


def holding() -> bool:
    """Whether the served version's crown changes are held for review: it is a menu version (`ACTIVE`) and the
    registered hold-off is not in force (`off_in_force`: both the served pack and the menu epoch match its entry).
    """
    return ACTIVE and not off_in_force()


def held(state_dir, submission_id, *, active=None) -> bool:
    """Whether this contender's crown change is held: the hold is on and the operator has not released it."""
    on = holding() if active is None else active
    return bool(on) and not released(state_dir, submission_id)
