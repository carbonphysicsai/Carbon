"""python -m carbon.challenge_readiness table|validate [--records DIR]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .record import RECORDS, ReadinessError, load_all, summary, table


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.challenge_readiness")
    parser.add_argument("command", choices=("table", "validate"))
    parser.add_argument("--records", type=Path, default=RECORDS)
    args = parser.parse_args(argv)
    try:
        records = load_all(args.records)
    except ReadinessError as refused:
        print(json.dumps({"refused": refused.code, "detail": refused.detail}))
        return 2
    if args.command == "table":
        print(table(records))
    else:
        print(
            json.dumps(
                [dict(summary(d), digest=g) for d, g in records],
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
