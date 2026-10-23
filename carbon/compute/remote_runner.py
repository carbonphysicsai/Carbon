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

**Carrier-layout jobs (catalog bundle practice, shared GPU path S4).** The
shared bundle worker's GPU phases (overlay preparation and the overlay
build) pass the carrier's own layout arguments: a `bootstrap`, a verified
`trusted_overlay`, the pinned uv stage. Their programs read `/input` and
write `/scratch/output`, as the local carrier mounts them. Such a job runs
only in Carbon's hardened job container (`ssh-docker`, whose empty `/input`
tmpfs sits beside `/scratch`), through one fixed adapter program
(`CARRIER_LAYOUT`) that lays the staged inputs out there, runs the
bootstrap and returns `/scratch/output`. The controller checks the overlay
and the uv stage before anything is sent, and the bundle worker's own output
validator checks what comes back, as it does locally.

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
#: A job's stderr naming a driver older than the worker's CUDA runtime.
DRIVER_TOO_OLD = re.compile(
    rb"cudaErrorInsufficientDriver|CUDA driver version is insufficient", re.IGNORECASE
)
#: The `RemoteJobFailure` detail for it, which a practice records as its note.
GPU_DRIVER_TOO_OLD = "gpu_driver_too_old"
#: What a carrier-layout job stages beside its inputs: the carrier's program,
#: its bootstrap, the layout itself and, for an overlay build, the verified
#: overlay as one archive.
CARRIER_PROGRAM = "carbon-carrier-program.py"
CARRIER_BOOTSTRAP = "carbon-carrier-bootstrap.py"
CARRIER_FILES = "carbon-carrier-layout.json"
CARRIER_OVERLAY = "carbon-carrier-overlay.tar"
CARRIER_NAMES = frozenset(
    {CARRIER_PROGRAM, CARRIER_BOOTSTRAP, CARRIER_FILES, CARRIER_OVERLAY}
)
#: The fixed program a carrier-layout job runs: stdlib only, from the job
#: server's own input directory. `/input` and `/scratch` are the hardened job
#: container's tmpfs mounts; a test of this module names others.
CARRIER_LAYOUT = r'''"""Carbon's carrier layout in a remote job container (remote_runner)."""
import json, os, shutil, subprocess, sys, tarfile
from pathlib import Path

here = Path(__file__).resolve().parent
out = Path.cwd().parent / "output"
layout = json.loads((here / "carbon-carrier-layout.json").read_bytes())
stage = Path(os.environ.get("CARBON_CARRIER_INPUT", "/input"))
scratch = Path(os.environ.get("CARBON_CARRIER_SCRATCH", "/scratch"))
if not stage.is_dir() or any(stage.iterdir()):
    raise SystemExit("carrier layout needs an empty /input")
for name in layout["files"]:
    shutil.copyfile(here / name, stage / name)
    (stage / name).chmod(0o555 if name in layout["executable"] else 0o444)
shutil.copyfile(here / "carbon-carrier-program.py", stage / "program.py")
(stage / "program.py").chmod(0o444)
if layout["overlay"]:
    with tarfile.open(here / "carbon-carrier-overlay.tar", mode="r:") as archive:
        members = archive.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if (member.name.startswith("/") or ".." in parts or not parts
                    or parts[0] != "overlay" or not (member.isreg() or member.isdir())):
                raise SystemExit("closed overlay archive required")
        archive.extractall(stage, members=members, filter="data")
    for entry in sorted((stage / "overlay").rglob("*"), reverse=True):
        entry.chmod(0o555 if entry.is_dir() else 0o444)
    (stage / "overlay").chmod(0o555)
bootstrap = (here / "carbon-carrier-bootstrap.py").read_text()
done = subprocess.run([sys.executable, "-I", "-c", bootstrap], check=False)
made = scratch / "output"
if made.is_dir():
    for item in sorted(made.iterdir()):
        if item.is_file() and not item.is_symlink():
            shutil.copyfile(item, out / item.name)
raise SystemExit(done.returncode)
'''


