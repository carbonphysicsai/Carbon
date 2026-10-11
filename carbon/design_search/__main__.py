"""Producer-side design_search commands. No command accepts miner material."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from carbon.design_search import tasks
from carbon.design_search.diversity import diversity_report
from carbon.design_search.power import power_report


def _severity_pairs(values):
    if not values:
        raise tasks.TaskError("battery control severity is required")
    result = {}
    for item in values:
        quantity, separator, number = item.partition("=")
        if not separator or not quantity or not number or quantity in result:
            raise tasks.TaskError("use one quantity=value severity per limit")
        try:
            result[quantity] = float(number)
        except ValueError as exc:
            raise tasks.TaskError("invalid control severity value") from exc
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="design_search")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser(
        "diversity-report", help="aggregate sealed producer bank"
    )
    report.add_argument("--bank", type=Path)
    report.add_argument("--battery-work", type=Path)
    report.add_argument("--journal", type=Path)
    report.add_argument("--law", required=True, type=Path)
    report.add_argument("--bootstrap-seed", type=int)
    report.add_argument("--replicates", type=int)
    report.add_argument("--interval-level", type=float)
    power = commands.add_parser(
        "power-report", help="aggregate producer control separation"
    )
    power.add_argument("--bank", type=Path)
    power.add_argument("--panel-export", type=Path)
    power.add_argument("--battery-work", type=Path)
    power.add_argument("--journal", type=Path)
    power.add_argument("--law", type=Path)
    power.add_argument("--grid-law", type=Path)
    power.add_argument("--continuous-law", type=Path)
    power.add_argument("--accumulation", type=Path)
    power.add_argument("--controls", type=Path)
    power.add_argument("--good-predictor", type=Path)
    power.add_argument("--alpha", required=True, type=float)
    power.add_argument("--power-target", required=True, type=float)
    power.add_argument("--simulation-seed", type=int)
    power.add_argument("--replicates", required=True, type=int)
    power.add_argument("--max-questions", type=int)
    power.add_argument("--bootstrap-seed", type=int)
    power.add_argument("--interval-level", type=float)
    for name in ("edge", "caution", "sign", "path"):
        power.add_argument("--severity-" + name, action="append")
    args = parser.parse_args(argv)
    try:
        if args.command == "diversity-report" and args.battery_work is not None:
            from carbon.design_search import battery_q3_v8

            if args.bank is not None or args.journal is None:
                parser.error(
                    "battery reports require --battery-work and --journal only"
                )
            result = battery_q3_v8.diversity_report(
                battery_q3_v8.load_bank(args.battery_work, args.journal, args.law),
                seed=args.bootstrap_seed,
                replicates=args.replicates,
                interval_level=args.interval_level,
            )
        elif args.command == "diversity-report":
            if args.bank is None:
                parser.error("--bank is required for a generic diversity report")
            result = diversity_report(
                json.loads(args.bank.read_text(encoding="utf-8")),
                json.loads(args.law.read_text(encoding="utf-8")),
            )
        elif args.battery_work is not None:
            from carbon.design_search import battery_q3_v8

            if (
                args.bank is not None
                or args.journal is None
                or args.law is None
                or any(
                    getattr(args, name) is not None
                    for name in (
                        "grid_law",
                        "continuous_law",
                        "accumulation",
                        "panel_export",
                        "controls",
                        "good_predictor",
                        "simulation_seed",
                        "max_questions",
                    )
                )
            ):
                parser.error(
                    "battery power requires --battery-work, --journal and --law"
                )
            result = battery_q3_v8.power_report(
                battery_q3_v8.load_bank(args.battery_work, args.journal, args.law),
                seed=args.bootstrap_seed,
                replicates=args.replicates,
                interval_level=args.interval_level,
                alpha=args.alpha,
                power_target=args.power_target,
                severities={
                    name: _severity_pairs(getattr(args, "severity_" + name))
                    for name in ("edge", "caution", "sign", "path")
                },
            )
        elif args.panel_export is not None:
            from carbon.design_search import producer_panels

            if any(
                getattr(args, name) is not None
                for name in (
                    "bank",
                    "battery_work",
                    "journal",
                    "law",
                    "grid_law",
                    "continuous_law",
                    "good_predictor",
                    "bootstrap_seed",
                    "interval_level",
                )
            ) or any(
                getattr(args, name) is None
                for name in (
                    "controls",
                    "accumulation",
                    "simulation_seed",
                    "max_questions",
                )
            ):
                parser.error("producer panel power registration is incomplete")
            read = lambda path: json.loads(path.read_text(encoding="utf-8"))
            result = producer_panels.panel_power_report(
                read(args.panel_export),
                read(args.controls),
                read(args.accumulation),
                alpha=args.alpha,
                power_target=args.power_target,
                simulation_seed=args.simulation_seed,
                replicates=args.replicates,
                max_questions=args.max_questions,
            )
        else:
            if any(
                getattr(args, name) is None
                for name in (
                    "bank",
                    "controls",
                    "good_predictor",
                    "max_questions",
                    "simulation_seed",
                )
            ) or not (args.grid_law or args.continuous_law or args.law):
                parser.error("generic power registration is incomplete")
            read = lambda path: json.loads(path.read_text(encoding="utf-8"))
            if args.law is not None and (args.grid_law or args.continuous_law):
                parser.error("use --law or separate --grid-law/--continuous-law")
            grid = read(args.grid_law) if args.grid_law else None
            continuous = read(args.continuous_law) if args.continuous_law else None
            if args.law is not None:
                one = read(args.law)
                if one.get("kind") == "grid":
                    grid = one
                elif one.get("kind") == "continuous":
                    continuous = one
                else:
                    parser.error("registered grid or continuous law required")
            result = power_report(
                read(args.bank),
                grid,
                continuous,
                read(args.controls),
                read(args.good_predictor),
                alpha=args.alpha,
                power_target=args.power_target,
                simulation_seed=args.simulation_seed,
                replicates=args.replicates,
                max_questions=args.max_questions,
                accumulation=read(args.accumulation) if args.accumulation else None,
            )
    except (OSError, ValueError, KeyError, TypeError, tasks.TaskError):
        parser.error("invalid producer report registration or sealed bank")
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
