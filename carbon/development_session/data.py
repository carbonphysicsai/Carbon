"""Evaluator-owned C-AUTH1 generation and isolated C-04 TRAIN label preparation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.generators import burgers_dynamics
from carbon.generators.burgers_dynamics import (
    DOMAIN_LENGTH,
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    candidate_query,
    canonical_public_case_bytes,
    generate_development_case,
    requested_times,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
from carbon.reference_runtime.controller import IsolatedBurgersReferenceController
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    runtime_environment_digest,
)
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

from .budget import SessionBudget
from .contracts import authored_contracts, build_contracts
from .profile import CHALLENGE, canonical, digest, profile_digest, profile_document


def write_once(path: Path, payload: bytes):
    if path.is_symlink():
        raise ValueError("symlink rejected")
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("immutable session artifact conflict")
        return
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)


def context(root: Path) -> MockContext:
    entropy = root / "private-generation-entropy.bin"
    if not entropy.exists():
        write_once(entropy, os.urandom(32))
    if entropy.is_symlink() or entropy.stat().st_size != 32:
        raise ValueError("invalid generation material")
    # Generation pins are independently retained. A prospective adapter repair
    # must not silently redraw a cohort by changing a scoring/profile digest.
    pin_path = root / "generation-pin.json"
    if not pin_path.exists():
        write_once(
            pin_path,
            canonical(
                {
                    "generator_digest": digest(
                        Path(burgers_dynamics.__file__).read_bytes()
                    ),
                    "scoring_digest": profile_digest(),
                    "evaluation_binding_hex": profile_digest()[7:],
                }
            ),
        )
    if pin_path.is_symlink() or pin_path.stat().st_size > 1024:
        raise ValueError("invalid retained generation pin")
    value = json.loads(pin_path.read_bytes())
    if set(value) != {"generator_digest", "scoring_digest", "evaluation_binding_hex"}:
        raise ValueError("invalid generation pin fields")
    if value["generator_digest"] != digest(
        Path(burgers_dynamics.__file__).read_bytes()
    ):
        raise ValueError("generator implementation changed")
    pin = SeedPin(
        CHALLENGE,
        "c-auth1-1.0",
        value["generator_digest"],
        "unresolved-development-v1",
        value["scoring_digest"],
        EvaluationBinding(bytes.fromhex(value["evaluation_binding_hex"])),
    )
    return MockContext(MockEntropy(entropy.read_bytes()), pin)


def frozen_cases(root: Path):
    ctx = context(root)
    return tuple(
        generate_development_case(ctx, BurgersCaseCoordinates(role, cell, 0, 0))
        for role in PublicDevelopmentRole
        for cell in range(12)
    )


def freeze(root: Path, image_manifest: Path) -> dict[str, object]:
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("private absolute session directory required")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    image = load_image_identity(image_manifest)
    write_once(root / "profile.json", canonical(profile_document()))
    contracts = build_contracts()
    for index, obj in enumerate(authored_contracts()):
        write_once(root / f"authored-{index}.json", obj.canonical_bytes())
    write_once(root / "assembly.json", contracts.assembly.canonical_bytes())
    write_once(
        root / "catalog.json",
        contracts.catalog.canonical_bytes(candidate_assembly=contracts.assembly),
    )
    cases = frozen_cases(root)
    rows = []
    for case in cases:
        name = f"{case.coordinates.role.value.lower()}-{case.coordinates.cell:02d}"
        payload = canonical_public_case_bytes(case)
        write_once(root / f"{name}-case.json", payload)
        request = build_reference_request(
            case,
            BurgersReferenceRole.CANDIDATE_PRIMARY,
            output_points=64,
            requested_times=requested_times(case, 4),
            environment_digest=runtime_environment_digest(),
        )
        write_once(
            root / f"{name}-reference-request.json", canonical(request.document())
        )
        rows.append(
            {
                "name": name,
                "role": case.coordinates.role.value,
                "case_digest": digest(payload),
                "reference_request_digest": request.request_digest,
            }
        )
    manifest = {
        "schema": "carbon.burgers-session.frozen-cases.v1",
        "profile_digest": profile_digest(),
        "worker_image": image.image_id,
        "cases": rows,
    }
    write_once(root / "case-manifest.json", canonical(manifest))
    return manifest


def prepare(root: Path, image_manifest: Path) -> dict[str, object]:
    manifest = freeze(root, image_manifest)
    image = load_image_identity(image_manifest)
    controller = IsolatedBurgersReferenceController(
        state_root=root / "references",
        image=image,
        worker_profile=DevelopmentWorkerProfile(
            profile_digest(), digest(canonical(profile_document()["budget"]))
        ),
    )
    budget = SessionBudget(root / "budget.sqlite3")
    initial, viscosity, times, solutions, records = [], [], [], [], []
    for case, row in zip(frozen_cases(root), manifest["cases"], strict=True):
        request = build_reference_request(
            case,
            BurgersReferenceRole.CANDIDATE_PRIMARY,
            output_points=64,
            requested_times=requested_times(case, 4),
            environment_digest=runtime_environment_digest(),
        )
        record_path = root / f"{row['name']}-reference-result.json"
        if record_path.exists():
            record = json.loads(record_path.read_bytes())
            if record["request_digest"] != request.request_digest:
                raise ValueError("reference association conflict")
            payload = Path(record["solution_path"]).read_bytes()
            if digest(payload) != record["payload_digest"]:
                raise ValueError("reference artifact changed")
        else:
            result = budget.run_worker(
                request.request_digest,
                lambda request=request: controller.execute(request),
            )
            if result.result.outcome is not ReferenceRunOutcome.SUPPORTED:
                raise ValueError(
                    "reference failure; retain run and stop, no case replacement"
                )
            solution_path = result.snapshot_path / "solution.f64le"
            payload = solution_path.read_bytes()
            record = {
                "request_digest": request.request_digest,
                "artifact_digest": result.result.artifact_digest,
                "shape": list(result.result.shape),
                "solution_path": str(solution_path),
                "payload_digest": digest(payload),
                "snapshot_digest": result.snapshot_digest,
                "timings": result.timings,
                "resources": result.resources,
                "controls": result.controls,
            }
            write_once(record_path, canonical(record))
        records.append(record)
        if case.coordinates.role is PublicDevelopmentRole.TRAIN:
            query = candidate_query(case, grid_points=64, intervals_per_phase=4)
            initial.append(query.initial_field)
            viscosity.append(query.viscosity)
            times.append(query.requested_times)
            solutions.append(np.frombuffer(payload, dtype="<f8").reshape(13, 64))
        print(f"Reference retained: {row['name']}", flush=True)
    archive = root / "public-train.npz"
    if not archive.exists():
        data = Trajectories(
            np.array(initial),
            np.array(viscosity),
            np.array(times),
            np.array(solutions),
            np.arange(64, dtype=np.float64) * DOMAIN_LENGTH / 64,
            "train",
            "carbon_c_auth1_c04_train",
            domain_length=DOMAIN_LENGTH,
        )
        data.save(archive)
        archive.chmod(0o600)
    report = {
        "schema": "carbon.burgers-session.preparation.v1",
        "profile_digest": profile_digest(),
        "case_manifest_digest": digest(canonical(manifest)),
        "reference_count": len(records),
        "training_parent_count": len(initial),
        "train_archive_digest": digest(archive.read_bytes()),
        "accounting": budget.summary(),
        "agent_inference": False,
        "training_runs": 0,
        "chain_transactions": 0,
    }
    write_once(root / "preparation.json", canonical(report))
    return report
