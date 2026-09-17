"""Isolated public-research carrier reusing C-03 mechanisms and output parser.

No API accepts host mounts, Docker options, credentials or protected inputs.
Research script output is always untrusted/self-reported. Trusted practice uses
a separate invocation with a controller-selected fixed program and staged data.
"""

from __future__ import annotations

import json
import math
import time
from contextlib import contextmanager

from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    create_arguments,
    doctor,
    inspect_effective_controls,
    observe_effective_resources,
    remove_exact_container,
    spawn_watchdog,
)
from carbon.reconstruction.worker.model import (
    CONTROL_BYTES,
    OUTPUT_BYTES,
    DevelopmentWorkerProfile,
)
from carbon.reconstruction.worker.protocol import decode_output_stream

from .data import write_once
from .profile import canonical, digest
from .research_workspace import MAX_FILES, MAX_WORKSPACE_BYTES, ResearchWorkspace

BOOTSTRAP = """
import os,shutil
from pathlib import Path
work=Path('/scratch/workspace');work.mkdir()
out=Path('/scratch/output');out.mkdir()
for item in Path('/input').iterdir():
    if item.name!='program.py': shutil.copyfile(item,work/item.name)
os.chdir(work)
os.execv('/opt/carbon-worker/bin/python',['python','-I','/input/program.py'])
"""


def run_script(ledger, *, owner, identity, source, files, image, seconds=600):
    """Run miner Python only on explicitly staged public/own file bytes."""
    if type(source) is not str or len(source.encode()) > 65536:
        raise ValueError("bounded research source required")
    return _run(
        ledger,
        owner=owner,
        identity=identity,
        source=source,
        files=files,
        image=image,
        seconds=seconds,
        provenance="MINER_SELF_REPORTED",
        extra_resources={},
    )


@contextmanager
def _numerical_lease(ledger):
    import fcntl

    path = ledger.root / "numerical-supervisor.lock"
    if path.is_symlink():
        raise ValueError("numerical lease symlink")
    with path.open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError(
                "numerical supervisor active; do not reconcile live work"
            ) from None
        yield


def _run(ledger, **kwargs):
    with _numerical_lease(ledger):
        return _run_locked(ledger, **kwargs)


def _run_locked(
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
):
    if type(seconds) is not int or not 40 <= seconds <= 600:
        raise ValueError("bounded worker wall allowance required")
    if type(files) is not dict or len(files) > MAX_FILES or "program.py" in files:
        raise ValueError("bounded closed stage required")
    for name, body in files.items():
        ResearchWorkspace.name(name)
        if type(body) is not bytes:
            raise ValueError("stage accepts bytes, never paths")
    if sum(map(len, files.values())) > MAX_WORKSPACE_BYTES:
        raise ValueError("aggregate input cap")
    request = {
        "source": digest(source.encode()),
        "files": {n: digest(b) for n, b in files.items()},
        "image": image.image_id,
        "seconds": seconds,
        "provenance": provenance,
    }
    launch = digest(
        canonical({"owner": owner, "identity": identity, "request": request})
    )
    operation = ledger.root / ("operation-" + launch[7:])
    storage = sum(p.stat().st_size for p in ledger.root.rglob("*") if p.is_file())
    # Account stored input, provisional stream and decoded bounded output.
    reservation_bytes = (
        sum(map(len, files.values())) + 2 * OUTPUT_BYTES + 2 * CONTROL_BYTES + 65536
    )
    if storage + reservation_bytes > 10 * 1024**3:
        raise ValueError("campaign retained storage ceiling")
    resources = {
        "numerical_milliseconds": seconds * 1000,
        "retained_bytes": reservation_bytes,
        **extra_resources,
    }
    admission = ledger.reserve(
        identity, owner=owner, phase="research", request=request, resources=resources
    )
    if not admission["dispatch"]:
        if admission["state"] == "RESERVED":
            raise ValueError("research operation ambiguous; reconcile, never duplicate")
        return admission["result"]
    started = time.monotonic()
    started_unix = time.time()
    stage = operation / "input"
    stage.mkdir(parents=True, mode=0o755)
    stage.chmod(0o755)
    for name, body in {**files, "program.py": source.encode()}.items():
        path = stage / name
        write_once(path, body)
        path.chmod(0o444)
    name = "carbon-d4-" + launch[7:31]
    cli = DockerCLI()
    checked = doctor(image_id=image.image_id, image_identity=image, cli=cli)
    if not checked.eligible:
        # No attempt is automatically retried and its reservation remains visible.
        raise ValueError("research host ineligible")
    worker = DevelopmentWorkerProfile(
        digest(b"carbon.autoresearch.public-research.v1"),
        digest(b"2cpu-4gib-noswap-600seconds"),
    )
    write_once(
        operation / "intent.json",
        canonical(
            {
                "launch": launch,
                "container": name,
                "request": request,
                "owner": owner,
                "identity": identity,
                "deadline_unix": started_unix + seconds - 30,
            }
        ),
    )
    create_attempted = False
    output = operation / "export.stream"
    try:
        create_attempted = True
        cli.run(
            create_arguments(
                container_name=name,
                image_id=image.image_id,
                input_directory=stage,
                cpuset=checked.cpuset,
                launch_digest=launch,
                worker_profile=worker,
            ),
            timeout=30,
        )
        spawn_watchdog(
            container_name=name,
            launch_digest=launch,
            deadline_unix=float(started_unix + seconds - 30),
        )
        cli.run(["start", name], timeout=20)
        control_digest, controls = inspect_effective_controls(
            cli=cli,
            container_name=name,
            image_id=image.image_id,
            input_directory=stage,
            cpuset=checked.cpuset,
            launch_digest=launch,
            worker_profile=worker,
        )
        cli.stream_to_file(
            ["exec", name, "/opt/carbon-worker/bin/python", "-I", "-c", BOOTSTRAP],
            operation / "stdout.txt",
            maximum=1024**2,
            timeout=max(1, seconds - 45 - (time.monotonic() - started)),
        )
        observed = observe_effective_resources(cli=cli, container_name=name)
        cli.stream_to_file(
            [
                "exec",
                name,
                "/opt/carbon-worker/bin/python",
                "-I",
                "-m",
                "carbon.reconstruction.worker.exporter",
            ],
            output,
            maximum=OUTPUT_BYTES + 2 * CONTROL_BYTES,
            timeout=max(1, seconds - 35 - (time.monotonic() - started)),
        )
        write_once(
            operation / "resources.json",
            canonical(
                {
                    "controls": controls,
                    "controls_digest": control_digest,
                    "resources": observed,
                }
            ),
        )
    finally:
        if create_attempted:
            # C-03 checks the exact launch label, removes the entire container,
            # and confirms absence before any output becomes an associated result.
            remove_exact_container(cli=cli, container_name=name, launch_digest=launch)
            # Require a successful daemon query too: an inspect transport error
            # alone is not evidence that the container and descendants are gone.
            remaining = cli.run(
                ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
            )
            if remaining.stdout.strip():
                raise ValueError("research cleanup uncertain; capacity stays reserved")
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
        "scientific_qualification": False,
        "official_eligible": False,
    }
    elapsed = math.ceil((time.monotonic() - started) * 1000)
    actual = {
        **resources,
        "numerical_milliseconds": elapsed,
        "retained_bytes": sum(
            p.stat().st_size for p in operation.rglob("*") if p.is_file()
        ),
    }
    ledger.finish(
        identity, owner=owner, state="SUCCEEDED", actual=actual, result=result
    )
    return result


