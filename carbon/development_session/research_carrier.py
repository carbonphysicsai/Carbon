"""Isolated public-research carrier reusing C-03 mechanisms and output parser.

No API accepts host mounts, Docker options, credentials or protected inputs.
Research script output is always untrusted/self-reported. Trusted practice uses
a separate invocation with a controller-selected fixed program and staged data.
"""

from __future__ import annotations

import json
import math
import re
import time
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import partial

from carbon.reconstruction.worker import liveness_reaper
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
    WorkerCode,
    WorkerFailure,
)
from carbon.reconstruction.worker.protocol import decode_output_stream

from .data import write_once
from .profile import canonical, digest
from .research_workspace import ResearchWorkspace

PRECHARGED_TRIAL = ContextVar("carbon_precharged_trial", default=None)

ACTIVE_TASK = ContextVar("carbon_public_research_task", default=None)

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


def run_script(
    ledger, *, owner, identity, source, files, image, seconds=600, accelerator=None
):
    """Run miner Python only on explicitly staged public/own file bytes.

    `accelerator=MINER_GPU` runs it on the host's installed GPU, in the
    campaign's pinned GPU worker image (RSURF-D20, owner, 2026-10-03): the
    same miner lane and isolation with the device attached. Omitted, it runs
    in the CPU analysis image exactly as before.
    """
    from .research_image import ResearchImageIdentity

    if accelerator is None:
        if type(image) is not ResearchImageIdentity:
            raise ValueError("miner scripts require the separate analysis image")
    else:
        from .gpu_practice import is_gpu_image

        if accelerator != MINER_GPU or not is_gpu_image(image):
            raise ValueError("a GPU code cell runs the campaign's pinned GPU worker")
    if type(source) is not str or not source:
        raise ValueError("research source required")
    return _run(
        ledger,
        owner=owner,
        identity=identity,
        source=source,
        files=files,
        image=image,
        seconds=seconds,
        provenance="MINER_SELF_REPORTED",
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        miner_authored=True,
        **({} if accelerator is None else {"accelerator": accelerator}),
    )


class MinerProgramFailure(Exception):
    """The miner's own program failed, observed - not an infrastructure failure.

    Raised only where the evidence was observed: the miner's own wall allowance
    elapsed, the daemon reported the container OOM-killed, the miner's program
    exited nonzero inside a still-running container, or the miner's output was
    refused for its own content. The operation is already settled as
    FAILED_MINER with the full reservation retained and cleanup observed, so
    there is nothing to reconcile. Daemon, CLI and host failures never take this
    type; they stay infrastructure failures.
    """

    def __init__(self, result):
        if (
            type(result) is not dict
            or result.get("schema") != MINER_FAILURE_SCHEMA
            or result.get("failure_code")
            not in {code.value for code in MINER_FAILURE_CODES}
        ):
            raise TypeError("typed miner program failure result required")
        super().__init__(result["observation"])
        self.result = result
        self.code = WorkerCode(result["failure_code"])


