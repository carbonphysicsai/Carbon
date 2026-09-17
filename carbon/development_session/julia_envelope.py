"""Two exact public cases through existing Julia controller, tasks and ledger.

The operator grants the ordered cases prospectively. This finite comparison has
no sampling law, population claim, grading authority or private-data permission.
"""

from __future__ import annotations

import math
import time

from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.generators.burgers_dynamics import PublicDevelopmentRole, requested_times
from carbon.reconstruction.worker.model import OUTPUT_BYTES
from carbon.reference_runtime.julia.adapter import julia_crosscheck_request
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    runtime_environment_digest,
)

from .julia_research import (
    DIAGNOSTICS,
    JuliaPublicMaterial,
    PublicJuliaStudy,
    julia_burgers_scope,
)
from .profile import canonical, digest
from .research_carrier import ACTIVE_TASK, _cancel_path, _check_cancel, _numerical_lease
from .research_data import decode_public_case
from .research_profile import public_cases
from .research_sequences import SCOPE
from .research_workspace import ResearchWorkspace

MATERIAL = "julia_burgers_envelope_v2"
RESULT = "carbon.public-julia-envelope.result.v2"


def _requests(role_root):
    records = public_cases(role_root, "research-train")
    if len(records) < 2:
        raise ValueError("two frozen public TRAIN cases required")
    requests = []
    for record in records[:2]:
        case = decode_public_case(record)
        if case.coordinates.role is not PublicDevelopmentRole.TRAIN:
            raise ValueError("public TRAIN cases required")
        source = build_reference_request(
            case,
            BurgersReferenceRole.CANDIDATE_PRIMARY,
            output_points=64,
            requested_times=requested_times(case, 4),
            environment_digest=runtime_environment_digest(),
        )
        requests.append(julia_crosscheck_request(source, units="dimensionless"))
    if requests[0].case_digest == requests[1].case_digest:
        raise ValueError("two distinct public cases required")
    return requests


def julia_envelope_scope(image, role_root):
    """Expected bytes only; this factory grants no dispatch authority."""
    requests = _requests(role_root)
    return {
        **julia_burgers_scope(image, role_root),
        "schema": SCOPE,
        "material": MATERIAL,
        "case_selector": "first-two-public-train-records-in-order",
        "case_digests": [r.case_digest for r in requests],
        "request_digests": [r.request_digest for r in requests],
        "requested_times": [list(r.requested_times) for r in requests],
        "backend": "cpu",
        "axes": ["time", "space"],
        "shape": [13, 64],
        "dtype": "little-endian-float64",
        "array_order": "C",
        "comparison": "TWO_PUBLIC_DEVELOPMENT_CASES; no population claim",
    }


