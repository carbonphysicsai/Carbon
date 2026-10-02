"""Generate the photonic coupler's DEVELOPMENT pools: public TRAIN and
PRACTICE with their reference outputs, and a private evaluation pool from an
operator-held root.

    python scripts/dev/photonic/pools.py PRIVATE_DIR --root ROOT_FILE
        --public PUBLIC_DIR [--train 1000] [--practice 200] [--private 500]

The reference is arithmetic on the committed tables, so the pools are
generated whole, not planned and run:
- **TRAIN and PRACTICE** are public draws (`population.public_rng`), written
  to PUBLIC_DIR with their outputs; anyone can regenerate them.
- **The private pool** is drawn from a 32-byte root held by the operator,
  outside the repository, owner-only, created if absent; its generator is
  seeded with HMAC-SHA256(root, label). Only sha256(domain || root) is
  published (`commitment.json`), which commits to the root without revealing
  it. Its inputs and outputs are written owner-only into PRIVATE_DIR, which
  must lie outside the repository, and are never committed (invariant 1).

The root handling is the cold plate's (`scripts/dev/cold_plate/reference/
pool_plan.py`), with this Challenge's own domain separation.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import random
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.photonic import exam, population, reference

LABEL = "carbon.photonic.pools-v1"
COMMIT_DOMAIN = b"carbon.photonic.private-root.v1"
POOL_SCHEMA = "carbon.photonic.pool-record.v1"


def load_or_create_root(path):
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(os.urandom(32))
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit("the root must be a regular file, not a link")
    if info.st_mode & 0o077:
        raise SystemExit("the root must be readable by its owner only")
    data = path.read_bytes()
    if len(data) != 32:
        raise SystemExit("the root must be exactly 32 bytes")
    return data


def private_rng(root, label):
    seed = hmac.new(root, label.encode(), hashlib.sha256).digest()[:8]
    return random.Random(int.from_bytes(seed, "big"))


def records(prefix, draws, tables):
    out = []
    for i, inputs in enumerate(draws):
        outputs = reference.evaluate(inputs, tables)
        failed = [k for k, v in exam.gates(outputs).items() if v == exam.FAIL]
        out.append(
            {
                "schema": POOL_SCHEMA,
                "case_id": f"{prefix}-{i:04d}",
                "inputs": inputs,
                "status": "REFERENCE_INVALID" if failed else "OK",
                "reasons": [f"reference fails gates {failed}"] if failed else [],
                "outputs": outputs,
            }
        )
    return out


def write_jsonl(path, rows, mode=0o644):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("private_dir", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--tables", type=Path, default=reference.TABLES)
    parser.add_argument("--train", type=int, default=1000)
    parser.add_argument("--practice", type=int, default=200)
    parser.add_argument("--private", type=int, default=500)
    args = parser.parse_args(argv)
    private_dir = args.private_dir.resolve()
    if private_dir.is_relative_to(ROOT) or args.root.resolve().is_relative_to(ROOT):
        parser.error("the private pool and the root must live outside the repository")
    tables = reference.load_tables(args.tables)
    tables_sha = "sha256:" + hashlib.sha256(args.tables.read_bytes()).hexdigest()
    args.public.mkdir(parents=True, exist_ok=True)
    summary = {
        "population": population.POPULATION_VERSION,
        "tables": tables_sha,
        "z_points": reference.Z_POINTS,
    }
    for name, count in (("train", args.train), ("practice", args.practice)):
        label = f"{LABEL}.{name}"
        rows = records(
            name, population.draw(population.public_rng(label), count), tables
        )
        write_jsonl(args.public / f"{name}.jsonl", rows)
        summary[name] = {
            "label": label,
            "cases": count,
            "ok": sum(r["status"] == "OK" for r in rows),
        }
    root = load_or_create_root(args.root)
    commitment = "sha256:" + hashlib.sha256(COMMIT_DOMAIN + root).hexdigest()
    rows = records(
        "private",
        population.draw(private_rng(root, f"{LABEL}.private"), args.private),
        tables,
    )
    private_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_jsonl(private_dir / "private.jsonl", rows, mode=0o600)
    summary["private"] = {
        "root_commitment": commitment,
        "cases": args.private,
        "ok": sum(r["status"] == "OK" for r in rows),
    }
    (args.public / "pools.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
