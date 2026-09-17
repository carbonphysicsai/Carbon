"""Prospective, explicitly granted Julia diagnostics on one public TRAIN case.

This is a consumer of the existing task controller, C-04 worker and campaign
ledger. It grants no execution by installation and changes no primary reference,
training labels, historical catalogue, grader or scientific qualification.
"""

from __future__ import annotations

import json
import math
import time

from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.generators.burgers_dynamics import PublicDevelopmentRole, requested_times
from carbon.reconstruction.worker.model import OUTPUT_BYTES
from carbon.reference_runtime.julia.adapter import (
    julia_crosscheck_request,
    julia_environment_digest,
)
from carbon.reference_runtime.julia.protocol import METHOD_ID
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    runtime_environment_digest,
)

from .profile import canonical, digest
from .research_admission import MANIFEST, verify_cleanup_owner
from .research_carrier import ACTIVE_TASK, _cancel_path, _check_cancel, _numerical_lease
from .research_catalog import public_catalog
from .research_data import PublicReferenceData, decode_public_case
from .research_material import PublicMaterial, capabilities
from .research_profile import public_cases
from .research_workspace import ResearchWorkspace

MATERIAL = "julia_burgers_study_v1"
DIAGNOSTICS = frozenset(
    {
        "method",
        "language",
        "runtime_version",
        "units",
        "coarse_points",
        "fine_points",
        "coarse_steps",
        "fine_steps",
        "coarse_internal_mean_drift",
        "fine_internal_mean_drift",
        "refinement_rms",
        "refinement_max",
        "completed_horizon",
        "solver_seconds",
        "julia_cumulative_allocated_bytes",
        "refinement_interpretation",
    }
)


def julia_burgers_scope(image, role_root):
    """Expected grant bytes; constructing this document is not authorization."""
    return {
        "schema": "carbon.public-julia-study.scope.v1",
        "material": MATERIAL,
        "method": METHOD_ID,
        "environment": julia_environment_digest(),
        "image": image.image_id,
        "public_train_digest": digest(
            canonical(public_cases(role_root, "research-train"))
        ),
        "case_selector": "first-public-train-record",
        "units": "dimensionless",
        "output_points": 64,
        "intervals_per_phase": 4,
        "role": "DEVELOPMENT_CROSSCHECK",
        "official_eligible": False,
        "training_support_eligible": False,
    }


