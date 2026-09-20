"""Closed request staging and bounded output intake for C-03."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
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
from carbon.reconstruction.accelerators import require_profile_admission
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
    VALIDATION_WALL_SECONDS,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    exact_digest,
    tagged_sha256,
)
from carbon.registry import ChallengeKey
from carbon.seeding import DerivedSeed

_VALIDATED_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "artifact_digest",
        "execution_id",
        "plan_digest",
        "profile_digest",
        "training_data_digest",
        "randomness_digest",
        "checkpoint_digest",
        "status",
        "completed_steps",
        "compile_seconds",
        "train_execution_seconds",
        "source_digest",
        "environment_digest",
        "observed_environment_digest",
        "environment_eligibility",
        "input_interface_digest",
        "output_interface_digest",
        "physical_scaling_digest",
        "physical_unit_system",
        "normalization_scale",
        "inference_weights",
    }
)

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
_STREAM_HEADER_FIELDS = frozenset({"schema"})
_STREAM_MEMBER_FIELDS = frozenset({"path", "size"})
_STREAM_END_FIELDS = frozenset({"bytes", "end", "members"})


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


def _closed_json(
    path: Path, fields: frozenset[str], alternate: frozenset[str] | None = None
) -> dict[str, object]:
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
    if type(value) is not dict or (
        set(value) != fields and (alternate is None or set(value) != alternate)
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    return value


def _json_line(stream) -> dict[str, object]:
    line = stream.readline(2049)
    if not line.endswith(b"\n") or len(line) > 2048:
        raise WorkerFailure(WorkerCode.OUTPUT)

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise WorkerFailure(WorkerCode.OUTPUT)
            result[key] = value
        return result

    try:
        value = json.loads(
            line,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except WorkerFailure:
        raise
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise WorkerFailure(WorkerCode.OUTPUT) from None
    if type(value) is not dict:
        raise WorkerFailure(WorkerCode.OUTPUT)
    return value


def _closed_json_line(stream, fields: frozenset[str]) -> dict[str, object]:
    value = _json_line(stream)
    if set(value) != fields:
        raise WorkerFailure(WorkerCode.OUTPUT)
    return value


def decode_output_stream(source: Path, destination: Path) -> None:
    """Decode the fixed worker framing into a fresh controller-owned tree."""

    if (
        source.is_symlink()
        or not source.is_file()
        or source.stat().st_size > OUTPUT_BYTES + 2 * CONTROL_BYTES
        or destination.exists()
        or destination.is_symlink()
    ):
        raise WorkerFailure(WorkerCode.OUTPUT)
    count = 0
    total = 0
    seen: set[str] = set()
    try:
        destination.mkdir(mode=0o700)
        with source.open("rb") as stream:
            header = _closed_json_line(stream, _STREAM_HEADER_FIELDS)
            if header["schema"] != "carbon.c03.output-stream.v1":
                raise WorkerFailure(WorkerCode.OUTPUT)
            while True:
                record = _json_line(stream)
                if set(record) == _STREAM_END_FIELDS:
                    end = record
                    if (
                        end["end"] is not True
                        or end["members"] != count
                        or end["bytes"] != total
                        or stream.read(1) != b""
                        or count == 0
                    ):
                        raise WorkerFailure(WorkerCode.OUTPUT)
                    break
                if set(record) != _STREAM_MEMBER_FIELDS:
                    raise WorkerFailure(WorkerCode.OUTPUT)
                member = record
                relative = _safe_relative(member["path"])
                size = member["size"]
                if (
                    type(size) is not int
                    or size < 0
                    or size > OUTPUT_BYTES - total
                    or relative.as_posix() in seen
                ):
                    raise WorkerFailure(WorkerCode.OUTPUT)
                seen.add(relative.as_posix())
                count += 1
                if count > OUTPUT_MEMBERS:
                    raise WorkerFailure(WorkerCode.OUTPUT)
                target = destination.joinpath(*relative.parts)
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with target.open("xb") as output:
                    remaining = size
                    while remaining:
                        block = stream.read(min(1 << 20, remaining))
                        if not block:
                            raise WorkerFailure(WorkerCode.OUTPUT)
                        output.write(block)
                        remaining -= len(block)
                    output.flush()
                    os.fsync(output.fileno())
                total += size
    except WorkerFailure:
        shutil.rmtree(destination, ignore_errors=True)
        raise WorkerFailure(WorkerCode.OUTPUT) from None
    except Exception:  # noqa: BLE001
        shutil.rmtree(destination, ignore_errors=True)
        raise WorkerFailure(WorkerCode.OUTPUT) from None
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise


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
                file_type = stat.S_IFMT(mode)
                # ZIP creators commonly preserve permissions without setting
                # Unix file-type bits. Reject an explicit non-regular type,
                # while accepting those permission-only regular members.
                if file_type and file_type != stat.S_IFREG:
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
        # C-W1 retains real authenticated provenance inside this same closed
        # public DEVELOPMENT worker. PRODUCTION is C-01's non-fixture enum;
        # neither pair grants protected/LIVE/qualification authority.
        or type(claimed.binding.handle.admission_kind) is not AdmissionKind
        or type(claimed.binding.scope) is not ExecutionScope
        or (claimed.binding.handle.admission_kind, claimed.binding.scope)
        not in (
            (AdmissionKind.FIXTURE, ExecutionScope.FIXTURE_DEVELOPMENT),
            (AdmissionKind.PRODUCTION, ExecutionScope.REAL_PATH_NON_LIVE),
        )
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
    require_profile_admission(profile, worker_profile=worker_profile)
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
        if worker_profile.accelerator_profile_id is not None:
            request["schema"] = _accelerator_request_schema(worker_profile)
            from carbon.reconstruction.worker.model import (
                LOCAL_DEVELOPMENT_AUTHORITY,
            )

            if worker_profile.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY:
                # Distinct key and authority: a staged local request can never be
                # read as a strict one by a consumer looking for grant_digest.
                request["accelerator"] = {
                    "profile_id": worker_profile.accelerator_profile_id,
                    "authority": LOCAL_DEVELOPMENT_AUTHORITY,
                    "approval_digest": worker_profile.accelerator_grant_digest,
                    "diagnostic_plan_digest": worker_profile.accelerator_plan_digest,
                    "role": worker_profile.accelerator_role,
                }
            else:
                request["accelerator"] = {
                    "profile_id": worker_profile.accelerator_profile_id,
                    "grant_digest": worker_profile.accelerator_grant_digest,
                    "role": worker_profile.accelerator_role,
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


def _permitted_request_schemas(request):
    """Pair the request schema with the authority its accelerator block declares.

    The pairing is closed in both directions: a CPU request is v1, a strict or
    TPU accelerator request is v2/v3, and a local development request is v4. A
    local block presented under a strict schema, or a strict block under the
    local schema, matches nothing and is refused.
    """
    from carbon.reconstruction.worker.model import LOCAL_DEVELOPMENT_AUTHORITY

    accelerator = request.get("accelerator")
    if accelerator is None:
        return ("carbon.c03.worker-request.v1",)
    if (
        type(accelerator) is dict
        and accelerator.get("authority") == LOCAL_DEVELOPMENT_AUTHORITY
    ):
        return ("carbon.c03.worker-request.v4",)
    return ("carbon.c03.worker-request.v2", "carbon.c03.worker-request.v3")


def _accelerator_request_schema(profile):
    from carbon.reconstruction.accelerators import TPU_PROFILE
    from carbon.reconstruction.worker.model import LOCAL_DEVELOPMENT_AUTHORITY

    if profile.accelerator_profile_id == TPU_PROFILE.profile_id:
        return "carbon.c03.worker-request.v3"
    if profile.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY:
        # A closed, separately versioned request form. The historical strict
        # representation keeps v2 byte for byte.
        return "carbon.c03.worker-request.v4"
    return "carbon.c03.worker-request.v2"


def _request_worker_profile(request):
    replicate = request["replicate"]
    accelerator = request.get("accelerator")
    if accelerator is None:
        return DevelopmentWorkerProfile(
            replicate["policy_digest"], replicate["resource_class_digest"]
        )
    from carbon.reconstruction.accelerators import TPU_PROFILE
    from carbon.reconstruction.worker.model import LOCAL_DEVELOPMENT_AUTHORITY

    if type(accelerator) is not dict:
        raise WorkerFailure(WorkerCode.INVALID)
    local_fields = {
        "profile_id",
        "authority",
        "approval_digest",
        "diagnostic_plan_digest",
        "role",
    }
    strict_fields = {"profile_id", "grant_digest", "role"}
    if set(accelerator) == local_fields:
        if accelerator["authority"] != LOCAL_DEVELOPMENT_AUTHORITY:
            raise WorkerFailure(WorkerCode.INVALID)
        profile = DevelopmentWorkerProfile(
            replicate["policy_digest"],
            replicate["resource_class_digest"],
            "carbon.c03.cuda.development.v1",
            "1.0",
            accelerator["profile_id"],
            accelerator["approval_digest"],
            accelerator["role"],
            LOCAL_DEVELOPMENT_AUTHORITY,
            accelerator["diagnostic_plan_digest"],
        )
    elif set(accelerator) == strict_fields:
        profile = DevelopmentWorkerProfile(
            replicate["policy_digest"],
            replicate["resource_class_digest"],
            (
                "carbon.c03.tpu.preparation.v1"
                if accelerator["profile_id"] == TPU_PROFILE.profile_id
                else "carbon.c03.cuda.development.v1"
            ),
            "1.0",
            accelerator["profile_id"],
            accelerator["grant_digest"],
            accelerator["role"],
        )
    else:
        raise WorkerFailure(WorkerCode.INVALID)
    if request["schema"] != _accelerator_request_schema(profile):
        raise WorkerFailure(WorkerCode.INVALID)
    return profile


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
    request = _closed_json(
        input_directory / "request.json",
        _REQUEST_FIELDS,
        _REQUEST_FIELDS | {"accelerator"},
    )
    try:
        if request["schema"] not in _permitted_request_schemas(request):
            raise WorkerFailure(WorkerCode.INVALID)
        if request["scope"] != SCOPE:
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
        expected_worker_profile = _request_worker_profile(request)
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
        require_profile_admission(profile, worker_profile=expected_worker_profile)
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
        worker_profile = _request_worker_profile(
            _closed_json(
                input_directory / "request.json",
                _REQUEST_FIELDS,
                _REQUEST_FIELDS | {"accelerator"},
            )
        )
        # This function is released by the existing controller only after
        # admission, deadline ownership and effective container controls. Never
        # initialize a backend in the controller or select one from miner input.
        from carbon.reconstruction.profile import DEPENDENCY_SPECS
        from carbon.reconstruction.worker.backend_probe import (
            Backend,
            BackendProbeError,
            BackendRequest,
            probe_backend,
        )

        dependencies = {name: version for name, version, _ in DEPENDENCY_SPECS}
        try:
            probe_backend(
                BackendRequest(
                    (
                        Backend.CPU
                        if worker_profile.accelerator_profile_id is None
                        else Backend.NVIDIA
                    ),
                    local_device_count=1,
                    jax_version=dependencies["jax"],
                    jaxlib_version=dependencies["jaxlib"],
                )
            )
        except BackendProbeError:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        output = scratch_directory / "output"
        output.mkdir(parents=True, exist_ok=False)
        if split is None:
            receipt = reconstruct(
                execution_ref=ref,
                worker_profile=worker_profile,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
                artifact_path=(output / "artifact").resolve(),
            )
        else:
            partial = reconstruct(
                execution_ref=ref,
                worker_profile=worker_profile,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
                artifact_path=(scratch_directory / "partial-artifact").resolve(),
                until_step=split,
            )
            receipt = reconstruct(
                execution_ref=ref,
                worker_profile=worker_profile,
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


def validated_receipt_payload(receipt: ReconstructionReceipt) -> dict[str, object]:
    """Closed process-boundary projection for one already validated receipt."""

    if type(receipt) is not ReconstructionReceipt:
        raise WorkerFailure(WorkerCode.OUTPUT)
    return {
        "schema": "carbon.c03.validated-receipt.v1",
        "artifact_digest": receipt.artifact_digest,
        "execution_id": receipt.execution_id,
        "plan_digest": receipt.plan_digest,
        "profile_digest": receipt.profile_digest,
        "training_data_digest": receipt.training_data_digest,
        "randomness_digest": receipt.randomness_digest,
        "checkpoint_digest": receipt.checkpoint_digest,
        "status": receipt.status.value,
        "completed_steps": receipt.completed_steps,
        "compile_seconds": receipt.compile_seconds,
        "train_execution_seconds": receipt.train_execution_seconds,
        "source_digest": receipt.source_digest,
        "environment_digest": receipt.environment_digest,
        "observed_environment_digest": receipt.observed_environment_digest,
        "environment_eligibility": (
            None
            if receipt.environment_eligibility is None
            else receipt.environment_eligibility.value
        ),
        "input_interface_digest": receipt.input_interface_digest,
        "output_interface_digest": receipt.output_interface_digest,
        "physical_scaling_digest": receipt.physical_scaling_digest,
        "physical_unit_system": receipt.physical_unit_system,
        "normalization_scale": receipt.normalization_scale,
        "inference_weights": receipt.inference_weights,
    }


def _receipt_from_validated_payload(
    value: object, *, artifact_path: Path
) -> ReconstructionReceipt:
    from carbon.reconstruction.model import (
        EnvironmentEligibility,
        ReconstructionStatus,
    )

    if (
        type(value) is not dict
        or set(value) != _VALIDATED_RECEIPT_FIELDS
        or value.get("schema") != "carbon.c03.validated-receipt.v1"
    ):
        raise WorkerFailure(WorkerCode.OUTPUT)
    try:
        return ReconstructionReceipt(
            artifact_path=artifact_path,
            artifact_digest=value["artifact_digest"],
            execution_id=value["execution_id"],
            plan_digest=value["plan_digest"],
            profile_digest=value["profile_digest"],
            training_data_digest=value["training_data_digest"],
            randomness_digest=value["randomness_digest"],
            checkpoint_digest=value["checkpoint_digest"],
            status=ReconstructionStatus(value["status"]),
            completed_steps=value["completed_steps"],
            compile_seconds=value["compile_seconds"],
            train_execution_seconds=value["train_execution_seconds"],
            source_digest=value["source_digest"],
            environment_digest=value["environment_digest"],
            observed_environment_digest=value["observed_environment_digest"],
            environment_eligibility=(
                None
                if value["environment_eligibility"] is None
                else EnvironmentEligibility(value["environment_eligibility"])
            ),
            input_interface_digest=value["input_interface_digest"],
            output_interface_digest=value["output_interface_digest"],
            physical_scaling_digest=value["physical_scaling_digest"],
            physical_unit_system=value["physical_unit_system"],
            normalization_scale=value["normalization_scale"],
            inference_weights=value["inference_weights"],
        )
    except (KeyError, TypeError, ValueError, ReconstructionFailure, WorkerFailure):
        raise WorkerFailure(WorkerCode.OUTPUT) from None


def validate_snapshot_bounded(snapshot: Path, stage: Path) -> ReconstructionReceipt:
    """Validate untrusted artifact bytes in a capped, separately owned process."""

    if (
        not snapshot.is_absolute()
        or snapshot.is_symlink()
        or not snapshot.is_dir()
        or not stage.is_absolute()
        or stage.is_symlink()
        or not stage.is_dir()
    ):
        raise WorkerFailure(WorkerCode.OUTPUT)
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "JAX_PLATFORMS": "cpu",
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
    }
    root = Path(__file__).resolve().parents[3]
    command = [
        sys.executable,
        "-m",
        "carbon.reconstruction.worker.artifact_validator",
        str(snapshot),
        str(stage),
    ]
    from carbon.reconstruction.worker.docker_runtime import _bounded_capture

    try:
        process = _bounded_capture(
            command,
            environment=environment,
            timeout=VALIDATION_WALL_SECONDS,
            maximum=CONTROL_BYTES,
            cwd=root,
        )
    except WorkerFailure:
        raise WorkerFailure(WorkerCode.OUTPUT)
    if process.returncode != 0:
        raise WorkerFailure(WorkerCode.OUTPUT)
    try:
        value = json.loads(
            process.stdout,
            object_pairs_hook=lambda pairs: _unique_pairs(pairs, WorkerCode.OUTPUT),
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError, WorkerFailure):
        raise WorkerFailure(WorkerCode.OUTPUT) from None
    return _receipt_from_validated_payload(value, artifact_path=snapshot / "artifact")


def _unique_pairs(
    items: list[tuple[str, object]], code: WorkerCode
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise WorkerFailure(code)
        result[key] = value
    return result


__all__ = [
    "decode_output_stream",
    "load_worker_request",
    "run_staged_worker",
    "snapshot_output",
    "stage_request",
    "validate_snapshot",
    "validate_snapshot_bounded",
    "validated_receipt_payload",
]