MINER_FAILURE_SCHEMA = "carbon.autoresearch.miner-program-failure.v1"
# Existing worker codes, reused: the miner's allowance elapsed (DEADLINE), their
# program failed (RUNTIME: nonzero exit or OOM kill), their output was refused
# for its own content (OUTPUT).
MINER_FAILURE_CODES = frozenset(
    {WorkerCode.DEADLINE, WorkerCode.RUNTIME, WorkerCode.OUTPUT}
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


def _cancel_path(ledger, owner, identity):
    return ledger.root / (
        "cancel-" + digest(canonical([owner, identity]))[7:] + ".json"
    )


def request_cancel(ledger, *, owner, identity):
    """Trusted task provider only; a flag grants no arbitrary process handle."""
    write_once(
        _cancel_path(ledger, owner, identity),
        canonical({"owner": owner, "identity": identity}),
    )


def _check_cancel(ledger, owner, identity):
    if _cancel_path(ledger, owner, identity).exists():
        raise ValueError("research operation cancelled")


def _run(ledger, **kwargs):
    import threading

    owner, identity = kwargs["owner"], kwargs["identity"]
    with _numerical_lease(ledger):
        _check_cancel(ledger, owner, identity)
        stop = threading.Event()
        errors = []

        def watch():
            # Finite worker-lifetime helper. It never dispatches numerical work,
            # reads another owner's intent, or accepts a caller container name.
            while not stop.wait(0.1):
                if not _cancel_path(ledger, owner, identity).exists():
                    continue
                try:
                    _cancel_active_intent(ledger, owner=owner, identity=identity)
                except Exception:  # noqa: BLE001
                    errors.append("cancellation cleanup uncertain")
                    return

        def settle():
            # Called immediately before the ledger records a terminal state.
            # The watcher is stopped and its errors read first, so the ledger
            # can never say an operation finished while the task then fails on
            # an uncertain cancellation: raising here leaves it RESERVED.
            stop.set()
            watcher.join(timeout=45)
            if watcher.is_alive():
                raise ValueError("cancellation supervisor did not stop")
            if errors:
                raise ValueError(errors[0])

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            result = _run_locked(ledger, before_finish=settle, **kwargs)
            if errors:
                raise ValueError(errors[0])
            return result
        finally:
            stop.set()
            watcher.join(timeout=45)
            if watcher.is_alive():
                raise ValueError("cancellation supervisor did not stop")


def _cancel_active_intent(ledger, *, owner, identity):
    cli = DockerCLI()
    for path in ledger.root.glob("operation-*/intent.json"):
        if path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError("invalid cancellation intent")
        intent = json.loads(path.read_bytes())
        if (intent.get("owner"), intent.get("identity")) != (owner, identity):
            continue
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
            raise ValueError("cancellation intent conflict")
        remove_exact_container(cli=cli, container_name=name, launch_digest=launch)


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
    phase="research",
    program_name="program.py",
    bootstrap=BOOTSTRAP,
    execution_contract=None,
    output_validator=None,
    miner_authored=False,
    before_finish=None,
    accelerator=None,
):
    before_finish = before_finish or (lambda: None)
    # The miner's own research has no Carbon limits (owner direction): any
    # positive wall allowance, or none at all. Carbon's own work in this carrier
    # keeps its bounded allowance.
    miner_lane = provenance == "MINER_SELF_REPORTED"
    if miner_lane:
        if seconds is not None and (type(seconds) is not int or seconds < 1):
            raise ValueError("a positive wall allowance, or none")
        if seconds is None and _has_time_budget(ledger):
            # The miner's own budget still binds where they set one: a run
            # with no allowance could not be reserved against it.
            raise ValueError(
                "you set a compute-time budget; give this run a wall allowance"
            )
    elif type(seconds) is not int or not 40 <= seconds <= 600:
        raise ValueError("bounded worker wall allowance required")
    if type(files) is not dict or "program.py" in files or program_name in files:
        raise ValueError("closed stage required")
    for name, body in files.items():
        ResearchWorkspace.name(name)
        if type(body) is not bytes:
            raise ValueError("stage accepts bytes, never paths")
    request = {
        "source": digest(source.encode()),
        "files": {n: digest(b) for n, b in files.items()},
        "image": image.image_id,
        "seconds": seconds,
        "provenance": provenance,
    }
    if execution_contract is not None:
        # Prospective language routes bind their complete reviewed environment.
        # Leaving this absent preserves historical Python operation identities.
        request["execution_contract"] = execution_contract
    device = None
    if accelerator is not None:
        # The miner's own GPU: Carbon's fixed practice program (C-MLP-03 slice
        # 3), or the miner's own code cell (RSURF-D20). The device is the
        # host's installed record, bound to this request, so a replaced or
        # withdrawn record is a different request. Absent for every CPU run,
        # so their identities are unchanged.
        if accelerator != MINER_GPU or (miner_lane and not miner_authored):
            raise ValueError("unsupported accelerator request")
        device = _gpu_device()
        request["accelerator"] = {
            "kind": MINER_GPU,
            "profile": _gpu_profile_id(),
            "device": device.digest,
        }
    launch = digest(
        canonical({"owner": owner, "identity": identity, "request": request})
    )
    operation = ledger.root / ("operation-" + launch[7:])
    if miner_lane:
        # The miner's disk; the only bound is their own retained_bytes budget.
        reservation_bytes = sum(map(len, files.values())) + 65536
    else:
        storage = sum(p.stat().st_size for p in ledger.root.rglob("*") if p.is_file())
        # Account stored input, provisional stream and decoded bounded output.
        reservation_bytes = (
            sum(map(len, files.values())) + 2 * OUTPUT_BYTES + 2 * CONTROL_BYTES + 65536
        )
        if storage + reservation_bytes > 10 * 1024**3:
            raise ValueError("campaign retained storage ceiling")
    resources = {
        "numerical_milliseconds": (seconds or 0) * 1000,
        "retained_bytes": reservation_bytes,
        **extra_resources,
    }
    admission = ledger.reserve(
        identity, owner=owner, phase=phase, request=request, resources=resources
    )
    if not admission["dispatch"]:
        if admission["state"] == "RESERVED":
            raise ValueError("research operation ambiguous; reconcile, never duplicate")
        if admission["state"] == "FAILED_MINER":
            # A replay reports the same typed outcome, never a success.
            raise MinerProgramFailure(admission["result"])
        return admission["result"]
    started = time.monotonic()
    started_unix = time.time()
    name = "carbon-d4-" + launch[7:31]
    # The durable intent is written first, before staging, image verification
    # or the host doctor: an interruption anywhere after the reservation then
    # leaves an operation reconcile_worker can settle, rather than a RESERVED
    # row with no record of what might have been launched.
    operation.mkdir()
    # What removes a miner-lane container if its owner cannot: the deadline
    # watchdog when the miner set a time budget, otherwise a reaper that
    # watches this controller process and removes the container only once it
    # is gone. An unbounded run has no time limit, but it is never unguarded.
    guard = _miner_guard(seconds) if miner_lane else None
    write_once(
        operation / "intent.json",
        canonical(
            {
                "launch": launch,
                "container": name,
                "request": request,
                "owner": owner,
                "identity": identity,
                "deadline_unix": (
                    None if seconds is None else started_unix + seconds - 30
                ),
                **({} if guard is None else {"reaper": guard}),
            }
        ),
    )
    stage = operation / "input"
    cli = DockerCLI()
    try:
        stage.mkdir(mode=0o755)
        stage.chmod(0o755)
        for filename, body in {**files, program_name: source.encode()}.items():
            path = stage / filename
            write_once(path, body)
            path.chmod(0o444)
        if provenance == "MINER_SELF_REPORTED":
            from .julia_analysis import JuliaResearchImageIdentity, verify_julia_image
            from .research_image import verify_image

            if device is not None and type(image) is JuliaResearchImageIdentity:
                # A Julia GPU code cell (JULIA-GPU-01): the composed image and
                # its depot, checked as every Julia run is, and the host's GPU
                # readiness without the Python GPU worker's lock.
                verify_julia_image(image, cli)
                checked = doctor(image_id=image.image_id, cli=cli)
                _check_gpu_host(cli, None, device)
            elif device is not None:
                # A GPU code cell: the pinned GPU worker and the host's GPU
                # readiness, checked as GPU practice checks them.
                checked = doctor(image_id=image.image_id, image_identity=image, cli=cli)
                _check_gpu_host(cli, image, device)
            elif type(image) is JuliaResearchImageIdentity:
                verify_julia_image(image, cli)
                checked = doctor(image_id=image.image_id, cli=cli)
            else:
                verify_image(image, cli)
                checked = doctor(image_id=image.image_id, cli=cli)
        else:
            checked = doctor(image_id=image.image_id, image_identity=image, cli=cli)
            if device is not None:
                _check_gpu_host(cli, image, device)
        if not checked.eligible:
            # No attempt is automatically retried and its reservation remains
            # visible.
            raise ValueError("research host ineligible")
    except Exception:
        _settle_nothing_created(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            before_finish=before_finish,
        )
        raise
    if miner_lane:
        return _run_miner_lane(
            ledger,
            guard=guard,
            owner=owner,
            identity=identity,
            operation=operation,
            stage=stage,
            name=name,
            cli=cli,
            image=image,
            launch=launch,
            request=request,
            seconds=seconds,
            started=started,
            started_unix=started_unix,
            bootstrap=bootstrap,
            output_validator=output_validator,
            provenance=provenance,
            resources=resources,
            miner_authored=miner_authored,
            before_finish=before_finish,
            device=device,
        )
    worker = _worker_profile(device)
    create_attempted = False
    output = operation / "export.stream"
    lease = ExitStack()
    try:
        if device is not None:
            from carbon.reconstruction.worker.accelerator_runtime import (
                miner_device_lease,
                reject_existing_device_containers,
            )

            # This host's own concurrent runs on the device, and Carbon's own
            # retained work on it; nothing about anyone else's use of the GPU.
            lease.enter_context(miner_device_lease(device.device_uuid))
            reject_existing_device_containers(cli=cli)
        _check_cancel(ledger, owner, identity)
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
        _check_cancel(ledger, owner, identity)
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
            ["exec", name, "/opt/carbon-worker/bin/python", "-I", "-c", bootstrap],
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
        try:
            if create_attempted:
                # C-03 checks the exact launch label, removes the entire
                # container, and confirms absence before any output becomes an
                # associated result.
                remove_exact_container(
                    cli=cli, container_name=name, launch_digest=launch
                )
                # Require a successful daemon query too: an inspect transport
                # error alone is not evidence that the container and descendants
                # are gone.
                remaining = cli.run(
                    ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
                )
                if remaining.stdout.strip():
                    raise ValueError(
                        "research cleanup uncertain; capacity stays reserved"
                    )
        finally:
            lease.close()
    _check_cancel(ledger, owner, identity)
    snapshot = operation / "snapshot"
    decode_output_stream(output, snapshot)
    if output_validator is not None:
        output_validator(snapshot)
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
    before_finish()
    ledger.finish(
        identity, owner=owner, state="SUCCEEDED", actual=actual, result=result
    )
    return result


