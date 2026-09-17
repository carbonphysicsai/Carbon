"""Private Workbench view over the same admitted public Julia research task.

An authenticated host installs a resolver for reviewed draft records. Request
fields and rights assertions never create that authority. This bounded adapter
accepts only the already-public fixed TRAIN definition, never customer inputs.
No scheduler, task store, scientific evaluator or accounting ledger is added.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from dataclasses import dataclass

import numpy as np

from carbon import research
from carbon.development_session.julia_research import MATERIAL, JuliaPublicMaterial
from carbon.development_session.profile import CHALLENGE, canonical, digest
from carbon.development_session.research_data import decode_public_case
from carbon.development_session.research_ledger import FINAL_RESERVE
from carbon.development_session.research_profile import public_cases
from carbon.generators.burgers_dynamics import DOMAIN_LENGTH, requested_times
from carbon.miner_mcp.standard import ResearchToolAdapter, ResearchToolRequest
from carbon.reference_runtime.julia.protocol import METHOD_ID

TEMPLATE = "periodic_viscous_burgers_1d_v1"
REQUEST = "carbon.workbench.scientific-study.request.v1"
RESPONSE = "carbon.workbench.scientific-study.response.v1"
CAPABILITIES = "carbon.workbench.scientific-study.capabilities.v1"
_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SCOPE = frozenset(
    {
        "physics_family",
        "requested_goal",
        "inputs",
        "outputs",
        "units",
        "geometry",
        "conditions",
        "regime",
        "exclusions",
        "query_workload",
        "rights_scope",
        "reference_equation",
        "reference_method",
    }
)


def wire_digest(value):
    """UTF-8 sorted JSON with every number replaced by big-endian binary64 bits.

    Matches the Workbench client without language-dependent decimal formatting.
    This is an identity encoding, not a change to the numerical request values.
    """

    def normalize(item, depth=0):
        if depth > 12:
            raise ValueError("study nesting limit")
        if type(item) in (int, float):
            if not math.isfinite(item) or (type(item) is int and abs(item) > 2**53 - 1):
                raise ValueError("finite interoperable study number required")
            return {"$f64": struct.pack(">d", float(item)).hex()}
        if item is None or type(item) in (str, bool):
            return item
        if type(item) is list:
            return [normalize(v, depth + 1) for v in item]
        if type(item) is dict and all(type(k) is str for k in item):
            return {k: normalize(item[k], depth + 1) for k in sorted(item)}
        raise ValueError("plain study JSON required")

    body = json.dumps(
        normalize(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(body) > 131072:
        raise ValueError("study byte limit")
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class RegisteredWorkbenchDraft:
    """Returned only by the host's trusted draft/rights resolver, never a POST.

    current_revision distinguishes retained history from current association.
    Installation of this record is an operator action outside request handling.
    """

    principal: str
    job_id: str
    design_id: str
    revision: int
    current_revision: int
    draft_scope: dict
    physical: dict
    rights_scope: str


def _ident(value):
    if type(value) is not str or _IDENT.fullmatch(value) is None:
        raise ValueError("bounded study identity required")


class WorkbenchScience:
    def __init__(self, adapter, *, draft_resolver):
        if type(adapter) is not ResearchToolAdapter or not callable(draft_resolver):
            raise ValueError(
                "bound research adapter and trusted draft resolver required"
            )
        adapter._check_binding()
        material = adapter._sdk.composition.executor.public_material
        if type(material) is not JuliaPublicMaterial:
            raise ValueError("explicit prospective Julia service required")
        if (
            material.study.data.ledger is not adapter._sdk.ledger
            or material.study.data.owner != adapter.principal
        ):
            raise ValueError("study campaign or principal differs")
        self.adapter, self.resolver, self.material = adapter, draft_resolver, material

    def _physical(self):
        data = self.material.study.data
        case = decode_public_case(public_cases(data.role_root, "research-train")[0])
        return {
            "domain_length": DOMAIN_LENGTH,
            "viscosity": case.viscosity,
            "mean": case.mean,
            "cosine_coefficients": list(case.cosine_coefficients),
            "sine_coefficients": list(case.sine_coefficients),
            "requested_times": list(requested_times(case, 4)),
            "output_points": 64,
            "units": "dimensionless",
        }

    async def _access(self, *, cleanup=False):
        self.adapter._check_binding()
        if self.adapter._sdk.composition.executor.public_material is not self.material:
            raise ValueError("study composition changed")
        connection = self.adapter._sdk.connection
        cleanup_registration = getattr(connection, "check_cleanup_registration", None)
        if cleanup and callable(cleanup_registration):
            await cleanup_registration()
        else:
            await connection.check_registration()
        self.material.study._authorize(cleanup=cleanup)

    async def capabilities(self):
        await self._access()
        return {
            "schema": CAPABILITIES,
            "template_id": TEMPLATE,
            "physical": self._physical(),
            "method": METHOD_ID,
            "environment": self.material.study.scope["environment"],
            "available": True,
        }

    def _validate(self, request, *, stale=False):
        if type(request) is not dict or set(request) != {
            "schema",
            "operation_id",
            "action",
            "binding",
            "template_id",
            "physical",
            "draft_scope",
            "rights_scope",
        }:
            raise ValueError("closed study request required")
        wire_digest(request)  # Finite types, depth and total bytes before lookups.
        binding = request["binding"]
        if type(binding) is not dict or set(binding) != {
            "job_id",
            "design_id",
            "design_revision",
            "physical_sha256",
        }:
            raise ValueError("closed study binding required")
        for key in ("job_id", "design_id"):
            _ident(binding[key])
        revision = binding["design_revision"]
        if type(revision) is not int or not 1 <= revision <= 2**53 - 1:
            raise ValueError("positive safe draft revision required")
        scope = request["draft_scope"]
        if (
            type(scope) is not dict
            or set(scope) != _SCOPE
            or any(type(v) is not str or len(v) > 8000 for v in scope.values())
        ):
            raise ValueError("closed draft scope required")
        if (
            request["schema"] != REQUEST
            or request["template_id"] != TEMPLATE
            or request["action"] != "REFERENCE_FEASIBILITY"
            or request["rights_scope"] != "SYNTHETIC_INTERNAL"
            or scope["rights_scope"] != "SYNTHETIC_INTERNAL"
            or scope["physics_family"] != TEMPLATE
            or scope["requested_goal"] != "Dynamics"
            or wire_digest(request["physical"]) != wire_digest(self._physical())
        ):
            raise ValueError("only the granted public source definition is available")
        expected = wire_digest(
            {
                "template_id": TEMPLATE,
                "physical": request["physical"],
                "draft_scope": scope,
            }
        )
        if binding["physical_sha256"] != expected or request[
            "operation_id"
        ] != "study-" + wire_digest(binding):
            raise ValueError("study content identity differs")
        registered = self.resolver(
            self.adapter.principal, binding["job_id"], binding["design_id"], revision
        )
        if (
            type(registered) is not RegisteredWorkbenchDraft
            or registered.principal != self.adapter.principal
            or registered.job_id != binding["job_id"]
            or registered.design_id != binding["design_id"]
            or registered.revision != revision
            or type(registered.current_revision) is not int
            or (not stale and registered.current_revision != revision)
            or registered.rights_scope != "SYNTHETIC_INTERNAL"
            or registered.draft_scope != scope
            or wire_digest(registered.physical) != wire_digest(request["physical"])
        ):
            raise PermissionError("operator draft binding is absent, changed or stale")
        return json.loads(canonical(request))

    def _lookup(self, operation_id):
        tasks = self.adapter._sdk.composition.tasks
        with tasks._lock:
            identity = tasks._idempotency.get((CHALLENGE, operation_id))
            if identity is None:
                raise ValueError("study has no existing admitted task")
            request = research.load_canonical(
                tasks._requests[identity], research.StartResearchTaskRequest
            )
            if (
                type(request.task_spec) is not research.DevelopmentWorkspaceTaskSpecV1
                or request.task_spec.action != "public_material"
                or request.task_spec.arguments_json
                != canonical({"name": MATERIAL}).decode()
            ):
                raise ValueError("study operation belongs to a different task")
            sequence = tasks._tasks[identity].last_poll_sequence
            return identity.value, 0 if sequence is None else sequence + 1

    async def call(self, action, request):
        if action not in {"start", "status", "result", "cancel"}:
            raise ValueError("registered study action required")
        await self._access(cleanup=action == "cancel")
        bound = self._validate(request, stale=action == "cancel")
        operation_id = bound["operation_id"]
        if action == "start":
            operation, arguments = "start_research_task", {
                "kind": "workspace",
                "strategy": None,
                "action": "public_material",
                "arguments": {"name": MATERIAL},
                "hypothesis": "Assess the registered Julia public-source refinement diagnostic for draft "
                + bound["binding"]["physical_sha256"],
                "expected_effect": "Retain conservation, horizon and resource observations; no reference promotion",
            }
            transmission = operation_id
        else:
            task_id, sequence = self._lookup(operation_id)
            operation = (
                "cancel_research_task" if action == "cancel" else "get_research_result"
            )
            arguments = {"task_id": task_id}
            if action != "cancel":
                arguments["poll_sequence"] = sequence
            transmission = operation_id + "-" + action
        response = await self.adapter.call(
            ResearchToolRequest(operation, transmission, arguments)
        )
        # Resource cleanup remains the controller's duty if the caller goes away
        # or its draft changes while the admitted task runs.
        self._validate(bound, stale=action == "cancel")
        payload = response.payload
        task = payload.get("terminal_task")
        if payload.get("reply", {}).get("status") != "OK" or type(task) is not dict:
            raise ValueError("study service rejected operation")
        status = {
            "QUEUED": "PENDING",
            "RUNNING": "RUNNING",
            "SUCCEEDED": "COMPLETE",
            "FAILED_INFRA": "FAILED",
            "CANCEL_REQUESTED": "CANCEL_REQUESTED",
            "CANCELLED": "CANCELLED",
        }.get(task["state"])
        if status is None:
            raise ValueError("unrecognized study state")
        ledger = self.adapter._sdk.ledger
        observed = ledger.status(owner=self.adapter.principal)
        if status in {"FAILED", "CANCELLED"} and any(
            item["state"] == "RESERVED" for item in observed["operations"]
        ):
            status = "REQUIRES_RECONCILIATION"
        result = None
        if status == "COMPLETE":
            metadata = payload["public_result"]["result"]
            if (
                metadata["method"] != METHOD_ID
                or metadata["environment"] != self.material.study.scope["environment"]
                or metadata["scope_digest"]
                != digest(canonical(self.material.study.scope))
                or metadata["official_eligible"] is not False
                or metadata["training_support_eligible"] is not False
            ):
                raise ValueError("study result provenance differs")
            raw = self.adapter._sdk.composition.executor.workspace.get(
                metadata["solution"]
            )
            if len(raw) != 13 * 64 * 8 or digest(raw) != metadata["payload_digest"]:
                raise ValueError("study numerical artifact changed")
            values = np.frombuffer(raw, dtype="<f8").reshape(13, 64)
            if not np.all(np.isfinite(values)):
                raise ValueError("study numerical artifact nonfinite")
            result = {"metadata": metadata, "values": values.tolist()}
        remaining = {
            key
            + "_remaining": max(
                0,
                observed["ceilings"][key]
                - observed["used"][key]
                - FINAL_RESERVE.get(key, 0),
            )
            for key in (
                "research_trials",
                "numerical_milliseconds",
                "reference_invocations",
            )
        }
        return {
            "schema": RESPONSE,
            "operation_id": operation_id,
            "task_id": task["task_id"]["value"],
            "status": status,
            "binding": bound["binding"],
            "remaining_budget": remaining,
            "method": METHOD_ID,
            "environment": self.material.study.scope["environment"],
            "result": result,
            "official_eligible": False,
            "qualification": "NOT_QUALIFIED",
        }
