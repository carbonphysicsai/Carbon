"""Metered public TRAIN/practice access through the existing C-04 controller.

This service has no final-role selector. Its constructor binds one campaign;
the authenticated requester can only copy the two public role archives.
"""

from __future__ import annotations

import json
import math
import time

import numpy as np

from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.generators.burgers_dynamics import (
    DOMAIN_LENGTH,
    BurgersCaseCoordinates,
    BurgersDevelopmentCase,
    PublicDevelopmentRole,
    candidate_query,
    requested_times,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.worker.model import OUTPUT_BYTES, DevelopmentWorkerProfile
from carbon.reference_runtime.controller import IsolatedBurgersReferenceController
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    runtime_environment_digest,
)

from .data import write_once
from .profile import canonical, digest
from .research_carrier import _numerical_lease
from .research_profile import document, public_cases


def decode_public_case(value):
    """Round-trip the generator's exact public record, rejecting extra fields."""
    if type(value) is not dict:
        raise ValueError("public case record required")
    coordinates = BurgersCaseCoordinates(
        PublicDevelopmentRole(value["role"]),
        value["cell"],
        value["ordinal"],
        value["build"],
    )
    case = BurgersDevelopmentCase(
        value["parent_id"],
        coordinates,
        value["shape_family"],
        value["reynolds_regime"],
        value["amplitude"],
        value["mean"],
        value["k_rms"],
        value["reynolds_number"],
        value["viscosity"],
        value["characteristic_time"],
        value["horizon"],
        tuple(value["cosine_coefficients"]),
        tuple(value["sine_coefficients"]),
    )
    if canonical(case.public_record()) != canonical(value):
        raise ValueError("public case fields differ")
    return case


