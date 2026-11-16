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
  "only implementation.revision changes"), except by a DECLARED DOOR MIGRATION (below);
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

DECLARED DOOR MIGRATION (owner, Mon 16 Nov 2026, typed in Deploy-B: "Get it working. Turn it on." for the 116 graph
GPU builds; Lead: one migration for the GPU build lane and the remote grade lane; design posted for Validator-2 at
05:08 CST, M1-M5):

- M1 scope: only `MIGRATABLE_KEYS` may differ: the worker image keys (``parent``, ``inference_image``,
  ``construction_parents``) and the graph GPU lane keys (``graph_gpu_image``, ``graph_gpu_ops_digest``,
  ``graph_gpu_device``), changed or ADDED. Every other door key stays byte-equal and no key may be dropped;
- M2 authority: never on its own. The operator installs ``door-migration.json`` in the state root (a plain file; the
  owner's words and a Validator receipt to install it) naming ``from`` = `door_digest` of the door the state holds now
  and ``to`` = `door_digest` of the exact door this release brings. A start whose door differs prints both digests
  and the differing key names (`differs_event`), which is what the operator puts in the record. The image values
  are verified by the receiver before it binds (`research_campaign.verify_current_worker`, `graph_gpu_lane`, the
  hardware acceptance); a migration adds no trust in them;
- M3 record: ``door-binding.json`` is never rewritten. Each migration adds one write-once link
  ``door-migrations/<n>.json`` = {from, to, the request's digest, the new door}; the current door is the original door
  folded through every link, each link re-checked (its ``from`` is the previous door's digest, its door is that door
  changed only in `MIGRATABLE_KEYS`, its ``to`` is its door's digest);
- M4 rollback: an older release reads only ``door-binding.json`` (the ORIGINAL door), so it starts on the migrated
  state only with the original images (the pre-migration release itself);
- the legacy ``receiver-binding.json`` and the pack digest never move.

Nothing here scores, grades or decides; it only refuses a state that belongs to another door.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
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
#: The door keys a DECLARED door migration may change or add (M1): the worker images and the graph GPU lane.
MIGRATABLE_KEYS = frozenset(
    {
        "parent",
        "inference_image",
        "construction_parents",
        "graph_gpu_image",
        "graph_gpu_ops_digest",
        "graph_gpu_device",
    }
)
MIGRATION_REQUEST = "door-migration.json"
MIGRATION_SCHEMA = "carbon.challenge-validator.door-migration-request.v1"
MIGRATIONS_DIR = "door-migrations"
LINK_SCHEMA = "carbon.challenge-validator.door-migration.v1"
_LINK_NAME = re.compile(r"[0-9]{4}\.json")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


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


def door_digest(door: dict) -> str:
    """The digest a migration names a door by: sha256 of its canonical bytes."""
    return "sha256:" + hashlib.sha256(canonical(door)).hexdigest()


def migration_keys(old: dict, new: dict):
    """The door keys that differ between ``old`` and ``new`` (sorted), or None if any of them is outside
    `MIGRATABLE_KEYS` or ``new`` drops a key ``old`` has (M1)."""
    changed = sorted(
        key
        for key in set(old) | set(new)
        if old.get(key, None) != new.get(key, None) or (key in old) != (key in new)
    )
    if any(key not in MIGRATABLE_KEYS or key not in new for key in changed):
        return None
    return changed


def _links(root: Path):
    """The migration links, in order (``door-migrations/0001.json`` ...): their documents. A gap, a link or a stray
    name refuses."""
    folder = root / MIGRATIONS_DIR
    if folder.is_symlink():
        raise StateBindingRefused("door migrations link refused")
    if not folder.exists():
        return []
    names = sorted(path.name for path in folder.iterdir())
    if any(_LINK_NAME.fullmatch(name) is None for name in names) or names != [
        f"{index:04d}.json" for index in range(1, len(names) + 1)
    ]:
        raise StateBindingRefused("door migrations unreadable")
    return [_read(folder / name) for name in names]


def _folded(root: Path, original: dict) -> dict:
    """The current door: ``original`` through every migration link, each re-checked (M3)."""
    door = original
    for index, link in enumerate(_links(root), start=1):
        if (
            type(link) is not dict
            or set(link) != {"schema", "index", "from", "to", "request", "door"}
            or link["schema"] != LINK_SCHEMA
            or link["index"] != index
            or link["from"] != door_digest(door)
            or type(link["door"]) is not dict
            or link["to"] != door_digest(link["door"])
            or type(link["request"]) is not str
            or _DIGEST.fullmatch(link["request"]) is None
            or not migration_keys(door, link["door"])
        ):
            raise StateBindingRefused("door migration link invalid")
        door = link["door"]
    return door


def differs_event(current: dict, door: dict) -> dict:
    """What a start whose door differs prints (key names and digests only; no value): the operator's migration request
    is written from it (M2)."""
    keys = migration_keys(current, door)
    return {
        "event": "door_binding_differs",
        "from": door_digest(current),
        "to": door_digest(door),
        "keys": sorted(
            key
            for key in set(current) | set(door)
            if current.get(key) != door.get(key) or (key in current) != (key in door)
        ),
        "migratable": bool(keys),
    }


def _migration_link(root: Path, current: dict, door: dict) -> dict:
    """The link the operator's declared migration from ``current`` to ``door`` adds (M2), checked and NOT written yet;
    refuses (`StateBindingRefused`) otherwise."""
    print(
        json.dumps(differs_event(current, door), sort_keys=True),
        file=sys.stderr,
        flush=True,
    )
    request_path = root / MIGRATION_REQUEST
    request = _read(request_path)
    if request is None:
        raise StateBindingRefused("retained door binding differs")
    keys = migration_keys(current, door)
    if (
        set(request) != {"schema", "from", "to"}
        or request["schema"] != MIGRATION_SCHEMA
        or request["from"] != door_digest(current)
        or request["to"] != door_digest(door)
        or not keys
    ):
        raise StateBindingRefused("retained door binding differs")
    index = len(_links(root)) + 1
    return {
        "schema": LINK_SCHEMA,
        "index": index,
        "from": request["from"],
        "to": request["to"],
        "request": "sha256:" + hashlib.sha256(request_path.read_bytes()).hexdigest(),
        "door": door,
    }


def _write_link(root: Path, link: dict, current: dict):
    folder = root / MIGRATIONS_DIR
    folder.mkdir(mode=0o700, exist_ok=True)
    write_once(folder / f"{link['index']:04d}.json", canonical(link))
    print(
        json.dumps(
            {
                "event": "door_binding_migrated",
                "index": link["index"],
                "from": link["from"],
                "to": link["to"],
                "keys": migration_keys(current, link["door"]),
            },
            sort_keys=True,
        ),
        file=sys.stderr,
        flush=True,
    )


#: The door keys of the worker images (a migration that moved one of them moved the images the owners' frozen
#: campaign manifests name: `migrated_images`).
IMAGE_KEYS = frozenset({"parent", "inference_image", "construction_parents"})


def migrated_images(root: Path) -> bool:
    """Whether a declared migration link of this state moved a worker image key (`IMAGE_KEYS`): the owners' frozen
    manifests may then adopt the images of the CURRENT door (`direct_receiver._revision_only_change`).
    """
    root = Path(root).absolute()
    door = _read(root / DOOR_NAME)
    if door is None:
        return False
    moved = False
    for link in _links(root):
        moved = moved or bool(
            IMAGE_KEYS & set(migration_keys(door, link["door"]) or ())
        )
        door = link["door"]
    return moved


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
    return _folded(root, door if door is not None else door_of(legacy))


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

    Refuses (`StateBindingRefused`, nothing written) if the state's CURRENT door (the original folded through its
    migration links) differs from ``binding``'s door, unless the operator's declared migration covers exactly that
    change (`_migration_link`: one link added). Writes, each once: the original door binding, this release's binding under
    ``bindings/``, and the legacy file only when the state has none.
    """
    root = Path(root)
    if type(binding) is not dict:
        raise StateBindingRefused("receiver binding must be a mapping")
    door = door_of(binding)
    legacy_path = root / LEGACY_NAME
    door_path = root / DOOR_NAME
    legacy = _read(legacy_path)
    retained_door = _read(door_path)
    if (
        retained_door is not None
        and legacy is not None
        and door_of(legacy) != retained_door
    ):
        raise StateBindingRefused("retained door binding differs")
    original = (
        retained_door
        if retained_door is not None
        else (door_of(legacy) if legacy is not None else door)
    )
    current = _folded(root, original)
    migrated = None
    if current != door:
        migrated = _migration_link(root, current, door)
    releases = root / RELEASES_DIR
    if releases.is_symlink():
        raise StateBindingRefused("receiver bindings link refused")
    releases.mkdir(mode=0o700, exist_ok=True)
    name = release_name(binding)
    payload = canonical(binding)
    # Every check is done; the writes below only add files (each one write-once).
    if migrated is not None:
        _write_link(root, migrated, current)
    write_once(releases / name, payload)
    write_once(door_path, canonical(original))
    legacy_written = legacy is None
    if legacy_written:
        write_once(legacy_path, payload)
    return {
        "door": door,
        "release_binding": f"{RELEASES_DIR}/{name}",
        "legacy_written": legacy_written,
        "legacy_is_this_release": legacy_written or legacy == binding,
        "migrated": None if migrated is None else migrated["index"],
    }
