"""Closed miner SDK: readable arguments, existing authenticated v2 operations.

Only the trusted supervisor holds this object. The model receives schemas and
public result values, never transport journals, signing keys or provider objects.
"""

from __future__ import annotations

import base64
import dataclasses
import enum
import json
import time

from carbon import research
from carbon.chain.auth import BittensorMessageSigner
from carbon.transport.models import message

from .profile import CHALLENGE, canonical, digest

PREFIX = "carbon_research_v2__"
PROMPT = """You are an authenticated Carbon DEVELOPMENT miner researcher. Your job
is to learn a stronger reconstructable recipe, not just make a valid submission.
Discover the public objective, capability catalog and unexecuted scaffold. Obtain
public TRAIN and practice material through workspace public_material actions.
Use the twelve namespaced research functions. The SDK binds immutable references;
you supply readable arguments. JSON-string fields contain ordinary JSON objects.

Before every materially new trial state a falsifiable hypothesis and expected
effect. Inspect actual learning curves and practice diagnostics. Retain or reject
changes for stated reasons. Cheap single-construction practice screens precede
the separately controlled three-replica final exam. Practice data is adaptive,
not independent final evidence. The scientific rule stays fixed. Do not select
or remove final cases, edit the grader, seek final labels, or infer authority from
a request. Mean preservation is legitimate but does not prove accuracy or energy
evolution. Unsupported architectures or optimizers require a capability request;
do not disguise them as FNO. Never run an unmetered inner training search in an
analysis script: one declared hypothesis/construction per numerical task.

Use workspace notebook actions to keep hypotheses, decisions and capability
requests. Each arbitrary Python task consumes a trial slot. Scripts see only
staged public/own files, have no network, and must export bounded useful files to
/scratch/output. Practice diagnostics are service-produced; script diagnostics
are self-reported. Do not ask for repository, evaluator, wallet or credential
access. If work is running the supervisor waits; do not repeatedly poll it.
Stop on budget, unresolved dispatch, cancellation, no useful feasible hypothesis,
or a justified final candidate. A stop without improvement is a valid outcome.
No chain writes, payment or scientific qualification occur in this campaign.
"""


def _schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


STRING = {"type": "string"}
FIELDS = {
    "get_challenge_info": {},
    "get_interaction_manifest": {},
    "get_prior": {},
    "get_mock_scaffold": {},
    "dry_validate": {"strategy_json": STRING},
    "compile_strategy": {"strategy_json": STRING},
    "inspect_prior_alignment": {"strategy_json": STRING},
    "inspect_resources": {"strategy_json": STRING},
    "forecast_resources": {
        "strategy_json": STRING,
        "seconds": {"type": "integer", "minimum": 1, "maximum": 600},
    },
    "start_research_task": {
        "kind": {"type": "string", "enum": ["practice", "workspace"]},
        "strategy_json": {"type": ["string", "null"]},
        "action": {
            "type": ["string", "null"],
            "enum": [
                "public_material",
                "inventory",
                "read_file",
                "write_file",
                "notebook",
                "capability_request",
                "run_python",
                None,
            ],
        },
        "arguments_json": {"type": ["string", "null"]},
        "hypothesis": STRING,
        "expected_effect": STRING,
    },
    "get_research_result": {
        "task_id": STRING,
        "poll_sequence": {"type": "integer", "minimum": 0},
    },
    "cancel_research_task": {"task_id": STRING},
}
DESCRIPTIONS = {
    "start_research_task": "Run one real practice recipe, or a public workspace action. Set kind=practice for a registered recipe: strategy_json is the recipe, action/arguments_json=null. Set kind=workspace for every workspace action, including run_python: strategy_json=null, action names the action and arguments_json contains its JSON object. Actions: public_material {name: objective|capabilities|training_data|practice_data|reference_method}; inventory {}; read_file {name,offset,count<=4096}; write_file {name,content_base64,expected_digest}; notebook {kind:hypothesis|decision|notebook,body:object}; capability_request {request:{purpose,operation,hypothesis,public_evidence,reason,expected_benefit,estimated_cost,minimal_safe_design,verification}}; run_python {source,files:[own filenames to stage],seconds:40..600,hypothesis,expected_effect}. An empty files list stages no workspace files. Supervisor waits without model polling.",
    "get_prior": "Discover prior availability; no registered prior pack in this profile.",
    "inspect_prior_alignment": "Unavailable without a registered prior pack; records capability limitation.",
}

