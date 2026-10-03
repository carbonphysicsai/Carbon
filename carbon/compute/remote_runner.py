"""Carbon's fixed practice program on the miner's own remote setup.

`RemoteRunner` has the carrier's call signature (`research_carrier._run`), so
practice runs on a machine or container the miner runs exactly as it runs
locally: the same staged files, the same program, the same output files,
scored on the miner's own controller. What differs is where the program runs:

1. The ledger reserves the trial first, as the carrier does.
2. A durable job record (`operation/remote-job.json`, owner-only) fixes the
   request, the job token and the deadline before anything is sent.
3. The transport the miner chose (`remote_transport`) checks the setup holds
   the pinned worker and starts one job there: a container by image ID
   (`ssh-docker`), or a process in the miner's container whose build identity
   was checked (`ssh-container`). Its port is on the machine's loopback only.
4. An SSH port forward reaches it; the controller stages the job's public
   inputs, runs it and fetches its output (`RemoteJob`).
5. The tunnel is closed and the job cleaned up, whether it succeeded or not,
   and the record says whether the cleanup was confirmed.

`RemoteWorker` is the Challenge's part: the pinned worker image and the
environment its practice program needs. The runner names no Challenge.

OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon never starts, stops or bills the
machine; that is the miner's. **The trust boundary stays on the miner's
controller.** The controller, the hotkey signer and every key stay there; the
machine receives the pinned worker, the job's public inputs and a per-job
token, nothing else. Nothing measured there is evidence the validator reads.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .job_server import PROGRAM
from .remote_job import RemoteJob, RemoteJobFailure, new_token
from .remote_machine import RemoteMachineError, checked_command, environment_lines
from .remote_transport import RemoteTransport, outcome

SCHEMA = "carbon.compute.remote-job-record.v1"
#: The job's start command: the job server from the pinned worker's own
#: wheel.
START_COMMAND = (
    "/opt/carbon-worker/bin/python",
    "-I",
    "-m",
    "carbon.compute.job_server",
)
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


def _cancel_requested(ledger, owner, identity):
    """The carrier's own stop signal for this task."""
    from carbon.development_session.research_carrier import _cancel_path

    return _cancel_path(ledger, owner, identity).exists()


def job_name(launch: str) -> str:
    """The job's name, as a container or a directory: fixed by the operation,
    so a restart finds the same job."""
    return "carbon-job-" + launch[7:31]


@dataclass(frozen=True)
class RemoteWorker:
    """The Challenge's worker on a remote setup.

    `image` is the pinned GPU worker identity (`WorkerImageIdentity`);
    `environment` is what the Challenge's practice program needs there (the
    JAX platform its GPU program runs on, for example). The job's own
    variables are the runner's and the transport's, never the Challenge's.
    """

    image: object
    environment: tuple = ()
    command: tuple = START_COMMAND

    def __post_init__(self):
        if not _IMAGE_ID.fullmatch(str(getattr(self.image, "image_id", ""))):
            raise ValueError("the remote worker is the pinned image, by ID")
        environment = tuple(tuple(pair) for pair in self.environment)
        if any(key.startswith("CARBON_JOB_") for key, _ in environment):
            raise ValueError("the job's own variables are not the Challenge's")
        if environment:
            environment_lines(environment)
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "command", checked_command(self.command))


class RemoteRunner:
    """A carrier-compatible practice runner on the miner's own remote setup.

    `transport` is a `RemoteTransport` over the miner's own SSH, and `worker`
    the Challenge's `RemoteWorker`.
    """

    def __init__(
        self,
        *,
        transport: RemoteTransport,
        worker: RemoteWorker,
        startup_seconds: int = 120,
        clock: Callable[[], float] = time.time,
        job: Callable = RemoteJob,
    ):
        if type(worker) is not RemoteWorker:
            raise ValueError("the remote worker is the pinned image, by ID")
        if type(startup_seconds) is not int or not 10 <= startup_seconds <= 900:
            raise ValueError("bounded startup allowance required")
        self.transport, self.worker = transport, worker
        self.startup_seconds, self.clock, self.job = startup_seconds, clock, job

    @property
    def image_id(self) -> str:
        return self.worker.image.image_id

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
        """Check the setup holds the pinned worker, then start the job; its
        port on the machine's loopback."""
        self.transport.verify(self.worker.image)
        return self.transport.start(
            name,
            self.worker.image,
            (
                ("CARBON_JOB_TOKEN", record["token"]),
                ("CARBON_JOB_SECONDS", str(seconds)),
                # The server ends itself after this, and the transport's own
                # cleanup (`--rm`, or the job directory) follows, even if this
                # controller never returns.
                (
                    "CARBON_JOB_LIFETIME",
                    str(self.startup_seconds + seconds + 300),
                ),
                *self.worker.environment,
            ),
            self.worker.command,
            timeout=self.startup_seconds,
        )

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
        remote = self.transport.describe(self.worker.image)
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
        name = job_name(launch)
        started = time.monotonic()
        cleaned = False
        try:
            tunnel = None
            try:
                port = self._start(name, record, seconds)
                tunnel = self.transport.tunnel(port)
                job = self.job(
                    tunnel.url,
                    record["token"],
                    cancelled=lambda: _cancel_requested(ledger, owner, identity),
                )
                now = job.clock()
                result, output = job.run(
                    {**files, PROGRAM: source.encode()},
                    ready_deadline=now + self.startup_seconds,
                    run_deadline=now + self.startup_seconds + seconds + 60,
                )
            finally:
                # Whatever happened: close the tunnel and clean up the job.
                # The machine itself is the miner's and is never touched.
                if tunnel is not None:
                    tunnel.close()
                cleaned = self.transport.cleanup(name)
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
                    "remote": outcome(remote, cleaned),
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
        worker_result = {
            "schema": "carbon.autoresearch.worker-result.v1",
            "provenance": provenance,
            "output_digest": digest(
                canonical({n: digest(b) for n, b in output.items()})
            ),
            "files": {n: digest(b) for n, b in sorted(output.items())},
            "operation": operation.name,
            "remote": {**outcome(remote, cleaned), "job": result},
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
            result=worker_result,
        )
        return worker_result
