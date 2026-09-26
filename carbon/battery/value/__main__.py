"""python -m carbon.battery.value run|resume|status|evaluate|import-references|export"""

from __future__ import annotations

import argparse
import json
import sys

from .contract import ContractError
from .experiment import Experiment, ExperimentError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.value")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume"):
        command = sub.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--workers", type=int, default=1)
        if name == "run":
            command.add_argument("--contract")
    for name in ("status", "evaluate"):
        sub.add_parser(name).add_argument("--root", required=True)
    imported = sub.add_parser("import-references")
    imported.add_argument("--root", required=True)
    imported.add_argument("--records", required=True)
    export = sub.add_parser("export")
    export.add_argument("--root", required=True)
    export.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    experiment = Experiment(args.root)
    try:
        if args.command == "run":
            result = experiment.run(contract_path=args.contract, workers=args.workers)
        elif args.command == "resume":
            if not experiment.manifest_path.exists():
                raise ExperimentError("not_frozen", "use run")
            result = experiment.run(workers=args.workers)
        elif args.command == "status":
            result = experiment.status()
        elif args.command == "evaluate":
            with experiment.lock():
                result = experiment.evaluate()["summary"]
        elif args.command == "import-references":
            with experiment.lock():
                result = experiment.import_references(args.records)
        else:
            result = experiment.export(args.out)
    except (ExperimentError, ContractError) as refused:
        print(json.dumps({"refused": refused.code, "detail": str(refused)}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
