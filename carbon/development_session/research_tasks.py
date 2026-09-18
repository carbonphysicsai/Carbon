"""Versioned public workspace tasks behind B-07's existing twelve operations.

The legacy provider does not execute the new task kind. This explicit D4
composition opts in; all files/scripts remain miner-owned and non-authoritative.
"""

from __future__ import annotations

import base64
import json

from carbon.authoring.model import EvidenceRole
from carbon.research import (
    DevelopmentWorkspaceTaskSpecV1,
    PracticeTaskSpec,
    ResearchTaskKind,
    ResearchTaskState,
    StartResearchTaskRequest,
    canonical_bytes,
    load_canonical,
)
from carbon.research.durable import DurableResearchTaskProvider
from carbon.research.records import (
    AuthorizedResearchOutcome,
    EvidenceContext,
    EvidenceQualityMetadata,
    PrivateIdentityRef,
    ResearchCensoringStatus,
    ResearchEvidenceClass,
    ResearchRetentionScope,
    RetentionReuseBinding,
)

from .profile import canonical, digest
from .research_carrier import ACTIVE_TASK, request_cancel, run_script
from .research_workspace import ResearchWorkspace, request_capability


class PublicDevelopmentResearchTasks(DurableResearchTaskProvider):
    @staticmethod
    def _spec_parts(request):
        if type(request.task_spec) is DevelopmentWorkspaceTaskSpecV1:
            return ResearchTaskKind.DEVELOPMENT_WORKSPACE_V1, (), (), ()
        return DurableResearchTaskProvider._spec_parts(request)

    def cancel_research_task(self, request):
        result = super().cancel_research_task(request)
        if result.task.state is ResearchTaskState.CANCEL_REQUESTED:
            self._executor.executor.cancel(request.task_id.value)
        return result

    def request_for_execution(self, task_id):
        """Trusted executor lookup, never a public operation."""
        with self._lock:
            if self._tasks[task_id].state not in {
                ResearchTaskState.RUNNING,
                ResearchTaskState.CANCEL_REQUESTED,
            }:
                raise ValueError("task is not running")
            return load_canonical(self._requests[task_id], StartResearchTaskRequest)


def _arguments(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate workspace argument")
            result[key] = value
        return result

    value = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite workspace argument")
        ),
    )
    if type(value) is not dict or canonical(value).decode() != raw:
        raise ValueError("canonical closed workspace arguments required")
    return value


