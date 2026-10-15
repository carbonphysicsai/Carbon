"""Trusted operator route. It is deliberately absent from miner/MCP tools."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .bundle import (
    SetupRefused,
    materialize,
    runtime_identity,
    runtime_lease,
    select_release,
    verify,
)


def bound(args):
    bundle = verify(Path(args.bundle), args.digest)
    if Path(__file__).resolve() != bundle.root / "carbon/validator_setup/__main__.py":
        raise SetupRefused("EXECUTED_SOURCE_NOT_BOUND_BUNDLE")
    image_bundle = os.environ.get("CARBON_VALIDATOR_IMAGE_BUNDLE_DIGEST")
    if image_bundle is not None and image_bundle != bundle.digest:
        raise SetupRefused("IMAGE_AND_EXECUTED_SOURCE_BUNDLE_DIFFER")
    return bundle


def initialize(args, bundle):
    """Open import-only state explicitly; never generate a replacement exam."""
    from carbon.battery import deployment, operate

    config = deployment.load_config(Path(args.config))
    if config.get("batch_source") != "answer_key":
        raise SetupRefused("REMOTE_VALIDATOR_REQUIRES_SHARED_ANSWER_KEY")
    operate.init(Path(args.config), repository=bundle.root)
    target = deployment.validator(Path(args.config), repository=bundle.root)
    pool = target.open_pool()
    return {
        "status": "INITIALIZED_IMPORT_ONLY",
        "pool": pool["status"],
        "evaluation_ready": pool["status"] == "OPEN",
        "references": "SHARED_IMPORT_ONLY",
    }


def delegate(args, bundle):
    if args.command == "initialize":
        return 0, initialize(args, bundle)
    if args.command == "weights":
        from .weights import run

        args.repository = bundle.root
        return 0, run(args)
    if args.command == "sync":
        from carbon.challenge_validator import answer_key

        return answer_key.main(["sync", "--config", args.config]), None
    from scripts.dev.battery_validator_service import service, supervisor

    if args.action == "supervise":
        from scripts.dev.battery_validator_service.__main__ import main as service_main

        return service_main(["supervise", "--config", args.config]), None
    if args.action == "units":
        if args.out is None:
            raise SetupRefused("UNIT_OUTPUT_REQUIRED")
        return 0, supervisor.units(args.config, args.out, repository=bundle.root)
    if args.action == "status":
        result = service.status(args.config, repository=bundle.root)
        return (0 if result["healthy"] else 3), result
    result = service.preflight(args.config, repository=bundle.root)
    return (0 if result["ready"] else 2), result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.validator_setup")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("materialize")
    build.add_argument("--repository", required=True)
    build.add_argument("--revision", required=True)
    build.add_argument("--target", required=True)
    image = sub.add_parser("image-context")
    image.add_argument("--repository", required=True)
    image.add_argument("--revision", required=True)
    image.add_argument("--target", required=True)
    image.add_argument("--build", action="store_true")
    extract = sub.add_parser("extract")
    extract.add_argument("--image", required=True)
    extract.add_argument("--revision", required=True)
    extract.add_argument("--digest", required=True)
    extract.add_argument("--target", required=True)
    units = sub.add_parser("runtime-units")
    units.add_argument("--profile", required=True)
    units.add_argument("--out", required=True)
    for name in (
        "verify",
        "select",
        "initialize",
        "service",
        "weights",
        "sync",
        "runtime",
        "mirror-check",
    ):
        command = sub.add_parser(name)
        command.add_argument("--bundle", required=True)
        command.add_argument("--digest", required=True)
        if name in ("initialize", "service", "weights", "sync"):
            command.add_argument("--config", required=True)
        if name in ("initialize", "weights", "sync"):
            command.add_argument("--service-config", required=True)
        if name == "select":
            command.add_argument("--service-config", required=True)
            command.add_argument("--pointer", required=True)
            command.add_argument("--expected-current-file")
        if name == "service":
            command.add_argument(
                "action", choices=("preflight", "status", "supervise", "units")
            )
            command.add_argument("--out")
        if name == "weights":
            command.add_argument("action", choices=("preview", "run"))
            for flag in ("standing", "journal", "ledger"):
                command.add_argument("--" + flag, required=True)
            command.add_argument("--battery-deployment")
            command.add_argument("--policy-version")
        if name == "runtime":
            command.add_argument(
                "--network", choices=("testnet", "finney"), required=True
            )
            command.add_argument("--endpoint", required=True)
            command.add_argument("--genesis", required=True)
            command.add_argument("--expected-spec", type=int, required=True)
        if name == "mirror-check":
            command.add_argument("--image", required=True)
    args = parser.parse_args(argv)
    try:
        code = 0
        if args.command == "runtime-units":
            from .units import write

            result = write(Path(args.profile), Path(args.out))
        elif args.command == "extract":
            from .image import extract as extract_image

            bundle = extract_image(
                args.image, Path(args.target), args.digest, args.revision
            )
            result = {
                "status": "PUBLIC_OPERATOR_SOURCE_EXTRACTED",
                "digest": bundle.digest,
                "source_revision": bundle.manifest["source_revision"],
                "host_acceptance": "NOT_RUN",
            }
        elif args.command == "image-context":
            from .image import build as image_build
            from .image import prepare

            result = prepare(Path(args.repository), args.revision, Path(args.target))
            if args.build:
                result = image_build(Path(args.target))
        elif args.command == "materialize":
            bundle = materialize(
                Path(args.repository), args.revision, Path(args.target)
            )
            result = {
                "status": "PUBLIC_OPERATOR_SOURCE_BOUND",
                "digest": bundle.digest,
                "source_revision": bundle.manifest["source_revision"],
                "files": len(bundle.manifest["files"]),
                "qualification": "NOT_GRANTED",
            }
        elif args.command == "verify":
            bundle = verify(Path(args.bundle), args.digest)
            result = {
                "status": "BYTES_VERIFIED",
                "digest": bundle.digest,
                "source_revision": bundle.manifest["source_revision"],
                "qualification": "NOT_GRANTED",
            }
        else:
            bundle = bound(args)
            if args.command == "select":
                expected = (
                    json.loads(Path(args.expected_current_file).read_bytes())
                    if args.expected_current_file
                    else None
                )
                result = select_release(
                    bundle,
                    Path(args.pointer),
                    Path(args.service_config),
                    expected_current=expected,
                )
            elif args.command == "runtime":
                from .runtime import run as runtime_check

                result, code = runtime_check(args)
            elif args.command == "mirror-check":
                from .image import check_host_mirror

                result = check_host_mirror(args.image, bundle)
            else:
                with (
                    runtime_identity(bundle),
                    runtime_lease(
                        args.config
                        if args.command == "service"
                        else args.service_config
                    ),
                ):
                    code, result = delegate(args, bundle)
                if result is None:
                    return code
        print(json.dumps(result, sort_keys=True, default=str))
        return code
    except SetupRefused as refused:
        print(json.dumps({"status": "REFUSED", "reason": str(refused)}))
        return 2
    except Exception:  # noqa: BLE001 - no input/provider/private payload is echoed
        print(json.dumps({"status": "FAILED_CLOSED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