class PublicReferenceData:
    def __init__(self, *, ledger, owner, image, role_root):
        self.ledger, self.owner, self.image, self.role_root = (
            ledger,
            owner,
            image,
            role_root,
        )
        self.root = ledger.root / "public-reference-data"
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.profile_digest = digest(canonical(document()))
        self.controller = IsolatedBurgersReferenceController(
            state_root=self.root / "c04",
            image=image,
            worker_profile=DevelopmentWorkerProfile(
                self.profile_digest, digest(canonical(document()["final_worker"]))
            ),
        )

    def _reference(self, case):
        request = build_reference_request(
            case,
            BurgersReferenceRole.CANDIDATE_PRIMARY,
            output_points=64,
            requested_times=requested_times(case, 4),
            environment_digest=runtime_environment_digest(),
        )
        identity = "reference-" + request.request_digest[7:]
        resources = {
            "reference_trajectories": 1,
            "reference_invocations": 1,
            "numerical_milliseconds": 600000,
            "retained_bytes": 3 * OUTPUT_BYTES,
        }
        with _numerical_lease(self.ledger):
            admitted = self.ledger.reserve(
                identity,
                owner=self.owner,
                phase="research",
                request={
                    "reference": request.document(),
                    "image": self.image.image_id,
                    "profile": self.profile_digest,
                },
                resources=resources,
            )
            if not admitted["dispatch"]:
                if admitted["state"] != "SUCCEEDED":
                    raise ValueError(
                        "reference incomplete; reconcile without duplicate execution"
                    )
                record = admitted["result"]
            else:
                started = time.monotonic()
                storage_before = sum(
                    p.stat().st_size for p in self.root.rglob("*") if p.is_file()
                )
                # Any exception retains the full reservation and C-04 journals.
                # No alternate solver, automatic retry, or replacement case.
                result = self.controller.execute(request)
                supported = result.result.outcome is ReferenceRunOutcome.SUPPORTED
                relative = result.snapshot_path.relative_to(self.ledger.root).as_posix()
                record = {
                    "request_digest": request.request_digest,
                    "outcome": result.result.outcome.value,
                    "snapshot": relative,
                    "snapshot_digest": result.snapshot_digest,
                    "artifact_digest": result.result.artifact_digest,
                    "shape": list(result.result.shape) if supported else None,
                    "controls": result.controls,
                    "resources": result.resources,
                    "timings": result.timings,
                    "solver_invocations": 1,
                    "refinement_invocations": 0,
                    "scientifically_qualified": False,
                }
                if supported:
                    payload = (result.snapshot_path / "solution.f64le").read_bytes()
                    record["payload_digest"] = digest(payload)
                actual = {
                    **resources,
                    "numerical_milliseconds": math.ceil(
                        (time.monotonic() - started) * 1000
                    ),
                    "retained_bytes": max(
                        0,
                        sum(
                            p.stat().st_size
                            for p in self.root.rglob("*")
                            if p.is_file()
                        )
                        - storage_before,
                    ),
                }
                # Measure all retained C-04 staging, stream, snapshot and journal bytes.
                self.ledger.finish(
                    identity,
                    owner=self.owner,
                    state="SUCCEEDED" if supported else "FAILED_INFRA",
                    actual=actual,
                    result=record,
                )
                if not supported:
                    raise ValueError("reference failure; candidate not judged")
        path = self.ledger.root / record["snapshot"] / "solution.f64le"
        if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("reference artifact path conflict")
        payload = path.read_bytes()
        if (
            digest(payload) != record["payload_digest"]
            or record["request_digest"] != request.request_digest
            or record["shape"] != [13, 64]
        ):
            raise ValueError("reference artifact association conflict")
        return np.frombuffer(payload, dtype="<f8").reshape(13, 64), record

    def prepare(self, role):
        if role not in {"research-train", "research-validation"}:
            raise ValueError("final data is not a public reference capability")
        values = public_cases(self.role_root, role)
        source_digest = digest(canonical(values))
        archive = self.root / (role + ".npz")
        receipt = self.root / (role + "-archive.json")
        if receipt.exists():
            record = json.loads(receipt.read_bytes())
            if record["source_digest"] != source_digest or record[
                "archive_digest"
            ] != digest(archive.read_bytes()):
                raise ValueError("public archive identity conflict")
            # Each retained reference is still checked, even when preparation
            # is a replay. The ledger will not dispatch a completed request.
        initial, viscosity, times, solutions, records, scales = [], [], [], [], [], []
        for value in values:
            case = decode_public_case(value)
            solution, reference = self._reference(case)
            query = candidate_query(case, grid_points=64, intervals_per_phase=4)
            initial.append(query.initial_field)
            viscosity.append(query.viscosity)
            times.append(query.requested_times)
            solutions.append(solution)
            records.append(reference)
            scales.append(
                {
                    "amplitude": case.amplitude,
                    "characteristic_time": case.characteristic_time,
                    "role": case.coordinates.role.value,
                    "cell": case.coordinates.cell,
                }
            )
        if not archive.exists():
            Trajectories(
                np.array(initial),
                np.array(viscosity),
                np.array(times),
                np.array(solutions),
                np.arange(64, dtype=np.float64) * DOMAIN_LENGTH / 64,
                "train" if role == "research-train" else "validation",
                "carbon_c_auth1_c04_public_autoresearch",
                domain_length=DOMAIN_LENGTH,
            ).save(archive)
            archive.chmod(0o600)
        record = {
            "schema": "carbon.autoresearch.public-data.v1",
            "role": role,
            "source_digest": source_digest,
            "archive_digest": digest(archive.read_bytes()),
            "parents": len(values),
            "references": records,
            "scales": scales,
            "reference_uncertainty": "not measured by this primary-only research material",
            "adaptive_learning_material": True,
            "official_eligible": False,
        }
        write_once(receipt, canonical(record))
        return archive.read_bytes(), record

    def disclose(self, role, workspace):
        payload, record = self.prepare(role)
        name = role + ".npz"
        workspace.put(name, payload)
        workspace.put(
            role + "-cases.json", canonical(public_cases(self.role_root, role))
        )
        workspace.put(role + "-scales.json", canonical(record["scales"]))
        # Host paths, controller journals, private roots and final identities
        # never enter the miner projection.
        return {
            "schema": record["schema"],
            "role": role,
            "archive": name,
            "archive_digest": record["archive_digest"],
            "parents": record["parents"],
            "cases": role + "-cases.json",
            "scales": role + "-scales.json",
            "reference_uncertainty": record["reference_uncertainty"],
            "adaptive_learning_material": True,
            "official_eligible": False,
        }
