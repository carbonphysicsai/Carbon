"""Write the cold plate's DEVELOPMENT pool plans: public TRAIN and PRACTICE,
and a private evaluation pool from an operator-held root.

    python scripts/dev/cold_plate/reference/pool_plan.py OUTDIR --root ROOT_FILE
        [--train 400] [--practice 100] [--private 200]

- **TRAIN and PRACTICE** are public draws of the population
  (`population.public_rng`), reproducible by anyone from their labels.
- **The private pool** is drawn from a 32-byte root held by the operator,
  outside the repository: a regular file, not a symlink, readable by its
  owner only. If ROOT_FILE does not exist it is created that way. The draw
  generator is seeded with HMAC-SHA256(root, label), so nothing about the
  private cases can be recomputed without the root.
- **Commit before use.** The private plan records only
  sha256(domain || root): publishing that commits to the root without
  revealing it; revealing the root at retirement lets anyone check it.

The private plan file holds the private inputs. It is written owner-only
into OUTDIR, which must lie outside the repository, and it is never committed
(invariant 1: no hidden evaluation case, seed or root on a public surface).
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

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import population

LABEL = "carbon.cold-plate.pools-v1"
COMMIT_DOMAIN = b"carbon.cold-plate.private-root.v1"
ITERATIONS = 2000  # the pilot: every case agreed between 2,000 and 4,000 to 2e-7 K


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


def _cases(prefix, draws, kind):
    return [
        {
            "case_id": f"{prefix}-{i:04d}",
            "kind": kind,
            "inputs": case,
            "options": {"iterations": ITERATIONS},
        }
        for i, case in enumerate(draws)
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--train", type=int, default=400)
    parser.add_argument("--practice", type=int, default=100)
    parser.add_argument("--private", type=int, default=200)
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if out.is_relative_to(ROOT) or args.root.resolve().is_relative_to(ROOT):
        parser.error("plans and the root must live outside the repository")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = load_or_create_root(args.root)
    commitment = "sha256:" + hashlib.sha256(COMMIT_DOMAIN + root).hexdigest()
    public = {}
    for name, count in (("train", args.train), ("practice", args.practice)):
        draws, attempts = population.draw(
            population.public_rng(f"{LABEL}.{name}"), count
        )
        public[name] = {
            "batch": f"cold-plate-{name}-v1",
            "population": population.POPULATION_VERSION,
            "label": f"{LABEL}.{name}",
            "draws": attempts,
            "cases": _cases(name, draws, "ordinary"),
        }
        (out / f"{name}.plan.json").write_text(
            json.dumps(public[name], indent=1) + "\n"
        )
    draws, attempts = population.draw(
        private_rng(root, f"{LABEL}.private"), args.private
    )
    private = {
        "batch": "cold-plate-private-v1",
        "population": population.POPULATION_VERSION,
        "root_commitment": commitment,
        "draws": attempts,
        "cases": _cases("private", draws, "ordinary"),
    }
    path = out / "private.plan.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(private, indent=1) + "\n")
    print(
        json.dumps(
            {
                "root_commitment": commitment,
                **{
                    name: {"cases": len(plan["cases"]), "draws": plan["draws"]}
                    for name, plan in public.items()
                },
                "private": {"cases": len(private["cases"]), "draws": attempts},
            }
        )
    )


if __name__ == "__main__":
    main()
