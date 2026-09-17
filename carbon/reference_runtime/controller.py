"""Trusted controller for one C-04 public qualification-candidate reference run."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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
    OUTPUT_MEMBERS,
    PRODUCTIVE_DEADLINE_SECONDS,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
)
from carbon.reconstruction.worker.protocol import (
    decode_output_stream,
    snapshot_output,
)
from carbon.reference_runtime.model import BurgersReferenceRequest
from carbon.reference_runtime.protocol import (
    ValidatedReferenceResult,
    stage_reference_request,
    validate_reference_snapshot_bounded,
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _unique_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate journal field")
        result[key] = value
    return result


def _snapshot_digest(path: Path) -> str:
    """Recompute the immutable snapshot identity under the exported-byte cap."""

    if path.is_symlink() or not path.is_dir():
        raise WorkerFailure(WorkerCode.CONFLICT)
    digest = hashlib.sha256()
    total = 0
    count = 0
    try:
        for member in sorted(path.rglob("*")):
            if member.is_dir() and not member.is_symlink():
                continue
            info = member.lstat()
            if member.is_symlink() or not stat.S_ISREG(info.st_mode):
                raise WorkerFailure(WorkerCode.CONFLICT)
            count += 1
            total += info.st_size
            if count > OUTPUT_MEMBERS or total > OUTPUT_BYTES:
                raise WorkerFailure(WorkerCode.CONFLICT)
            member_digest = hashlib.sha256()
            with member.open("rb") as stream:
                remaining = info.st_size
                while remaining:
                    block = stream.read(min(1 << 20, remaining))
                    if not block:
                        raise WorkerFailure(WorkerCode.CONFLICT)
                    member_digest.update(block)
                    remaining -= len(block)
                if stream.read(1):
                    raise WorkerFailure(WorkerCode.CONFLICT)
            digest.update(member.relative_to(path).as_posix().encode("utf-8"))
            digest.update(member_digest.digest())
    except (OSError, ValueError):
        raise WorkerFailure(WorkerCode.CONFLICT) from None
    if count == 0:
        raise WorkerFailure(WorkerCode.CONFLICT)
    return "sha256:" + digest.hexdigest()


@dataclass(frozen=True, slots=True)
class IsolatedReferenceResult:
    result: ValidatedReferenceResult
    launch_digest: str
    image_id: str
    controls_digest: str
    snapshot_digest: str
    snapshot_path: Path
    timings: dict[str, float]
    controls: dict[str, object]
    resources: dict[str, object]


class IsolatedBurgersReferenceController:
    """Run a fixed reference role under the exact accepted C-03 envelope."""

    def __init__(
        self,
        *,
        state_root: Path,
        image: WorkerImageIdentity,
        worker_profile: DevelopmentWorkerProfile,
        cli: DockerCLI | None = None,
    ) -> None:
        if (
            not state_root.is_absolute()
            or state_root.is_symlink()
            or type(image) is not WorkerImageIdentity
            or type(worker_profile) is not DevelopmentWorkerProfile
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        self.state_root = state_root
        self.image = image
        self.worker_profile = worker_profile
        self.cli = cli or DockerCLI()
        for name in ("staging", "outputs", "snapshots", "launches", "quarantine"):
            path = state_root / name
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o700)

    def _remove_stage(self, stage: Path) -> None:
        """Remove only this controller's immutable, flat request staging directory."""

        if stage.parent != self.state_root / "staging" or stage.is_symlink():
            raise WorkerFailure(WorkerCode.CLEANUP)
        if not stage.exists():
            return
        try:
            # Staging is immutable while mounted; directory write permission is
            # required to unlink its request after the exact worker is removed.
            stage.chmod(0o700)
            shutil.rmtree(stage)
        except OSError:
            raise WorkerFailure(WorkerCode.CLEANUP) from None

    def _journal(self, launch_digest: str, payload: dict[str, object]) -> None:
        path = self.state_root / "launches" / (launch_digest[7:] + ".json")
        temporary = path.with_suffix(".tmp")
        body = _canonical(payload) + b"\n"
        with temporary.open("wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)

    def _load_journal(self, launch_digest: str) -> dict[str, object] | None:
        path = self.state_root / "launches" / (launch_digest[7:] + ".json")
        if not path.exists():
            return None
        try:
            if path.is_symlink() or path.stat().st_size > CONTROL_BYTES:
                raise WorkerFailure(WorkerCode.CONFLICT)
            with path.open("rb") as stream:
                payload = stream.read(CONTROL_BYTES + 1)
            if len(payload) > CONTROL_BYTES:
                raise WorkerFailure(WorkerCode.CONFLICT)
            value = json.loads(
                payload,
                object_pairs_hook=_unique_pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            )
        except (OSError, ValueError, json.JSONDecodeError):
            raise WorkerFailure(WorkerCode.CONFLICT) from None
        if type(value) is not dict:
            raise WorkerFailure(WorkerCode.CONFLICT)
        return value

    @staticmethod
    def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
        if cancelled is None:
            return
        value = cancelled()
        if type(value) is not bool:
            raise WorkerFailure(WorkerCode.INVALID)
        if value:
            raise WorkerFailure(WorkerCode.CANCELLED)

    def _wait_file(
        self,
        container_name: str,
        path: str,
        deadline: float,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        while time.monotonic() < deadline:
            self._check_cancelled(cancelled)
            remaining = deadline - time.monotonic()
            status = self.cli.run(
                ["exec", container_name, "/usr/bin/test", "-f", path],
                timeout=max(0.1, min(5.0, remaining)),
                accepted=(0, 1),
            )
            if status.returncode == 0:
                self._check_cancelled(cancelled)
                return
            state = self.cli.json(
                ["inspect", container_name, "--format", "{{json .State}}"],
                timeout=max(0.1, min(5.0, deadline - time.monotonic())),
            )
            if type(state) is not dict or state.get("Running") is not True:
                raise WorkerFailure(WorkerCode.RUNTIME)
            time.sleep(0.1)
        raise WorkerFailure(WorkerCode.DEADLINE)

    def execute(
        self,
        request: BurgersReferenceRequest,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> IsolatedReferenceResult:
        if type(request) is not BurgersReferenceRequest:
            raise WorkerFailure(WorkerCode.INVALID)
        if cancelled is not None and not callable(cancelled):
            raise WorkerFailure(WorkerCode.INVALID)
        self._check_cancelled(cancelled)
        started_unix = float(time.time())
        started_mono = float(time.monotonic())
        deadline_unix = started_unix + PRODUCTIVE_DEADLINE_SECONDS
        deadline_mono = started_mono + PRODUCTIVE_DEADLINE_SECONDS
        stage_started = time.monotonic()
        stage, stage_digest = stage_reference_request(
            self.state_root / "staging", request
        )
        stage_seconds = time.monotonic() - stage_started
        launch_digest = (
            "sha256:"
            + hashlib.sha256(
                _canonical(
                    {
                        "image": self.image.image_id,
                        "policy": self.worker_profile.digest,
                        "request": request.request_digest,
                        "stage": stage_digest,
                    }
                )
            ).hexdigest()
        )
        container_name = "carbon-c04-" + launch_digest[7:39]
        retained = self._load_journal(launch_digest)
        if retained is not None:
            if (
                retained.get("state") != "ASSOCIATED_DEVELOPMENT_ONLY"
                or retained.get("request_digest") != request.request_digest
                or retained.get("image_id") != self.image.image_id
                or retained.get("worker_profile_digest") != self.worker_profile.digest
                or type(retained.get("snapshot_digest")) is not str
                or type(retained.get("controls_digest")) is not str
                or "artifact_digest" not in retained
            ):
                self._remove_stage(stage)
                raise WorkerFailure(WorkerCode.CONFLICT)
            snapshot = self.state_root / "snapshots" / launch_digest[7:]
            result = validate_reference_snapshot_bounded(snapshot, stage)
            if (
                _snapshot_digest(snapshot) != retained["snapshot_digest"]
                or result.artifact_digest != retained["artifact_digest"]
            ):
                self._remove_stage(stage)
                raise WorkerFailure(WorkerCode.CONFLICT)
            self._remove_stage(stage)
            return IsolatedReferenceResult(
                result,
                launch_digest,
                self.image.image_id,
                str(retained["controls_digest"]),
                str(retained["snapshot_digest"]),
                snapshot,
                {"replay": 0.0, "total": float(time.monotonic() - started_mono)},
                {"retained_exact_replay": True},
                (
                    retained.get("resource_observation")
                    if type(retained.get("resource_observation")) is dict
                    else {"status": "UNAVAILABLE_FOR_HISTORICAL_REPLAY"}
                ),
            )
        lock_path = self.state_root / "launches" / (launch_digest[7:] + ".lock")
        try:
            descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
            os.close(descriptor)
        except OSError:
            self._remove_stage(stage)
            raise WorkerFailure(WorkerCode.CONFLICT) from None
        journal = {
            "schema": "carbon.c04.reference-launch.v1",
            "state": "INTENT_RECORDED",
            "request_digest": request.request_digest,
            "stage_digest": stage_digest,
            "launch_digest": launch_digest,
            "image_id": self.image.image_id,
            "worker_profile_digest": self.worker_profile.digest,
            "container_name": container_name,
            "launch_started_unix": started_unix,
            "productive_deadline_unix": deadline_unix,
            "replacement_authority": "NONE",
            "protected_or_score_eligible": False,
        }
        self._journal(launch_digest, journal)
        checked = doctor(
            image_id=self.image.image_id, image_identity=self.image, cli=self.cli
        )
        if not checked.eligible or checked.cpuset is None:
            journal["state"] = "FAILED_INFRA"
            journal["terminal_code"] = checked.code
            self._journal(launch_digest, journal)
            self._remove_stage(stage)
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        container_created = False
        try:
            self._check_cancelled(cancelled)
            create_started = time.monotonic()
            try:
                created = self.cli.run(
                    create_arguments(
                        container_name=container_name,
                        image_id=self.image.image_id,
                        input_directory=stage,
                        cpuset=checked.cpuset,
                        launch_digest=launch_digest,
                        worker_profile=self.worker_profile,
                    ),
                    timeout=30,
                )
                container_id = created.stdout.decode("ascii", "strict").strip()
            except (WorkerFailure, UnicodeError):
                observed = self.cli.json(
                    ["inspect", container_name, "--format", "{{json .}}"]
                )
                if (
                    type(observed) is not dict
                    or observed.get("Config", {})
                    .get("Labels", {})
                    .get("org.opencontainers.image.carbon.c03.launch")
                    != launch_digest
                ):
                    raise WorkerFailure(WorkerCode.CONFLICT)
                container_id = observed["Id"]
            container_created = True
            create_seconds = time.monotonic() - create_started
            journal.update({"state": "CREATED", "container_id": container_id})
            self._journal(launch_digest, journal)
            spawn_watchdog(
                container_name=container_name,
                launch_digest=launch_digest,
                deadline_unix=deadline_unix,
            )
            self._check_cancelled(cancelled)
            self.cli.run(["start", container_name], timeout=20)
            self._wait_file(
                container_name, "/scratch/control-ready", deadline_mono, cancelled
            )
            controls_digest, controls = inspect_effective_controls(
                cli=self.cli,
                container_name=container_name,
                image_id=self.image.image_id,
                input_directory=stage,
                cpuset=checked.cpuset,
                launch_digest=launch_digest,
                worker_profile=self.worker_profile,
            )
            journal.update(
                {"state": "CONTROLS_VERIFIED", "controls_digest": controls_digest}
            )
            self._journal(launch_digest, journal)
            self._check_cancelled(cancelled)
            self.cli.run(
                [
                    "exec",
                    "--user",
                    "65532:65532",
                    container_name,
                    "/usr/bin/touch",
                    "/scratch/authorized",
                ],
                timeout=10,
            )
            numerical_started = time.monotonic()
            self._wait_file(container_name, "/scratch/ready", deadline_mono, cancelled)
            numerical_seconds = time.monotonic() - numerical_started
            export_started = time.monotonic()
            remaining = deadline_mono - time.monotonic()
            if remaining <= 0:
                raise WorkerFailure(WorkerCode.DEADLINE)
            raw_parent = Path(
                tempfile.mkdtemp(prefix=".c04-raw-", dir=self.state_root / "outputs")
            )
            raw = raw_parent / "output"
            framed = raw_parent / "output.stream"
            self.cli.stream_to_file(
                [
                    "exec",
                    "--user",
                    "65532:65532",
                    container_name,
                    "/opt/carbon-worker/bin/python",
                    "-I",
                    "-m",
                    "carbon.reconstruction.worker.exporter",
                ],
                framed,
                maximum=OUTPUT_BYTES + 2 * CONTROL_BYTES,
                timeout=min(30.0, remaining),
            )
            decode_output_stream(framed, raw)
            framed.unlink()
            snapshot, snapshot_digest = snapshot_output(
                raw,
                self.state_root / "snapshots",
                destination_name=launch_digest[7:],
            )
            shutil.rmtree(raw_parent, ignore_errors=True)
            export_seconds = time.monotonic() - export_started
            if time.monotonic() > deadline_mono:
                raise WorkerFailure(WorkerCode.DEADLINE)
            resources = observe_effective_resources(
                cli=self.cli, container_name=container_name
            )
            self._check_cancelled(cancelled)
            files = tuple(item for item in snapshot.rglob("*") if item.is_file())
            resources["output_snapshot"] = {
                "observed_bytes": sum(item.stat().st_size for item in files),
                "observed_members": len(files),
                "bounded_bytes": OUTPUT_BYTES,
            }
            journal.update(
                {
                    "state": "OUTPUT_SNAPSHOTTED",
                    "snapshot_digest": snapshot_digest,
                    "resource_observation": resources,
                }
            )
            self._journal(launch_digest, journal)
            cleanup_started = time.monotonic()
            remove_exact_container(
                cli=self.cli,
                container_name=container_name,
                launch_digest=launch_digest,
            )
            container_created = False
            cleanup_seconds = time.monotonic() - cleanup_started
            journal["state"] = "TERMINATED"
            self._journal(launch_digest, journal)
            self._check_cancelled(cancelled)
            validation_started = time.monotonic()
            result = validate_reference_snapshot_bounded(snapshot, stage)
            validation_seconds = time.monotonic() - validation_started
            self._check_cancelled(cancelled)
            self._remove_stage(stage)
            journal["state"] = "ASSOCIATED_DEVELOPMENT_ONLY"
            journal["artifact_digest"] = result.artifact_digest
            self._journal(launch_digest, journal)
            return IsolatedReferenceResult(
                result,
                launch_digest,
                self.image.image_id,
                controls_digest,
                snapshot_digest,
                snapshot,
                {
                    "staging": float(stage_seconds),
                    "create": float(create_seconds),
                    "numerical": float(numerical_seconds),
                    "export": float(export_seconds),
                    "cleanup": float(cleanup_seconds),
                    "validation": float(validation_seconds),
                    "total": float(time.monotonic() - started_mono),
                },
                controls,
                resources,
            )
        except BaseException as error:
            terminal = (
                error.code if type(error) is WorkerFailure else WorkerCode.RUNTIME
            )
            journal.update(
                {
                    "state": "FAILED_OR_RECONCILIATION_REQUIRED",
                    "terminal_code": terminal.value,
                    "elapsed_seconds": float(time.monotonic() - started_mono),
                    "observed_consumption": "PARTIAL_OR_UNKNOWN",
                }
            )
            if container_created:
                try:
                    remove_exact_container(
                        cli=self.cli,
                        container_name=container_name,
                        launch_digest=launch_digest,
                    )
                    journal["cleanup"] = "CONFIRMED"
                except WorkerFailure:
                    journal["cleanup"] = "UNCERTAIN_QUARANTINED"
                    (self.state_root / "quarantine" / launch_digest[7:]).touch(
                        mode=0o400, exist_ok=True
                    )
                    self._journal(launch_digest, journal)
                    raise WorkerFailure(WorkerCode.QUARANTINED) from None
            self._journal(launch_digest, journal)
            self._remove_stage(stage)
            raise


__all__ = ["IsolatedBurgersReferenceController", "IsolatedReferenceResult"]
