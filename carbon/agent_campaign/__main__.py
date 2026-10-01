"""`python -m carbon.agent_campaign`: capabilities, grant template, study sheet."""

from __future__ import annotations

import argparse
import json
import sys

from . import grant, mira, study


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.agent_campaign")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities", help="the Mira adapter's verified capabilities")
    sub.add_parser("grant-template", help="the spending grant the owner completes")
    sheet = sub.add_parser("study", help="write or check the Level-0 study sheet")
    sheet.add_argument("--out")
    sheet.add_argument("--check")
    args = parser.parse_args(argv)
    if args.command == "capabilities":
        caps = mira.MiraProvider().capabilities()
        print(
            json.dumps(
                {
                    "provider": caps.provider,
                    "product": mira.PRODUCT_URL,
                    "mode": caps.mode.value,
                    "verified": caps.verified,
                    "dispatchable": caps.dispatchable,
                    "basis": caps.basis,
                    "blocked": mira.BLOCKED,
                },
                indent=1,
            )
        )
        return 0
    if args.command == "grant-template":
        print(json.dumps(grant.template(mira.PROVIDER), indent=1))
        return 0
    if args.check:
        changed = study.drift(args.check)
        print(
            json.dumps(changed, indent=1, sort_keys=True) if changed else "no pin drift"
        )
        return 1 if changed else 0
    if args.out:
        print(study.write(args.out))
        return 0
    parser.error("study needs --out or --check")
    return 2


if __name__ == "__main__":
    sys.exit(main())
