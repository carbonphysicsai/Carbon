"""Producer-side design_search commands. No command accepts miner material."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from carbon.design_search import tasks
from carbon.design_search.diversity import diversity_report
from carbon.design_search.power import power_report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="design_search")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser(
        "diversity-report", help="aggregate sealed producer bank"
    )
    report.add_argument("--bank", required=True, type=Path)
    report.add_argument("--law", required=True, type=Path)
    power = commands.add_parser(
        "power-report", help="aggregate producer control separation"
    )
    power.add_argument("--bank", required=True, type=Path)
    power.add_argument("--grid-law", required=True, type=Path)
    power.add_argument("--continuous-law", required=True, type=Path)
    power.add_argument("--controls", required=True, type=Path)
    power.add_argument("--good-predictor", required=True, type=Path)
    power.add_argument("--alpha", required=True, type=float)
    power.add_argument("--power-target", required=True, type=float)
    power.add_argument("--simulation-seed", required=True, type=int)
    power.add_argument("--replicates", required=True, type=int)
    power.add_argument("--max-questions", required=True, type=int)
    args = parser.parse_args(argv)
    if args.command == "diversity-report":
        bank = json.loads(args.bank.read_text(encoding="utf-8"))
        law = json.loads(args.law.read_text(encoding="utf-8"))
        result = diversity_report(bank, law)
    else:
        try:
            read = lambda path: json.loads(path.read_text(encoding="utf-8"))
            result = power_report(
                read(args.bank),
                read(args.grid_law),
                read(args.continuous_law),
                read(args.controls),
                read(args.good_predictor),
                alpha=args.alpha,
                power_target=args.power_target,
                simulation_seed=args.simulation_seed,
                replicates=args.replicates,
                max_questions=args.max_questions,
            )
        except (OSError, ValueError, KeyError, TypeError, tasks.TaskError):
            parser.error("invalid producer power registration")
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
