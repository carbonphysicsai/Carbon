"""`python -m scripts.dev.battery_validator_service <command> --config SERVICE.json`.

Run from the repository root (a systemd unit sets `WorkingDirectory`). Each
command prints one JSON document. Exit codes: 0 done or ready, 2 refused by a
named code (nothing changed), 3 running but unhealthy.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading

from carbon.battery.deployment import EvaluationUnavailable

from . import backup, service, supervisor


def _print(value):
    print(json.dumps(value, sort_keys=True, indent=2, default=str))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scripts.dev.battery_validator_service"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "parity", "status", "backup", "supervise"):
        sub.add_parser(name).add_argument("--config", required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--config", required=True)
    restore.add_argument("--from", dest="source", required=True)
    units = sub.add_parser("units")
    units.add_argument("--config", required=True)
    units.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("preflight", "parity"):
            run = (
                service.preflight
                if args.command == "preflight"
                else service.parity_report
            )
            report = run(args.config)
            _print(report)
            return 0 if report["ready"] else 2
        if args.command == "status":
            found = service.status(args.config)
            _print(found)
            return 0 if found["healthy"] else 3
        if args.command == "backup":
            _print(backup.backup(args.config))
            return 0
        if args.command == "restore":
            _print(backup.restore(args.config, args.source))
            return 0
        if args.command == "units":
            _print(supervisor.units(args.config, args.out))
            return 0
        stop = threading.Event()
        for number in (signal.SIGTERM, signal.SIGINT):
            signal.signal(number, lambda *_: stop.set())
        return supervisor.supervise(args.config, stop=stop)
    except service.ServiceRefused as refused:
        _print(refused.as_dict())
        return 2
    except EvaluationUnavailable as refused:
        _print({"refused": refused.code})
        return 2


if __name__ == "__main__":
    sys.exit(main())
