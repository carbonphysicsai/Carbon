#!/usr/bin/env python3
"""Credential-free native macOS diagnostics and one-update C-02 smoke run."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))


def _doctor() -> int:
    report: dict[str, object] = {
        "schema": "carbon.c02.macos-doctor.v1",
        "platform": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_ok": sys.version_info[:2] == (3, 11),
        "disk_free_gib": round(shutil.disk_usage(Path.cwd()).free / 2**30, 2),
        "credentials_required": False,
    }
    try:
        memory = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            text=True,
        )
        report["memory_gib"] = round(int(memory.stdout.strip()) / 2**30, 2)
    except (OSError, ValueError, subprocess.CalledProcessError):
        report["memory_gib"] = None
    try:
        import jax
        import jaxlib
        import numpy
        import scipy

        report["runtime"] = {
            "jax": jax.__version__,
            "jaxlib": jaxlib.__version__,
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "backend": jax.default_backend(),
        }
    except ImportError as error:
        report["runtime_error"] = error.name
    ok = (
        report["platform"] == "Darwin"
        and report["machine"] == "arm64"
        and report["python_ok"] is True
        and report["disk_free_gib"] >= 5.0
        and "runtime_error" not in report
    )
    report["status"] = "READY" if ok else "NOT_READY"
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if ok else 2


def _smoke() -> int:
    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
        load_inference,
        save_checkpoint,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.config import (
        ModelConfig,
        TaskConfig,
        TrainConfig,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
    from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer

    points = 16
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack((np.sin(2 * np.pi * positions), np.cos(2 * np.pi * positions)))
    times = np.array([[0.05, 0.1], [0.05, 0.1]], dtype=np.float64)
    # Preserve [case,time,point] ordering explicitly.
    solution = np.stack((initial * 0.98, initial * 0.96), axis=1)
    data = Trajectories(
        initial,
        np.array([0.01, 0.02]),
        times,
        solution,
        positions,
        "train",
        "carbon_c02_native_smoke",
    )
    trainer = Trainer(
        ModelConfig(width=8, depth=1, heads=2, n_modes=8),
        TaskConfig(),
        TrainConfig(steps=1, warmup_steps=0, batch_size=2),
        data,
        runtime_key_material=bytes(range(32)),
    )
    started = time.perf_counter()
    trainer.fit()
    with tempfile.TemporaryDirectory(prefix="carbon-c02-smoke-") as directory:
        checkpoint = Path(directory) / "checkpoint"
        save_checkpoint(trainer, checkpoint)
        predictor, parameters, _ = load_inference(checkpoint)
        prediction = predictor(
            parameters,
            jnp.asarray(initial, jnp.float32),
            jnp.asarray(data.viscosity, jnp.float32),
            jnp.asarray(times[:, 0], jnp.float32),
            jnp.asarray(positions, jnp.float32),
        )
        jax.block_until_ready(prediction)
    result = {
        "schema": "carbon.c02.macos-smoke.v1",
        "status": "PASS",
        "steps": int(trainer.state.step),
        "compile_seconds": trainer.timing["compile_seconds"],
        "train_execution_seconds": trainer.timing["train_execution_seconds"],
        "total_seconds": time.perf_counter() - started,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _repeat_demo(output_directory: Path) -> int:
    """Run the fixed three-member FNO and DeepONet development fixtures."""
    import uuid
    from dataclasses import replace

    import numpy as np

    fixture_path = _REPOSITORY_ROOT / "tests" / "cpu"
    if str(fixture_path) not in sys.path:
        sys.path.insert(0, str(fixture_path))
    from c02_fixtures import compile_c02_plan

    from carbon.execution import ExecutionAttemptRef
    from carbon.fees import SubmissionId
    from carbon.reconstruction import (
        DevelopmentReplica,
        PublicTrainingArchive,
        development_replicate_digest,
        development_request_digest,
        freeze_development_repeat_plan,
        run_development_repeats,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
    from carbon.resource_policy import (
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        RESOURCE_POLICY_SCHEMA_VERSION,
        BoundReconstructionReplicate,
        ReconstructionReplicateIdentity,
        ResearchResourcePolicyRef,
        ResourceClassRef,
    )
    from carbon.seeding import DerivedSeed

    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    points = 16
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack(
        (
            np.sin(2 * np.pi * positions),
            np.cos(2 * np.pi * positions),
            np.sin(4 * np.pi * positions) * 0.5,
            np.cos(4 * np.pi * positions) * 0.5,
        )
    )
    times = np.broadcast_to(np.array([0.05, 0.1]), (4, 2)).copy()
    data = Trajectories(
        initial,
        np.array([0.01, 0.02, 0.015, 0.025]),
        times,
        np.stack((initial * 0.98, initial * 0.96), axis=1),
        positions,
        "train",
        "carbon_c02_authored_repeat_demo_not_pde_truth",
    )
    archive_path = output_directory / "public-authored-train.npz"
    if not archive_path.exists():
        data.save(archive_path)
    archive = PublicTrainingArchive.from_file(
        archive_path, provenance="c02_authored_numerical_fixture"
    )
    request = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": data.times[:1, ::-1],
        "positions": data.positions,
    }
    request_digest = development_request_digest(request)
    reports = {}
    for backbone_index, backbone in enumerate(("fno", "deeponet"), start=6):
        plan = compile_c02_plan(output_directory / "authoring", backbone=backbone)
        policy = ResearchResourcePolicyRef(
            plan.challenge_key,
            "c02_development_repeat_policy",
            "1.0",
            RESOURCE_POLICY_SCHEMA_VERSION,
            RESOURCE_POLICY_CANONICALIZATION_PROFILE,
            "sha256:" + "2" * 64,
        )
        resource = ResourceClassRef(
            plan.challenge_key,
            "c02_local_cpu_fixture",
            "1.0",
            RESOURCE_POLICY_SCHEMA_VERSION,
            RESOURCE_POLICY_CANONICALIZATION_PROFILE,
            "sha256:" + "3" * 64,
        )
        seeds = {
            "replica-a": DerivedSeed(bytes(range(32))),
            "replica-b": DerivedSeed(bytes(reversed(range(32)))),
            "replica-cancelled": DerivedSeed(bytes([7]) * 32),
        }
        members = []
        for replica_index, (replica_id, seed) in enumerate(seeds.items(), start=1):
            execution = ExecutionAttemptRef(
                SubmissionId(
                    str(
                        uuid.UUID(
                            f"{backbone_index}2345678-1234-4234-8234-{replica_index:012d}"
                        )
                    )
                ),
                1,
            )
            randomness_digest = (
                "sha256:" + hashlib.sha256(seed.as_backend_bytes()).hexdigest()
            )
            placeholder = BoundReconstructionReplicate(
                ReconstructionReplicateIdentity(
                    plan.challenge_key,
                    plan.to_ref(),
                    policy,
                    resource,
                    replica_id,
                    "sha256:" + "0" * 64,
                )
            )
            digest = development_replicate_digest(
                binding=placeholder,
                execution_ref=execution,
                randomness_digest=randomness_digest,
                training_data_digest=archive.content_digest,
                request_digest=request_digest,
            )
            members.append(
                DevelopmentReplica(
                    BoundReconstructionReplicate(
                        replace(placeholder.replicate_identity, replicate_digest=digest)
                    ),
                    execution,
                    randomness_digest,
                    replica_id == "replica-cancelled",
                )
            )
        frozen = freeze_development_repeat_plan(
            plan_id=f"c02-{backbone}-fixed-repeat-demo",
            construction_plan_digest=plan.to_ref().content_digest,
            training_data_digest=archive.content_digest,
            request_digest=request_digest,
            replicas=tuple(members),
        )
        reports[backbone] = run_development_repeats(
            frozen,
            construction_plan=plan,
            training_archive=archive,
            derived_seeds=seeds,
            request=request,
            output_directory=output_directory / backbone,
        )
    print(
        json.dumps(
            {
                "schema": "carbon.c02.macos-repeat-demo.v1",
                "output_directory": str(output_directory),
                "reports": reports,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "repeat-demo":
        return _repeat_demo(Path(sys.argv[2]))
    if len(sys.argv) != 2 or sys.argv[1] not in {"doctor", "smoke"}:
        print(
            "usage: jax_macos_diagnostic.py {doctor|smoke|repeat-demo OUTPUT_DIR}",
            file=sys.stderr,
        )
        return 2
    return _doctor() if sys.argv[1] == "doctor" else _smoke()


if __name__ == "__main__":
    raise SystemExit(main())