class PublicResearchExecutor:
    """Trusted owner-bound composition; it receives no wallet or API key."""

    def __init__(self, *, ledger, owner, image, public_material, practice):
        self.ledger, self.owner, self.image = ledger, owner, image
        self.workspace = ResearchWorkspace(ledger, owner)
        self.public_material, self.practice = public_material, practice
        self.request_resolver = None
        with ledger.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,task))"
            )

    def _workspace_action(self, spec, identity):
        args = _arguments(spec.arguments_json)
        expected = {
            "public_material": {"name"},
            "inventory": set(),
            "read_file": {"name", "offset", "count"},
            "write_file": {"name", "content_base64", "expected_digest"},
            "notebook": {"kind", "body"},
            "capability_request": {"request"},
            "run_python": {
                "source",
                "files",
                "seconds",
                "hypothesis",
                "expected_effect",
            },
        }[spec.action]
        if set(args) != expected:
            raise ValueError("workspace fields differ from registered action")
        if spec.action == "public_material":
            from .julia_research import MATERIAL, JuliaPublicMaterial

            # The bound material service owns the allowlist. No arbitrary path,
            # case coordinate, URL, evaluator query or hidden-role selector.
            allowed = {
                "objective",
                "capabilities",
                "training_data",
                "practice_data",
                "reference_method",
            }
            if type(self.public_material) is JuliaPublicMaterial:
                allowed.add(MATERIAL)
            if args["name"] not in allowed:
                raise ValueError("public material unavailable")
            return self.public_material(args["name"], self.workspace)
        if spec.action == "inventory":
            return {"files": self.workspace.inventory()}
        if spec.action == "read_file":
            offset, count = args["offset"], args["count"]
            if (
                type(offset) is not int
                or offset < 0
                or type(count) is not int
                or not 1 <= count <= 4096
            ):
                raise ValueError("bounded byte range required")
            body = self.workspace.get(args["name"])
            return {
                "name": args["name"],
                "digest": digest(body),
                "bytes": len(body),
                "offset": offset,
                "content_base64": base64.b64encode(
                    body[offset : offset + count]
                ).decode("ascii"),
            }
        if spec.action == "write_file":
            if type(args["content_base64"]) is not str:
                raise ValueError("base64 file content required")
            body = base64.b64decode(args["content_base64"], validate=True)
            return {
                "name": args["name"],
                "digest": self.workspace.put(
                    args["name"], body, expected_digest=args["expected_digest"]
                ),
            }
        if spec.action == "notebook":
            if args["kind"] not in {"hypothesis", "decision", "notebook"}:
                raise ValueError("miner notebook kind unavailable")
            self.ledger.note(owner=self.owner, kind=args["kind"], body=args["body"])
            return {"retained": True}
        if spec.action == "capability_request":
            return request_capability(
                self.ledger, owner=self.owner, request=args["request"]
            )
        if any(
            type(args[k]) is not str or not 1 <= len(args[k]) <= 2048
            for k in ("hypothesis", "expected_effect")
        ):
            raise ValueError("prospective hypothesis and expected effect required")
        self.ledger.note(
            owner=self.owner,
            kind="hypothesis",
            body={
                "task": identity,
                "hypothesis": args["hypothesis"],
                "expected_effect": args["expected_effect"],
            },
        )
        result = run_script(
            self.ledger,
            owner=self.owner,
            identity=identity,
            source=args["source"],
            files=self.workspace.snapshot(args["files"]),
            image=self.image,
            seconds=args["seconds"],
        )
        # Import only the bounded validated export into the owner's scratch space.
        # No path from miner output is ever interpreted as a host source path.
        snapshot = self.ledger.root / result["operation"] / "snapshot"
        exported = []
        for relative, fingerprint in result["files"].items():
            if "/" in relative:
                continue  # nested checkpoint bundles remain retained by task
            body = (snapshot / relative).read_bytes()
            if digest(body) != fingerprint:
                raise ValueError("research export changed")
            name = identity[-20:] + "-" + relative
            if len(body) <= 8 * 1024**2 and len(name) <= 96:
                self.workspace.put(name, body)
                exported.append(name)
        return {
            "provenance": "MINER_SELF_REPORTED",
            "worker": result,
            "workspace_exports": exported,
        }

    def cancel(self, identity):
        request_cancel(self.ledger, owner=self.owner, identity=identity)

    def execute(self, attempt):
        token = ACTIVE_TASK.set(attempt.task_id.value)
        try:
            return self._execute(attempt)
        finally:
            ACTIVE_TASK.reset(token)

    def _execute(self, attempt):
        request = self.request_resolver(attempt.task_id)
        spec = request.task_spec
        identity = attempt.task_id.value
        if type(spec) is DevelopmentWorkspaceTaskSpecV1:
            result = self._workspace_action(spec, identity)
            evidence = ResearchEvidenceClass.STRUCTURAL_ONLY
        elif type(spec) is PracticeTaskSpec:
            # The practice adapter supplies trusted labels/randomness and the
            # catalog compiler; the requester supplies only a registered recipe.
            result = self.practice(identity, spec.strategy)
            evidence = ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE
        else:
            raise ValueError("task kind unavailable in real D4 provider")
        body = canonical(result)
        if len(body) > 1024**2:
            raise ValueError("bounded public result required")
        fingerprint = digest(body)
        with self.ledger.db() as db:
            prior = db.execute(
                "SELECT body FROM research_results WHERE owner=? AND task=?",
                (self.owner, identity),
            ).fetchone()
            if prior and prior[0] != body:
                raise ValueError("research result replay conflict")
            db.execute(
                "INSERT OR IGNORE INTO research_results VALUES(?,?,?,?)",
                (self.owner, identity, body, fingerprint),
            )
        origin = PrivateIdentityRef("research_evidence_origin", fingerprint)
        return AuthorizedResearchOutcome(
            evidence,
            EvidenceContext(
                EvidenceRole.NUMERICAL,
                origin,
                None,
                None,
                None,
                (),
                None,
                None,
                ResearchCensoringStatus.NOT_APPLICABLE,
                EvidenceQualityMetadata(),
            ),
            RetentionReuseBinding(ResearchRetentionScope.LOCAL_PRIVATE_ONLY),
            (),
            (PrivateIdentityRef("research_result", fingerprint),),
            None,
            (),
        )

    def public_result(self, task):
        # Called only after B-07 confirms an owned terminal task and the
        # authenticated gateway confirms this executor's requester binding.
        if task.state is not ResearchTaskState.SUCCEEDED:
            return None
        with self.ledger.db() as db:
            row = db.execute(
                "SELECT body,digest FROM research_results WHERE owner=? AND task=?",
                (self.owner, task.task_id.value),
            ).fetchone()
        if row is None or digest(row[0]) != row[1]:
            raise ValueError("owned research result unavailable")
        return {
            "schema": "carbon.autoresearch.public-result.v1",
            "task_id": task.task_id.value,
            "receipt_digest": digest(canonical_bytes(task.terminal_receipt)),
            "result_digest": row[1],
            "result": json.loads(row[0]),
            "official_eligible": False,
        }
