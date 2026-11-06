"""Reclaim the trusted stage items of FINISHED operations already on a receiver's disk (GPUYard 6 Nov, Lead 07:00).

    python3 -B scripts/dev/reclaim_operation_stages.py <receiver state root> [--apply] [--min-age-hours 6]

The carrier now reclaims each operation's pinned ``uv-bin`` (~52 MB) and copied ``overlay`` tree itself, once its
container is confirmed removed (`research_carrier.reclaim_trusted_stage`). This tool does the same for operations
written before that fix, under ``<root>/owners/*/ledger/operation-*/input``. Self-contained (standard library only), so
it runs against a door's current revision.

An operation is touched only when BOTH hold:
- its input is at least ``--min-age-hours`` old (default 6; the longest worker wall is 648 s, so no live run is that
  old), and
- the container its ``intent.json`` names is absent (``docker ps -aq --filter name=^<container>$`` answers empty; an
  unanswered query skips the operation).

Dry run by default: it prints counts and bytes only (no ids, paths or hotkeys). ``--apply`` reclaims, writing
``reclaimed.json`` (the uv sha256 and the overlay's own receipt) beside the removed items first. Everything else in the
input (the program, a build's ``example.npz``, which retention reads) stays.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

RECLAIMED = "reclaimed.json"


def _container_absent(name):
    try:
        done = subprocess.run(
            ["docker", "ps", "-aq", "--filter", "name=^" + name + "$"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0 and not done.stdout.strip()


def _writable(path):
    path.chmod(0o700 if path.is_dir() and not path.is_symlink() else 0o600)


def _size(path):
    if path.is_file() and not path.is_symlink():
        return path.stat().st_size
    if path.is_dir() and not path.is_symlink():
        return sum(
            p.stat().st_size
            for p in path.rglob("*")
            if p.is_file() and not p.is_symlink()
        )
    return 0


def reclaim(stage):
    """The carrier's `reclaim_trusted_stage`, standalone. Returns the bytes freed."""
    uv, overlay = stage / "uv-bin", stage / "overlay"
    has_uv = uv.is_file() and not uv.is_symlink()
    has_overlay = overlay.is_dir() and not overlay.is_symlink()
    if not (has_uv or has_overlay):
        return 0
    receipt = overlay / ".overlay.json"
    record = {
        "schema": "carbon.autoresearch.reclaimed-stage.v1",
        "uv_sha256": (
            ("sha256:" + hashlib.sha256(uv.read_bytes()).hexdigest())
            if has_uv
            else None
        ),
        "overlay_receipt": (
            json.loads(receipt.read_bytes())
            if has_overlay and receipt.is_file() and not receipt.is_symlink()
            else None
        ),
    }
    stage.chmod(0o755)
    marker = stage / RECLAIMED
    if not marker.exists():
        marker.write_bytes(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        )
        marker.chmod(0o444)
    freed = 0
    if has_uv:
        freed += uv.stat().st_size
        _writable(uv)
        uv.unlink()
    if has_overlay:
        freed += _size(overlay)
        for entry in sorted(overlay.rglob("*"), reverse=True):
            if not entry.is_symlink():
                _writable(entry)
        _writable(overlay)
        shutil.rmtree(overlay)
    stage.chmod(0o755)
    return freed


def main(argv=None):
    parser = argparse.ArgumentParser(prog="reclaim_operation_stages")
    parser.add_argument(
        "root", type=Path, help="the receiver state root (holds owners/)"
    )
    parser.add_argument(
        "--apply", action="store_true", help="reclaim (default: dry run)"
    )
    parser.add_argument("--min-age-hours", type=float, default=6.0)
    args = parser.parse_args(argv)
    if args.min_age_hours < 1:
        parser.error("--min-age-hours below 1 could touch a live operation")
    floor = time.time() - args.min_age_hours * 3600
    out = {"apply": args.apply, "stages_with_items": 0, "eligible": 0, "too_young": 0,
           "container_present_or_unknown": 0, "no_intent": 0, "bytes_eligible": 0,
           "bytes_freed": 0, "errors": 0}  # fmt: skip
    for stage in sorted(args.root.glob("owners/*/ledger/operation-*/input")):
        if stage.is_symlink() or not stage.is_dir():
            continue
        items = _size(stage / "uv-bin") + _size(stage / "overlay")
        if not items:
            continue
        out["stages_with_items"] += 1
        if stage.stat().st_mtime > floor:
            out["too_young"] += 1
            continue
        try:
            container = json.loads((stage.parent / "intent.json").read_bytes())[
                "container"
            ]
        except (OSError, ValueError, KeyError, TypeError):
            out["no_intent"] += 1
            continue
        if type(container) is not str or not _container_absent(container):
            out["container_present_or_unknown"] += 1
            continue
        out["eligible"] += 1
        out["bytes_eligible"] += items
        if args.apply:
            try:
                out["bytes_freed"] += reclaim(stage)
            except (OSError, ValueError):
                out["errors"] += 1
    out["gib_eligible"] = round(out["bytes_eligible"] / 1024**3, 2)
    out["gib_freed"] = round(out["bytes_freed"] / 1024**3, 2)
    print(json.dumps(out, indent=1))
    return 0 if out["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
