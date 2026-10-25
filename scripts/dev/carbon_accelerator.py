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
    run        start one miner-lane run on this host
    cancel     ask a running launch to stop
    recover    remove containers unfinished launches still own

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
    MINER_DEVICE_SCHEMA,
    PLATFORMS,
    HostDeviceRecord,
    MinerHostDeviceRecord,
    load_miner_lane_record,
    require_host_device,
    require_miner_host_device,
)
from carbon.reconstruction.worker.model import WorkerFailure

#: What a host-record field must be, in plain words, for a refusal that names
#: it. Facts about the record's shape only; nothing read from the host.
FIELD_HINTS = {
    "gpu_vendor": "this machine's GPU is not an NVIDIA GPU (GPU practice supports NVIDIA only for now)",
    "nvidia_smi": "the NVIDIA query tool (nvidia-smi) was not found or could not talk to the driver",
    "device": "this host has several GPUs (or the one named is not among them): pass --device GPU-<uuid>, one of `choices`",
    "record": "the record is missing or has unexpected fields",
    "schema": "the record's schema is not the host device record's",
    "observation_authority": "the record must say it is a host observation only",
    "record_id": "letters, digits, '-' and '_' only, up to 64 characters",
    "workload_profile_id": "the workload profile this record serves (leave --profile unset)",
    "device_uuid": "the vendor's device id (NVIDIA: GPU-<uuid> or MIG-<uuid>, lowercase hex)",
    "device_kind": "the device's marketed name (letters, digits, spaces, '_', '.', '-')",
    "driver_version": "digits and dots only, up to 16 characters",
    "driver_model": "must be WDDM, TCC or N/A",
    "compute_capability": "like 8.6",
    "device_memory_mib": "a whole number of MiB above 0",
    "display_active": "must be Enabled or Disabled (the vendor tool printed something else)",
    "platform": "must be WSL2, LINUX_BARE_METAL, LINUX_VIRTUAL_MACHINE or HOSTED_COMPUTE_INSTANCE",
    "container_runtime": "must be DOCKER_ENGINE or DOCKER_DESKTOP",
    "provider": "letters, digits, '-' and '_' only, up to 64 characters",
    "observed_at_unix": "a positive time in seconds",
    "observation_provenance": "a sentence of letters, digits and simple punctuation",
}


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
        # A read-only view: a miner-lane record is shown as what it is.
        record = load_miner_lane_record(root)
        if type(record) is HostDeviceRecord:
            require_host_device(record, profile)
        else:
            require_miner_host_device(record, profile)
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
        try:
            observed = onboarding.observe_local_device(binary=args.smi)
        except WorkerFailure as failure:
            if onboarding.not_nvidia(onboarding.probe_vendors()):
                return (
                    _emit(
                        {
                            "status": "REFUSED",
                            "code": failure.code.value,
                            "fields": ["gpu_vendor"],
                            "reasons": {"gpu_vendor": onboarding.NOT_NVIDIA_REASON},
                            "next": onboarding.NOT_NVIDIA_NEXT,
                        }
                    )
                    or 2
                )
            return (
                _emit(
                    {
                        "status": "REFUSED",
                        "code": failure.code.value,
                        "fields": ["nvidia_smi"],
                        "reasons": {"nvidia_smi": FIELD_HINTS["nvidia_smi"]},
                        "next": "install the NVIDIA driver (https://www.nvidia.com/en-us/drivers/) and reboot, then check that `nvidia-smi` lists your GPU; or pass --smi with the path to nvidia-smi, or --from with a recorded observation file",
                    }
                )
                or 2
            )
        provenance = args.provenance or (
            f"vendor query tool at {observed.get('source')}, run by the operator"
        )
    record = {
        "profile": profile,
        "record_id": onboarding.valid_record_id(args.record_id),
        "provider": args.provider,
        "platform": args.platform,
        "container_runtime": args.container_runtime,
        "provenance": provenance,
    }
    chosen = None
    device = args.device
    if args.miner_lane and device is None and len(observed.get("devices") or []) > 1:
        # Your own practice on a machine with several GPUs: the first usable one,
        # in the vendor tool's order, printed; `--device` picks another. A missing
        # choice never refuses here (validator hosts still choose explicitly).
        found = onboarding.first_usable_device(observed, **record)
        if found is not None:
            device = found[1]
            chosen = {
                "index": found[0],
                "device_uuid": found[1],
                "device_kind": observed["devices"][found[0]].get("device_kind"),
                "how": "the first usable GPU; use --device to choose another",
            }
    document = onboarding.build_host_record(
        observed=observed, device_uuid=device, miner_lane=args.miner_lane, **record
    )
    if args.dry_run:
        return _emit(
            {
                "status": "NOT_WRITTEN",
                "document": document,
                **({"chosen": chosen} if chosen else {}),
            }
        )
    path = onboarding.install_record(root, document, name=HOST_DEVICE_RECORD)
    if document["schema"] == MINER_DEVICE_SCHEMA:
        record = require_miner_host_device(MinerHostDeviceRecord.load(root), profile)
    else:
        record = require_host_device(HostDeviceRecord.load(root), profile)
    return _emit(
        {
            "status": "INSTALLED",
            "path": str(path),
            "record_digest": record.digest,
            **(
                {"lane": "MINER", "unknown_fields": list(record.unknown_fields)}
                if document["schema"] == MINER_DEVICE_SCHEMA
                else {}
            ),
            "authority": "HOST_OBSERVATION_ONLY_NOT_QUALIFICATION",
            "next": "run `doctor` to see what still blocks this host",
            **({"chosen": chosen} if chosen else {}),
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
    # The strict exit is the default: a validator or owner-authorised host must
    # pass every check (a grant or approval, display routing, the attempt journal).
    # Your own practice asks explicitly with `--miner-lane`, which needs only the
    # miner lane's checks.
    ready = report["miner_lane_ready"] if args.miner_lane else report["checks_passed"]
    return 0 if ready else 1


def command_status(args) -> int:
    return _emit(
        onboarding.status_report(
            root=_host_root(args),
            state_root=Path(args.state_root) if args.state_root else None,
        )
    )


def command_run(args) -> int:
    """Start one miner-lane run, through the controller that already exists."""
    from carbon.reconstruction.miner_launch import MinerLaunchRequest, launch

    result = launch(
        request=MinerLaunchRequest.load(Path(args.manifest)),
        state_root=Path(args.state_root),
    )
    return _emit(
        {
            "schema": "carbon.accelerator-miner-run.v1",
            "status": "COMPLETE",
            "launch_digest": result.launch_digest,
            "output_snapshot_digest": result.output_snapshot_digest,
            "effective_controls": result.effective_controls,
            "timings": result.timings,
            # Said plainly at the point a miner reads it: this ran, and that is
            # all it establishes.
            "lane": "MINER_CONTAINED",
            "official_eligible": False,
            "authority": "MINER_LANE_RUN_NOT_EVIDENCE",
        }
    )


def command_cancel(args) -> int:
    from carbon.reconstruction.miner_launch import request_cancel

    path = request_cancel(
        state_root=Path(args.state_root), execution_id=args.execution_id
    )
    return _emit(
        {
            "schema": "carbon.accelerator-miner-cancel.v1",
            "status": "REQUESTED",
            "execution_id": args.execution_id,
            "request": str(path),
            # A request, not a kill: the run stops at its own next boundary and
            # performs its own cleanup.
            "authority": "COOPERATIVE_STOP_REQUEST_NOT_TERMINATION",
        }
    )


def command_recover(args) -> int:
    from carbon.reconstruction.miner_launch import recover

    report = recover(state_root=Path(args.state_root), dry_run=args.dry_run)
    _emit(report)
    return 0 if all(entry.get("removed", True) for entry in report["launches"]) else 1


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
    prepare.add_argument(
        "--miner-lane",
        action="store_true",
        help="your own practice host: on a machine with several GPUs use the first usable one (printed)",
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

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument(
        "--miner-lane",
        action="store_true",
        help="exit on your own practice's checks only (no owner grant needed)",
    )
    doctor.set_defaults(handler=command_doctor)

    status = subparsers.add_parser("status")
    status.add_argument("--state-root", help="the controller state directory")
    status.set_defaults(handler=command_status)

    run = subparsers.add_parser("run")
    run.add_argument("manifest", help="the launch manifest for this run")
    run.add_argument(
        "--state-root", required=True, help="the controller state directory"
    )
    run.set_defaults(handler=command_run)

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("execution_id", help="which launch to stop")
    cancel.add_argument(
        "--state-root", required=True, help="the controller state directory"
    )
    cancel.set_defaults(handler=command_cancel)

    recover = subparsers.add_parser("recover")
    recover.add_argument(
        "--state-root", required=True, help="the controller state directory"
    )
    recover.add_argument(
        "--dry-run", action="store_true", help="report without removing anything"
    )
    recover.set_defaults(handler=command_recover)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except WorkerFailure as failure:
        refusal = {"status": "REFUSED", "code": failure.code.value}
        fields = getattr(failure, "fields", None)
        if fields:
            # Which fields of the host record failed, and what each must
            # be. Names only; the values stay on the host.
            refusal["fields"] = list(fields)
            refusal["reasons"] = {
                name: FIELD_HINTS.get(name, "does not match the record's shape")
                for name in fields
            }
            if getattr(failure, "choices", None):
                refusal["choices"] = list(failure.choices)
            refusal["next"] = (
                "fix the named fields: record them with `prepare --from <file>` after checking them with `observe`; if the vendor tool itself reports a value the record does not accept, report the field name to Carbon (this host class may not be supported yet)"
            )
        return _emit(refusal) or 2
    except ValueError as error:
        return _emit({"status": "REFUSED", "detail": str(error)}) or 2


if __name__ == "__main__":
    raise SystemExit(main())
