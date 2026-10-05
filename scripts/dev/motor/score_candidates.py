"""Run SR-M1 (motor score candidates) and write its result.

    python -m scripts.dev.motor.score_candidates --out RESULT.json

Definitions were registered in `.agent/tickets/SR-M1_motor_score_candidates.md`
before computing. Public data and the counted replay only; nothing spent.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.motor import score_candidates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as directory:
        result = score_candidates.run(ROOT, directory)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    widened = result["widened_panel"]
    print(json.dumps({c: v["kendall_tau_b"] for c, v in widened.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
