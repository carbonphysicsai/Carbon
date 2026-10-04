"""Plan or run the bounded accelerator-cooling DEVELOPMENT decision study.

Fixture smoke test (analytical pseudo-reference, never counted CFD):

    python -m scripts.dev.cold_plate.decision_study fixture --out OUT

Prepare the owner-reviewable 48-execution CFD plan without running it:

    python -m scripts.dev.cold_plate.decision_study plan-cfd --out PLAN.json

After separately authorized execution with ``reference.run_batch``, import
retained artifacts and run the counted comparison:

    python -m scripts.dev.cold_plate.decision_study counted \
        --reference-dir CFD_DIR --out OUT
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import decision_study

DEFAULT_CONFIG = (
    ROOT
    / "docs"
    / "development"
    / "studies"
    / "AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json"
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    fixture = subparsers.add_parser("fixture")
    fixture.add_argument("--out", type=Path, required=True)
    plan = subparsers.add_parser("plan-cfd")
    plan.add_argument("--out", type=Path, required=True)
    retry = subparsers.add_parser("plan-retry")
    retry.add_argument("--initial-dir", type=Path, required=True)
    retry.add_argument("--out", type=Path, required=True)
    counted = subparsers.add_parser("counted")
    counted.add_argument("--reference-dir", type=Path, action="append", required=True)
    counted.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    config = decision_study.load_config(args.config, repository=ROOT)
    if args.command in ("plan-cfd", "plan-retry"):
        document = (
            decision_study.reference_plan(config, attempt=1)
            if args.command == "plan-cfd"
            else decision_study.reference_retry_plan(config, args.initial_dir)
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        budget = config["budgets"]
        print(
            json.dumps(
                {
                    "plan": str(args.out),
                    "cases": len(document["cases"]),
                    "retry_reserve": budget["retry_reserve"],
                    "hard_solver_execution_cap": budget["hard_solver_execution_cap"],
                    "cpus_per_execution": budget["cpus_per_solver_execution"],
                    "parallel": budget["parallel_solver_executions"],
                    "timeout_s": budget["solver_timeout_seconds"],
                    "estimated_initial_core_hours": budget[
                        "estimated_initial_core_hours"
                    ],
                    "estimated_hard_cap_core_hours": budget[
                        "estimated_hard_cap_core_hours"
                    ],
                    "authorized": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "fixture":
        reference = decision_study.fixture_reference(config)
        label = "ANALYTICAL_FIXTURE_SMOKE_TEST_NOT_CFD"
    else:
        reference = decision_study.import_counted_cfd(config, args.reference_dir)
        label = "COUNTED_CFD_DEVELOPMENT_EVIDENCE"
    result = decision_study.run(
        config,
        repository=ROOT,
        reference=reference,
        output=args.out,
        evidence_label=label,
    )
    print(
        json.dumps(
            {
                "result": str(args.out / "result.json"),
                "report": str(args.out / "report.md"),
                "evidence_class": result["evidence_class"],
                "arms": len(result["arms"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
