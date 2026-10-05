#!/usr/bin/env python3
"""Re-judge a finished attack session's journal with the current oracle.

Read-only closure tool for OWNER-GRAPHITE phase-4 triage. It reads an attack
session's run directory and prints, per attempt, Carbon's verdict and its
evidence digests, plus a summary by outcome and the list of findings. The
executor uses it to close the 35 FAILING_TRIGGER findings of session 1 through
`record_repair`, citing the fix commit and these per-finding verdicts and
digests.

It never writes to the run root and launches nothing: `analysis.attempts` only
reads the journal, and `verify.verify` is called with no `specimen_dir`, so no
specimen is bundled. Point it at a COPY of the run root to be certain; it is
safe on the original, but the triage protocol is strictly read-only there.

    python scripts/dev/attack_rejudge.py <session_dir> \\
        --challenge battery-fastcharge-ageing-development-v1 --level 0

`<session_dir>` holds `ledger/` (a run directory). The canary registry and the
carrier evidence are operator-side hooks (`--canary TOKEN`, repeatable; a
`--carrier FILE` JSON mapping of attempt identity to carrier evidence); both
default to empty, so a run with no planted canaries judges a miner-local action
by its own recorded result alone. Canary tokens are passed on the command line,
never stored in the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from carbon.agent_campaign.attack import analysis, verify
from carbon.agent_campaign.attack.adapter import ADAPTERS
from carbon.agent_campaign.graphite.phase4 import FINISH_TOOL_NAME


def rejudge(session_dir, adapter, *, canaries=(), carrier=None):
    """Every attempt's verdict record, in run order (read-only)."""
    # The phase-4 stop rule's finish call ends a session and probes nothing.
    found = [a for a in analysis.attempts(session_dir) if a.tool != FINISH_TOOL_NAME]
    verdicts = [
        verify.verify(attempt, adapter, canaries=canaries, carrier=carrier)
        for attempt in found
    ]
    summary = {}
    for verdict in verdicts:
        key = verdict.outcome + ("/finding" if verdict.finding else "")
        summary[key] = summary.get(key, 0) + 1
    return {
        "session_dir": str(session_dir),
        "challenge": adapter.challenge_id,
        "level": adapter.level,
        "attempts": len(found),
        "summary": summary,
        "finding_count": sum(1 for v in verdicts if v.finding),
        "findings": [v.record() for v in verdicts if v.finding],
        "usability": [v.usability for v in verdicts if v.usability],
        "verdicts": [v.record() for v in verdicts],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", help="a run directory holding ledger/ (a copy)")
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--level", type=int, default=0)
    parser.add_argument(
        "--canary",
        action="append",
        default=[],
        help="a registered canary token (repeatable); never from the repository",
    )
    parser.add_argument(
        "--carrier",
        default=None,
        help="a JSON file mapping attempt identity to carrier evidence",
    )
    args = parser.parse_args(argv)
    adapter = ADAPTERS[(args.challenge, args.level)]
    carrier = None
    if args.carrier is not None:
        evidence = json.loads(Path(args.carrier).read_text())

        def carrier(attempt):
            return evidence.get(attempt.identity, {})

    report = rejudge(
        args.session_dir, adapter, canaries=tuple(args.canary), carrier=carrier
    )
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
