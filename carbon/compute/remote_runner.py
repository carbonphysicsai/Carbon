"""Carbon's fixed practice program on the miner's own remote GPU machine.

`RemoteRunner` has the carrier's call signature (`research_carrier._run`), so
practice runs on a GPU machine the miner runs exactly as it runs locally: the
same staged files, the same program, the same output files, scored on the
miner's own controller. What differs is where the program runs:

1. The ledger reserves the trial first, as the carrier does.
2. A durable job record (`operation/remote-job.json`, owner-only) fixes the
   request, the job token and the deadline before anything is sent.
3. Over SSH, one job container starts on the machine from the pinned worker,
   by image ID, under a per-operation name, with the job port published on
   the machine's loopback only (`remote_machine.start_script`).
4. An SSH port forward reaches it; the controller stages the job's public
   inputs, runs it and fetches its output (`RemoteJob`).
5. The tunnel is closed and the container removed, whether the job succeeded
   or not, and the record says whether the removal was confirmed.

OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon never starts, stops or bills the
machine; that is the miner's. **The trust boundary stays on the miner's
controller.** The controller, the hotkey signer and every key stay there; the
machine receives the pinned worker, the job's public inputs and a per-job
token, nothing else. Nothing measured there is evidence the validator reads.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .job_server import PROGRAM
from .remote_job import RemoteJob, RemoteJobFailure, new_token
from .remote_machine import (
    JOB_PORT,
    RemoteMachineError,
    failure_for,
    published_port,
    remove_script,
    start_script,
)

SCHEMA = "carbon.compute.remote-job-record.v1"
#: How the controller reaches the job: an SSH local port forward.
JOB_TRANSPORT = "ssh-tunnel"
#: The container's start command: the job server from the pinned worker's
#: own wheel.
START_COMMAND = (
    "/opt/carbon-worker/bin/python",
    "-I",
    "-m",
    "carbon.compute.job_server",
)


def _cancel_requested(ledger, owner, identity):
    """The carrier's own stop signal for this task."""
    from carbon.development_session.research_carrier import _cancel_path

    return _cancel_path(ledger, owner, identity).exists()


def container_name(launch: str) -> str:
    """The job container's name: fixed by the operation, so a restart finds
    the same container."""
    return "carbon-job-" + launch[7:31]


