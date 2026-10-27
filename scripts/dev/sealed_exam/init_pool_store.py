"""Create (or check) a receiver's lean pool store: the one command for the operator.

A launch receiver that grades (`--auto-grade`, or the operator `--retain-task`) files each
counted grade in a lean POOL STORE (a SQLite file the king-of-the-hill comparison and the
weights operator read). The receiver never creates one (`direct_receiver._open_pool_store`
refuses a path that is not an existing file), and the empty directories under
/var/lib/carbon-val/pools/ are not stores. Create one per Challenge version:

    python -B scripts/dev/sealed_exam/init_pool_store.py \
        --path /var/lib/carbon-val/pools/electric-motor-magnetics/lean-pool.sqlite3

then give that exact path to the receiver (`receiver_setup prepare ... --auto-grade
--auto-grade-pool-store <path>`) and to the weights operator's `--lean-pool
CHALLENGE=<path>`. Run it as the receiver's own user (carbon-val): the file is created
0600 and its directory must be that user's, with no group or world write (SQLite's WAL
files live beside it).

    --check   report on an existing store (the schema is idempotent); creates nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path


class Refused(Exception):
    pass


def _directory(path):
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise Refused(
            f"the directory {parent} does not exist (create it first, as this user)"
        )
    info = os.lstat(parent)
    if info.st_uid != os.getuid():
        raise Refused(f"the directory {parent} is not owned by this user")
    if info.st_mode & 0o022:
        raise Refused(f"the directory {parent} is group or world writable")
    if not os.access(parent, os.W_OK | os.X_OK):
        raise Refused(f"the directory {parent} is not writable by this user")


def create(path):
    from carbon.battery.pool_store import PoolStore

    path = Path(path)
    if not path.is_absolute():
        raise Refused("give an absolute path")
    if path.is_symlink() or path.exists():
        raise Refused(f"{path} already exists; use --check, or another path")
    _directory(path)
    PoolStore(path)  # creates the schema and sets the file 0600
    return check(path, created=True)


def check(path, *, created=False):
    from carbon.battery.pool_store import PoolStore

    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Refused(f"{path} is not an existing regular file")
    info = os.lstat(path)
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise Refused(f"{path} is not owner-only (0600) and this user's")
    store = PoolStore(path)
    with store.db() as db:
        tables = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    return {
        "status": "POOL_STORE_READY",
        "path": str(path),
        "created": created,
        "mode": oct(stat.S_IMODE(info.st_mode)),
        "tables": tables,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = check(args.path) if args.check else create(args.path)
    except Refused as refused:
        print(json.dumps({"refused": str(refused)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
