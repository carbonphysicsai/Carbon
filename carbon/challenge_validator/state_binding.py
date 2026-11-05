"""Bind a receiver state directory to its door, not to one code release (MAINNET_UPDATE_ARCHITECTURE s1.3 (a)).

Until now the receiver wrote ``receiver-binding.json`` once (`data.write_once`) with its whole binding: the code
revision, the images, the pack digest and the door identity. A second release on the same state then raised
``immutable session artifact conflict``, so every code move needed a new state directory and a copy of the miners'
workspaces into it (the copy that failed on 2 and 3 Nov).

Here the binding is split in two:

- the DOOR binding (``door-binding.json``, write-once): EVERY binding field except ``implementation`` (the code
  revision): the chain context, the receiver hotkey, the Challenge, the measure query, the pack digest, every CPU and
  GPU image, the GPU device and ops records, the cache size. None of them may change for the life of a state
  directory; a different value refuses, exactly as before. Only the code revision may move (the Validator's M3 rule:
  "only implementation.revision changes"); an image or device move still needs a new state, as it did before;
- the RELEASE bindings (``bindings/<sha256>.json``, each write-once): the full binding of every release that bound
  this state at its start (a release that then refused later in its start, e.g. at owner restore, is still listed).
  A new release adds one; nothing is replaced.

Compatibility (expand step; for THIS file both directions start):

- a state written by an older receiver keeps its ``receiver-binding.json`` byte-for-byte: it is never rewritten, so
  that older receiver still starts on it after a newer one ran (rollback);
- on a state that has none, the first release writes it once (as before), so every reader of that file keeps working.
  It then names the FIRST release that served the state, not the current one; the current one is in ``bindings/``.

The evaluation pack digest a restart reloads (`direct_receiver._sealed_pack`) is read through `retained_pack_digest`,
which takes it from the door binding or, on an older state, from the legacy file, and refuses if the two disagree.

Rollback is limited elsewhere: retained owner campaign manifests are re-frozen forward to the new revision at start
(`direct_receiver._migrate_owner_manifest`), and an older receiver refuses them. That is the next head's subject
(MAINNET_UPDATE_ARCHITECTURE s1.3 (b)); this module only makes the receiver binding release-neutral.

Nothing here scores, grades or decides; it only refuses a state that belongs to another door.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.private_records import private_json
from carbon.development_session.profile import canonical

DOOR_SCHEMA = "carbon.challenge-validator.door-binding.v1"
LEGACY_NAME = "receiver-binding.json"
DOOR_NAME = "door-binding.json"
RELEASES_DIR = "bindings"
#: The one binding field a later release may change on the same state: the code it runs.
RELEASE_KEYS = ("implementation",)


class StateBindingRefused(ValueError):
    """The state directory belongs to another door (or its binding files are unsafe)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _read(path: Path):
    if path.is_symlink():
        raise StateBindingRefused("receiver binding link refused")
    if not path.exists():
        return None
    value = private_json(path)
    if type(value) is not dict:
        raise StateBindingRefused("receiver binding unreadable")
    return value


def door_of(binding: dict) -> dict:
    """The door part of a full receiver binding: every field but `RELEASE_KEYS` (the receiver's own schema kept as
    ``receiver_schema``), plus this schema."""
    door = {key: value for key, value in binding.items() if key not in RELEASE_KEYS}
    if "schema" in door:
        door["receiver_schema"] = door.pop("schema")
    door["schema"] = DOOR_SCHEMA
    return door


def release_name(binding: dict) -> str:
    return hashlib.sha256(canonical(binding)).hexdigest() + ".json"


def read_door(root: Path) -> dict:
    """The door this state is bound to: the door binding, or on an older state the door part of its legacy file.

    Readers that need what a door serves (its Challenge, its pack) read it here, never from ``receiver-binding.json``
    directly: on a fresh state that file names the FIRST release that served it, so its release fields
    (``implementation``) are not the running release's. Refuses (`StateBindingRefused`) if the state has no binding,
    or if both records exist and their doors differ."""
    root = Path(root).absolute()
    door = _read(root / DOOR_NAME)
    legacy = _read(root / LEGACY_NAME)
    if door is None and legacy is None:
        raise StateBindingRefused("receiver binding missing")
    if door is not None and legacy is not None and door_of(legacy) != door:
        raise StateBindingRefused("retained door binding differs")
    return door if door is not None else door_of(legacy)


def retained_pack_digest(root: Path):
    """The evaluation pack digest this state was bound to, or None (a fresh state, or a door without a pack).

    Read from the door binding, or from the legacy file of an older state; refused if both exist and differ.
    """
    root = Path(root)
    door = _read(root / DOOR_NAME)
    legacy = _read(root / LEGACY_NAME)
    found = {
        record["evaluation_pack_digest"]
        for record in (door, legacy)
        if record is not None and "evaluation_pack_digest" in record
    }
    if len(found) > 1:
        raise StateBindingRefused("receiver binding pack digest differs")
    return next(iter(found), None)


def bind(root: Path, binding: dict) -> dict:
    """Bind ``root`` to this release's full ``binding``; return what was checked and written.

    Refuses (`StateBindingRefused`, nothing written) if the state's door differs from ``binding``'s door: on the door
    binding, or, on an older state, on the legacy file's door keys. Writes, each once: the door binding, this
    release's binding under ``bindings/``, and the legacy file only when the state has none.
    """
    root = Path(root)
    if type(binding) is not dict:
        raise StateBindingRefused("receiver binding must be a mapping")
    door = door_of(binding)
    legacy_path = root / LEGACY_NAME
    door_path = root / DOOR_NAME
    legacy = _read(legacy_path)
    retained_door = _read(door_path)
    if retained_door is not None and retained_door != door:
        raise StateBindingRefused("retained door binding differs")
    if legacy is not None and door_of(legacy) != door:
        raise StateBindingRefused("retained door binding differs")
    releases = root / RELEASES_DIR
    if releases.is_symlink():
        raise StateBindingRefused("receiver bindings link refused")
    releases.mkdir(mode=0o700, exist_ok=True)
    name = release_name(binding)
    payload = canonical(binding)
    # Every check is done; the writes below only add files (each one write-once).
    write_once(releases / name, payload)
    write_once(door_path, canonical(door))
    legacy_written = legacy is None
    if legacy_written:
        write_once(legacy_path, payload)
    return {
        "door": door,
        "release_binding": f"{RELEASES_DIR}/{name}",
        "legacy_written": legacy_written,
        "legacy_is_this_release": legacy_written or legacy == binding,
    }
