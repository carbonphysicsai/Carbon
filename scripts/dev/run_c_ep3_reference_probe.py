#!/usr/bin/env python3
"""Run C-EP3's closed, detached public numerical component probe.

The harness verifies an exact owner-supplied archive before importing its code.
It never writes to Carbon's candidate, pack, reward, archive, or result owners.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import platform
import shutil
import stat
import sys
import time
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "carbon.c-ep3-public-reference-probe.observation.v1"
PROTOCOL_SCHEMA = "carbon.c-ep3-public-reference-probe.protocol.v1"
ARCHIVE_SHA256 = "40f1fd47d62dd2269f8e141e6bb398d03a403aa6eb3ac08750b49dd68018bcdc"
EXPECTED_RELEASE_DIGEST = (
    "sha256:7805f87c3b4745454ec9c8fa852a20de6731d8f85e1356eb5d91a708cdafa7ac"
)
EXPECTED_PINS = {
    "carbon_challenge/burgers.py": "929f631b9c61f6ecacfca12f5dbf90306e6c4b7d5702c42daed9b7937b9c6372",
    "carbon_challenge/contracts.py": "86f57744f6ceb58328d8045bbb43b1362e22a96ffb5091c3968e2ff740ac35b9",
    "carbon_challenge/measurement.py": "1c9a0fa23f8ce8546469a6500a13fd042bafcde89965c4115a5fc28c10cdccf0",
    "carbon_challenge/numerics.py": "f2922d058e253c2afd60b848624bc3296cede46e323e0327a8cb7ab88eaf6360",
    "config/burgers_dynamics.json": "a24d615bede4c7594f261aac870545e9f957effbf28529ea3906e473a6935016",
    "config/gauntlet.json": "11dd9b69d93c517c9d0dc8669645887d8c60378f03264a94a1be62fff3b08e5f",
}
REQUIRED_EXTRACT = {
    "carbon_challenge/__init__.py",
    "carbon_challenge/burgers.py",
    "carbon_challenge/contracts.py",
    "carbon_challenge/measurement.py",
    "carbon_challenge/numerics.py",
    "config/burgers_dynamics.json",
    "config/gauntlet.json",
    "evidence/reference_audit.json",
    "packages/release_manifest.json",
    "pyproject.toml",
    "requirements-evidence.txt",
}
FORBIDDEN_PUBLIC_KEYS = {
    "strategy",
    "strategy_hash",
    "pack",
    "pack_id",
    "attempt_id",
    "parent",
    "latent",
    "initial_field",
    "solution",
    "raw_array",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(name: str) -> PurePosixPath:
    candidate = PurePosixPath(name)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or ".." in candidate.parts
        or "\\" in name
        or any(part in {"", "."} for part in candidate.parts)
    ):
        raise ValueError(f"unsafe archive member: {name!r}")
    return candidate


def _member_is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def _archive_layout(archive: Path) -> tuple[str, dict[str, zipfile.ZipInfo]]:
    with zipfile.ZipFile(archive) as bundle:
        infos: dict[str, zipfile.ZipInfo] = {}
        manifests: list[str] = []
        for info in bundle.infolist():
            member = _safe_relative(info.filename)
            if _member_is_symlink(info):
                raise ValueError(f"archive symlink is forbidden: {info.filename!r}")
            if info.is_dir():
                continue
            normalized = member.as_posix()
            if normalized in infos:
                raise ValueError(f"duplicate archive member: {normalized!r}")
            infos[normalized] = info
            if member.name == "artifact_manifest.json":
                manifests.append(normalized)
        if len(manifests) != 1:
            raise ValueError("archive must contain exactly one artifact_manifest.json")
        manifest_name = manifests[0]
        prefix = manifest_name[: -len("artifact_manifest.json")]
        return prefix, infos


def verify_archive(archive: Path) -> dict[str, Any]:
    archive = archive.resolve()
    actual_archive_hash = sha256_file(archive)
    if actual_archive_hash != ARCHIVE_SHA256:
        raise ValueError("archive SHA-256 mismatch")
    prefix, infos = _archive_layout(archive)
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read(prefix + "artifact_manifest.json"))
        if manifest.get("schema") != "public-artifact-manifest/1":
            raise ValueError("unexpected artifact manifest schema")
        if manifest.get("scientifically_qualified") is not False:
            raise ValueError("archive must remain scientifically unqualified")
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("artifact manifest has no files")
        actual_relatives = {
            name[len(prefix) :]
            for name in infos
            if name.startswith(prefix) and name != prefix + "artifact_manifest.json"
        }
        if actual_relatives != set(files):
            raise ValueError("archive members differ from the artifact manifest")
        for relative, record in files.items():
            _safe_relative(relative)
            data = bundle.read(prefix + relative)
            if record.get("bytes") != len(data):
                raise ValueError(f"size mismatch for {relative}")
            if record.get("sha256") != hashlib.sha256(data).hexdigest():
                raise ValueError(f"SHA-256 mismatch for {relative}")
        for relative, expected in EXPECTED_PINS.items():
            if files.get(relative, {}).get("sha256") != expected:
                raise ValueError(f"required source pin mismatch for {relative}")
        release = json.loads(bundle.read(prefix + "packages/release_manifest.json"))
        if release.get("release_digest") != EXPECTED_RELEASE_DIGEST:
            raise ValueError("release digest mismatch")
    return {
        "archive_sha256": actual_archive_hash,
        "release_digest": EXPECTED_RELEASE_DIGEST,
        "archive_entries": len(infos),
        "manifest_entries": len(files),
        "verified_entries": len(files),
        "source_pins": dict(sorted(EXPECTED_PINS.items())),
        "scientifically_qualified": False,
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("schema_version") != PROTOCOL_SCHEMA:
        raise ValueError("unexpected protocol schema")
    source = protocol.get("source", {})
    if source.get("archive_sha256") != ARCHIVE_SHA256:
        raise ValueError("protocol archive pin mismatch")
    if source.get("release_digest") != EXPECTED_RELEASE_DIGEST:
        raise ValueError("protocol release pin mismatch")
    if source.get("permission_scope") != "PUBLIC_DEVELOPMENT_ONLY":
        raise ValueError("probe requires the closed public-development scope")
    if source.get("scientifically_qualified") is not False:
        raise ValueError("protocol may not claim scientific qualification")
    if source.get("runtime_integrated") is not False:
        raise ValueError("protocol may not claim runtime integration")
    config = protocol.get("configuration", {})
    expected = {
        "phase_intervals": 64,
        "query_grid": 512,
        "reference_grid": 1024,
        "reference_cfl": 0.12,
        "reference_time_fraction": 0.005,
        "warm_primary_repetitions": 2,
        "refinement_grid": 2048,
        "refinement_cfl": 0.06,
        "refinement_time_fraction": 0.0025,
        "refinement_phase_intervals": 256,
        "witness_nodes": [1024, 2048],
        "witness_time_indices": [0, 1, 64, 128, 192],
        "witness_space_points": 32,
        "thread_limit": 1,
        "provider_calls": 0,
        "official_evaluations": 0,
    }
    if config != expected:
        raise ValueError("protocol configuration is not the frozen C-EP3 vector")


def _public_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _public_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _public_keys(child)


def validate_observation(observation: dict[str, Any]) -> None:
    if observation.get("schema_version") != SCHEMA:
        raise ValueError("unexpected observation schema")
    if observation.get("evidence_class") != "OBSERVED_PUBLIC_NUMERICAL_PROBE":
        raise ValueError("incorrect evidence class")
    if observation.get("qualified") is not False:
        raise ValueError("component observation may not claim qualification")
    if observation.get("integrated_exam") is not False:
        raise ValueError("component observation may not claim an integrated exam")
    run_id = observation.get("run_id")
    if not isinstance(run_id, str) or len(run_id) != 64:
        raise ValueError("run_id must be a SHA-256 hex digest")
    try:
        int(run_id, 16)
    except ValueError as exc:
        raise ValueError("run_id must be a SHA-256 hex digest") from exc
    operations = observation.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("observation has no operations")
    seen: set[str] = set()
    for operation in operations:
        name = operation.get("name")
        if not isinstance(name, str) or name in seen:
            raise ValueError("operation names must be unique")
        seen.add(name)
        if operation.get("unit") != "ns":
            raise ValueError("operation duration unit must be ns")
        for field in ("wall_elapsed", "process_elapsed"):
            value = operation.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"invalid {field}")
        if operation.get("outcome") not in {"SUCCEEDED", "FAILED_RETAINED"}:
            raise ValueError("invalid operation outcome")
    counts = observation.get("counts", {})
    for key, value in counts.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"invalid count {key}")
    for quantity in observation.get("unknown_quantities", []):
        if quantity.get("value") is not None or not quantity.get("missing_reason"):
            raise ValueError("unknown quantities must remain null with a reason")
    forbidden = FORBIDDEN_PUBLIC_KEYS.intersection(_public_keys(observation))
    if forbidden:
        raise ValueError(
            f"public observation exposes forbidden keys: {sorted(forbidden)}"
        )
    encoded = json.dumps(observation, allow_nan=False)
    if not encoded:
        raise ValueError("empty observation")


def record_operation(name: str, action: Any, operations: list[dict[str, Any]]) -> Any:
    wall_start = time.perf_counter_ns()
    process_start = time.process_time_ns()
    try:
        result = action()
    except Exception as exc:
        operations.append(
            {
                "name": name,
                "unit": "ns",
                "wall_elapsed": time.perf_counter_ns() - wall_start,
                "process_elapsed": time.process_time_ns() - process_start,
                "outcome": "FAILED_RETAINED",
                "failure_type": type(exc).__name__,
                "failure_message": str(exc),
            }
        )
        raise
    operations.append(
        {
            "name": name,
            "unit": "ns",
            "wall_elapsed": time.perf_counter_ns() - wall_start,
            "process_elapsed": time.process_time_ns() - process_start,
            "outcome": "SUCCEEDED",
        }
    )
    return result


def extract_verified_source(archive: Path, target: Path) -> Path:
    prefix, infos = _archive_layout(archive)
    available = {name[len(prefix) :] for name in infos if name.startswith(prefix)}
    missing = REQUIRED_EXTRACT - available
    if missing:
        raise ValueError(f"archive lacks required probe files: {sorted(missing)}")
    root = target / "verified_workbench"
    root.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as bundle:
        for relative in sorted(REQUIRED_EXTRACT):
            destination = root.joinpath(*PurePosixPath(relative).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with (
                bundle.open(prefix + relative) as source,
                destination.open("wb") as sink,
            ):
                shutil.copyfileobj(source, sink)
    return root


@contextmanager
def imported_source(root: Path) -> Iterator[dict[str, Any]]:
    original = list(sys.path)
    old_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "carbon_challenge" or name.startswith("carbon_challenge.")
    }
    sys.path.insert(0, str(root))
    for name in old_modules:
        sys.modules.pop(name, None)
    try:
        yield {
            "burgers": importlib.import_module("carbon_challenge.burgers"),
            "contracts": importlib.import_module("carbon_challenge.contracts"),
            "measurement": importlib.import_module("carbon_challenge.measurement"),
            "numerics": importlib.import_module("carbon_challenge.numerics"),
        }
    finally:
        for name in list(sys.modules):
            if name == "carbon_challenge" or name.startswith("carbon_challenge."):
                sys.modules.pop(name, None)
        sys.modules.update(old_modules)
        sys.path[:] = original


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _environment() -> dict[str, Any]:
    import numpy
    import pydantic
    import scipy

    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "pydantic": pydantic.__version__,
        "thread_environment": {
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "accelerator_time_observed": False,
    }


def run_probe(archive: Path, protocol_path: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(
            "output directory already exists; refuse duplicate import/run"
        )
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    operations: list[dict[str, Any]] = []
    archive_result = record_operation(
        "archive_verification", lambda: verify_archive(archive), operations
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        source_root = record_operation(
            "source_extraction",
            lambda: extract_verified_source(archive, output_dir / "source_stage"),
            operations,
        )
        modules_context = imported_source(source_root)
        modules = record_operation(
            "source_import_initialization", modules_context.__enter__, operations
        )
        try:
            import numpy as np

            burgers = modules["burgers"]
            contracts = modules["contracts"]
            measurement = modules["measurement"]
            numerics = modules["numerics"]
            config = protocol["configuration"]

            def materialize() -> (
                tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]
            ):
                selector = protocol["case"]["selector"]
                archive_audit = json.loads(
                    (source_root / "evidence/reference_audit.json").read_text(
                        encoding="utf-8"
                    )
                )
                case = archive_audit["records"][0]["case"]
                claimed_digest = case.get("case_digest")
                digest_input = dict(case)
                digest_input.pop("case_digest", None)
                computed_digest = contracts.digest(digest_input)
                if claimed_digest != protocol["case"]["expected_case_digest"]:
                    raise ValueError("archived selected case digest mismatch")
                if computed_digest != claimed_digest:
                    raise ValueError("archived case content does not match its digest")
                generated_case = burgers.draw(**selector)
                case_replay = {
                    "archived_case_digest": claimed_digest,
                    "archived_content_digest": computed_digest,
                    "current_environment_generated_case_digest": generated_case[
                        "case_digest"
                    ],
                    "matches_archived_case": generated_case == case,
                    "status": (
                        "MATCHES_ARCHIVE"
                        if generated_case == case
                        else "SOURCE_SUPPORTED_ENVIRONMENT_REPLAY_MISMATCH_RETAINED"
                    ),
                }
                payload = burgers.payload(
                    case, config["phase_intervals"], config["query_grid"]
                )
                dense_payload = burgers.payload(
                    case,
                    config["refinement_phase_intervals"],
                    config["query_grid"] * 2,
                )
                return case, payload, dense_payload, case_replay

            case, payload, dense_payload, case_replay = record_operation(
                "case_materialization", materialize, operations
            )

            def primary() -> tuple[Any, dict[str, Any]]:
                return numerics.etd(
                    payload,
                    config["reference_grid"],
                    cfl=config["reference_cfl"],
                    time_fraction=config["reference_time_fraction"],
                )

            cold, cold_info = record_operation("primary_cold", primary, operations)
            warm_outputs = []
            warm_infos = []
            for index in range(config["warm_primary_repetitions"]):
                output, info = record_operation(
                    f"primary_warm_{index + 1}", primary, operations
                )
                warm_outputs.append(output)
                warm_infos.append(info)
            if not all(np.array_equal(cold, output) for output in warm_outputs):
                raise ValueError("repeated primary outputs differ")

            def refinement() -> tuple[Any, dict[str, Any]]:
                return numerics.etd(
                    dense_payload,
                    config["refinement_grid"],
                    cfl=config["refinement_cfl"],
                    time_fraction=config["refinement_time_fraction"],
                )

            fine, fine_info = record_operation("refinement", refinement, operations)
            stride = config["refinement_phase_intervals"] // config["phase_intervals"]
            fine_same = fine[::stride, ::2]
            indices = np.asarray(config["witness_time_indices"], dtype=int)
            times = payload["requested_times"][indices]
            x = burgers.grid(config["witness_space_points"])
            witness_outputs = []
            for nodes in config["witness_nodes"]:
                witness_outputs.append(
                    record_operation(
                        f"witness_{nodes}",
                        lambda nodes=nodes: numerics.cole_hopf(
                            case, times, x, nodes=nodes
                        ),
                        operations,
                    )
                )

            def diagnostics() -> dict[str, Any]:
                source_config = json.loads(
                    (source_root / "config/gauntlet.json").read_text(encoding="utf-8")
                )
                source_intake = json.loads(
                    (source_root / "config/burgers_dynamics.json").read_text(
                        encoding="utf-8"
                    )
                )
                tolerances = source_intake["tolerances"]

                class Tolerances:
                    pass

                tolerance_object = Tolerances()
                for key, value in tolerances.items():
                    setattr(tolerance_object, key, value)
                comparison = measurement.compare(
                    cold,
                    fine_same,
                    payload["requested_times"],
                    case,
                    tolerance_object,
                )
                coarse_qoi, _, _ = measurement.qois(
                    cold, payload["requested_times"], case["nu"]
                )
                fine_qoi, _, _ = measurement.qois(
                    fine, dense_payload["requested_times"], case["nu"]
                )
                energy_scale = math.pi * case["A"] ** 2
                qoi_scales = [
                    tolerances["compression_relative_with_floor"]
                    * max(fine_qoi["compression"], case["A"] * case["krms"]),
                    tolerances["dissipation_relative_with_floor"]
                    * max(fine_qoi["peak_dissipation"], energy_scale / case["tc"]),
                    tolerances["half_time_over_characteristic_time"] * case["tc"],
                ]
                qoi_resolution = [
                    abs(coarse_qoi[key] - fine_qoi[key]) / scale
                    for key, scale in zip(
                        ("compression", "peak_dissipation", "clipped_half_time"),
                        qoi_scales,
                    )
                ]
                sample_stride = config["query_grid"] // config["witness_space_points"]
                witness = []
                previous = None
                for nodes, output in zip(config["witness_nodes"], witness_outputs):
                    witness.append(
                        {
                            "nodes": nodes,
                            "max_absolute_over_A_against_refinement": float(
                                np.max(
                                    abs(output - fine_same[indices, ::sample_stride])
                                )
                                / case["A"]
                            ),
                            "successive_change_over_A": (
                                None
                                if previous is None
                                else float(np.max(abs(output - previous)) / case["A"])
                            ),
                        }
                    )
                    previous = output
                coarse_physics = measurement.physics(
                    cold, payload["requested_times"], case
                )
                return {
                    "outputs_finite": bool(
                        np.isfinite(cold).all()
                        and np.isfinite(fine).all()
                        and all(np.isfinite(output).all() for output in witness_outputs)
                    ),
                    "primary_repetitions_byte_equal": True,
                    "primary_shape": list(cold.shape),
                    "refinement_shape": list(fine.shape),
                    "primary_method": cold_info,
                    "warm_methods": warm_infos,
                    "refinement_method": fine_info,
                    "spatial_time_solution_refinement_normalized_errors": comparison[
                        "normalized_errors"
                    ],
                    "coarse_vs_refinement_qoi_tolerance_units": qoi_resolution,
                    "cole_hopf_witness": witness,
                    "coarse_physics": coarse_physics,
                    "source_proposed_physics_status": measurement.physics_diagnostic_status(
                        coarse_physics, source_config["physics_proposed_limits"]
                    ),
                    "source_limits_qualified": False,
                    "case_generator_replay": case_replay,
                }

            diagnostic = record_operation("diagnostics", diagnostics, operations)
            if not diagnostic["outputs_finite"]:
                raise FloatingPointError("probe produced nonfinite output")
            arrays_path = output_dir / "reference_arrays_v1.npz"

            def serialize() -> None:
                np.savez_compressed(arrays_path, primary=cold, refinement=fine)

            record_operation("serialization", serialize, operations)

            def retrieve() -> bool:
                with np.load(arrays_path, allow_pickle=False) as stored:
                    return bool(
                        np.array_equal(stored["primary"], cold)
                        and np.array_equal(stored["refinement"], fine)
                    )

            round_trip = record_operation("retrieval", retrieve, operations)
            if not round_trip:
                raise ValueError("serialized arrays failed round-trip verification")
        finally:
            modules_context.__exit__(None, None, None)

        protocol_hash = sha256_file(protocol_path)
        run_id = hashlib.sha256(
            (
                SCHEMA
                + "\0"
                + archive_result["archive_sha256"]
                + "\0"
                + protocol_hash
                + "\0"
                + platform.platform()
                + "\0"
                + str(time.time_ns())
            ).encode("utf-8")
        ).hexdigest()
        observation = {
            "schema_version": SCHEMA,
            "run_id": run_id,
            "evidence_class": "OBSERVED_PUBLIC_NUMERICAL_PROBE",
            "qualified": False,
            "integrated_exam": False,
            "source": archive_result,
            "protocol_sha256": protocol_hash,
            "case": {
                "case_digest": protocol["case"]["expected_case_digest"],
                "cell": protocol["case"]["selector"]["cell"],
                "ordinal": protocol["case"]["selector"]["ordinal"],
                "role": protocol["case"]["selector"]["role"],
                "family": case["family"],
                "regime": case["regime"],
                "equation": "periodic unforced positive-viscosity 1D Burgers",
            },
            "configuration": protocol["configuration"],
            "environment": _environment(),
            "operations": operations,
            "counts": {
                "distinct_public_cases": 1,
                "primary_reference_calls": 3,
                "primary_cold_calls": 1,
                "primary_warm_repeat_calls": 2,
                "refinement_calls": 1,
                "independent_witness_calls": 2,
                "physical_reference_attempts": 6,
                "integrated_candidate_jobs": 0,
                "provider_calls": 0,
                "official_evaluations": 0,
            },
            "diagnostics": diagnostic,
            "artifacts": {
                "private_arrays_file": arrays_path.name,
                "private_arrays_sha256": sha256_file(arrays_path),
                "round_trip_equal": True,
            },
            "unknown_quantities": [
                {
                    "name": "authorized_jax_reconstruction_work",
                    "value": None,
                    "missing_reason": "authorized immutable JAX source and interface absent",
                },
                {
                    "name": "compatible_miner_demand",
                    "value": None,
                    "missing_reason": "no eligible real submission trace exists",
                },
                {
                    "name": "variant_b_control_and_recovery_overhead",
                    "value": None,
                    "missing_reason": "Variant B is not implemented",
                },
                {
                    "name": "scientifically_adequate_reference_cost",
                    "value": None,
                    "missing_reason": "source methods and limits are not qualified",
                },
            ],
            "limitations": protocol["claim_limitations"],
        }
        validate_observation(observation)
        _write_json(output_dir / "public_observation_v1.json", observation)
        _write_json(
            output_dir / "environment_manifest_v1.json", observation["environment"]
        )
        checksums = {
            name: sha256_file(output_dir / name)
            for name in (
                "environment_manifest_v1.json",
                "public_observation_v1.json",
                "reference_arrays_v1.npz",
            )
        }
        _write_json(output_dir / "sha256sums_v1.json", checksums)
        shutil.rmtree(output_dir / "source_stage")
        return observation
    except Exception:
        failure = {
            "schema_version": SCHEMA,
            "evidence_class": "OBSERVED_PUBLIC_NUMERICAL_PROBE",
            "qualified": False,
            "integrated_exam": False,
            "operations": operations,
        }
        _write_json(output_dir / "failed_observation_v1.json", failure)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.archive, args.protocol, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