class PublicJuliaStudy:
    def __init__(self, data, *, cleanup=False):
        if type(data) is not PublicReferenceData or data.phase != "research":
            raise ValueError("public research data composition required")
        self.data = data
        self.scope = julia_burgers_scope(data.image, data.role_root)
        self._authorize(cleanup=cleanup)

    def _authorize(self, *, cleanup=False):
        data = self.data
        with data.ledger.db() as db:
            row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
        if row is None:
            raise ValueError("prospectively frozen Julia campaign required")
        manifest = json.loads(row[0])
        if (
            manifest.get("schema") != MANIFEST
            or manifest.get("owner") != data.owner
            or manifest.get("runtime", {}).get("scientific_tasks") != [self.scope]
            or self.scope != julia_burgers_scope(data.image, data.role_root)
        ):
            raise ValueError("explicit prospective Julia scope required")
        # Rechecks the pinned operator grant, expiry, principal and root. Budget
        # and live ownership are checked transactionally by the same ledger.
        if cleanup:
            verify_cleanup_owner(data.ledger, data.owner)
        else:
            data.ledger._grant(manifest)

    def __call__(self, workspace):
        self._authorize()
        data = self.data
        if (
            type(workspace) is not ResearchWorkspace
            or workspace.ledger is not data.ledger
            or workspace.owner != data.owner
            or ACTIVE_TASK.get() is None
        ):
            raise ValueError("owned admitted research task required")
        task = ACTIVE_TASK.get()
        _check_cancel(data.ledger, data.owner, task)
        case = decode_public_case(public_cases(data.role_root, "research-train")[0])
        if case.coordinates.role is not PublicDevelopmentRole.TRAIN:
            raise ValueError("registered public TRAIN case required")
        source = build_reference_request(
            case,
            BurgersReferenceRole.CANDIDATE_PRIMARY,
            output_points=64,
            requested_times=requested_times(case, 4),
            environment_digest=runtime_environment_digest(),
        )
        request = julia_crosscheck_request(source, units="dimensionless")
        identity = "julia-study-" + request.request_digest[7:]
        resources = {
            "reference_trajectories": 2,
            "reference_invocations": 2,
            "numerical_milliseconds": 720000,
            "retained_bytes": 3 * OUTPUT_BYTES,
        }
        with _numerical_lease(data.ledger):
            admitted = data.ledger.reserve(
                identity,
                owner=data.owner,
                phase="research",
                request={
                    "reference": request.document(),
                    "scope": self.scope,
                    "profile": data.profile_digest,
                },
                resources=resources,
            )
            if not admitted["dispatch"]:
                if admitted["state"] != "SUCCEEDED":
                    raise ValueError("Julia work requires reconciliation; no retry")
                record = admitted["result"]
            else:
                started = time.monotonic()
                storage_before = data.ledger.check_storage()
                # Exceptions retain the complete reservation. C-04 owns actual
                # cancellation, container removal and uncertainty journals.
                result = data.controller.execute(
                    request,
                    cancelled=lambda: _cancel_path(
                        data.ledger, data.owner, task
                    ).exists(),
                )
                supported = result.result.outcome is ReferenceRunOutcome.SUPPORTED
                record = {
                    "request_digest": request.request_digest,
                    "snapshot": result.snapshot_path.relative_to(
                        data.ledger.root
                    ).as_posix(),
                    "snapshot_digest": result.snapshot_digest,
                    "artifact_digest": result.result.artifact_digest,
                    "shape": list(result.result.shape) if supported else None,
                    "outcome": result.result.outcome.value,
                    "diagnostics": {
                        k: v for k, v in result.result.diagnostics if k in DIAGNOSTICS
                    },
                    "controls": result.controls,
                    "resources": result.resources,
                    "timings": result.timings,
                }
                if supported:
                    payload = (result.snapshot_path / "solution.f64le").read_bytes()
                    record["payload_digest"] = digest(payload)
                    self._export(record, request, workspace)
                actual = {
                    **resources,
                    "numerical_milliseconds": math.ceil(
                        (time.monotonic() - started) * 1000
                    ),
                    "retained_bytes": max(
                        0, data.ledger.check_storage() - storage_before
                    ),
                }
                record["accounting"] = actual
                data.ledger.finish(
                    identity,
                    owner=data.owner,
                    state="SUCCEEDED" if supported else "FAILED_INFRA",
                    actual=actual,
                    result=record,
                )
                if not supported:
                    raise ValueError(
                        "Julia reference diagnostic failed; candidate not judged"
                    )
            output = self._export(record, request, workspace)
            return {**output, "accounting": record["accounting"]}

    def _export(self, record, request, workspace):
        path = self.data.ledger.root / record["snapshot"] / "solution.f64le"
        if path.is_symlink() or not path.resolve().is_relative_to(
            self.data.root.resolve()
        ):
            raise ValueError("Julia artifact path conflict")
        payload = path.read_bytes()
        if (
            record["request_digest"] != request.request_digest
            or record["shape"] != [13, 64]
            or len(payload) != 13 * 64 * 8
            or digest(payload) != record["payload_digest"]
        ):
            raise ValueError("Julia artifact association conflict")
        name = "julia-study-" + request.request_digest[7:23]
        workspace.put(name + ".f64le", payload)
        metadata = {
            "schema": "carbon.public-julia-study.result.v1",
            "method": METHOD_ID,
            "language": "julia",
            "backend": "cpu",
            "request_digest": request.request_digest,
            "environment": request.environment_digest,
            "case_digest": request.case_digest,
            "scope_digest": digest(canonical(self.scope)),
            "solution": name + ".f64le",
            "payload_digest": record["payload_digest"],
            "shape": [13, 64],
            "axes": ["time", "space"],
            "dtype": "little-endian-float64",
            "array_order": "C",
            "units": "dimensionless",
            "times": list(request.requested_times),
            "positions": list(request.spatial_points),
            "diagnostics": record["diagnostics"],
            "reference_trajectories": 2,
            "reference_invocations": 2,
            "adaptive_learning_material": True,
            "official_eligible": False,
            "scientifically_qualified": False,
            "training_support_eligible": False,
            "reference_status": "DIAGNOSTIC_ONLY; accepted primary unchanged",
        }
        workspace.put(name + ".json", canonical(metadata))
        return {**metadata, "metadata": name + ".json"}


class JuliaPublicMaterial:
    """Exact trusted opt-in consumer; legacy material behaviour stays unchanged."""

    def __init__(self, primary, study):
        if type(primary) is not PublicMaterial or type(study) is not PublicJuliaStudy:
            raise ValueError("registered public material composition required")
        if primary.data is not study.data:
            raise ValueError("public material consumer binding differs")
        self.primary, self.study = primary, study

    def catalogue(self):
        return {
            "schema": "carbon.autoresearch.public-scaffold.julia.v1",
            "recipes": public_catalog(),
            "scientific_tasks": [self.study.scope],
        }

    def __call__(self, name, workspace):
        if name == MATERIAL:
            return self.study(workspace)
        if name == "capabilities":
            self.study._authorize()
            value = {
                **capabilities(),
                "scientific_tasks": [self.study.scope],
                "scientific_task_usage": {
                    "kind": "workspace",
                    "action": "public_material",
                    "arguments": {"name": MATERIAL},
                },
                "public_scaffold_catalogue_digest": digest(canonical(self.catalogue())),
            }
            name = "capabilities-julia-v1.json"
            payload = canonical(value)
            workspace.put(name, payload)
            return {"document": value, "file": name, "digest": digest(payload)}
        return self.primary(name, workspace)
