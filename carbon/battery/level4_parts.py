"""The development ladder's Level 4 envelope parts (VALIDATOR-25 slice 4).

A Level 4 submission's staging envelope (`carbon.level4.staging`: the graph
manifest and its documents) is far larger than one signed message (64 KiB,
`carbon.transport.models.MAX_BODY`). So the Launchpad sends it ahead of
`battery_submit` as signed `battery_level4_part` calls, each a slice of the
envelope's bytes, to the development-ladder deployment only and from one of
its listed hotkeys. This store keeps them, owner-only, keyed by the
submission digest (the strategy's `parameters.composition_graphs`):
- a part is idempotent by `(submission, part, bytes)`; other bytes for a
  held part are refused (`level4_part_conflict`);
- every part of one submission names the same part count
  (`level4_parts_mismatch`);
- nothing here parses the envelope. The ladder's own daemon entry point
  (`carbon.development_ladder.operate`) assembles it and runs the Level 4
  checks, so the intake never imports a Level 4 module.

Standard library only: the intake is on the miner surfaces' import path.
DEVELOPMENT only.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

#: The bytes of one part, below the 64 KiB signed message once base64-encoded
#: with its fields.
PART_BYTES = 40 * 1024
#: The most parts one envelope may take: base64 of OWNER-L4-VALUES-01's
#: largest submission (4 MiB of documents plus a 16 KiB manifest), with room
#: for the envelope's JSON, over `PART_BYTES` (pinned against
#: `carbon.level4.intake.BOUNDS` by the ladder's tests).
MAX_PARTS = 140
#: The strategy field that names a Level 4 submission (`carbon.battery.level4.FIELD`).
FIELD = "composition_graphs"
PART_TOOL = "battery_level4_part"
STATUS_TOOL = "battery_level4_status"
_SUBMISSION = re.compile(r"sha256:([0-9a-f]{64})\Z")


class PartRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise PartRefused("level4_store_not_owner_only")
    return path


def _write_once(path, data):
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.replace(temporary, path)


def submission_key(submission):
    """The hex of a well-formed submission digest, or `PartRefused`."""
    found = _SUBMISSION.fullmatch(submission) if type(submission) is str else None
    if found is None:
        raise PartRefused("level4_part_malformed")
    return found.group(1)


class Level4Parts:
    """The parts of the envelopes the ladder's listed hotkeys sent."""

    def __init__(self, directory, hotkeys):
        self.directory = _directory(directory)
        self.hotkeys = frozenset(hotkeys)

    def _submission_dir(self, submission):
        return self.directory / submission_key(submission)

    def put(self, hotkey, submission, part, parts, data):
        """Hold one part; returns `held(submission)`."""
        if hotkey not in self.hotkeys:
            raise PartRefused("ladder_hotkey_not_listed")
        if (
            type(part) is not int
            or type(parts) is not int
            or not 1 <= parts <= MAX_PARTS
            or not 0 <= part < parts
            or type(data) is not bytes
            or not data
            or len(data) > PART_BYTES
        ):
            raise PartRefused("level4_part_malformed")
        directory = _directory(self._submission_dir(submission))
        count = directory / "parts"
        if count.exists():
            if count.read_text() != str(parts):
                raise PartRefused("level4_parts_mismatch")
        else:
            _write_once(count, str(parts).encode())
        path = directory / f"part-{part:04d}"
        if path.exists():
            if path.read_bytes() != data:
                raise PartRefused("level4_part_conflict")
        else:
            _write_once(path, data)
        return self.held(submission)

    def held(self, submission):
        """`{"held": [part indices], "parts": n or None}`."""
        directory = self._submission_dir(submission)
        if not directory.is_dir():
            return {"held": [], "parts": None}
        count = directory / "parts"
        parts = int(count.read_text()) if count.exists() else None
        held = sorted(
            int(p.name.removeprefix("part-"))
            for p in directory.glob("part-[0-9][0-9][0-9][0-9]")
        )
        return {"held": held, "parts": parts}

    def complete(self, submission):
        found = self.held(submission)
        return found["parts"] is not None and found["held"] == list(
            range(found["parts"])
        )

    def envelope(self, submission):
        """The envelope's bytes, all parts in order, or None while incomplete."""
        if not self.complete(submission):
            return None
        directory = self._submission_dir(submission)
        parts = self.held(submission)["parts"]
        return b"".join(
            (directory / f"part-{index:04d}").read_bytes() for index in range(parts)
        )


__all__ = [
    "FIELD",
    "MAX_PARTS",
    "PART_BYTES",
    "PART_TOOL",
    "STATUS_TOOL",
    "Level4Parts",
    "PartRefused",
    "submission_key",
]