def reconcile_worker(ledger, *, owner, identity):
    """Trusted recovery after supervisor exit; never dispatch/retry work.

    Cleanup success does not prove completed training or exact lost runtime.
    Retain the entire original reservation as conservative charged consumption.
    """
    with _numerical_lease(ledger):
        matches = [
            op
            for op in ledger.status(owner=owner)["operations"]
            if op["id"] == identity
        ]
        if len(matches) != 1:
            raise ValueError("owned operation unavailable")
        op = matches[0]
        if op["state"] != "RESERVED":
            return op["result"]
        if not op["reservation"].get("numerical_milliseconds"):
            raise ValueError(
                "not a numerical worker; no provider billing reconciliation"
            )
        intents = []
        for path in ledger.root.glob("operation-*/intent.json"):
            if path.is_symlink() or path.stat().st_size > 65536:
                raise ValueError("invalid worker intent")
            value = json.loads(path.read_bytes())
            if value.get("owner") == owner and value.get("identity") == identity:
                intents.append((path, value))
        # An absent intent may represent another provider or a interrupted stage.
        # Do not infer safe cleanup from absence or invent lost launch details.
        if len(intents) != 1:
            raise ValueError(
                "exact durable worker intent unavailable; reservation retained"
            )
        path, intent = intents[0]
        launch = digest(
            canonical(
                {"owner": owner, "identity": identity, "request": intent["request"]}
            )
        )
        name = "carbon-d4-" + launch[7:31]
        if (
            intent["launch"] != launch
            or intent["container"] != name
            or path.parent.name != "operation-" + launch[7:]
        ):
            raise ValueError("worker intent identity conflict")
        cli = DockerCLI()
        remove_exact_container(cli=cli, container_name=name, launch_digest=launch)
        if cli.run(
            ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
        ).stdout.strip():
            raise ValueError("cleanup uncertain; reservation retained")
        result = {
            "schema": "carbon.autoresearch.worker-reconciliation.v1",
            "operation": path.parent.name,
            "state": "FAILED_INFRA",
            "cleanup_observed": True,
            "accounting": "full original reservation retained as conservative consumption",
            "scientific_outcome": "UNRESOLVED",
            "retry_dispatched": False,
        }
        ledger.finish(
            identity,
            owner=owner,
            state="FAILED_INFRA",
            actual=op["reservation"],
            result=result,
        )
        return result
