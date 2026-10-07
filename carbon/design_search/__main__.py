"""Producer-side design_search commands. No command accepts miner material."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from carbon.design_search.diversity import diversity_report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="design_search")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser(
        "diversity-report", help="aggregate sealed producer bank"
    )
    report.add_argument("--bank", required=True, type=Path)
    report.add_argument("--law", required=True, type=Path)
    args = parser.parse_args(argv)
    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    law = json.loads(args.law.read_text(encoding="utf-8"))
    print(json.dumps(diversity_report(bank, law), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
