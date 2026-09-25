"""Run a battery worker program in a real container, the carrier's way.

The sequence is the isolated carrier's (`research_carrier._run_locked`):
1. stage the files read-only;
2. `docker create` with the carrier's exact isolation arguments
   (`docker_runtime.create_arguments`: no network, read-only root, all
   capabilities dropped, no new privileges, private IPC, pid, memory, CPU and
   file limits, a noexec tmpfs scratch);
3. start the idle entrypoint and execute the carrier's bootstrap;
4. export through the real bounded exporter and decode with
   `decode_output_stream`;
5. remove the exact container.

The validator's `WorkLedger` makes it idempotent in the same way.

Two differences from production, named so no test result claims more:
- the host `doctor` is not consulted: this sandbox runs cgroup v1, and the
  doctor requires v2;
- the image is a local test image (`CARBON_BATTERY_TEST_IMAGE`), not the
  accepted, digest-pinned C-03 worker image.
Tests that use it therefore report `CONTAINER_ISOLATED_TEST_IMAGE`.
"""

from __future__ import annotations

import os
import subprocess

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_carrier import BOOTSTRAP
from carbon.reconstruction.worker.docker_runtime import create_arguments
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
from carbon.reconstruction.worker.protocol import decode_output_stream

IMAGE = os.environ.get("CARBON_BATTERY_TEST_IMAGE")
IDENTITY = {
    "backend": "CONTAINER_ISOLATED_TEST_IMAGE",
    "validator_path": False,
    "image": IMAGE,
}


def available():
    if not IMAGE:
        return False
    probe = subprocess.run(
        ["docker", "image", "inspect", IMAGE], capture_output=True, check=False
    )
    return probe.returncode == 0


def _docker(*arguments, timeout=60, check=True, stdout=None):
    return subprocess.run(
        ["docker", *arguments],
        capture_output=stdout is None,
        stdout=stdout,
        timeout=timeout,
        check=check,
    )


def run(
    ledger,
    *,
    owner,
    identity,
    source,
    files,
    image,
    seconds,
    provenance,
    extra_resources,
    phase="final",
):
    request = {
        "source": digest(source.encode()),
        "files": {n: digest(b) for n, b in files.items()},
        "seconds": seconds,
        "provenance": provenance,
    }
    admission = ledger.reserve(
        identity,
        owner=owner,
        phase=phase,
        request=request,
        resources={"numerical_milliseconds": seconds * 1000, **extra_resources},
    )
    if not admission["dispatch"]:
        if admission["state"] == "RESERVED":
            raise ValueError("operation ambiguous; reconcile, never duplicate")
        return admission["result"]
    launch = digest(
        canonical({"owner": owner, "identity": identity, "request": request})
    )
    operation = ledger.root / ("operation-" + launch[7:])
    stage = operation / "input"
    stage.mkdir(parents=True, mode=0o755)
    for name, body in {**files, "program.py": source.encode()}.items():
        (stage / name).write_bytes(body)
        (stage / name).chmod(0o444)
    stage.chmod(0o555)
    name = "carbon-d4-" + launch[7:31]
    image_id = (
        _docker("image", "inspect", "--format", "{{.Id}}", IMAGE)
        .stdout.decode()
        .strip()
    )
    arguments = create_arguments(
        container_name=name,
        image_id=image_id,
        input_directory=stage.resolve(),
        cpuset="0-" + str(max(0, (os.cpu_count() or 2) - 1)),
        launch_digest=launch,
        worker_profile=DevelopmentWorkerProfile(
            digest(b"carbon.battery.validator-test.v1"),
            digest(b"2cpu-4gib-noswap-600seconds"),
        ),
    )
    output = operation / "export.stream"
    try:
        _docker(*arguments, timeout=60)
        _docker("start", name, timeout=30)
        for _ in range(200):
            ready = _docker(
                "exec",
                name,
                "test",
                "-e",
                "/scratch/control-ready",
                check=False,
                timeout=10,
            )
            if ready.returncode == 0:
                break
        program = _docker(
            "exec",
            name,
            "/opt/carbon-worker/bin/python",
            "-I",
            "-c",
            BOOTSTRAP,
            timeout=seconds,
            check=False,
        )
        (operation / "stdout.txt").write_bytes(
            program.stdout[-65536:] + program.stderr[-65536:]
        )
        with output.open("wb") as handle:
            _docker(
                "exec",
                name,
                "/opt/carbon-worker/bin/python",
                "-I",
                "-m",
                "carbon.reconstruction.worker.exporter",
                timeout=120,
                stdout=handle,
            )
    finally:
        _docker("rm", "--force", name, check=False, timeout=60)
    remaining = _docker("ps", "-aq", "--filter", "name=^" + name + "$").stdout.strip()
    if remaining:
        raise ValueError("container cleanup uncertain")
    snapshot = operation / "snapshot"
    decode_output_stream(output, snapshot)
    result = {
        "schema": "carbon.autoresearch.worker-result.v1",
        "provenance": provenance,
        "output_digest": digest(output.read_bytes()),
        "files": {
            p.relative_to(snapshot).as_posix(): digest(p.read_bytes())
            for p in sorted(snapshot.rglob("*"))
            if p.is_file()
        },
        "operation": operation.name,
        "container_isolation": "create_arguments",
        "scientific_qualification": False,
        "official_eligible": False,
    }
    ledger.finish(
        identity,
        owner=owner,
        state="SUCCEEDED",
        actual={"numerical_milliseconds": seconds * 1000},
        result=result,
    )
    return result


def network_denied(image=None):
    """Probe: a container created with the carrier's arguments has no network."""
    probe = _docker(
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "/opt/carbon-worker/bin/python",
        image or IMAGE,
        "-I",
        "-c",
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
        "    print('CONNECTED')\n"
        "except OSError:\n"
        "    print('DENIED')",
        check=False,
        timeout=60,
    )
    return probe.stdout.decode().strip() == "DENIED"
