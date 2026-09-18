"""One fixed advection material through the existing admitted public Julia carrier."""

from __future__ import annotations

import json
import math

from carbon.reference_runtime.julia.advection import (
    CASE_ID,
    METHOD_ID,
    AdvectionRequest,
    decode_outputs,
    public_definition,
    source,
    source_digest,
)

from .julia_analysis import (
    BOOTSTRAP,
    authored_julia_scope,
    authorize_julia,
    validate_julia_output,
)
from .profile import canonical, digest
from .research_admission import MANIFEST
from .research_carrier import ACTIVE_TASK, PRECHARGED_TRIAL, _run
from .research_material import capabilities
from .research_workspace import ResearchWorkspace

MATERIAL = "julia_advection_study_v1"


def advection_scope(image):
    request = AdvectionRequest(public_definition())
    return {
        "schema": "carbon.public-advection-study.scope.v1",
        "material": MATERIAL,
        "method": METHOD_ID,
        "case_id": CASE_ID,
        "definition": request.definition.content_digest,
        "request": request.digest,
        "source": source_digest(),
        "image": image.image_id,
        "environment": image.runtime_digest,
        "provenance": "MINER_SELF_REPORTED",
        "official_eligible": False,
        "training_support_eligible": False,
    }


class PublicAdvectionMaterial:
    """Trusted material composition; callers select no physics, script or tolerance."""

    def __init__(self, primary, *, ledger, owner, image):
        self.primary, self.ledger, self.owner, self.image = (
            primary,
            ledger,
            owner,
            image,
        )
        self.scope = advection_scope(image)
        self._authorize()

    def _authorize(self):
        authorize_julia(self.ledger, self.owner, self.image)
        with self.ledger.db() as db:
            row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
        manifest = json.loads(row[0]) if row else {}
        scopes = manifest.get("runtime", {}).get("scientific_tasks")
        if (
            manifest.get("schema") != MANIFEST
            or manifest.get("owner") != self.owner
            or type(scopes) is not list
            or scopes.count(self.scope) != 1
            or self.scope != advection_scope(self.image)
        ):
            raise ValueError("exact prospective public advection scope required")
        self.ledger._grant(manifest)

    def __call__(self, name, workspace):
        if name in (MATERIAL, "capabilities"):
            self._authorize()
            if (
                type(workspace) is not ResearchWorkspace
                or workspace.ledger is not self.ledger
                or workspace.owner != self.owner
                or ACTIVE_TASK.get() is None
            ):
                raise ValueError("owned admitted research task required")
        if name == "capabilities":
            value = {
                **capabilities(),
                "scientific_tasks": [self.scope],
                "scientific_task_usage": {
                    "kind": "workspace",
                    "action": "public_material",
                    "arguments": {"name": MATERIAL},
                    "purpose": "Fixed public advection refinement/analytic reuse control",
                    "limits": "No Challenge, accepted reference or training-support promotion",
                },
            }
            payload = canonical(value)
            filename = "capabilities-advection-v1.json"
            workspace.put(filename, payload)
            return {"document": value, "file": filename, "digest": digest(payload)}
        if name != MATERIAL:
            return self.primary(name, workspace)
        request = AdvectionRequest(public_definition())

        def validate(snapshot):
            validate_julia_output(snapshot)
            decode_outputs(
                {p.name: p.read_bytes() for p in snapshot.iterdir()}, request
            )

        result = _run(
            self.ledger,
            owner=self.owner,
            identity="advection-" + request.digest[7:],
            source=source(),
            files={"request.txt": request.encode()},
            image=self.image,
            seconds=60,
            provenance="MINER_SELF_REPORTED",
            extra_resources=(
                {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
            ),
            program_name="program.jl",
            bootstrap=BOOTSTRAP,
            execution_contract={
                "runtime": authored_julia_scope(self.image),
                "study": self.scope,
            },
            output_validator=validate,
        )
        snapshot = self.ledger.root / result["operation"] / "snapshot"
        files = {p.name: p.read_bytes() for p in snapshot.iterdir()}
        if {name: digest(body) for name, body in files.items()} != result["files"]:
            raise ValueError("retained advection snapshot identity differs")
        diagnostics = decode_outputs(files, request)
        import struct

        analytic = [
            1.0 + 0.25 * math.sin(2 * math.pi * i / 64 - t)
            for t in request.definition.requested_times
            for i in range(64)
        ]
        for label in ("coarse", "fine"):
            values = [v[0] for v in struct.iter_unpack("<d", files[label + ".f64le"])]
            diagnostics[label + "_analytic_rms"] = math.sqrt(
                sum((a - b) ** 2 for a, b in zip(values, analytic)) / len(analytic)
            )
        document = {
            **request.public_view(),
            "scope": self.scope,
            "provenance": result["provenance"],
            "diagnostics": diagnostics,
            "operation": result["operation"],
            "output_digest": result["output_digest"],
            "case_interpretation": "FIXED_PUBLIC_ANALYTIC_CONTROL_NOT_POPULATION_EVIDENCE",
        }
        prefix = "advection-" + request.digest[7:23]
        for filename in ("coarse.f64le", "fine.f64le"):
            workspace.put(prefix + "-" + filename, files[filename])
        metadata = canonical(document)
        workspace.put(prefix + ".json", metadata)
        return {
            "document": document,
            "file": prefix + ".json",
            "digest": digest(metadata),
        }