#: The one accelerator a carrier run may ask for: the miner's own GPU, for
#: Carbon's fixed practice program or, in the miner lane's isolated
#: container, the miner's own code cell (RSURF-D20).
MINER_GPU = "MINER_OWN_GPU"


def _gpu_profile_id():
    from carbon.reconstruction.accelerators import GPU_PROFILE

    return GPU_PROFILE.profile_id


def _gpu_device():
    """The installed host device record; fails closed when absent."""
    from carbon.reconstruction.worker.accelerator_runtime import host_device

    try:
        return host_device()
    except WorkerFailure:
        raise ValueError(
            "no GPU device record is installed on this host; run setup's GPU "
            "check (or scripts/dev/carbon_accelerator.py prepare)"
        ) from None


def _check_gpu_host(cli, image, device):
    """The miner-lane readiness the GPU controller requires, and no more.

    `image` is the pinned Python GPU worker, checked by its lock and labels
    with the NVIDIA runtime. None for a Julia GPU code cell: its image is the
    composed Julia image (verified on its own), which carries no Python GPU
    worker lock, so only the NVIDIA container runtime is checked here.
    """
    from carbon.reconstruction.onboarding import doctor_report, miner_lane_blockers
    from carbon.reconstruction.worker.accelerator_runtime import (
        HOST_ROOT,
        verify_image_and_toolkit,
    )

    if image is None:
        info = cli.json(["info", "--format", "{{json .}}"])
        if type(info) is not dict or "nvidia" not in (info.get("Runtimes") or {}):
            raise ValueError("the NVIDIA container runtime is not available")
    else:
        verify_image_and_toolkit(cli=cli, image=image)
    if miner_lane_blockers(doctor_report(root=HOST_ROOT, cli=cli, image=image)):
        raise ValueError("GPU host not ready")
    if _gpu_device().digest != device.digest:
        raise ValueError("installed host device record changed before dispatch")


