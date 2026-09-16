"""Trusted comparison operator commands; no blockchain transaction methods."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from carbon.development_session.agent import check_authority, proposal, run
from carbon.development_session.budget import SessionBudget
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .experiment import freeze, implementation_digest, load_contract
from .owner import write_owner_report
from .report import write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("freeze", "plan", "run", "status", "report")
    )
    parser.add_argument("--root", type=Path, required=True)
    for name in (
        "baseline-source",
        "reference-root",
        "image-manifest",
        "quarantine-journal",
        "operator-config",
        "model-authority",
        "api-key-file",
        "miner-public",
        "miner-password-file",
    ):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    root = args.root
    if args.command == "freeze":
        if any(
            value is None
            for value in (
                args.baseline_source,
                args.image_manifest,
                args.quarantine_journal,
                args.reference_root,
            )
        ):
            parser.error(
                "freeze requires baseline source, image manifest and configured quarantine journal"
            )
        contract = freeze(
            root,
            baseline_source=args.baseline_source,
            image_manifest=args.image_manifest,
            quarantine_journal=args.quarantine_journal,
            reference_root=args.reference_root,
        )
        print(
            json.dumps(
                {
                    "root": str(root),
                    "contract_digest": digest(canonical(contract)),
                    "inference_dispatched": False,
                }
            )
        )
        return
    contract = load_contract(root)
    contract_digest = digest(canonical(contract))
    plan = proposal(comparison_contract_digest=contract_digest)
    if args.command == "plan":
        write_once(root / "model-run-proposal.json", canonical(plan))
        print(json.dumps(plan, indent=2))
    elif args.command == "status":
        print(
            json.dumps(
                {
                    "root": str(root),
                    "contract_digest": contract_digest,
                    "agent_report": (
                        str(root / "agent-report.json")
                        if (root / "agent-report.json").exists()
                        else None
                    ),
                    "stopped_report": (
                        str(root / "agent-stopped-report.json")
                        if (root / "agent-stopped-report.json").exists()
                        else None
                    ),
                    "reports": [str(p) for p in sorted(root.glob("comparison-*.md"))],
                    "sources": [str(p) for p in sorted(root.glob("source-*.json"))],
                    "accounting": SessionBudget(root / "budget.sqlite3").summary(),
                },
                indent=2,
            )
        )
    elif args.command == "report":
        for path in sorted(root.glob("source-*.json")):
            ref = write_report(root, path)
            print(
                json.dumps(
                    {
                        "path": str(ref.path),
                        "digest": ref.digest,
                        "disposition": "INDETERMINATE_NO_ACCEPTANCE_RULE",
                    }
                )
            )
        write_owner_report(root)
    else:
        if any(
            value is None
            for value in (
                args.image_manifest,
                args.operator_config,
                args.model_authority,
                args.api_key_file,
                args.miner_public,
                args.miner_password_file,
            )
        ):
            parser.error(
                "run requires image, operator config, model authority and private credential paths"
            )
        if contract["controller_implementation_digest"] != implementation_digest():
            raise ValueError(
                "controller code changed after prospective experiment freeze"
            )
        check_authority(args.model_authority, now=time.time(), run_proposal=plan)
        from carbon.chain.auth import open_external_hotkey
        from carbon.development_session.service import LocalMinerConnection
        from carbon.development_testnet.operator import load_config

        config = load_config(args.operator_config)
        public = json.loads(args.miner_public.read_bytes())
        key = open_external_hotkey(
            Path(public["key_file"]), args.miner_password_file, public["hotkey"]
        )
        connection = LocalMinerConnection(
            root,
            args.image_manifest,
            config.context,
            config.publisher_hotkey,
            key,
            comparison_contract_digest=contract_digest,
        )
        try:
            result = asyncio.run(
                run(
                    connection,
                    args.model_authority,
                    args.api_key_file,
                    comparison_contract_digest=contract_digest,
                )
            )
        finally:
            write_owner_report(root)
        for path in sorted(root.glob("source-*.json")):
            ref = write_report(root, path)
            print(json.dumps({"comparison_report": str(ref.path)}), flush=True)
        print(
            json.dumps(
                {
                    "real_inference": result["real_inference"],
                    "calls": len(result["calls"]),
                    "proposals": result["proposals"],
                    "completed_evaluations": result["completed_evaluations"],
                }
            )
        )


if __name__ == "__main__":
    main()
