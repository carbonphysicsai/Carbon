"""Construct, plan and evaluate the bounded motor DEVELOPMENT decision study.

    python -m scripts.dev.motor.decision_study construct --out CONSTRUCTION_DIR
    python -m scripts.dev.motor.decision_study plan --construction DIR \
        --solver-image IMAGE@sha256:DIGEST --out PLAN.json
    python -m scripts.dev.motor.decision_study evaluate-fixture \
        --construction DIR --out EVALUATION_DIR

No command in this module launches GetDP. The separate batch runner executes a
registered plan only after durable ledger reservation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.motor import decision_study

DEFAULT_CONFIG = (
    ROOT / "docs" / "development" / "studies" / "MOTOR_SYNTHETIC_DECISION_V1.json"
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    construction = subparsers.add_parser("construct")
    construction.add_argument("--out", type=Path, required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--construction", type=Path, required=True)
    plan.add_argument("--solver-image", required=True)
    plan.add_argument("--out", type=Path, required=True)
    retry = subparsers.add_parser("retry-plan")
    retry.add_argument("--initial", type=Path, required=True)
    retry.add_argument("--out", type=Path, required=True)
    fixture = subparsers.add_parser("evaluate-fixture")
    fixture.add_argument("--construction", type=Path, required=True)
    fixture.add_argument("--out", type=Path, required=True)
    counted = subparsers.add_parser("evaluate-counted")
    counted.add_argument("--construction", type=Path, required=True)
    counted.add_argument("--reference", type=Path, action="append", required=True)
    counted.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    config = decision_study.load_config(args.config, repository=ROOT)
    if args.command == "construct":
        document = decision_study.construct(config, repository=ROOT, output=args.out)
        summary = {
            "construction": str(args.out / "construction.json"),
            "construction_identity_digest": document["construction_identity_digest"],
            "state": document["state"],
        }
    elif args.command == "plan":
        _, construction_document, _, _ = decision_study.load_construction(
            config, repository=ROOT, directory=args.construction
        )
        document = decision_study.reference_plan(
            config,
            construction_document["construction_identity_digest"],
            solver_image=args.solver_image,
        )
        if args.out.exists():
            parser.error("plan output already exists")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        summary = {
            "plan": str(args.out),
            "campaign_id": document["campaign"]["campaign_id"],
            "reserved_attempt_cap": document["campaign"]["total_execution_limit"],
        }
    elif args.command == "retry-plan":
        document = decision_study.reference_retry_plan(config, args.initial)
        if args.out.exists():
            parser.error("retry plan output already exists")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        summary = {"retry_plan": str(args.out), "cases": len(document["cases"])}
    elif args.command == "evaluate-fixture":
        document = decision_study.evaluate(
            config,
            repository=ROOT,
            construction_directory=args.construction,
            reference=decision_study.fixture_reference(config),
            output=args.out,
            evidence_label="ANALYTICAL_FIXTURE_NOT_GETDP_EVIDENCE",
        )
        summary = {
            "result": str(args.out / "result.json"),
            "schema": document["schema"],
        }
    else:
        reference = decision_study.import_counted_getdp(config, args.reference)
        document = decision_study.evaluate(
            config,
            repository=ROOT,
            construction_directory=args.construction,
            reference=reference,
            output=args.out,
            evidence_label="COUNTED_GETDP",
        )
        summary = {
            "result": str(args.out / "result.json"),
            "schema": document["schema"],
        }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
