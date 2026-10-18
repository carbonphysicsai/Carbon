"""Prospective Graphite consumer of the miner's direct DEVELOPMENT tool session.

The session is opened by the normal Launchpad route. This adapter supplies the
existing research loop's ``tools`` and ``sdk.call`` interface; it owns neither
the signed construction transport nor a historical Graphite edition identity.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import re
from copy import deepcopy

from carbon.development_session.research_tools import (
    DIRECT_PREFIX,
    DirectResearchMinerTools,
)

from .miner.toolbox import protected, refusal

SESSION = "direct-development-1.3"
SUBMIT = DIRECT_PREFIX + "submit_construction"
STAGE_GRAPH = DIRECT_PREFIX + "stage_construction_graph"
_IDENTITY = re.compile(r"[A-Za-z0-9._:-]{16,114}\Z")
_CAMPAIGN_IDENTITY = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_RECIPE_JSON = 32768


def _schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_RECIPE = {
    "type": "string",
    "minLength": 2,
    "maxLength": _MAX_RECIPE_JSON,
    "description": "Complete registered construction recipe as one JSON object.",
}
_TEXT = {"type": "string"}
_DIRECT_PARAMETERS = {
    "get_challenge_info": _schema({}),
    "get_interaction_manifest": _schema({}),
    "stage_research_source": _schema(
        {
            "name": _TEXT,
            "offset": {"type": "integer", "minimum": 0},
            "total_bytes": {"type": "integer", "minimum": 1},
            "content_digest": _TEXT,
            "expected_digest": {"type": ["string", "null"]},
            "chunk_base64": _TEXT,
        }
    ),
    "start_research_task": _schema({"recipe_json": _RECIPE}),
    "get_research_result": _schema({"task_id": _TEXT}),
    "cancel_research_task": _schema({"task_id": _TEXT}),
}
_CONSTRUCTION_TOOLS = (
    {
        "type": "function",
        "name": STAGE_GRAPH,
        "description": (
            "Stage the graph source already saved in this owner's DEVELOPMENT "
            "workspace to the profile-pinned receiver before submitting its recipe."
        ),
        "strict": True,
        "parameters": _schema(
            {
                "recipe_json": _RECIPE,
                "expected_manifest_digest": {
                    "type": ["string", "null"],
                    "description": "Previously published receiver manifest digest, or null.",
                },
            }
        ),
    },
    {
        "type": "function",
        "name": SUBMIT,
        "description": (
            "Submit one registered construction recipe through the miner's "
            "profile-pinned signed DEVELOPMENT intake. The resulting task is "
            "not an official grade."
        ),
        "strict": True,
        "parameters": _schema({"recipe_json": _RECIPE}),
    },
)


def _recipe(raw):
    if type(raw) is not str or len(raw.encode("utf-8")) > _MAX_RECIPE_JSON:
        raise ValueError("bounded recipe JSON required")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate recipe field")
            value[key] = item
        return value

    value = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    if type(value) is not dict:
        raise ValueError("recipe object required")
    return value


class DirectToolSession:
    """Closed, prospective SDK over an already opened public Launchpad route.

    ``route(action, value)`` is the same authenticated ``tool_door.route``
    path the miner's Tools page uses, bound to its host and SESSION campaign.
    ``run_epoch`` can consume ``tools`` and ``call`` without changing its
    provider, ledger, retry, or journal semantics.
    """

    def __init__(self, route, opened, *, campaign_identity):
        if (
            not callable(route)
            or type(opened) is not dict
            or opened.get("campaign") != SESSION
            or opened.get("open") is not True
            or opened.get("development_only") is not True
            or opened.get("official_eligible") is not False
            or type(opened.get("tools")) is not list
            or type(campaign_identity) is not str
            or _CAMPAIGN_IDENTITY.fullmatch(campaign_identity) is None
        ):
            raise ValueError("open direct DEVELOPMENT tool session required")
        self._route = route
        self._campaign_identity = campaign_identity
        self._closed = False
        self._offered = {}
        tools = []
        for entry in opened["tools"]:
            if type(entry) is not dict:
                raise ValueError("malformed direct tool description")
            name, schema = entry.get("name"), entry.get("input_schema")
            if (
                type(name) is not str
                or not name.startswith(DIRECT_PREFIX)
                or name.removeprefix(DIRECT_PREFIX)
                not in DirectResearchMinerTools.OPERATIONS
                or type(schema) is not dict
                or schema.get("type") != "object"
                or name in self._offered
                or name in (SUBMIT, STAGE_GRAPH)
            ):
                raise ValueError("malformed direct tool description")
            self._offered[name] = True
            operation = name.removeprefix(DIRECT_PREFIX)
            if operation not in _DIRECT_PARAMETERS:
                raise ValueError("unknown direct agent tool")
            tools.append(
                {
                    "type": "function",
                    "name": name,
                    "description": entry.get("description", "Direct DEVELOPMENT tool"),
                    "strict": True,
                    "parameters": deepcopy(_DIRECT_PARAMETERS[operation]),
                }
            )
        if opened.get("construction_intake_configured") is True:
            tools.extend(deepcopy(_CONSTRUCTION_TOOLS))
            self._offered.update({STAGE_GRAPH: True, SUBMIT: True})
        self.tools = tools

    @classmethod
    def open(cls, route, *, campaign_identity):
        """Open through admission and bind a trusted frozen campaign digest."""
        opened = route("open", {})
        try:
            return cls(route, opened, campaign_identity=campaign_identity)
        except ValueError:
            with contextlib.suppress(Exception):
                route("close", {})
            raise

    def close(self):
        """Release the normal Launchpad session lock when the agent finishes."""
        if not self._closed:
            self._route("close", {})
            self._closed = True

    async def call(self, name, arguments, identity):
        if self._closed:
            return refusal("UNAVAILABLE", "direct_tool_session_closed")
        if name not in self._offered:
            return refusal("REFUSED_NOT_IN_MANIFEST", "tool_not_offered")
        if type(arguments) is not dict or protected(arguments):
            return refusal("REFUSED_PROTECTED_MATERIAL", "invalid_or_protected_args")
        if type(identity) is not str or _IDENTITY.fullmatch(identity) is None:
            return refusal("REJECTED_BEFORE_DISPATCH", "invalid_operation_identity")
        operation_id = (
            "graphite-direct-"
            + hashlib.sha256(
                (self._campaign_identity + "\0" + identity).encode("utf-8")
            ).hexdigest()
        )
        try:
            if name in (STAGE_GRAPH, SUBMIT):
                expected = (
                    {"recipe_json", "expected_manifest_digest"}
                    if name == STAGE_GRAPH
                    else {"recipe_json"}
                )
                if set(arguments) != expected:
                    raise ValueError("construction arguments differ")
                value = {"recipe": _recipe(arguments["recipe_json"])}
                if name == STAGE_GRAPH:
                    expected_digest = arguments["expected_manifest_digest"]
                    if expected_digest is not None and type(expected_digest) is not str:
                        raise ValueError("manifest digest must be text or null")
                    value["expected_manifest_digest"] = expected_digest
                action = (
                    "stage_construction_graph"
                    if name == STAGE_GRAPH
                    else "submit_construction"
                )
            else:
                if "operation_id" in arguments:
                    raise ValueError("operation identity is loop-owned")
                if name == DIRECT_PREFIX + "start_research_task":
                    if set(arguments) != {"recipe_json"}:
                        raise ValueError("direct start arguments differ")
                    arguments = {"recipe": _recipe(arguments["recipe_json"])}
                action = "call"
                value = {
                    "tool": name,
                    "arguments": {**arguments, "operation_id": operation_id},
                }
        except (ValueError, TypeError, json.JSONDecodeError):
            return refusal("REJECTED_BEFORE_DISPATCH", "invalid_tool_arguments")
        try:
            result = await asyncio.to_thread(self._route, action, value)
        except Exception:  # noqa: BLE001 - route failures may carry private detail
            raise UncertainDirectToolDispatch(
                "direct tool outcome requires reconciliation"
            ) from None
        if (
            type(result) is not dict
            or result.get("ok") is not True
            or protected(result)
        ):
            raise UncertainDirectToolDispatch(
                "direct tool outcome requires reconciliation"
            )
        direct = result.get("result")
        if (
            result.get("ok") is True
            and type(direct) is dict
            and direct.get("requires_reconciliation") is True
        ):
            return {**result, "requires_reconciliation": True}
        return result


class UncertainDirectToolDispatch(RuntimeError):
    """The route may have dispatched; retain the loop intent for reconciliation."""