class PublicJuliaEnvelope:
    def __init__(self, study):
        if type(study) is not PublicJuliaStudy or study.envelope_scope is None:
            raise ValueError("explicit companion Julia study required")
        self.study, self.data, self.scope = study, study.data, study.envelope_scope
        self._authorize()

    def _authorize(self, *, cleanup=False):
        self.study._authorize(cleanup=cleanup)
        if self.scope != julia_envelope_scope(self.data.image, self.data.role_root):
            raise ValueError("public envelope source changed")

    def _export(self, record, request, workspace):
        # Preserve the typed per-case artifact format, with the v2 scope digest.
        return PublicJuliaStudy._export(
            self, record, request, workspace, name_prefix="julia-envelope-"
        )

    def __call__(self, workspace):
        self._authorize()
        data, ledger = self.data, self.data.ledger
        parent = ACTIVE_TASK.get()
        if (
            type(workspace) is not ResearchWorkspace
            or workspace.ledger is not ledger
            or workspace.owner != data.owner
            or parent is None
        ):
            raise ValueError("owned durable envelope task required")
        requests = _requests(data.role_root)
        resources = {
            "reference_trajectories": 2,
            "reference_invocations": 2,
            "numerical_milliseconds": 720000,
            "retained_bytes": 3 * OUTPUT_BYTES,
        }
        children = [
            {
                "request": {
                    "reference": r.document(),
                    "request_digest": r.request_digest,
                    "image": data.image.image_id,
                    "profile": data.profile_digest,
                },
                "resources": resources,
            }
            for r in requests
        ]
        with _numerical_lease(ledger):
            _check_cancel(ledger, data.owner, parent)
            ledger.reserve_sequence(
                parent, owner=data.owner, scope=self.scope, children=children
            )
            try:
                for ordinal, request in enumerate(requests):
                    state = ledger.sequence_status(parent, owner=data.owner)[
                        "children"
                    ][ordinal]["state"]
                    if state == "SUCCEEDED":
                        continue
                    if state != "HELD":
                        raise ValueError(
                            "envelope child requires reconciliation; no retry"
                        )
                    _check_cancel(ledger, data.owner, parent)
                    ledger.checkpoint()
                    child = ledger.claim_sequence_child(
                        parent, owner=data.owner, ordinal=ordinal
                    )
                    self._execute(workspace, request, child, parent)
                ledger.settle_sequence(parent, owner=data.owner)
            except BaseException:
                ledger.cancel_sequence_held(parent, owner=data.owner)
                try:
                    ledger.settle_sequence(parent, owner=data.owner)
                except ValueError:
                    # A claimed worker with unknown consumption stays reserved.
                    pass
                raise
        return self.projection(parent, workspace)

    def _execute(self, workspace, request, child, parent):
        data, ledger = self.data, self.data.ledger
        started, before = time.monotonic(), ledger.check_storage()
        result = data.controller.execute(
            request, cancelled=lambda: _cancel_path(ledger, data.owner, parent).exists()
        )
        supported = result.result.outcome is ReferenceRunOutcome.SUPPORTED
        journal = (
            data.controller.state_root
            / "launches"
            / (result.launch_digest[7:] + ".json")
        )
        record = {
            "request_digest": request.request_digest,
            "snapshot": result.snapshot_path.relative_to(ledger.root).as_posix(),
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
            "cleanup_receipt": {
                "path": journal.relative_to(ledger.root).as_posix(),
                "digest": digest(journal.read_bytes()),
            },
        }
        if supported:
            record["payload_digest"] = digest(
                (result.snapshot_path / "solution.f64le").read_bytes()
            )
            self._export(record, request, workspace)
        actual = {
            **child["resources"],
            "numerical_milliseconds": math.ceil((time.monotonic() - started) * 1000),
            "retained_bytes": max(0, ledger.check_storage() - before),
        }
        record["accounting"] = actual
        ledger.finish(
            child["id"],
            owner=data.owner,
            state="SUCCEEDED" if supported else "FAILED_INFRA",
            actual=actual,
            result=record,
        )
        if not supported:
            raise ValueError("Julia reference diagnostic failed; candidate not judged")

    def projection(self, parent, workspace):
        """Read retained partial evidence; never start a worker."""
        observed = self.data.ledger.sequence_status(parent, owner=self.data.owner)
        children = []
        for request, child in zip(
            _requests(self.data.role_root), observed["children"], strict=True
        ):
            result = (
                self._export(child["result"], request, workspace)
                if child["state"] == "SUCCEEDED"
                else None
            )
            children.append(
                {
                    "operation_id": child["id"],
                    "case_digest": request.case_digest,
                    "state": child["state"],
                    "reservation": child["reservation"],
                    "actual": child["actual"],
                    "result": result,
                }
            )
        return {
            "schema": RESULT,
            "parent": parent,
            "scope_digest": digest(canonical(self.scope)),
            "children": children,
            "official_eligible": False,
            "scientifically_qualified": False,
            "training_support_eligible": False,
        }


class JuliaEnvelopeMaterial:
    def __init__(self, primary):
        if type(primary) is not JuliaPublicMaterial:
            raise ValueError("exact Julia public material required")
        self.primary, self.study = primary, primary.study
        self.envelope = PublicJuliaEnvelope(self.study)

    def catalogue(self):
        return {
            **self.primary.catalogue(),
            "schema": "carbon.autoresearch.public-scaffold.julia.v2",
            "scientific_tasks": [self.study.scope, self.envelope.scope],
        }

    def __call__(self, name, workspace):
        if name == MATERIAL:
            return self.envelope(workspace)
        if name == "capabilities":
            self.envelope._authorize()
            value = self.primary(name, workspace)["document"]
            value = {
                **value,
                "scientific_tasks": [self.study.scope, self.envelope.scope],
                "public_scaffold_catalogue_digest": digest(canonical(self.catalogue())),
                "envelope_task_usage": {
                    "kind": "workspace",
                    "action": "public_material",
                    "arguments": {"name": MATERIAL},
                },
            }
            payload = canonical(value)
            workspace.put("capabilities-julia-v2.json", payload)
            return {
                "document": value,
                "file": "capabilities-julia-v2.json",
                "digest": digest(payload),
            }
        return self.primary(name, workspace)
