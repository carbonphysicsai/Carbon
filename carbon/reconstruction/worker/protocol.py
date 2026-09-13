"""Closed request staging and bounded output intake for C-03."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from carbon.construction import (
    ResolvedConstructionPlan,
    ResolvedConstructionPlanRef,
    decode_resolved_construction_plan,
)
from carbon.execution import ClaimedExecution, ExecutionAttemptRef, ExecutionScope
from carbon.fees import AdmissionKind, SubmissionId
from carbon.reconstruction.model import (
    PublicTrainingArchive,
    ReconstructionFailure,
    ReconstructionReceipt,
)
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import DevelopmentRepeatPlan, DevelopmentReplica
from carbon.reconstruction.service import _read_json, _validate_artifact, reconstruct
from carbon.reconstruction.worker.model import (
    CONTROL_BYTES,
    EXPANDED_INPUT_BYTES,
    EXPANDED_OUTPUT_BYTES,
    INPUT_BYTES,
    OUTPUT_BYTES,
    OUTPUT_MEMBERS,
    SCOPE,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    exact_digest,
    tagged_sha256,
)
from carbon.registry import ChallengeKey
from carbon.seeding import DerivedSeed

_REQUEST_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "execution",
        "plan",
        "reconstruction_profile_digest",
        "worker_profile_digest",
        "training",
        "randomness_digest",
        "replicate",
        "paths",
        "continuation_split_step",
    }
)
_RESULT_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "artifact_digest",
        "checkpoint_digest",
        "execution_id",
        "plan_digest",
        "profile_digest",
        "training_data_digest",
        "randomness_digest",
        "status",
        "completed_steps",
    }
)
_EXECUTION_FIELDS = frozenset({"submission_id", "attempt_number"})
_PLAN_FIELDS = frozenset(
    {
        "challenge_id",
        "challenge_version",
        "schema_version",
        "canonicalization_profile",
        "digest",
    }
)
_TRAINING_FIELDS = frozenset({"digest", "provenance", "role", "format"})
_REPLICATE_FIELDS = frozenset(
    {
        "repeat_plan_digest",
        "request_digest",
        "id",
        "digest",
        "policy_digest",
        "resource_class_digest",
    }
)
_PATH_FIELDS = frozenset({"plan", "training", "seed"})


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _safe_relative(value: object) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise WorkerFailure(WorkerCode.INVALID)
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise WorkerFailure(WorkerCode.INVALID)
    return path


def _closed_json(path: Path, fields: frozenset[str]) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > CONTROL_BYTES:
        raise WorkerFailure(WorkerCode.INVALID)

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise WorkerFailure(WorkerCode.INVALID)
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except WorkerFailure:
        raise
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise WorkerFailure(WorkerCode.INVALID) from None
    if type(value) is not dict or set(value) != fields:
        raise WorkerFailure(WorkerCode.INVALID)
    return value


def _audit_zip(path: Path, *, expanded_limit: int) -> int | None:
    if not zipfile.is_zipfile(path):
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > OUTPUT_MEMBERS:
                raise WorkerFailure(WorkerCode.STAGING)
            names: set[str] = set()
            expanded = 0
            compressed = 0
            for info in infos:
                relative = _safe_relative(info.filename)
                if info.filename in names or not relative.parts or info.is_dir():
                    raise WorkerFailure(WorkerCode.STAGING)
                names.add(info.filename)
                mode = info.external_attr >> 16
                if mode and not stat.S_ISREG(mode):
                    raise WorkerFailure(WorkerCode.STAGING)
                expanded += info.file_size
                compressed += info.compress_size
                if expanded > expanded_limit or compressed > INPUT_BYTES:
                    raise WorkerFailure(WorkerCode.STAGING)
            return expanded
    except WorkerFailure:
        raise
    except (OSError, zipfile.BadZipFile, OverflowError):
        raise WorkerFailure(WorkerCode.STAGING) from None


def _copy_snapshot(source: Path, destination: Path, *, maximum: int) -> str:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(source, flags)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise WorkerFailure(WorkerCode.STAGING)
        output = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        digest = hashlib.sha256()
        written = 0
        try:
            while True:
                block = os.read(descriptor, min(1 << 20, maximum + 1 - written))
                if not block:
                    break
                written += len(block)
                if written > maximum:
                    raise WorkerFailure(WorkerCode.STAGING)
                digest.update(block)
                os.write(output, block)
            os.fsync(output)
        finally:
            os.close(output)
            os.close(descriptor)
    except WorkerFailure:
        raise
    except OSError:
        raise WorkerFailure(WorkerCode.STAGING) from None
    return "sha256:" + digest.hexdigest()


def stage_request(
    *,
    stage_root: Path,
    claimed: ClaimedExecution,
    repeat_plan: DevelopmentRepeatPlan,
    replica: DevelopmentReplica,
    plan: ResolvedConstructionPlan,
    training_archive: PublicTrainingArchive,
    derived_seed: DerivedSeed,
    worker_profile: DevelopmentWorkerProfile,
    continuation_split_step: int | None = None,
) -> tuple[Path, str]:
    """Write one immutable, relocation-safe request snapshot."""
    if (
        not isinstance(stage_root, Path)
        or not stage_root.is_absolute()
        or stage_root.is_symlink()
        or type(claimed) is not ClaimedExecution
        or type(repeat_plan) is not DevelopmentRepeatPlan
        or type(replica) is not DevelopmentReplica
        or type(plan) is not ResolvedConstructionPlan
        or type(training_archive) is not PublicTrainingArchive
        or type(derived_seed) is not DerivedSeed
        or type(worker_profile) is not DevelopmentWorkerProfile
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    plan_ref = plan.to_ref()
    identity = replica.binding.replicate_identity
    if (
        replica not in repeat_plan.replicas
        or claimed.binding.handle.admission_kind is not AdmissionKind.FIXTURE
        or claimed.binding.scope is not ExecutionScope.FIXTURE_DEVELOPMENT
        or repeat_plan.construction_plan_digest != plan_ref.content_digest
        or repeat_plan.training_data_digest != training_archive.content_digest
        or replica.execution_ref != claimed.claim.ref
        or plan_ref != identity.construction_plan_ref
        or claimed.binding.resolved_plan_digest != plan_ref.content_digest
        or claimed.binding.resource_policy_digest != identity.policy_ref.content_digest
        or worker_profile.research_resource_policy_digest
        != identity.policy_ref.content_digest
        or worker_profile.resource_class_digest
        != identity.resource_class_ref.content_digest
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    seed = derived_seed.as_backend_bytes()
    randomness_digest = tagged_sha256(seed)
    if randomness_digest != replica.randomness_digest:
        raise WorkerFailure(WorkerCode.POLICY)
    profile = compile_development_profile(plan)
    if (
        profile.plan_digest != plan_ref.content_digest
        or claimed.binding.reconstruction_policy_digest != profile.profile_digest
        or claimed.binding.handle.environment_pin.backend_profile_id
        != profile.profile_id
        or claimed.binding.handle.environment_pin.container_digest
        != profile.environment_digest
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    train_steps = json.loads(profile.train_config_json)["steps"]
    if continuation_split_step is not None and (
        type(continuation_split_step) is not int
        or not 1 <= continuation_split_step < train_steps
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    stage_root.mkdir(parents=True, exist_ok=True)
    os.chmod(stage_root, 0o700)
    staging = Path(tempfile.mkdtemp(prefix=".c03-stage-", dir=stage_root))
    try:
        plan_path = staging / "plan.bin"
        plan_bytes = plan.canonical_bytes()
        if len(plan_bytes) > CONTROL_BYTES:
            raise WorkerFailure(WorkerCode.STAGING)
        with plan_path.open("xb") as stream:
            stream.write(plan_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(plan_path, 0o400)
        archive_path = staging / "train.npz"
        observed_archive = _copy_snapshot(
            training_archive.path, archive_path, maximum=INPUT_BYTES
        )
        if observed_archive != training_archive.content_digest:
            raise WorkerFailure(WorkerCode.STAGING)
        _audit_zip(archive_path, expanded_limit=EXPANDED_INPUT_BYTES)
        seed_path = staging / "derived-seed.bin"
        with seed_path.open("xb") as stream:
            stream.write(seed)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(seed_path, 0o400)
        request = {
            "schema": "carbon.c03.worker-request.v1",
            "scope": SCOPE,
            "execution": {
                "submission_id": replica.execution_ref.submission_id.value,
                "attempt_number": replica.execution_ref.attempt_number,
            },
            "plan": {
                "challenge_id": plan_ref.challenge_key.challenge_id,
                "challenge_version": plan_ref.challenge_key.version,
                "schema_version": plan_ref.schema_version,
                "canonicalization_profile": plan_ref.canonicalization_profile,
                "digest": plan_ref.content_digest,
            },
            "reconstruction_profile_digest": profile.profile_digest,
            "worker_profile_digest": worker_profile.digest,
            "training": {
                "digest": training_archive.content_digest,
                "provenance": training_archive.provenance,
                "role": training_archive.role,
                "format": training_archive.format,
            },
            "randomness_digest": randomness_digest,
            "replicate": {
                "repeat_plan_digest": repeat_plan.plan_digest,
                "request_digest": repeat_plan.request_digest,
                "id": identity.replicate_id,
                "digest": identity.replicate_digest,
                "policy_digest": identity.policy_ref.content_digest,
                "resource_class_digest": identity.resource_class_ref.content_digest,
            },
            "paths": {
                "plan": "plan.bin",
                "training": "train.npz",
                "seed": "derived-seed.bin",
            },
            "continuation_split_step": continuation_split_step,
        }
        payload = _canonical(request) + b"\n"
        if len(payload) > CONTROL_BYTES:
            raise WorkerFailure(WorkerCode.STAGING)
        request_path = staging / "request.json"
        with request_path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(request_path, 0o400)
        digest = hashlib.sha256()
        for member in sorted(staging.iterdir()):
            digest.update(member.name.encode("utf-8"))
            digest.update(bytes.fromhex(_file_digest(member)[7:]))
        stage_digest = "sha256:" + digest.hexdigest()
        # The container runs as a fixed numeric UID distinct from the trusted
        # controller. The bind itself is read-only; world-read here grants only
        # that container access to this attempt-specific snapshot.
        for member in staging.iterdir():
            os.chmod(member, 0o444)
        os.chmod(staging, 0o555)
        return staging, stage_digest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def load_worker_request(
    input_directory: Path,
) -> tuple[
    ExecutionAttemptRef,
    ResolvedConstructionPlan,
    PublicTrainingArchive,
    DerivedSeed,
    int | None,
]:
    """Decode one staged request inside the bounded worker."""
    request = _closed_json(input_directory / "request.json", _REQUEST_FIELDS)
    try:
        if (
            request["schema"] != "carbon.c03.worker-request.v1"
            or request["scope"] != SCOPE
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        paths = request["paths"]
        execution = request["execution"]
        plan_value = request["plan"]
        training = request["training"]
        replicate = request["replicate"]
        if not all(
            type(value) is dict
            for value in (paths, execution, plan_value, training, replicate)
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        if (
            set(paths) != _PATH_FIELDS
            or set(execution) != _EXECUTION_FIELDS
            or set(plan_value) != _PLAN_FIELDS
            or set(training) != _TRAINING_FIELDS
            or set(replicate) != _REPLICATE_FIELDS
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        for key in (
            "repeat_plan_digest",
            "request_digest",
            "digest",
            "policy_digest",
            "resource_class_digest",
        ):
            exact_digest(replicate[key])
        if type(replicate["id"]) is not str or not replicate["id"]:
            raise WorkerFailure(WorkerCode.INVALID)
        expected_worker_profile = DevelopmentWorkerProfile(
            replicate["policy_digest"], replicate["resource_class_digest"]
        )
        if expected_worker_profile.digest != request["worker_profile_digest"]:
            raise WorkerFailure(WorkerCode.POLICY)
        resolved = {
            name: input_directory / _safe_relative(paths[name]) for name in paths
        }
        plan_ref = ResolvedConstructionPlanRef(
            ChallengeKey(plan_value["challenge_id"], plan_value["challenge_version"]),
            plan_value["schema_version"],
            plan_value["canonicalization_profile"],
            plan_value["digest"],
        )
        plan = decode_resolved_construction_plan(
            resolved["plan"].read_bytes(), expected_ref=plan_ref
        )
        profile = compile_development_profile(plan)
        if profile.profile_digest != request["reconstruction_profile_digest"]:
            raise WorkerFailure(WorkerCode.POLICY)
        split = request["continuation_split_step"]
        train_steps = json.loads(profile.train_config_json)["steps"]
        if split is not None and (
            type(split) is not int or not 1 <= split < train_steps
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        archive = PublicTrainingArchive(
            resolved["training"],
            training["digest"],
            training["provenance"],
            training["role"],
            training["format"],
        )
        seed_bytes = resolved["seed"].read_bytes()
        seed = DerivedSeed(seed_bytes)
        if tagged_sha256(seed_bytes) != request["randomness_digest"]:
            raise WorkerFailure(WorkerCode.POLICY)
        ref = ExecutionAttemptRef(
            submission_id=SubmissionId(execution["submission_id"]),
            attempt_number=execution["attempt_number"],
        )
    except WorkerFailure:
        raise
    # This is the hostile decode boundary: all library/parser failures become
    # one non-echoing protocol rejection.
    except Exception:  # noqa: BLE001
        raise WorkerFailure(WorkerCode.INVALID) from None
    return ref, plan, archive, seed, split


def run_staged_worker(input_directory: Path, scratch_directory: Path) -> int:
    """Fixed image entry point. It accepts no command or import path from input."""
    try:
        ref, plan, archive, seed, split = load_worker_request(input_directory)
        output = scratch_directory / "output"
        output.mkdir(parents=True, exist_ok=False)
        if split is None:
            receipt = reconstruct(
                execution_ref=ref,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
                artifact_path=(output / "artifact").resolve(),
            )
        else:
            partial = reconstruct(
                execution_ref=ref,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
                artifact_path=(scratch_directory / "partial-artifact").resolve(),
                until_step=split,
            )
            receipt = reconstruct(
                execution_ref=ref,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
                artifact_path=(output / "artifact").resolve(),
                resume_from=partial,
            )
        result = {
            "schema": "carbon.c03.worker-result.v1",
            "scope": SCOPE,
            "artifact_digest": receipt.artifact_digest,
            "checkpoint_digest": receipt.checkpoint_digest,
            "execution_id": receipt.execution_id,
            "plan_digest": receipt.plan_digest,
            "profile_digest": receipt.profile_digest,
            "training_data_digest": receipt.training_data_digest,
            "randomness_digest": receipt.randomness_digest,
            "status": receipt.status.value,
            "completed_steps": receipt.completed_steps,
        }
        result_path = output / "result.json"
        with result_path.open("xb") as stream:
            stream.write(_canonical(result) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        (scratch_directory / "ready").touch(mode=0o400, exist_ok=False)
        return 0
    except (WorkerFailure, ReconstructionFailure):
        return 20
    # Never serialize an implementation exception back to the controller.
    except Exception:  # noqa: BLE001
        return 21


def snapshot_output(
    source: Path, destination_root: Path, *, destination_name: str | None = None
) -> tuple[Path, str]:
    """Copy a provisional worker tree without links, devices, or path authority."""
    if source.is_symlink() or not source.is_dir() or destination_root.is_symlink():
        raise WorkerFailure(WorkerCode.OUTPUT)
    destination_root.mkdir(parents=True, exist_ok=True)
    os.chmod(destination_root, 0o700)
    if destination_name is None:
        destination = Path(
            tempfile.mkdtemp(prefix=".c03-output-", dir=destination_root)
        )
    else:
        if (
            type(destination_name) is not str
            or len(destination_name) != 64
            or any(
                character not in "0123456789abcdef" for character in destination_name
            )
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        destination = destination_root / destination_name
        try:
            destination.mkdir(mode=0o700)
        except FileExistsError:
            raise WorkerFailure(WorkerCode.CONFLICT) from None
    total = 0
    expanded_total = 0
    count = 0
    digest = hashlib.sha256()
    try:
        for member in sorted(source.rglob("*")):
            relative = member.relative_to(source)
            if member.is_symlink() or not member.is_file():
                if member.is_dir() and not member.is_symlink():
                    continue
                raise WorkerFailure(WorkerCode.OUTPUT)
            count += 1
            if count > OUTPUT_MEMBERS:
                raise WorkerFailure(WorkerCode.OUTPUT)
            size = member.stat(follow_symlinks=False).st_size
            total += size
            if total > OUTPUT_BYTES:
                raise WorkerFailure(WorkerCode.OUTPUT)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            observed = _copy_snapshot(
                member, target, maximum=OUTPUT_BYTES - total + size
            )
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(bytes.fromhex(observed[7:]))
            expanded = _audit_zip(target, expanded_limit=EXPANDED_OUTPUT_BYTES)
            expanded_total += size if expanded is None else expanded
            if expanded_total > EXPANDED_OUTPUT_BYTES:
                raise WorkerFailure(WorkerCode.OUTPUT)
        if count == 0:
            raise WorkerFailure(WorkerCode.OUTPUT)
        for directory in sorted(
            (item for item in destination.rglob("*") if item.is_dir()), reverse=True
        ):
            os.chmod(directory, 0o500)
        os.chmod(destination, 0o500)
        return destination, "sha256:" + digest.hexdigest()
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def validate_snapshot(
    snapshot: Path,
    *,
    execution_ref: ExecutionAttemptRef,
    plan: ResolvedConstructionPlan,
    training_archive: PublicTrainingArchive,
    randomness_digest: str,
) -> ReconstructionReceipt:
    """Rebuild the C-02 receipt from immutable controller-owned bytes."""
    exact_digest(randomness_digest)
    artifact = snapshot / "artifact"
    try:
        proposal = _closed_json(snapshot / "result.json", _RESULT_FIELDS)
        if (
            proposal["schema"] != "carbon.c03.worker-result.v1"
            or proposal["scope"] != SCOPE
        ):
            raise WorkerFailure(WorkerCode.OUTPUT)
        manifest = _read_json(artifact / "manifest.json")
        mapping = manifest["mapping_receipt"]
        if type(mapping) is not dict:
            raise WorkerFailure(WorkerCode.OUTPUT)
        if mapping.get("implementation_profile") == "foundax_fno_v1":
            from carbon.reconstruction.foundax_adapter import inspect_checkpoint
        else:
            from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
                inspect_checkpoint,
            )
        receipt = _validate_artifact(
            artifact,
            inspect_checkpoint=inspect_checkpoint,
            execution_id=(
                f"{execution_ref.submission_id.value}:{execution_ref.attempt_number}"
            ),
            profile=compile_development_profile(plan),
            archive=training_archive,
            randomness_digest=randomness_digest,
        )
        expected = {
            "artifact_digest": receipt.artifact_digest,
            "checkpoint_digest": receipt.checkpoint_digest,
            "execution_id": receipt.execution_id,
            "plan_digest": receipt.plan_digest,
            "profile_digest": receipt.profile_digest,
            "training_data_digest": receipt.training_data_digest,
            "randomness_digest": receipt.randomness_digest,
            "status": receipt.status.value,
            "completed_steps": receipt.completed_steps,
        }
        if any(proposal.get(key) != value for key, value in expected.items()):
            raise WorkerFailure(WorkerCode.OUTPUT)
        return receipt
    except WorkerFailure:
        raise
    # Artifact readers include native/array libraries; collapse their error
    # surface to the source-owned output rejection.
    except Exception:  # noqa: BLE001
        raise WorkerFailure(WorkerCode.OUTPUT) from None


__all__ = [
    "load_worker_request",
    "run_staged_worker",
    "snapshot_output",
    "stage_request",
    "validate_snapshot",
]