TASK_CORRECTIONS = {
    "practice_recipe_required": (
        "kind=practice requires a registered recipe JSON string in strategy_json "
        "and null action/arguments_json. For run_python or any other workspace "
        "action, use kind=workspace, strategy_json=null and the action's arguments_json. "
        "Only files explicitly listed in run_python arguments are staged."
    ),
    "workspace_recipe_forbidden": (
        "kind=workspace requires strategy_json=null, an allowed action and its "
        "arguments_json object. To practice a registered recipe, use kind=practice "
        "with the recipe JSON string and null action/arguments_json."
    ),
}


class TaskContractMismatch(ValueError):
    """Allow-listed corrective feedback, never a private exception message."""


TOOLS = [
    {
        "type": "function",
        "name": PREFIX + op,
        "description": DESCRIPTIONS.get(
            op,
            "Call authenticated " + op + " in the registered Carbon research protocol.",
        ),
        "strict": True,
        "parameters": _schema(FIELDS[op]),
    }
    for op in research.SUPPORTED_OPERATIONS
]


def _json(raw):
    if type(raw) is not str or len(raw.encode()) > 16384:
        raise ValueError("bounded JSON object required")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate argument")
            result[key] = value
        return result

    value = json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite argument")
        ),
    )
    if type(value) is not dict:
        raise ValueError("JSON object required")
    return value


def tools_for_sdk(sdk):
    """Prospective discovery only; historical campaign tool schemas are immutable."""
    image = getattr(
        getattr(getattr(sdk, "composition", None), "executor", None),
        "julia_image",
        None,
    )
    if image is None:
        return TOOLS
    from .julia_analysis import authorize_julia

    authorize_julia(sdk.ledger, sdk.owner, image)
    result = json.loads(canonical(TOOLS))
    tool = next(
        item for item in result if item["name"] == PREFIX + "start_research_task"
    )
    tool["parameters"]["properties"]["action"]["enum"].append("run_julia")
    tool["description"] += (
        " Prospectively admitted run_julia uses the same workspace arguments as run_python "
        "and the isolated Julia 1.13.0 Base/standard-library image. No runtime package "
        "installation. Exports: finite .json, little-endian finite .f64le, UTF-8 .txt, "
        "at most 8 MiB each. All output remains MINER_SELF_REPORTED."
    )
    return result


