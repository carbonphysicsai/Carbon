"""python -m carbon.battery.value
run|resume|freeze|status|evaluate|import-references|import-predictions|export|optimize
"""

from __future__ import annotations

import argparse
import json
import sys

from .contract import ContractError
from .experiment import Experiment, ExperimentError
from .optimizer import OptimizerError


def _optimize(experiment, args):
    from . import optimizer as op

    with experiment.lock():
        if args.action == "import-grid":
            return op.import_grids(experiment, args.source)
        if args.action == "select":
            selection = op.run_select(experiment)
            return {
                "members": selection["members"],
                "mode_d": {
                    m: r.get("design", r["status"])
                    for m, r in selection["mode_d"].items()
                },
                "designs": selection["designs"],
                "mode_d_solves": selection["mode_d_solves"],
                "mode_x_solves": selection["mode_x_solves"],
                "jobs": len(selection["jobs"]),
                "jobs_file": str(experiment.root / "optimizer" / "jobs.json"),
            }
        if args.action == "import-references":
            return op.import_references(experiment, args.records)
        return op.run_report(experiment)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.value")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume"):
        command = sub.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--workers", type=int, default=1)
        if name == "run":
            command.add_argument("--contract")
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--root", required=True)
    freeze.add_argument("--contract", required=True)
    for name in ("status", "evaluate"):
        sub.add_parser(name).add_argument("--root", required=True)
    imported = sub.add_parser("import-references")
    imported.add_argument("--root", required=True)
    imported.add_argument("--records", required=True)
    predictions = sub.add_parser("import-predictions")
    predictions.add_argument("--root", required=True)
    predictions.add_argument("--source", required=True)
    export = sub.add_parser("export")
    export.add_argument("--root", required=True)
    export.add_argument("--out", required=True)
    optimize = sub.add_parser("optimize")
    optimize.add_argument(
        "action", choices=("import-grid", "select", "import-references", "report")
    )
    optimize.add_argument("--root", required=True)
    optimize.add_argument("--source", help="import-grid: a pod's grid directory")
    optimize.add_argument("--records", help="import-references: records.jsonl")
    args = parser.parse_args(argv)
    experiment = Experiment(args.root)
    try:
        if args.command == "run":
            result = experiment.run(contract_path=args.contract, workers=args.workers)
        elif args.command == "resume":
            if not experiment.manifest_path.exists():
                raise ExperimentError("not_frozen", "use run")
            result = experiment.run(workers=args.workers)
        elif args.command == "freeze":
            with experiment.lock():
                manifest = experiment.freeze(args.contract)
            result = {
                "contract": manifest["contract"]["contract_id"],
                "contract_digest": manifest["contract_digest"],
                "decision_cases": manifest["decision_cases"],
                "members": len(manifest["panel"]),
            }
        elif args.command == "status":
            result = experiment.status()
        elif args.command == "evaluate":
            with experiment.lock():
                result = experiment.evaluate()["summary"]
        elif args.command == "import-references":
            with experiment.lock():
                result = experiment.import_references(args.records)
        elif args.command == "import-predictions":
            with experiment.lock():
                result = experiment.import_predictions(args.source)
        elif args.command == "optimize":
            result = _optimize(experiment, args)
        else:
            result = experiment.export(args.out)
    except (ExperimentError, ContractError, OptimizerError) as refused:
        print(json.dumps({"refused": refused.code, "detail": str(refused)}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
