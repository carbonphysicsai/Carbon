"""Write the motor's DEVELOPMENT pool plans: public TRAIN and PRACTICE, and a
private evaluation pool from an operator-held root.

    python scripts/dev/motor/reference/pool_plan.py OUTDIR --root ROOT_FILE
        [--train 150] [--practice 30] [--private 60]

The cold plate's procedure (`scripts/dev/cold_plate/reference/pool_plan.py`)
with this Challenge's own label and domain separation:
- **TRAIN and PRACTICE** are public draws (`population.public_rng`).
- **The private pool** is drawn from a 32-byte operator-held root outside
  the repository, owner-only, created if absent, with a generator seeded by
  HMAC-SHA256(root, label). Only sha256(domain || root) is published.
- The private plan holds the private inputs; it is written owner-only into
  OUTDIR, which must lie outside the repository, and never committed
  (invariant 1).

Sizes are DEVELOPMENT choices scaled to cost (ticket D8, amended).
- A case costs about 18 core-minutes alone (61 rotor positions, pilot).
- Beside the cold plate pools, the host completed about 0.13 motor cases per
  minute. At that rate 300/60/120 would take more than two days; 150/30/60
  take about a third of that.
- Draws are sequential from a fixed generator, so each smaller pool is
  exactly the first N cases of a larger plan with the same label or root.
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

from carbon.motor import population

LABEL = "carbon.motor.pools-v1"
COMMIT_DOMAIN = b"carbon.motor.private-root.v1"


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


def _cases(prefix, draws):
    return [
        {"case_id": f"{prefix}-{i:04d}", "kind": "ordinary", "inputs": case}
        for i, case in enumerate(draws)
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--train", type=int, default=150)
    parser.add_argument("--practice", type=int, default=30)
    parser.add_argument("--private", type=int, default=60)
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
            "batch": f"motor-{name}-v1",
            "population": population.POPULATION_VERSION,
            "label": f"{LABEL}.{name}",
            "draws": attempts,
            "cases": _cases(name, draws),
        }
        (out / f"{name}.plan.json").write_text(
            json.dumps(public[name], indent=1) + "\n"
        )
    draws, attempts = population.draw(
        private_rng(root, f"{LABEL}.private"), args.private
    )
    private = {
        "batch": "motor-private-v1",
        "population": population.POPULATION_VERSION,
        "root_commitment": commitment,
        "draws": attempts,
        "cases": _cases("private", draws),
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
