"""The validator host's tested software stack: one registered answer, checked, never assumed.

A validator host rebuilds untrusted work on a GPU and then grades on its CPU, so the software under it is part
of the result: the Docker engine and its image store decide how an image is addressed and how a container is
created, the NVIDIA driver and container toolkit decide what a kernel computes. A box ships whatever its
provider installed, and a newer minor version silently changed behaviour (a GPU prep that ran on one engine
failed at staging on the next). So the validator path does not report READY on "whatever is there": it reads
the facts below and refuses unless they are the registered, tested ones.

This module is data plus a pure check. `read_facts` asks the host with plain, version-stable commands; `problems`
compares the facts with `HOST_STACK`. Changing what is accepted is a reviewed edit to `HOST_STACK`, naming the
evidence for each version, by the Validator. It is not a setting and not a flag.
"""

from __future__ import annotations

import re
import shutil
import subprocess

SCHEMA = "carbon.validator.host-stack.v1"

HOST_STACK = {
    "schema": SCHEMA,
    # Exact engine versions a rebuild has been shown to run on, each with its evidence. A version not
    # listed is refused, newer included: "tested" is a fact about one version, not a range.
    "docker_engine_tested": {
        "29.1.3": (
            "M1 rehearsal installs and catalog builds (SHIP_MATRIX_20261023); the engine the supported "
            "setup was written against"
        ),
    },
    # Versions seen to fail, kept so the refusal can say why rather than only 'not tested'.
    "docker_engine_refused": {
        "29.6.1": (
            "CloudRift 4090 VM, 2026-10-27: the GPU overlay prep ended FAILED_INFRA at STAGING "
            "(worker_code reconstruction.worker.runtime.failed); under diagnosis"
        ),
    },
    # The image store: Carbon's worker, parent and uv lookups are written for the containerd store that
    # Docker 29 defaults to (addressing by manifest digest + the install's recorded fingerprint).
    "image_store": "containerd",
    # The NVIDIA Linux driver: at least the CUDA 13.0 minimum, and in a series a determinism check ran on.
    "nvidia_driver_min": "580.65.06",
    "nvidia_driver_series_tested": (580,),
    # The NVIDIA container toolkit must be present and answer with a version; its exact tested versions
    # are the Validator's to register with evidence (none is claimed here).
    "nvidia_toolkit_tested": (),
}

_VERSION = re.compile(r"\d+(?:\.\d+)*")


def _numbers(text) -> tuple:
    found = _VERSION.search(str(text or ""))
    return tuple(int(part) for part in found.group(0).split(".")) if found else ()


def image_store(info) -> str:
    """'containerd', 'classic' or 'unknown' from `docker info --format '{{json .}}'`, without relying on
    any one engine release's field set: the containerd snapshotter announces itself in `DriverStatus`
    (any row naming a containerd snapshotter), the classic store by an `overlay2` storage driver.
    """
    if type(info) is not dict:
        return "unknown"
    status = info.get("DriverStatus")
    rows = status if type(status) is list else []
    if any(
        type(row) is list and any("containerd" in str(cell).lower() for cell in row)
        for row in rows
    ):
        return "containerd"
    if str(info.get("Driver", "")).lower() == "overlay2":
        return "classic"
    return "unknown"


def problems(facts, stack=HOST_STACK) -> list:
    """Every way `facts` differs from the registered stack, as ``{"check", "found", "required"}`` rows;
    empty means this host runs the tested stack. A fact that could not be read is a problem, never a pass.
    """
    rows = []

    def add(check, found, required):
        rows.append({"check": check, "found": found, "required": required})

    engine = facts.get("docker_engine")
    tested = stack["docker_engine_tested"]
    if engine is None:
        add("docker_engine", None, "a readable engine version")
    elif engine in stack["docker_engine_refused"]:
        add(
            "docker_engine",
            engine,
            f"refused: {stack['docker_engine_refused'][engine]}",
        )
    elif engine not in tested:
        add("docker_engine", engine, "exactly one of: " + ", ".join(sorted(tested)))
    store = facts.get("image_store")
    if store != stack["image_store"]:
        add("image_store", store, stack["image_store"])
    driver = _numbers(facts.get("nvidia_driver"))
    if not driver:
        add(
            "nvidia_driver",
            facts.get("nvidia_driver"),
            f">= {stack['nvidia_driver_min']}",
        )
    else:
        if driver < _numbers(stack["nvidia_driver_min"]):
            add(
                "nvidia_driver",
                facts.get("nvidia_driver"),
                f">= {stack['nvidia_driver_min']}",
            )
        if driver[0] not in stack["nvidia_driver_series_tested"]:
            add(
                "nvidia_driver_series",
                facts.get("nvidia_driver"),
                "a tested series: "
                + ", ".join(str(s) for s in stack["nvidia_driver_series_tested"]),
            )
    toolkit = facts.get("nvidia_toolkit")
    if not _numbers(toolkit):
        add(
            "nvidia_toolkit",
            toolkit,
            "the NVIDIA container toolkit, answering with a version",
        )
    elif (
        stack["nvidia_toolkit_tested"] and toolkit not in stack["nvidia_toolkit_tested"]
    ):
        add(
            "nvidia_toolkit",
            toolkit,
            "exactly one of: " + ", ".join(stack["nvidia_toolkit_tested"]),
        )
    return rows


def _out(command, run) -> str | None:
    try:
        done = run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def read_facts(run=subprocess.run, which=shutil.which) -> dict:
    """The host's stack facts, from commands whose output format has not changed between engine releases:
    `docker version --format {{.Server.Version}}`, `docker info --format {{json .}}`,
    `nvidia-smi --query-gpu=driver_version`, `nvidia-ctk --version`. Anything unreadable is None.
    """
    import json

    info = None
    raw = _out(["docker", "info", "--format", "{{json .}}"], run)
    if raw:
        try:
            info = json.loads(raw)
        except ValueError:
            info = None
    toolkit = None
    if which("nvidia-ctk"):
        text = _out(["nvidia-ctk", "--version"], run) or ""
        found = re.search(r"version\s+(\d+(?:\.\d+)+)", text, re.IGNORECASE)
        toolkit = found.group(1) if found else None
    driver = _out(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], run
    )
    return {
        "docker_engine": _out(
            ["docker", "version", "--format", "{{.Server.Version}}"], run
        )
        or None,
        "image_store": image_store(info),
        "nvidia_driver": driver.splitlines()[0].strip() if driver else None,
        "nvidia_toolkit": toolkit,
    }
