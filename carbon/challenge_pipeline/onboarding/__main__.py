"""Explicit-file offline draft commands. Never invokes a solver or network."""

import argparse
import json
import sys
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_pipeline.onboarding"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("packet")
    p.add_argument("--brief", type=Path, required=True)
    p.add_argument("--compare", help="real packet path relative to repository")
    p.add_argument("--format", choices=("json", "markdown"), default="markdown")
    law_parser = sub.add_parser("law")
    law_parser.add_argument("--brief", type=Path, required=True)
    law_parser.add_argument(
        "--panel", type=Path, help="explicit non-hidden DEVELOPMENT export"
    )
    law_parser.add_argument(
        "--law-source", help="existing proposal, relative public repository path"
    )
    panel_parser = sub.add_parser("panel")
    panel_parser.add_argument("--brief", type=Path, required=True)
    panel_parser.add_argument(
        "--seed", type=Path, help="explicit proposed physical/rung manifest"
    )
    panel_parser.add_argument(
        "--reuse", type=Path, help="non-hidden completed AND scheduled identity index"
    )
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--challenge", required=True)
    status_parser.add_argument(
        "--bindings", help="public artifact path bindings for additional challenges"
    )
    status_parser.add_argument("--format", choices=("text", "json"), default="text")
    status_parser.add_argument(
        "--main-ref", default="origin/main", help="locally available main ref; no fetch"
    )
    pack_parser = sub.add_parser(
        "pack",
        help="provenance and freshness of a committed evidence pack (read only)",
    )
    pack_parser.add_argument(
        "--run", required=True, help="the pack's run record, relative to the repository"
    )
    pack_parser.add_argument("--format", choices=("text", "json"), default="text")
    readiness_parser = sub.add_parser("readiness")
    readiness_parser.add_argument(
        "--challenge", help="omit for ranked eleven-family report"
    )
    readiness_parser.add_argument("--main-ref", default="origin/main")
    readiness_parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    if args.command == "pack":
        from carbon.challenge_pipeline.onboarding import provenance

        report = provenance.check(args.root, args.run)
        print(
            json.dumps(report, indent=1, sort_keys=True)
            if args.format == "json"
            else provenance.render(report)
        )
        # Freshness is a reported status; only a provenance problem fails.
        return 1 if report["provenance_problems"] else 0
    try:
        if args.command in ("status", "readiness"):
            from carbon.challenge_pipeline.onboarding import evidence_readiness, status

            if args.command == "readiness":
                result = (
                    evidence_readiness.generate(
                        args.root, args.challenge, main_ref=args.main_ref
                    )
                    if args.challenge
                    else evidence_readiness.portfolio(args.root, main_ref=args.main_ref)
                )
                if args.format == "text":
                    reports = result if isinstance(result, list) else [result]
                    print("\n\n".join(evidence_readiness.render(r) for r in reports))
                else:
                    print(json.dumps(result, indent=2, allow_nan=False))
                return 0

            result = status.generate(
                args.root,
                args.challenge,
                bindings_path=args.bindings or status.BINDINGS,
                main_ref=args.main_ref,
            )
            # Preserve the historical renderer used by retained tool-run receipts.
            result["evidence_readiness"] = evidence_readiness.generate(
                args.root, args.challenge, main_ref=args.main_ref
            )
            if args.format == "text":
                print(status.render(result))
                print(evidence_readiness.render(result["evidence_readiness"]))
                return 0
        else:
            draft = packet.generate(packet.read_json(args.brief), args.root)
        if args.command == "status":
            pass
        elif args.command == "panel":
            from carbon.challenge_pipeline.onboarding import panel

            result = panel.generate(
                draft,
                seed=packet.read_json(args.seed) if args.seed else None,
                reuse=packet.read_json(args.reuse) if args.reuse else None,
            )
        elif args.command == "law":
            from carbon.challenge_pipeline.onboarding import law

            result = law.generate(
                draft,
                export=packet.read_json(args.panel) if args.panel else None,
                law_source=(
                    packet.read_json(packet.source_path(args.root, args.law_source))
                    if args.law_source
                    else None
                ),
            )
        elif args.compare:
            result = packet.compare(
                draft,
                packet.source_path(args.root, args.compare).read_text(encoding="utf-8"),
            )
        elif args.format == "markdown":
            print(packet.render(draft))
            return 0
        else:
            result = draft
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (packet.DraftError, OSError, UnicodeError):
        print(
            "onboarding refused: invalid, missing or unverified input", file=sys.stderr
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
