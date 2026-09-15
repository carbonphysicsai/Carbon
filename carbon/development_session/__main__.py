"""Operator entry point. No command here dispatches a blockchain transaction."""

import argparse
import asyncio
import json
from pathlib import Path

from carbon.development_testnet.operator import load_config

from .agent import proposal, run
from .budget import SessionBudget
from .data import freeze, prepare, write_once
from .profile import canonical, profile_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("freeze", "prepare", "plan", "status", "run")
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--image-manifest", type=Path)
    parser.add_argument("--operator-config", type=Path)
    parser.add_argument("--model-authority", type=Path)
    parser.add_argument("--api-key-file", type=Path)
    parser.add_argument("--miner-public", type=Path)
    parser.add_argument("--miner-password-file", type=Path)
    args = parser.parse_args()
    root = args.root
    if not root.is_absolute() or root.is_symlink():
        parser.error("--root must be an absolute private session directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.command in ("freeze", "prepare"):
        if args.image_manifest is None:
            parser.error("--image-manifest required")
        value = (freeze if args.command == "freeze" else prepare)(
            root, args.image_manifest
        )
        print(
            json.dumps(
                {
                    "profile_digest": value["profile_digest"],
                    "command": args.command,
                    "completed": True,
                }
            )
        )
    elif args.command == "plan":
        write_once(root / "model-run-proposal.json", canonical(proposal()))
        if args.operator_config:
            config = load_config(args.operator_config)
            if config.netuid != 567:
                parser.error("operator config must bind subnet 567")
            raw = json.loads(args.operator_config.read_bytes())
            raw["execution"]["resource_policy_digest"] = profile_digest()
            raw["retention"]["root"] = str(root)
            raw["retention"]["export_root"] = str(root / "exports")
            raw["transaction_authorization"] = None
            write_once(root / "development-testnet.json", canonical(raw))
        print(json.dumps(proposal(), indent=2))
    elif args.command == "status":
        print(
            json.dumps(
                {
                    "prepared": (root / "preparation.json").is_file(),
                    "agent_report_present": (root / "agent-report.json").is_file(),
                    "sources": [
                        str(path) for path in sorted(root.glob("source-*.json"))
                    ],
                    "accounting": SessionBudget(root / "budget.sqlite3").summary(),
                },
                indent=2,
            )
        )
    else:
        required = (
            args.operator_config,
            args.model_authority,
            args.api_key_file,
            args.miner_public,
            args.miner_password_file,
            args.image_manifest,
        )
        if any(value is None for value in required):
            parser.error(
                "run requires operator config, model authority, API key file, miner public/password files and image manifest"
            )
        import time

        from .agent import check_authority

        check_authority(args.model_authority, now=time.time())
        # No key is loaded for prepare, plan or status. All private key access
        # is on this trusted side of the data-only model connection.
        from carbon.chain.auth import open_external_hotkey

        from .service import LocalMinerConnection

        config = load_config(args.operator_config)
        public = json.loads(args.miner_public.read_bytes())
        key = open_external_hotkey(
            Path(public["key_file"]), args.miner_password_file, public["hotkey"]
        )
        if key.ss58_address != public["hotkey"] or public["netuid"] != 567:
            raise ValueError("miner identity mismatch")
        connection = LocalMinerConnection(
            root, args.image_manifest, config.context, config.publisher_hotkey, key
        )
        result = asyncio.run(run(connection, args.model_authority, args.api_key_file))
        print(
            json.dumps(
                {
                    "real_inference": result["real_inference"],
                    "proposals": result["proposals"],
                    "completed_evaluations": result["completed_evaluations"],
                }
            )
        )


if __name__ == "__main__":
    main()