def overlay_archive(root) -> bytes:
    """A verified overlay tree as one deterministic tar under `overlay/`:
    regular files and directories only."""
    import io
    import tarfile
    from pathlib import Path

    root = Path(root)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        entries = sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())
        for path in (root, *entries):
            relative = path.relative_to(root).as_posix()
            name = "overlay" if relative == "." else "overlay/" + relative
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise ValueError("a verified overlay holds files and directories")
            info = tarfile.TarInfo(name)
            info.mtime, info.uid, info.gid = 0, 0, 0
            if path.is_dir():
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                archive.addfile(info)
            else:
                body = path.read_bytes()
                info.size, info.mode = len(body), 0o644
                archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


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
        """Check the setup holds the pinned worker, then start the job; where
        it listens on the machine (`JobEndpoint`)."""
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

    def _layout(
        self,
        image,
        files,
        *,
        bootstrap,
        executable_files,
        trusted_overlay,
        trusted_stage_provider,
        trusted_stage_identity,
    ):
        """What a carrier-layout job binds in its request, checked before
        anything is reserved; None for a job in the job server's own layout
        (a GPU practice program, unchanged)."""
        if (
            bootstrap is None
            and trusted_overlay is None
            and trusted_stage_provider is None
            and not executable_files
        ):
            if trusted_stage_identity is not None:
                raise ValueError("trusted stage identity without provider")
            return None
        if not getattr(self.transport, "carrier_layout", False):
            raise ValueError(
                "catalog bundle practice on a remote GPU runs over ssh-docker"
            )
        if type(bootstrap) is not str or not bootstrap:
            raise ValueError("a carrier-layout job names its bootstrap")
        if CARRIER_NAMES & set(files) or "program.py" in files:
            raise ValueError("closed stage required")
        if executable_files not in ((), ("uv-bin",)) or (
            executable_files and trusted_stage_provider is None
        ):
            raise ValueError("trusted preparation executable role required")
        if (trusted_stage_provider is None) != (trusted_stage_identity is None) or (
            trusted_stage_provider is not None and not callable(trusted_stage_provider)
        ):
            raise ValueError("trusted pinned UV stage required")
        layout = {
            "bootstrap": digest(bootstrap.encode()),
            "executable_files": list(executable_files),
        }
        if trusted_stage_identity is not None:
            layout["trusted_stage_identity"] = trusted_stage_identity
        if trusted_overlay is not None:
            from carbon.development_session.library_environment_cache import (
                VerifiedLibraryOverlay,
            )

            if (
                type(trusted_overlay) is not VerifiedLibraryOverlay
                or trusted_overlay.parent_image_id != image.image_id
            ):
                raise ValueError("trusted construction-only overlay required")
            layout["verified_overlay"] = {
                "tree_digest": trusted_overlay.tree_digest,
                "bundle_ref": trusted_overlay.bundle_ref.to_dict(),
                "parent_image_id": trusted_overlay.parent_image_id,
                "archive_digest": trusted_overlay.archive_digest,
            }
        return layout

    def _staged(self, source, files, layout, *, bootstrap, overlay, provider):
        """The job's whole stage: its inputs and the job server's program,
        or, for a carrier-layout job, the fixed adapter with the carrier's
        program, bootstrap, uv stage and verified overlay beside them."""
        if layout is None:
            return {**files, PROGRAM: source.encode()}
        staged = dict(files)
        if provider is not None:
            from carbon.development_session.research_carrier import (
                _checked_pinned_uv_stage,
            )
            from carbon.reconstruction.worker.docker_runtime import DockerCLI

            # The pinned uv binary, copied from the controller's own pinned
            # image exactly as the local carrier stages it.
            staged.update(
                _checked_pinned_uv_stage(
                    provider(DockerCLI()), layout["trusted_stage_identity"]
                )
            )
        listed = sorted(staged)
        if overlay is not None:
            from carbon.development_session.library_environment_cache import (
                _verified_overlay_tree,
            )

            receipt = json.loads((overlay.path / ".overlay.json").read_bytes())
            if (
                type(receipt) is not dict
                or receipt.get("tree_digest") != overlay.tree_digest
                or receipt.get("bundle_ref") != overlay.bundle_ref.to_dict()
                or receipt.get("parent_image_id") != overlay.parent_image_id
                or receipt.get("archive_sha256") != overlay.archive_digest
            ):
                raise ValueError("trusted overlay receipt differs")
            _verified_overlay_tree(overlay.path, receipt)
            staged[CARRIER_OVERLAY] = overlay_archive(overlay.path)
        staged[CARRIER_FILES] = canonical(
            {
                "files": listed,
                "executable": layout["executable_files"],
                "overlay": overlay is not None,
            }
        )
        staged[CARRIER_PROGRAM] = source.encode()
        staged[CARRIER_BOOTSTRAP] = bootstrap.encode()
        staged[PROGRAM] = CARRIER_LAYOUT.encode()
        return staged

    def _failed(self, ledger, *, cleaned, failure, **settle):
        """Settle a trial that did not complete: infrastructure, never the
        candidate's, with the full reservation retained."""
        ledger.finish(
            settle["identity"],
            owner=settle["owner"],
            state="FAILED_INFRA",
            actual=settle["resources"],
            result={
                "schema": "carbon.autoresearch.worker-reconciliation.v1",
                "operation": settle["operation"].name,
                "state": "FAILED_INFRA",
                "remote": outcome(settle["remote"], cleaned),
                "failed": getattr(failure, "code", type(failure).__name__),
                "accounting": "full original reservation retained",
                "scientific_outcome": "UNRESOLVED",
                "retry_dispatched": False,
            },
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
        bootstrap=None,
        output_validator=None,
        executable_files=(),
        trusted_overlay=None,
        trusted_stage_provider=None,
        trusted_stage_identity=None,
    ):
        del accelerator  # The machine's GPUs, through the pinned worker.
        if getattr(image, "image_id", None) != self.image_id:
            raise ValueError("practice asks for another worker than the machine's")
        if type(seconds) is not int or not 40 <= seconds <= 3600:
            raise ValueError("bounded worker wall allowance required")
        if type(files) is not dict or PROGRAM in files:
            raise ValueError("closed stage required")
        if output_validator is not None and not callable(output_validator):
            raise ValueError("output validator required")
        layout = self._layout(
            image,
            files,
            bootstrap=bootstrap,
            executable_files=tuple(executable_files),
            trusted_overlay=trusted_overlay,
            trusted_stage_provider=trusted_stage_provider,
            trusted_stage_identity=trusted_stage_identity,
        )
        remote = self.transport.describe(self.worker.image)
        request = {
            "source": digest(source.encode()),
            "files": {n: digest(b) for n, b in files.items()},
            "seconds": seconds,
            "provenance": provenance,
            "remote": remote,
            # Absent for a job in the job server's own layout, so existing
            # remote operation identities are unchanged.
            **({} if layout is None else {"carrier_layout": layout}),
        }
        launch = digest(
            canonical({"owner": owner, "identity": identity, "request": request})
        )
        operation = ledger.root / ("operation-" + launch[7:])
        resources = {
            "numerical_milliseconds": seconds * 1000,
            "retained_bytes": sum(map(len, files.values()))
            + (0 if trusted_overlay is None else trusted_overlay.total_bytes)
            + 2 * 64 * 1024**2,
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
        settle = {
            "owner": owner,
            "identity": identity,
            "resources": resources,
            "operation": operation,
            "remote": remote,
        }
        try:
            tunnel = None
            try:
                staged = self._staged(
                    source,
                    files,
                    layout,
                    bootstrap=bootstrap,
                    overlay=trusted_overlay,
                    provider=trusted_stage_provider,
                )
                endpoint = self._start(name, record, seconds)
                tunnel = self.transport.tunnel(endpoint)
                # The job is reached only through the tunnel's owner-only Unix
                # socket, never a local TCP port.
                job = self.job(
                    tunnel.url,
                    record["token"],
                    transport=tunnel.transport,
                    cancelled=lambda: _cancel_requested(ledger, owner, identity),
                )
                now = job.clock()
                result, output = job.run(
                    staged,
                    ready_deadline=now + self.startup_seconds,
                    run_deadline=now + self.startup_seconds + seconds + 60,
                )
            finally:
                # Whatever happened: close the tunnel and clean up the job.
                # The machine itself is the miner's and is never touched.
                if tunnel is not None:
                    tunnel.close()
                cleaned = self.transport.cleanup(name)
            if layout is not None:
                # The carrier's output set only: the job's stderr stays beside
                # the snapshot, never in it.
                stderr = output.pop("carbon-job-stderr.txt", b"")
                write_once(operation / "remote-stderr.txt", stderr[-65536:])
                if result.get("state") != "DONE":
                    # The one cause a miner can act on, by its closed code
                    # (M1 S5: the JAX cuda13 worker on a CUDA 12.8 driver).
                    if DRIVER_TOO_OLD.search(stderr[-65536:]):
                        raise RemoteJobFailure("run", GPU_DRIVER_TOO_OLD)
                    raise RemoteJobFailure("run", "the carrier program failed")
        except (RemoteMachineError, RemoteJobFailure, OSError, ValueError) as failure:
            self._failed(ledger, cleaned=cleaned, failure=failure, **settle)
            raise
        snapshot = operation / "snapshot"
        snapshot.mkdir(mode=0o700)
        for file_name, body in output.items():
            write_once(snapshot / file_name, body)
        if output_validator is not None:
            # The bundle worker's own check of its program's output, applied
            # before settling, as the local carrier applies it.
            try:
                output_validator(snapshot)
            except (ValueError, OSError, KeyError, TypeError) as failure:
                self._failed(ledger, cleaned=cleaned, failure=failure, **settle)
                raise
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