class RemoteRunner:
    """A carrier-compatible practice runner on the miner's own GPU machine.

    `machine` is an `SSHClient` (or a double with its `run` and `tunnel`), and
    `image` the pinned GPU worker identity it holds by image ID.
    """

    def __init__(
        self,
        *,
        machine,
        image,
        startup_seconds: int = 120,
        clock: Callable[[], float] = time.time,
        job: Callable = RemoteJob,
    ):
        image_id = getattr(image, "image_id", None)
        if not isinstance(image_id, str) or not image_id.startswith("sha256:"):
            raise ValueError("the remote worker is the pinned image, by ID")
        if type(startup_seconds) is not int or not 10 <= startup_seconds <= 900:
            raise ValueError("bounded startup allowance required")
        self.machine, self.image_id = machine, image_id
        self.startup_seconds, self.clock, self.job = startup_seconds, clock, job

    def _record(self, operation, request, seconds):
        """The durable job record: written once, before anything is sent."""
        path = operation / "remote-job.json"
        if not path.exists():
            operation.mkdir(mode=0o700, exist_ok=True)
            write_once(
                path,
                canonical(
                    {
                        "schema": SCHEMA,
                        "request": request,
                        "token": new_token(),
                        "deadline_at": math.ceil(
                            self.clock() + self.startup_seconds + seconds + 300
                        ),
                    }
                ),
            )
            path.chmod(0o600)
        record = json.loads(path.read_bytes())
        if record.get("schema") != SCHEMA or record.get("request") != request:
            raise ValueError("remote job record conflict")
        return record

    def _start(self, name, record, seconds):
        """Start the job container; its host port on the machine's loopback."""
        script = start_script(
            image_id=self.image_id,
            name=name,
            env=(
                ("CARBON_JOB_TOKEN", record["token"]),
                ("CARBON_JOB_PORT", str(JOB_PORT)),
                ("CARBON_JOB_SECONDS", str(seconds)),
                # The server ends itself after this, and `--rm` removes the
                # container, even if this controller never returns.
                (
                    "CARBON_JOB_LIFETIME",
                    str(self.startup_seconds + seconds + 300),
                ),
                ("JAX_PLATFORMS", "cuda"),
            ),
            command=START_COMMAND,
        )
        code, stdout = self.machine.run(script, timeout=self.startup_seconds)
        if code != 0:
            raise failure_for(code)
        return published_port(stdout)

    def _remove(self, name) -> bool:
        """Remove the job container; True only once the machine confirms it."""
        try:
            code, _ = self.machine.run(remove_script(name), timeout=120)
        except OSError:
            return False
        return code == 0

    def __call__(
        self,
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
        accelerator=None,
    ):
        del accelerator  # The machine's GPUs, through the pinned worker.
        if getattr(image, "image_id", None) != self.image_id:
            raise ValueError("practice asks for another worker than the machine's")
        if type(seconds) is not int or not 40 <= seconds <= 3600:
            raise ValueError("bounded worker wall allowance required")
        if type(files) is not dict or PROGRAM in files:
            raise ValueError("closed stage required")
        remote = {"image": self.image_id, "job_transport": JOB_TRANSPORT}
        request = {
            "source": digest(source.encode()),
            "files": {n: digest(b) for n, b in files.items()},
            "seconds": seconds,
            "provenance": provenance,
            "remote": remote,
        }
        launch = digest(
            canonical({"owner": owner, "identity": identity, "request": request})
        )
        operation = ledger.root / ("operation-" + launch[7:])
        resources = {
            "numerical_milliseconds": seconds * 1000,
            "retained_bytes": sum(map(len, files.values())) + 2 * 64 * 1024**2,
            **extra_resources,
        }
        admission = ledger.reserve(
            identity,
            owner=owner,
            phase="research",
            request=request,
            resources=resources,
        )
        if not admission["dispatch"]:
            if admission["state"] == "RESERVED":
                raise ValueError(
                    "remote operation ambiguous; reconcile, never duplicate"
                )
            return admission["result"]
        record = self._record(operation, request, seconds)
        name = container_name(launch)
        started = time.monotonic()
        removed = False
        try:
            tunnel = None
            try:
                port = self._start(name, record, seconds)
                tunnel = self.machine.tunnel(port)
                job = self.job(
                    tunnel.url,
                    record["token"],
                    cancelled=lambda: _cancel_requested(ledger, owner, identity),
                )
                now = job.clock()
                outcome, output = job.run(
                    {**files, PROGRAM: source.encode()},
                    ready_deadline=now + self.startup_seconds,
                    run_deadline=now + self.startup_seconds + seconds + 60,
                )
            finally:
                # Whatever happened: close the tunnel and remove the container.
                # The machine itself is the miner's and is never touched.
                if tunnel is not None:
                    tunnel.close()
                removed = self._remove(name)
        except (RemoteMachineError, RemoteJobFailure, OSError, ValueError) as failure:
            ledger.finish(
                identity,
                owner=owner,
                state="FAILED_INFRA",
                actual=resources,
                result={
                    "schema": "carbon.autoresearch.worker-reconciliation.v1",
                    "operation": operation.name,
                    "state": "FAILED_INFRA",
                    "remote": {**remote, "container_removed": removed},
                    "failed": getattr(failure, "code", type(failure).__name__),
                    "accounting": "full original reservation retained",
                    "scientific_outcome": "UNRESOLVED",
                    "retry_dispatched": False,
                },
            )
            raise
        snapshot = operation / "snapshot"
        snapshot.mkdir(mode=0o700)
        for file_name, body in output.items():
            write_once(snapshot / file_name, body)
        result = {
            "schema": "carbon.autoresearch.worker-result.v1",
            "provenance": provenance,
            "output_digest": digest(
                canonical({n: digest(b) for n, b in output.items()})
            ),
            "files": {n: digest(b) for n, b in sorted(output.items())},
            "operation": operation.name,
            "remote": {**remote, "container_removed": removed, "job": outcome},
            "scientific_qualification": False,
            "official_eligible": False,
        }
        ledger.finish(
            identity,
            owner=owner,
            state="SUCCEEDED",
            actual={
                **resources,
                "numerical_milliseconds": math.ceil(
                    (time.monotonic() - started) * 1000
                ),
                "retained_bytes": sum(
                    p.stat().st_size for p in operation.rglob("*") if p.is_file()
                ),
            },
            result=result,
        )
        return result
