"""Operator onboarding for an accelerator host, on any machine.

Everything here is host-side and provider-independent. There is no per-vendor
and no per-provider branch: a laptop, a workstation, a virtual machine and
rented compute all go through the same steps, and the differences between them
live in the installed `HostDeviceRecord` rather than in Carbon.

Two rules shape this module.

First, describing a host is not authorizing it. `prepare` writes a record of
what was observed, with the provenance of that observation. It does not grant
anything, and a record cannot make itself authoritative.

Second, this tool never mints authority. `install_authority` validates and
installs a grant or approval record that the owner authored; it cannot create
one. A miner-side command that could grant itself device access would defeat
the admission design it is supposed to sit in front of.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from carbon.reconstruction.accelerators import GPU_PROFILE, resolve_profile
from carbon.reconstruction.host_inventory import (
    HOST_DEVICE_AUTHORITY,
    HOST_DEVICE_RECORD,
    HOST_DEVICE_SCHEMA,
    HostDeviceRecord,
    require_host_device,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

READY = "READY"
BLOCKED = "BLOCKED"
UNKNOWN = "UNKNOWN"

# What `doctor` reports about the container runtime in front of the device.
# Engine and Desktop differ in device passthrough and in what the controller can
# observe, so the difference is named rather than assumed away. Neither is
# preferred here, and neither is treated as evidence about telemetry.
DOCKER_ENGINE = "DOCKER_ENGINE"
DOCKER_DESKTOP = "DOCKER_DESKTOP"

_SMI_QUERY = (
    "uuid,name,driver_version,driver_model.current,"
    "compute_cap,memory.total,display_active"
)


def _finding(check: str, state: str, detail: str, **extra) -> dict:
    return {"check": check, "state": state, "detail": detail, **extra}


# --- observation --------------------------------------------------------------


def observe_local_device(*, binary: str | None = None, timeout: float = 15.0) -> dict:
    """Read this host's device with the vendor tool, if it is present.

    This is a plain read of what the tool reports. It establishes nothing about
    exclusivity, about whether every process using the device is visible, or
    about whether the host is suitable. Those remain separate questions.
    """
    candidates = (
        [binary]
        if binary
        else [
            shutil.which("nvidia-smi"),
            "/usr/bin/nvidia-smi",
            "/usr/lib/wsl/lib/nvidia-smi",
        ]
    )
    found = next((c for c in candidates if c and Path(c).is_file()), None)
    if found is None:
        raise WorkerFailure(WorkerCode.UNAVAILABLE)
    try:
        result = subprocess.run(
            [found, f"--query-gpu={_SMI_QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True,
            timeout=timeout,
            check=False,
            env={"PATH": "/usr/bin:/bin"},
        )
    except (OSError, subprocess.SubprocessError):
        raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
    if result.returncode != 0:
        raise WorkerFailure(WorkerCode.UNAVAILABLE)
    rows = result.stdout.decode("ascii", "replace").strip().splitlines()
    devices = []
    for row in rows:
        parts = [part.strip() for part in row.split(",")]
        if len(parts) != 7:
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        devices.append(
            {
                "device_uuid": parts[0],
                "device_kind": parts[1],
                "driver_version": parts[2],
                "driver_model": parts[3] if parts[3] else "N/A",
                "compute_capability": parts[4],
                "device_memory_mib": parts[5],
                "display_active": parts[6].capitalize(),
            }
        )
    return {"devices": devices, "source": found}


def _detect_container_runtime(info: dict | None) -> str:
    """Name the runtime in front of the device, or say it is unknown.

    Guessing here would be worse than reporting UNKNOWN: the two behave
    differently, and a wrong guess would be recorded as if it were observed.
    """
    if type(info) is not dict:
        return UNKNOWN
    haystack = " ".join(
        str(info.get(key, "")) for key in ("OperatingSystem", "Name", "ServerVersion")
    ).lower()
    if "docker desktop" in haystack or "docker-desktop" in haystack:
        return DOCKER_DESKTOP
    if info.get("OperatingSystem"):
        return DOCKER_ENGINE
    return UNKNOWN


def detect_platform() -> str:
    """Where this host sits, as far as it can be told from the host itself."""
    from carbon.reconstruction.host_inventory import PLATFORMS

    release = ""
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text("ascii", "replace")
    except OSError:
        release = ""
    if "microsoft" in release.lower() or os.environ.get("WSL_DISTRO_NAME"):
        return "WSL2"
    product = ""
    for path in ("/sys/class/dmi/id/product_name", "/sys/class/dmi/id/sys_vendor"):
        try:
            product += Path(path).read_text("ascii", "replace").lower()
        except OSError:
            continue
    if any(
        marker in product
        for marker in ("virtual", "kvm", "qemu", "vmware", "xen", "hvm", "cloud")
    ):
        return "LINUX_VIRTUAL_MACHINE"
    if product:
        return "LINUX_BARE_METAL"
    assert "LINUX_BARE_METAL" in PLATFORMS
    return UNKNOWN


# --- prepare ------------------------------------------------------------------


def build_host_record(
    *,
    observed: dict,
    device_uuid: str | None = None,
    profile=GPU_PROFILE,
    record_id: str,
    provider: str,
    platform: str | None = None,
    container_runtime: str | None = None,
    provenance: str,
    now: float | None = None,
) -> dict:
    """Turn one observation into a record document, without judging the host.

    When the host exposes several devices, `device_uuid` selects which one this
    record describes; the workload profile still names exactly one device.
    """
    devices = observed.get("devices") or []
    if device_uuid is None:
        if len(devices) != 1:
            # Ambiguous on a multi-device host: the operator must choose rather
            # than have Carbon pick one for them.
            raise WorkerFailure(WorkerCode.INVALID)
        chosen = devices[0]
    else:
        chosen = next((d for d in devices if d["device_uuid"] == device_uuid), None)
        if chosen is None:
            raise WorkerFailure(WorkerCode.INVALID)
    try:
        memory = int(str(chosen["device_memory_mib"]).split()[0])
    except (KeyError, ValueError, IndexError):
        raise WorkerFailure(WorkerCode.INVALID) from None
    moment = float(time.time() if now is None else now)
    if not math.isfinite(moment) or moment <= 0:
        raise WorkerFailure(WorkerCode.INVALID)
    document = {
        "schema": HOST_DEVICE_SCHEMA,
        "record_id": record_id,
        "workload_profile_id": profile.profile_id,
        "device_uuid": chosen["device_uuid"],
        "device_kind": chosen["device_kind"],
        "driver_version": chosen["driver_version"],
        "driver_model": chosen["driver_model"],
        "compute_capability": chosen["compute_capability"],
        "device_memory_mib": memory,
        "display_active": chosen["display_active"],
        "platform": platform or detect_platform(),
        "container_runtime": container_runtime or UNKNOWN,
        "provider": provider,
        "observed_at_unix": moment,
        "observation_provenance": provenance,
        "observation_authority": HOST_DEVICE_AUTHORITY,
    }
    # Validate before anything is written, so a bad observation never lands on
    # disk where a later command would read it back as installed evidence.
    HostDeviceRecord(document, "sha256:" + "0" * 64).validate()
    require_host_device(HostDeviceRecord(document, "sha256:" + "0" * 64), profile)
    return document


def install_record(root: Path, document: dict, *, name: str) -> Path:
    """Write one operator-private record into the host root."""
    from carbon.development_session.profile import canonical

    root = Path(root)
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = canonical(document)
    except (OSError, TypeError, ValueError):
        raise WorkerFailure(WorkerCode.INVALID) from None
    path = root / name
    try:
        path.write_bytes(payload)
        path.chmod(0o600)
    except OSError:
        raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
    return path


def install_authority(root: Path, document: dict) -> Path:
    """Install an owner-authored grant or approval; never create one.

    The document must already say which kind of authority it is. This command
    validates its shape and writes it where the controller looks. It cannot
    manufacture authority, and it does not decide whether the authority is
    warranted - that judgement belongs to whoever authored the record.
    """
    from carbon.reconstruction.worker import accelerator_runtime as runtime
    from carbon.reconstruction.worker.development_admission import (
        DEVELOPMENT_RECORD,
        DEVELOPMENT_SCHEMA,
    )

    if type(document) is not dict:
        raise WorkerFailure(WorkerCode.INVALID)
    schema = document.get("schema")
    if schema == runtime.GRANT_SCHEMA:
        name = "grant.json"
    elif schema == DEVELOPMENT_SCHEMA:
        name = DEVELOPMENT_RECORD
    else:
        raise WorkerFailure(WorkerCode.POLICY)
    return install_record(root, document, name=name)


# --- doctor -------------------------------------------------------------------


def doctor_report(*, root: Path, profile=GPU_PROFILE, cli=None, image=None) -> dict:
    """A read-only readiness report. Changes nothing, anywhere.

    Every finding is either READY, BLOCKED with a reason, or UNKNOWN. UNKNOWN is
    used wherever the host cannot be read rather than being folded into READY,
    because "we could not see a problem" is not the same as "there is none".
    """
    from carbon.reconstruction.worker import accelerator_runtime as runtime
    from carbon.reconstruction.worker.docker_runtime import DockerCLI, doctor

    root = Path(root)
    findings: list[dict] = []
    cli = cli or DockerCLI()

    info = None
    try:
        info = cli.json(["info", "--format", "{{json .}}"])
    except WorkerFailure:
        info = None
    container_runtime = _detect_container_runtime(info)
    findings.append(
        _finding(
            "container_runtime",
            UNKNOWN if container_runtime == UNKNOWN else READY,
            f"container runtime reported as {container_runtime}",
            value=container_runtime,
        )
    )
    has_nvidia = type(info) is dict and "nvidia" in (info.get("Runtimes") or {})
    findings.append(
        _finding(
            "container_device_runtime",
            READY if has_nvidia else BLOCKED,
            (
                "the container runtime exposes an nvidia runtime"
                if has_nvidia
                else "no nvidia container runtime is registered with the daemon"
            ),
        )
    )

    checked = doctor(
        image_id=None if image is None else image.image_id,
        image_identity=image,
        cli=cli,
    )
    findings.append(
        _finding(
            "container_daemon",
            READY if checked.eligible else BLOCKED,
            checked.code or "the daemon is eligible for a bounded worker",
        )
    )

    record = None
    try:
        record = require_host_device(HostDeviceRecord.load(root), profile)
        findings.append(
            _finding(
                "host_device_record",
                READY,
                "a host device record is installed and bound to this workload",
                record_digest=record.digest,
                device_kind=record.device_kind,
                platform=record.platform,
                provider=record.provider,
            )
        )
    except WorkerFailure as failure:
        findings.append(
            _finding(
                "host_device_record",
                BLOCKED,
                (
                    "no bound host device record is installed; run `prepare`"
                    if failure.code is WorkerCode.UNAVAILABLE
                    else "the installed host device record does not bind to this "
                    "workload profile"
                ),
                path=str(root / HOST_DEVICE_RECORD),
            )
        )

    if record is not None:
        capability = runtime.enumeration_capability(record.driver_model)
        findings.append(
            _finding(
                "compute_process_enumeration",
                BLOCKED if capability != runtime.ENUMERATION_ESTABLISHED else READY,
                (
                    f"driver model {record.driver_model} gives enumeration "
                    f"capability {capability}; strict admission and verified "
                    "whole-device release need an established observation source"
                ),
                value=capability,
            )
        )
        findings.append(
            _finding(
                "display_output",
                READY if record.display_active == "Disabled" else BLOCKED,
                (
                    "the recorded device is not driving a display"
                    if record.display_active == "Disabled"
                    else "the recorded device is driving a display; Carbon does "
                    "not change display routing, so this must be resolved by the "
                    "operator"
                ),
            )
        )

    quarantined = (root / "device-quarantined").exists()
    findings.append(
        _finding(
            "device_quarantine",
            BLOCKED if quarantined else READY,
            (
                "an unreconciled device release is quarantined; this needs "
                "operator reconciliation and cannot be cleared by this tool"
                if quarantined
                else "no unreconciled device release"
            ),
        )
    )

    findings.append(_authority_finding(root))
    findings.append(_attempt_finding(root))

    blocked = [f for f in findings if f["state"] == BLOCKED]
    unknown = [f for f in findings if f["state"] == UNKNOWN]
    return {
        "schema": "carbon.accelerator-host-doctor.v1",
        "workload_profile_id": profile.profile_id,
        "workload_profile_digest": profile.digest,
        "host_root": str(root),
        "findings": findings,
        "blocked": [f["check"] for f in blocked],
        "unknown": [f["check"] for f in unknown],
        # Deliberately not "ready to run": this reports the checks this command
        # can make. It is not an acceptance, a qualification, or a statement
        # that a run on this host would produce comparable science.
        "checks_passed": not blocked,
        "authority": "HOST_READINESS_CHECKS_ONLY_NOT_ACCEPTANCE",
    }


def _authority_finding(root: Path) -> dict:
    from carbon.reconstruction.worker.development_admission import DEVELOPMENT_RECORD

    installed = [
        name for name in ("grant.json", DEVELOPMENT_RECORD) if (root / name).exists()
    ]
    if not installed:
        return _finding(
            "installed_authority",
            BLOCKED,
            "no grant or development approval is installed; this tool cannot "
            "create one, so it must be supplied by the owner",
        )
    return _finding(
        "installed_authority",
        READY,
        "an authority record is installed; its contents are verified by the "
        "controller at dispatch, not here",
        records=installed,
    )


def _attempt_finding(root: Path) -> dict:
    from carbon.reconstruction.worker.development_admission import (
        DevelopmentAttemptJournal,
    )

    journal = DevelopmentAttemptJournal(Path(root))
    try:
        consumed = journal.consumed()
        blocking = journal.blocking_attempt()
    except WorkerFailure:
        return _finding(
            "attempt_accounting",
            BLOCKED,
            "the attempt journal could not be read; an unreadable marker blocks "
            "a new launch rather than vanishing",
        )
    if blocking is not None:
        return _finding(
            "attempt_accounting",
            BLOCKED,
            "a previous attempt is unreconciled and blocks a new launch",
            consumed=consumed,
        )
    return _finding(
        "attempt_accounting",
        READY,
        "no unreconciled attempt",
        consumed=consumed,
    )


# --- status -------------------------------------------------------------------


def status_report(*, root: Path, state_root: Path | None = None) -> dict:
    """What has been consumed and what is outstanding. Read-only."""
    from carbon.reconstruction.worker.development_admission import (
        DevelopmentAttemptJournal,
    )

    root = Path(root)
    journal = DevelopmentAttemptJournal(root)
    try:
        consumed = journal.consumed()
        blocking = journal.blocking_attempt()
    except WorkerFailure:
        consumed, blocking = None, None
    result = {
        "schema": "carbon.accelerator-host-status.v1",
        "host_root": str(root),
        "attempts_consumed": consumed,
        "unreconciled_attempt": None if blocking is None else str(blocking),
        "device_quarantined": (root / "device-quarantined").exists(),
    }
    if state_root is not None:
        store = Path(state_root) / "launches.sqlite3"
        result["launch_store"] = str(store)
        result["launch_store_present"] = store.is_file()
    return result


_RECORD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def valid_record_id(value: str) -> str:
    if type(value) is not str or _RECORD_ID.fullmatch(value) is None:
        raise WorkerFailure(WorkerCode.INVALID)
    return value


def load_document(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        raise WorkerFailure(WorkerCode.INVALID) from None
    if type(value) is not dict:
        raise WorkerFailure(WorkerCode.INVALID)
    return value


def resolve_workload(profile_id: str | None):
    return GPU_PROFILE if profile_id is None else resolve_profile(profile_id)


__all__ = [
    "BLOCKED",
    "DOCKER_DESKTOP",
    "DOCKER_ENGINE",
    "READY",
    "UNKNOWN",
    "build_host_record",
    "detect_platform",
    "doctor_report",
    "install_authority",
    "install_record",
    "load_document",
    "observe_local_device",
    "resolve_workload",
    "status_report",
    "valid_record_id",
]
