"""Run the motor Q1 fixture panel and write its result.

    python -m scripts.dev.motor.q1_panel --out RESULT.json

See ``carbon.motor.q1_panel``. Public data and the counted replay only: no
solver runs, nothing is spent.
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

from carbon.motor import q1_panel


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as directory:
        result = q1_panel.run(ROOT, directory)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "tau": result["alignment"]["kendall_tau_b"],
                "conditions": len(result["alignment"]["conditions"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
