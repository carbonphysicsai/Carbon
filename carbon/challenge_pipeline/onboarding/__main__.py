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
    args = parser.parse_args(argv)
    try:
        draft = packet.generate(packet.read_json(args.brief), args.root)
        if args.compare:
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
