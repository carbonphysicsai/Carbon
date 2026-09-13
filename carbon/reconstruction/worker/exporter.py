"""Fixed, bounded output framing executed inside the isolated worker."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from carbon.reconstruction.worker.model import OUTPUT_BYTES, OUTPUT_MEMBERS

_ROOT = Path("/scratch/output")
_MAX_PATH_BYTES = 1024


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def main() -> int:
    """Write one closed, length-prefixed snapshot to stdout."""

    if _ROOT.is_symlink() or not _ROOT.is_dir():
        return 20
    members: list[Path] = []
    for root, directories, files in os.walk(_ROOT, followlinks=False):
        root_path = Path(root)
        for name in directories:
            directory = root_path / name
            try:
                if not stat.S_ISDIR(directory.lstat().st_mode):
                    return 20
            except OSError:
                return 20
        for name in files:
            members.append(root_path / name)
            if len(members) > OUTPUT_MEMBERS:
                return 20
    output = sys.stdout.buffer
    output.write(_canonical({"schema": "carbon.c03.output-stream.v1"}) + b"\n")
    total = 0
    for member in sorted(members):
        relative = member.relative_to(_ROOT).as_posix()
        if not relative or len(relative.encode("utf-8")) > _MAX_PATH_BYTES:
            return 20
        try:
            descriptor = os.open(member, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            return 20
        try:
            status = os.fstat(descriptor)
            if not stat.S_ISREG(status.st_mode) or status.st_size < 0:
                return 20
            total += status.st_size
            if total > OUTPUT_BYTES:
                return 20
            output.write(_canonical({"path": relative, "size": status.st_size}) + b"\n")
            remaining = status.st_size
            while remaining:
                block = os.read(descriptor, min(1 << 20, remaining))
                if not block:
                    return 20
                output.write(block)
                remaining -= len(block)
        finally:
            os.close(descriptor)
    if not members:
        return 20
    output.write(
        _canonical({"bytes": total, "end": True, "members": len(members)}) + b"\n"
    )
    output.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