def _worker_profile(device):
    """The carrier's worker profile: CPU, or the miner lane on `device`."""
    policy = digest(b"carbon.autoresearch.public-research.v1")
    resources = digest(b"2cpu-4gib-noswap-600seconds")
    if device is None:
        return DevelopmentWorkerProfile(policy, resources)
    from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
    from carbon.reconstruction.worker.model import (
        MINER_HOST_AUTHORITY,
        registered_run_controls,
    )

    return DevelopmentWorkerProfile(
        policy,
        resources,
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        device.digest,
        AcceleratorRole.MINER_RESEARCH.value,
        MINER_HOST_AUTHORITY,
        None,
        device.device_uuid,
        registered_run_controls(),
    )


def _miner_guard(seconds):
    """The deadline watchdog for a timed run; otherwise the controller-liveness
    reaper, so an unbounded run is never unguarded."""
    if seconds is not None:
        return {"kind": "DEADLINE"}
    return liveness_reaper.controller_guard()


def _settle_nothing_created(
    ledger, *, owner, identity, operation, resources, before_finish
):
    """Settle an operation refused before any container command.

    Nothing was created: no container command has been issued. That is a
    fact of this process, not an inference from absence, so settle now as
    infrastructure failure keeping the full reservation - no refund.
    """
    before_finish()
    ledger.finish(
        identity,
        owner=owner,
        state="FAILED_INFRA",
        actual=resources,
        result={
            "schema": "carbon.autoresearch.worker-reconciliation.v1",
            "operation": operation.name,
            "state": "FAILED_INFRA",
            "worker_created": False,
            "cleanup_observed": True,
            "accounting": "full original reservation retained as conservative consumption",
            "scientific_outcome": "UNRESOLVED",
            "retry_dispatched": False,
        },
    )


