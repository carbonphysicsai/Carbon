"""SR-B1: rebuild EV4's 100-member panel on the operator host's CPU.

    python -m scripts.dev.battery.srb1_ev4_rebuild --out DIR

EV4's original A40 prediction bundles are not retained on any host, so every
member is rebuilt with `Experiment.panel` and `DirectBackend` (CPU, no spend).
- References: EV4's committed decision grid, checked against EV4's
  `references.sha256`, so no PyBaMM solves.
- The EV4 contract is used unchanged, in a fresh experiment root. EV4's
  committed results are not touched or reinterpreted.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EV4 = ROOT / "docs/development/evidence/ev4-2026-10-01"
CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"


def main(argv=None):
    from carbon.battery.value.experiment import Experiment

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    experiment = Experiment(args.out / "experiment", repository=ROOT)
    if not experiment.manifest_path.exists():
        experiment.freeze(CONTRACT)
    plain = gzip.decompress((EV4 / "decision-references.jsonl.gz").read_bytes())
    recorded = (EV4 / "references.sha256").read_text().split()[0]
    if hashlib.sha256(plain).hexdigest() != recorded:
        raise SystemExit("EV4 decision references do not match references.sha256")
    unpacked = args.out / "ev4-decision-references.jsonl"
    unpacked.write_bytes(plain)
    experiment.import_references(unpacked)
    done = experiment.panel()
    print(json.dumps({"reconstructed": len(done["reconstructed"])}), flush=True)
    experiment.evaluate()
    print("evaluated", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
