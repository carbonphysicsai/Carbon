"""List, and settle, an owner's worker operations left RESERVED by a dead run (the supported way).

A grade whose worker operation died after its reservation leaves the operation RESERVED in the
owner's campaign ledger; every later use of that operation identity then refuses with
``research operation ambiguous; reconcile, never duplicate`` (and the receiver's close with
``direct_receiver_cleanup_unresolved``). Nobody edits the ledger by hand. The supported settle is
``research_carrier.reconcile_worker``: it removes exactly that operation's container (if any
survives), refuses unless cleanup is observed, and finishes the operation FAILED_INFRA with the
whole original reservation kept as conservative consumption. It never dispatches, retries or
duplicates work.

Stop the receiver's serve unit first (this takes the receiver's own state lock, so it refuses while
the receiver runs), then, as the receiver's user (carbon-val) with its checkout:

    python -B scripts/dev/sealed_exam/reconcile_dead_operation.py \
        --config <receiver.json> --owner <miner hotkey ss58> --list
    python -B scripts/dev/sealed_exam/reconcile_dead_operation.py \
        --config <receiver.json> --owner <miner hotkey ss58> --operation regrade-timed-<hex>

What this does NOT do: a settled FAILED_INFRA identity is a stored result, so the same grade
identity is never run again (no duplicate). The miner's recipe is graded afresh by a NEW task (its
resubmission), in the slot the failed grade already gave back; this settle only clears the
ambiguity so the receiver can close and restart cleanly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def open_operations(operations):
    """The RESERVED operations among a ledger status listing, oldest first."""
    return sorted(
        (op for op in operations if op.get("state") == "RESERVED"),
        key=lambda op: op.get("created") or 0,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--operation")
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_bytes())
    root = Path(config["root"])
    from scripts.dev.miner_launchpad.controller import LockHeld, owner_lock

    try:
        with owner_lock(root):
            ledger_root = (
                root / hashlib.sha256(args.owner.encode()).hexdigest() / "ledger"
            )
            if not (ledger_root / "campaign.sqlite3").is_file():
                print(json.dumps({"refused": "no campaign ledger for this owner"}))
                return 1
            from carbon.development_session.research_ledger import CampaignLedger

            ledger = CampaignLedger(ledger_root)
            if args.list:
                found = open_operations(ledger.status(owner=args.owner)["operations"])
                print(
                    json.dumps(
                        [
                            {
                                key: op.get(key)
                                for key in ("id", "phase", "state", "created")
                            }
                            for op in found
                        ],
                        indent=1,
                    )
                )
                return 0
            from carbon.development_session.research_carrier import reconcile_worker

            result = reconcile_worker(ledger, owner=args.owner, identity=args.operation)
            print(json.dumps(result, sort_keys=True, default=str))
            return 0
    except LockHeld:
        print(
            json.dumps(
                {"refused": "the receiver is running; stop its serve unit first"}
            )
        )
        return 1
    except ValueError as refused:
        print(json.dumps({"refused": str(refused)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