def _run_miner_lane(
    ledger,
    *,
    guard,
    owner,
    identity,
    operation,
    stage,
    name,
    cli,
    image,
    launch,
    request,
    seconds,
    started,
    started_unix,
    bootstrap,
    output_validator,
    provenance,
    resources,
    miner_authored,
    before_finish,
    device=None,
):
    """Run the miner's own research: isolated, no Carbon limits.

    `device` is the host's installed GPU record for a GPU code cell
    (RSURF-D20): the same container with that one device attached, under the
    same device lease as GPU practice. None for every CPU run.

    Same lifecycle as Carbon's lane - durable intent, exact-label removal,
    cancellation, a digest of every output - in the miner lane's container,
    which has no size or time limit, writing to scratch on the miner's own disk.

    Where the miner's own program is observed to be the cause of a failure
    (``miner_authored`` only), the operation settles FAILED_MINER with cleanup
    observed and the full reservation kept, and ``MinerProgramFailure`` is
    raised. Every other failure keeps its infrastructure meaning.
    """
    from .miner_container import (
        MinerOutputRefused,
        MinerResearchLaunch,
        collect_outputs,
        create_arguments,
        inspect_isolation,
        prepare_scratch,
    )

    try:
        scratch = prepare_scratch(operation / "scratch")
        run = MinerResearchLaunch(
            name,
            image.image_id,
            launch,
            stage,
            scratch,
            **({} if device is None else {"gpu_device": device.device_uuid}),
        )
    except Exception:
        # Refused before any container command: settle now, as the prechecks
        # do, rather than leave the reservation for reconciliation.
        _settle_nothing_created(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            before_finish=before_finish,
        )
        raise
    # No deadline unless the miner asked for one; a very long transport bound
    # stands in for "none" where the CLI needs a number.
    unbounded = 10 * 365 * 24 * 3600
    create_attempted = False
    failure = None
    lease = ExitStack()
    slot = ExitStack()
    try:
        if device is not None:
            from carbon.reconstruction.worker.accelerator_runtime import (
                miner_device_lease,
                reject_existing_device_containers,
                shared_host_lease,
            )

            # The same lease GPU practice takes: one run on the device at a
            # time, on this host.
            lease.enter_context(miner_device_lease(device.device_uuid))
            # And the shared Carbon slot across check-then-create. Validator
            # GPU work holds that slot for its whole run and checks for
            # labelled device containers under it, so neither side can pass
            # its check while the other is between check and create. Once
            # created, this run's device label is what the other side sees.
            slot.enter_context(shared_host_lease())
            reject_existing_device_containers(cli=cli)
        _check_cancel(ledger, owner, identity)
        create_attempted = True
        try:
            if device is not None:
                from carbon.reconstruction.worker.accelerator_runtime import (
                    mark_device_allocation,
                )
                from carbon.reconstruction.worker.model import MINER_HOST_AUTHORITY

                # Ownership is persisted before create, as GPU practice does,
                # under the miner lane's own task-owned authority. Removal of
                # a device-labelled container completes the allocation that
                # created it; without this record it takes the strict path,
                # which this run never had the evidence for, and refuses.
                mark_device_allocation(
                    container_name=name,
                    launch_digest=launch,
                    authority=MINER_HOST_AUTHORITY,
                )
            cli.run(create_arguments(run), timeout=30)
        finally:
            slot.close()
        _check_cancel(ledger, owner, identity)
        if seconds is not None:
            spawn_watchdog(
                container_name=name,
                launch_digest=launch,
                deadline_unix=float(started_unix + seconds),
            )
        else:
            liveness_reaper.spawn_liveness_reaper(
                container_name=name, launch_digest=launch, guard=guard
            )
        cli.run(["start", name], timeout=20)
        isolation = inspect_isolation(cli, run)
        try:
            # The last 64 KiB of stdout and of stderr are kept, whatever the
            # outcome (RSURF-D21). A Docker double supplies its own.
            keep = getattr(cli, "stream_kept", None) or partial(stream_kept, cli)
            keep(
                ["exec", name, "/opt/carbon-worker/bin/python", "-I", "-c", bootstrap],
                operation,
                timeout=unbounded if seconds is None else max(1, seconds),
            )
        except WorkerFailure as error:
            # Classified while the container still exists to be inspected. A
            # requested cancellation is never the miner's failure.
            if not miner_authored or _cancel_path(ledger, owner, identity).exists():
                raise
            failure = _observed_miner_failure(cli, name, error, seconds, started)
            if failure is None:
                raise
        if failure is None:
            # The worker writes as its fixed non-root uid, so a directory the
            # miner's code creates with default modes is unreadable to the host
            # that collects it. The worker owns every output, so it opens them
            # to reading before the container goes; links are refused at
            # collection, and chmod -R does not follow them.
            cli.run(
                ["exec", name, "chmod", "-R", "a+rX", "/scratch/output"], timeout=120
            )
        write_once(operation / "resources.json", canonical({"isolation": isolation}))
    finally:
        try:
            if create_attempted:
                remove_exact_container(
                    cli=cli, container_name=name, launch_digest=launch
                )
                remaining = cli.run(
                    ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
                )
                if remaining.stdout.strip():
                    raise ValueError(
                        "research cleanup uncertain; capacity stays reserved"
                    )
        finally:
            slot.close()
            lease.close()
    if failure is not None:
        _settle_miner_failure(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            started=started,
            failure=failure,
            before_finish=before_finish,
        )
    _check_cancel(ledger, owner, identity)
    snapshot = operation / "snapshot"
    try:
        collect_outputs(scratch, snapshot)
    except MinerOutputRefused:
        # A link, FIFO, socket or device in the output is the miner's own
        # doing. An unreadable tree is not typed this way: that can be the
        # host's, and stays an infrastructure failure.
        if not miner_authored:
            raise
        _settle_miner_failure(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            started=started,
            failure=(WorkerCode.OUTPUT, "OUTPUT_NOT_REGULAR_FILES"),
            before_finish=before_finish,
        )
    if output_validator is not None:
        try:
            output_validator(snapshot)
        except ValueError:
            # The declared validator refused the miner's own bytes (malformed,
            # non-finite, undeclared type). OSError and the like stay infra.
            if not miner_authored:
                raise
            _settle_miner_failure(
                ledger,
                owner=owner,
                identity=identity,
                operation=operation,
                resources=resources,
                started=started,
                failure=(WorkerCode.OUTPUT, "OUTPUT_REFUSED_BY_VALIDATOR"),
                before_finish=before_finish,
            )
    files = {
        p.relative_to(snapshot).as_posix(): _file_digest(p)
        for p in sorted(snapshot.rglob("*"))
        if p.is_file()
    }
    result = {
        "schema": "carbon.autoresearch.worker-result.v1",
        "provenance": provenance,
        "output_digest": digest(canonical(files)),
        "files": files,
        "operation": operation.name,
        "lane": "MINER_RESEARCH_UNLIMITED",
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
    before_finish()
    ledger.finish(
        identity, owner=owner, state="SUCCEEDED", actual=actual, result=result
    )
    return result


_DOCKER_OWN_EXITS = frozenset({125, 126, 127})

#: What a miner-lane run keeps of its stdout and of its stderr: the last
#: 64 KiB of each, for successful and failed runs alike (RSURF-D21, owner,
#: 2026-10-03: "Keep both, capped").
KEPT_BYTES = 64 * 1024
STDOUT_FILE, STDERR_FILE = "stdout.txt", "stderr.txt"


class _Tail:
    """The last `limit` bytes of a stream, in bounded memory."""

    def __init__(self, limit):
        self.limit, self.buffer = limit, bytearray()

    def add(self, block):
        self.buffer += block
        if len(self.buffer) > 2 * self.limit:
            del self.buffer[: -self.limit]

    def value(self):
        return bytes(self.buffer[-self.limit :])


def stream_kept(cli, arguments, operation, *, timeout):
    """Run one fixed Docker command for the miner lane, keeping the last
    `KEPT_BYTES` of its stdout and of its stderr in `operation`, whatever the
    outcome. A timeout or nonzero exit raises `WorkerFailure(RUNTIME)` with
    the diagnostic `DockerCLI.stream_to_file` gives, so a failure is
    classified exactly as before; a large stderr no longer fails a run.
    """
    import os
    import selectors
    import subprocess

    from carbon.reconstruction.worker.docker_runtime import _stop_process
    from carbon.reconstruction.worker.model import DIAGNOSTIC_BYTES

    if type(timeout) not in (int, float) or timeout <= 0:
        raise WorkerFailure(WorkerCode.INVALID)
    environment = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        if key in os.environ:
            environment[key] = os.environ[key]
    stdout, stderr = _Tail(KEPT_BYTES), _Tail(KEPT_BYTES)
    head = bytearray()
    process = None
    try:
        process = subprocess.Popen(
            [cli.executable, *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, stdout)
        selector.register(process.stderr, selectors.EVENT_READ, stderr)
        deadline = time.monotonic() + float(timeout)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkerFailure(
                    WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
                )
            for key, _ in selector.select(timeout=min(remaining, 0.25)):
                block = os.read(key.fd, 1 << 16)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                key.data.add(block)
                if key.data is stderr and len(head) < DIAGNOSTIC_BYTES:
                    head.extend(block[: DIAGNOSTIC_BYTES - len(head)])
        code = process.wait(timeout=1)
        if code != 0:
            raise WorkerFailure(
                WorkerCode.RUNTIME,
                private_diagnostic=(
                    f"exit={code}\nstderr:\n".encode("ascii") + bytes(head)
                )[:DIAGNOSTIC_BYTES],
            )
    except WorkerFailure:
        if process is not None:
            _stop_process(process)
        raise
    except (OSError, subprocess.SubprocessError):
        if process is not None:
            _stop_process(process)
        raise WorkerFailure(
            WorkerCode.RUNTIME, private_diagnostic=bytes(head)
        ) from None
    finally:
        for name, tail in ((STDOUT_FILE, stdout), (STDERR_FILE, stderr)):
            path = operation / name
            if not path.exists():
                write_once(path, tail.value())


def _observed_miner_failure(cli, name, error, seconds, started):
    """Name the miner's program as the cause only on observed evidence.

    Returns ``(WorkerCode, observation)`` or None. None keeps the failure an
    infrastructure failure: an ambiguous daemon or CLI error is never blamed on
    the miner.
    """
    if seconds is not None and time.monotonic() - started >= seconds:
        # The miner's own allowance elapsed; the watchdog or stream bound that
        # fired is the one they chose.
        return WorkerCode.DEADLINE, "OWN_ALLOWANCE_ELAPSED"
    try:
        state = cli.json(["inspect", name, "--format", "{{json .State}}"], timeout=10)
    except WorkerFailure:
        return None
    if type(state) is not dict:
        return None
    if state.get("OOMKilled") is True:
        return WorkerCode.RUNTIME, "OOM_KILLED"
    exited = re.match(rb"exit=(\d+)\n", error.private_diagnostic)
    if (
        exited is not None
        and state.get("Running") is True
        and int(exited.group(1)) not in _DOCKER_OWN_EXITS
        and int(exited.group(1)) != 0
        and b"Error response from daemon" not in error.private_diagnostic
    ):
        # docker exec returned the program's own status from a container that
        # is still running: the program ran and exited nonzero.
        return WorkerCode.RUNTIME, "NONZERO_EXIT"
    return None


def _settle_miner_failure(
    ledger, *, owner, identity, operation, resources, started, failure, before_finish
):
    """Settle an observed miner-caused failure and raise it, typed.

    The full reservation is kept, and anything measured beyond it is charged
    too: the metered dimensions record at least what the run used.
    """
    code, observation = failure
    result = {
        "schema": MINER_FAILURE_SCHEMA,
        "operation": operation.name,
        "state": "FAILED_MINER",
        "cause": "MINER_PROGRAM",
        "failure_code": code.value,
        "observation": observation,
        "cleanup_observed": True,
        "accounting": "full original reservation retained; no refund",
        "retry_dispatched": False,
        "scientific_qualification": False,
        "official_eligible": False,
    }
    elapsed = math.ceil((time.monotonic() - started) * 1000)
    retained = sum(p.stat().st_size for p in operation.rglob("*") if p.is_file())
    actual = {
        **resources,
        "numerical_milliseconds": max(resources["numerical_milliseconds"], elapsed),
        "retained_bytes": max(resources["retained_bytes"], retained),
    }
    before_finish()
    ledger.finish(
        identity, owner=owner, state="FAILED_MINER", actual=actual, result=result
    )
    raise MinerProgramFailure(result)


def record_output_tamper(ledger, *, owner, operation, name, expected, observed):
    """Leave a durable security_incident record, then refuse the output.

    A retained output whose digest no longer matches the one recorded when it
    was collected was changed after collection. Refusing it silently would
    leave no trace that anything happened; the record is written first, and if
    it cannot be written the refusal says so.
    """
    body = {
        "event": "RESEARCH_OUTPUT_DIGEST_MISMATCH",
        "operation": operation,
        "file": name[:256],
        "expected_digest": expected,
        "observed_digest": observed,
    }
    try:
        ledger.note(owner=owner, kind="security_incident", body=body)
    except Exception:  # noqa: BLE001
        raise ValueError(
            "research output changed; security incident record failed"
        ) from None
    raise ValueError("research output changed after collection")


def _has_time_budget(ledger):
    from .research_ledger import NO_BUDGET, _caps

    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    if row is None:
        return False
    return (
        _caps(json.loads(row[0])).get("numerical_milliseconds", NO_BUDGET)
        is not NO_BUDGET
    )


def _file_digest(path):
    import hashlib

    sha = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024**2):
            sha.update(chunk)
    return "sha256:" + sha.hexdigest()


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
        if op["state"] == "HELD":
            raise ValueError(
                "never-claimed sequence capacity requires sequence cleanup"
            )
        if op["state"] != "RESERVED":
            return op["result"]
        # Keyed on the durable intent, not the reserved milliseconds: the
        # miner's own run with no wall allowance reserves none and is still a
        # worker. An operation with no intent is refused below, never skipped.
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
