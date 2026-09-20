#!/usr/bin/env python3
"""Set up an accelerator host for Carbon, on whatever machine you have.

The same commands work on a laptop, a workstation, a virtual machine or rented
compute. Nothing here is specific to a vendor's device model, a driver version
or a compute provider: what differs between hosts goes into an installed record,
so running Carbon on your own hardware never means editing Carbon.

    inspect    what this workload needs, and what is installed here
    observe    read this host's device with the vendor tool (read-only)
    prepare    write the host device record from an observation
    authorize  install a grant or approval the owner authored
    doctor     check host readiness and report every blocker
    status     what has been consumed and what is outstanding

What these commands do NOT do, deliberately:

  * They never create authority. `authorize` installs a record the owner wrote;
    it cannot mint one. A host-side tool that could grant itself device access
    would defeat the admission design it sits in front of.
  * They never change host configuration: no driver install, no clock, power or
    display changes, no daemon reconfiguration, no reboot.
  * A passing `doctor` is not acceptance and not a scientific qualification. It
    reports the checks this command can make, and nothing beyond them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from carbon.reconstruction import onboarding
from carbon.reconstruction.host_inventory import (
    CONTAINER_RUNTIMES,
    HOST_DEVICE_RECORD,
    PLATFORMS,
    HostDeviceRecord,
    require_host_device,
)
from carbon.reconstruction.worker.model import WorkerFailure


def _emit(value: object) -> int:
    print(json.dumps(value, sort_keys=True, indent=2))
    return 0


def _host_root(args) -> Path:
    if args.host_root:
        return Path(args.host_root)
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

    return HOST_ROOT


def command_inspect(args) -> int:
    profile = onboarding.resolve_workload(args.profile)
    root = _host_root(args)
    try:
        record = require_host_device(HostDeviceRecord.load(root), profile)
        installed = {"digest": record.digest, **record.document}
    except WorkerFailure:
        installed = None
    return _emit(
        {
            "workload_profile": profile.document(),
            "workload_profile_digest": profile.digest,
            "host_root": str(root),
            "host_device_record": installed,
            # Stated plainly so the absence of machine-specific values in the
            # profile above is not mistaken for something missing.
            "note": (
                "the workload profile describes the work and is identical on "
                "every host; everything machine-specific lives in the host "
                "device record"
            ),
        }
    )


def command_observe(args) -> int:
    try:
        observed = onboarding.observe_local_device(binary=args.smi)
    except WorkerFailure:
        return _emit(
            {
                "status": "UNAVAILABLE",
                "detail": (
                    "the vendor query tool could not be run here; pass --smi "
                    "with its path, or record the values with `prepare --from`"
                ),
            }
        )
    return _emit(
        {
            "status": "OBSERVED",
            **observed,
            "authority": "HOST_OBSERVATION_ONLY_NOT_QUALIFICATION",
        }
    )


def command_prepare(args) -> int:
    profile = onboarding.resolve_workload(args.profile)
    root = _host_root(args)
    if args.source:
        observed = onboarding.load_document(Path(args.source))
        provenance = args.provenance or f"recorded observation from {args.source}"
    else:
        observed = onboarding.observe_local_device(binary=args.smi)
        provenance = args.provenance or (
            f"vendor query tool at {observed.get('source')}, run by the operator"
        )
    document = onboarding.build_host_record(
        observed=observed,
        device_uuid=args.device,
        profile=profile,
        record_id=onboarding.valid_record_id(args.record_id),
        provider=args.provider,
        platform=args.platform,
        container_runtime=args.container_runtime,
        provenance=provenance,
    )
    if args.dry_run:
        return _emit({"status": "NOT_WRITTEN", "document": document})
    path = onboarding.install_record(root, document, name=HOST_DEVICE_RECORD)
    record = require_host_device(HostDeviceRecord.load(root), profile)
    return _emit(
        {
            "status": "INSTALLED",
            "path": str(path),
            "record_digest": record.digest,
            "authority": "HOST_OBSERVATION_ONLY_NOT_QUALIFICATION",
            "next": "run `doctor` to see what still blocks this host",
        }
    )


def command_authorize(args) -> int:
    root = _host_root(args)
    document = onboarding.load_document(Path(args.record))
    path = onboarding.install_authority(root, document)
    return _emit(
        {
            "status": "INSTALLED",
            "path": str(path),
            "detail": (
                "the record was installed where the controller looks for it; "
                "its contents are verified at dispatch, not here"
            ),
            "note": "this command installs owner-authored authority; it never creates it",
        }
    )


def command_doctor(args) -> int:
    profile = onboarding.resolve_workload(args.profile)
    report = onboarding.doctor_report(root=_host_root(args), profile=profile)
    _emit(report)
    return 0 if report["checks_passed"] else 1


def command_status(args) -> int:
    return _emit(
        onboarding.status_report(
            root=_host_root(args),
            state_root=Path(args.state_root) if args.state_root else None,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="carbon-accelerator",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host-root", help="operator record directory for this host")
    parser.add_argument("--profile", help="workload profile id (default: the GPU one)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("inspect").set_defaults(handler=command_inspect)

    observe = subparsers.add_parser("observe")
    observe.add_argument("--smi", help="path to the vendor query tool")
    observe.set_defaults(handler=command_observe)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--record-id", required=True, help="a name for this host")
    prepare.add_argument(
        "--provider",
        required=True,
        help="who provides this host, as a plain token (for example self-hosted)",
    )
    prepare.add_argument(
        "--device", help="which device this record describes, on a multi-device host"
    )
    prepare.add_argument("--platform", choices=sorted(PLATFORMS))
    prepare.add_argument("--container-runtime", choices=sorted(CONTAINER_RUNTIMES))
    prepare.add_argument("--smi", help="path to the vendor query tool")
    prepare.add_argument("--from", dest="source", help="a recorded observation file")
    prepare.add_argument("--provenance", help="how this observation was made")
    prepare.add_argument("--dry-run", action="store_true")
    prepare.set_defaults(handler=command_prepare)

    authorize = subparsers.add_parser("authorize")
    authorize.add_argument("record", help="the owner-authored grant or approval")
    authorize.set_defaults(handler=command_authorize)

    subparsers.add_parser("doctor").set_defaults(handler=command_doctor)

    status = subparsers.add_parser("status")
    status.add_argument("--state-root", help="the controller state directory")
    status.set_defaults(handler=command_status)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except WorkerFailure as failure:
        return _emit({"status": "REFUSED", "code": failure.code.value}) or 2
    except ValueError as error:
        return _emit({"status": "REFUSED", "detail": str(error)}) or 2


if __name__ == "__main__":
    raise SystemExit(main())