def public_wire(value):
    """Only called on B-07's already projected public wire records."""
    if dataclasses.is_dataclass(value):
        return {
            field.name: public_wire(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, enum.Enum):
        return value.value
    if type(value) in (tuple, list):
        return [public_wire(item) for item in value]
    if type(value) is dict:
        return {str(key): public_wire(item) for key, item in value.items()}
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise ValueError("unsupported public wire value")


class ResearchMinerTools:
    def __init__(self, *, connection, wrapper, composition, ledger, owner):
        self.connection, self.wrapper, self.composition = (
            connection,
            wrapper,
            composition,
        )
        self.ledger, self.owner = ledger, owner

    def _request(self, operation, args, identity):
        c = self.composition
        support = c.discovery.info.training_support_ref
        if operation == "get_challenge_info":
            return research.GetChallengeInfoRequest(CHALLENGE)
        if operation == "get_interaction_manifest":
            return research.GetInteractionManifestRequest(CHALLENGE)
        if operation == "get_prior":
            return research.GetPriorRequest(CHALLENGE, research.NoPriorSelector())
        if operation == "get_mock_scaffold":
            return research.GetMockScaffoldRequest(CHALLENGE, support, None)
        if operation == "dry_validate":
            return research.DryValidateRequest(CHALLENGE, _json(args["strategy_json"]))
        if operation == "compile_strategy":
            return research.CompileStrategyRequest(
                CHALLENGE, _json(args["strategy_json"]), support
            )
        if operation == "inspect_resources":
            return research.InspectResourcesRequest(
                CHALLENGE, _json(args["strategy_json"]), c.inspection.policy_ref
            )
        if operation == "forecast_resources":
            return research.ForecastResourcesRequest(
                CHALLENGE,
                _json(args["strategy_json"]),
                c.inspection.policy_ref,
                args["seconds"],
            )
        if operation == "get_research_result":
            return research.GetResearchResultRequest(
                CHALLENGE,
                research.ResearchTaskId(args["task_id"]),
                args["poll_sequence"],
            )
        if operation == "cancel_research_task":
            return research.CancelResearchTaskRequest(
                CHALLENGE, research.ResearchTaskId(args["task_id"]), identity
            )
        if operation != "start_research_task":
            raise ValueError("operation requires unavailable prior")
        if any(
            type(args[name]) is not str or not 1 <= len(args[name]) <= 2048
            for name in ("hypothesis", "expected_effect")
        ):
            raise ValueError("prospective bounded hypothesis required")
        if args["kind"] == "practice":
            if (
                args["action"] is not None
                or args["arguments_json"] is not None
                or type(args["strategy_json"]) is not str
            ):
                raise TaskContractMismatch("practice_recipe_required")
            spec = research.PracticeTaskSpec(_json(args["strategy_json"]), None)
        elif args["kind"] == "workspace":
            if args["strategy_json"] is not None:
                raise TaskContractMismatch("workspace_recipe_forbidden")
            constructor, version = (
                research.DevelopmentWorkspaceTaskSpecV1,
                "carbon.autoresearch.workspace.v1",
            )
            if args["action"] == "run_julia":
                from .julia_analysis import authorize_julia

                authorize_julia(self.ledger, self.owner, c.executor.julia_image)
                constructor, version = (
                    research.DevelopmentWorkspaceTaskSpecV2,
                    "carbon.autoresearch.workspace.v2",
                )
            spec = constructor(
                version,
                args["action"],
                canonical(_json(args["arguments_json"])).decode(),
            )
        else:
            raise ValueError("unsupported task kind")
        return research.StartResearchTaskRequest(
            CHALLENGE,
            identity,
            spec,
            support,
            research.NoPriorSelector(),
            c.inspection.policy_ref,
            c.inspection.resource_class_ref,
            c.discovery.manifest.practice_scope_ref,
        )

    async def call(self, name, args, identity, *, transport_request_id=None):
        """Keep business identity stable while optionally renewing transmission.

        Legacy campaign calls retain their existing transport identity. External
        adapters supply a fresh transport request ID on each transmission while
        reusing ``identity`` for admission, task idempotency and cancellation.
        A fresh signature/request never grants another numerical allowance.
        """
        from .research_carrier import PRECHARGED_TRIAL

        if transport_request_id is not None and (
            type(transport_request_id) is not str
            or not 1 <= len(transport_request_id) <= 128
            or not all(
                c.isascii() and (c.isalnum() or c in "_.:-")
                for c in transport_request_id
            )
        ):
            raise ValueError("bounded transport request identity required")
        if (
            name == PREFIX + "start_research_task"
            and type(args) is dict
            and args.get("action") == "run_julia"
        ):
            from .julia_analysis import authorize_julia

            authorize_julia(
                self.ledger, self.owner, self.composition.executor.julia_image
            )
        numerical = (
            name == PREFIX + "start_research_task"
            and type(args) is dict
            and (
                args.get("kind") == "practice"
                or args.get("action") in {"run_python", "run_julia"}
            )
        )
        token = None
        if numerical:
            reservation = {"research_trials": 1}
            admission = self.ledger.reserve(
                "trial-attempt-" + identity,
                owner=self.owner,
                phase="research",
                request=args,
                resources=reservation,
            )
            if admission["dispatch"]:
                self.ledger.finish(
                    "trial-attempt-" + identity,
                    owner=self.owner,
                    state="SUCCEEDED",
                    actual=reservation,
                    result={
                        "status": "PROPOSAL_ATTEMPT_CHARGED",
                        "training_completed": False,
                    },
                )
            token = PRECHARGED_TRIAL.set(identity)
        try:
            return await self._call(
                name, args, identity, transport_request_id=transport_request_id
            )
        finally:
            if token is not None:
                PRECHARGED_TRIAL.reset(token)

    def rejected(
        self,
        operation,
        args,
        identity,
        *,
        reason="contract_incompatibility",
        correction=None,
    ):
        """A pre-dispatch rejection is feedback, never an ambiguous execution."""
        record = {
            "purpose": args.get("expected_effect", "Not supplied by the requester"),
            "operation": operation,
            "hypothesis": args.get("hypothesis", "Not supplied by the requester"),
            "public_evidence": "Rejected request " + identity,
            "request_digest": digest(canonical(args)),
            "reason": reason,
            "expected_benefit": "Requester has not yet justified an extension",
            "estimated_cost": "Unestimated; requires investigation",
            "minimal_safe_design": "Use the disclosed closed recipe/workspace contract; extensions require tested delivery",
            "verification": "A bounded valid request must execute and reconstruct with identical semantics",
            "disposition": "investigate",
            "authority_granted": False,
        }
        if correction in TASK_CORRECTIONS:
            record["minimal_safe_design"] = TASK_CORRECTIONS[correction]
        self.ledger.note(owner=self.owner, kind="capability_request", body=record)
        result = {
            "status": "REJECTED_BEFORE_DISPATCH",
            "reason": reason,
            "detail": "Request does not satisfy the disclosed argument/recipe contract. Inspect capabilities and correct the request. This consumed the applicable proposal counter, but started no task.",
            "authority_granted": False,
        }
        if correction in TASK_CORRECTIONS:
            result["correction_code"] = correction
            result["correction"] = TASK_CORRECTIONS[correction]
        return result

    async def _call(self, name, args, identity, *, transport_request_id=None):
        operation = name.removeprefix(PREFIX)
        if (
            name != PREFIX + operation
            or operation not in FIELDS
            or type(args) is not dict
            or set(args) != set(FIELDS[operation])
        ):
            return self.rejected(name, args if type(args) is dict else {}, identity)
        if len(canonical(args)) > 32768:
            raise ValueError("bounded tool arguments required")
        unavailable = operation == "inspect_prior_alignment"
        try:
            request = self._request(
                "get_interaction_manifest" if unavailable else operation,
                {} if unavailable else args,
                identity,
            )
        except TaskContractMismatch as exc:
            return self.rejected(operation, args, identity, correction=exc.args[0])
        except (ValueError, TypeError, KeyError):
            return self.rejected(operation, args, identity)
        # Authentication and execution exceptions remain operational stops. Only
        # the pre-dispatch closed request validation above is repairable feedback.
        observed = await self.connection.check_registration()
        if operation == "start_research_task":
            self.ledger.note(
                owner=self.owner,
                kind="hypothesis",
                body={
                    "task_request": identity,
                    "hypothesis": args["hypothesis"],
                    "expected_effect": args["expected_effect"],
                    "kind": args["kind"],
                },
            )
        actual_op = "get_interaction_manifest" if unavailable else operation
        call = research.ServiceCall(research.RESEARCH_NAMESPACE, actual_op, request)
        body = message(
            self.connection.chain_context,
            observed.snapshot_id,
            CHALLENGE,
            session="carbon-autoresearch",
            request=identity if transport_request_id is None else transport_request_id,
            tool=research.RESEARCH_NAMESPACE,
            fields={
                "call_base64": base64.b64encode(research.canonical_bytes(call)).decode(
                    "ascii"
                )
            },
        )
        headers = BittensorMessageSigner(self.connection.miner_key).sign(
            body, receiver=self.connection.publisher, nonce_ns=time.time_ns()
        )
        result = await self.wrapper.supervised_call(
            body, headers, {self.owner: self.composition}
        )
        if unavailable:
            value = {
                "operation": operation,
                "status": "UNAVAILABLE",
                "reason": "missing_data_support",
                "detail": "No registered public prior pack; no alignment computation occurred",
                "authority_granted": False,
            }
            self.ledger.note(owner=self.owner, kind="capability_request", body=value)
            return value
        reply = research.load_canonical(
            base64.b64decode(result["protocol_reply_base64"]), research.ServiceReply
        )
        if (
            reply.status is not research.ReplyStatus.OK
            and operation == "start_research_task"
        ):
            self.ledger.note(
                owner=self.owner,
                kind="capability_request",
                body={
                    "operation": operation,
                    "request_digest": digest(canonical(args)),
                    "reason": "contract_incompatibility",
                    "disposition": "investigate",
                    "authority_granted": False,
                    "public_error": public_wire(reply.result),
                },
            )
        return {
            "protocol": research.RESEARCH_NAMESPACE,
            "operation": operation,
            "reply": public_wire(reply),
            "terminal_task": (
                public_wire(
                    research.load_canonical(
                        base64.b64decode(result["terminal_observation_base64"]),
                        research.ResearchTaskView,
                    )
                )
                if result["terminal_observation_base64"]
                else None
            ),
            "public_result": result["public_result"],
            "requires_reconciliation": result["requires_reconciliation"],
        }
