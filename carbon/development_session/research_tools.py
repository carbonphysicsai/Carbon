"""Closed miner SDK: readable arguments, existing authenticated v2 operations.

Only the trusted supervisor holds this object. The model receives schemas and
public result values, never transport journals, signing keys or provider objects.
"""

from __future__ import annotations

import base64
import dataclasses
import enum
import json
import re
import time
from contextvars import ContextVar

from carbon import research
from carbon.chain.auth import BittensorMessageSigner
from carbon.research.model import DEVELOPMENT_WORKSPACE_ACTIONS
from carbon.transport.models import message

from .profile import canonical, digest
from .research_workspace import CAPABILITY_FIELDS, CAPABILITY_REASONS, CAPABILITY_TEXT

PREFIX = "carbon_research_v2__"
_TASK_MODE = ContextVar("carbon_trusted_task_mode", default=None)


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
            "enum": [*DEVELOPMENT_WORKSPACE_ACTIONS, None],
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
    "start_research_task": 'Run one real practice recipe, or a public workspace action. Set kind=practice for a registered recipe: strategy_json is the recipe, action/arguments_json=null. null always means JSON null (unquoted), never the string "null". Set kind=workspace for every workspace action, including run_python: strategy_json=null, action names the action and arguments_json contains its JSON object. Actions: public_material {name: objective|capabilities|training_data|practice_data|reference_method}; inventory {}; read_file {name,offset,count<=4096}; write_file {name,content_base64,expected_digest}; notebook {kind:hypothesis|decision|notebook,body:object}; capability_request {request:{purpose,operation,hypothesis,public_evidence,reason,expected_benefit,estimated_cost,minimal_safe_design,verification}}; check_design {design:{strategy:{schema_version,challenge_id,backbone,parameters},capabilities?:[registry ids]}} - can I submit this? a verdict per choice and, when every choice is rebuildable, the canonical design Carbon would rebuild; roadmap {} - every capability, what blocks it, and how many miners asked; capability_request also takes an optional capability (a registry id) to count as demand; run_python {source,files:[own filenames to stage],seconds?:optional wall allowance - omit for none; no Carbon limit on time, memory, CPU or output size,hypothesis,expected_effect}. An empty files list stages no workspace files. Supervisor waits without model polling.',
    "get_prior": "No prior pack is registered in this profile. This takes no selector and returns no prior (the service answers REQUEST_TYPE_INVALID); it is not worth a call.",
    "inspect_prior_alignment": "Unavailable without a registered prior pack; records capability limitation.",
}

TASK_CORRECTIONS = {
    "practice_recipe_required": (
        "kind=practice requires a registered recipe JSON string in strategy_json "
        "and null action/arguments_json. For run_python or any other workspace "
        "action, use kind=workspace, strategy_json=null and the action's arguments_json. "
        "Only files explicitly listed in run_python arguments are staged."
    ),
    "json_string_required": (
        "This field carries JSON encoded as a string: send the object as a "
        'quoted string such as "{\\"name\\":\\"objective\\"}", not as a '
        "JSON object, list or number."
    ),
    "workspace_field_missing": (
        "arguments_json for this workspace action is missing a required field; "
        "the start_research_task description lists each action's fields."
    ),
    "workspace_field_unexpected": (
        "arguments_json for this workspace action has a field the action does "
        "not take; the start_research_task description lists each action's "
        "fields."
    ),
    # The code cell's device (RSURF-D20).
    "device_choice_invalid": (
        "run_python and run_julia take device=cpu (the default) or device=gpu "
        "in their arguments."
    ),
    "gpu_lane_not_configured": (
        "This campaign has no GPU lane: its runtime was frozen at launch without "
        "a GPU. Run on cpu, or set up a GPU (Control Center: Set up, Compute) "
        "and launch a campaign with it."
    ),
    "julia_gpu_environment_without_cuda": (
        "run_julia runs on the GPU only in an environment that carries CUDA.jl: "
        "current (CUDA 13.0). pde has no CUDA. Use environment=current with "
        "device=gpu, or run pde on cpu."
    ),
    "remote_julia_gpu_unavailable": (
        "Your remote GPU runs run_python only: the remote route is bound to the "
        "pinned Python GPU worker. Run run_julia on cpu, or on this machine's GPU "
        "with a campaign launched with it."
    ),
    "remote_gpu_seconds_required": (
        "A run on your remote GPU needs seconds between 40 and 3600 in its "
        "arguments: the remote route's job has a lifetime."
    ),
    "remote_gpu_unsandboxed_opt_in_required": (
        "Your remote GPU is an ssh-container setup: a code cell there runs "
        "inside your own container with no sandbox and with that container's "
        "network. It runs only if you opt in yourself: add "
        '"unsandboxed_code_cell": true to remote_machine in your runner '
        "profile. Or run on cpu, or use an ssh-docker setup, which runs each "
        "job in a hardened container."
    ),
    "workspace_recipe_forbidden": (
        "kind=workspace requires strategy_json=null, an allowed action and its "
        "arguments_json object. To practice a registered recipe, use kind=practice "
        "with the recipe JSON string and null action/arguments_json."
    ),
    # LP-PROD-D: every refusal names its tool and field and says how to fix
    # it. Registered text only: none of it repeats what a requester sent.
    "tool_unknown": (
        "That name is not one of the research tools offered. Call a tool by "
        "its exact offered name."
    ),
    "tool_arguments_object_required": (
        "A tool's arguments are one JSON object holding exactly the fields its "
        "schema lists."
    ),
    "tool_field_missing": (
        "A required argument of this tool is missing. Every field its schema "
        "lists is required; send JSON null where the schema allows null."
    ),
    "tool_field_unexpected": (
        "This tool received an argument its schema does not list. Send exactly "
        "the fields the schema lists."
    ),
    "tool_text_bounded": (
        "hypothesis and expected_effect are each a string of 1 to 2048 "
        "characters, stated before the result is known."
    ),
    "tool_value_invalid": (
        "This argument's value is outside what the tool's schema allows; the "
        "schema states its type and range."
    ),
    "task_id_invalid": (
        "task_id is the task id a start_research_task reply returned, " "unchanged."
    ),
    "json_object_required": (
        "This field holds one JSON object encoded as a string: valid JSON, an "
        "object (not a list or a number), no repeated keys, finite numbers, "
        "at most 16384 bytes."
    ),
    "backend_not_served": (
        "This host's practice serves only the backends listed below, and the "
        "recipe names another. Choose a served backend in the recipe, or "
        "practise it on a host whose worker image serves it. Nothing started "
        "and no research-trial slot was charged."
    ),
    "workspace_action_unknown": (
        "action names one workspace action, as the start_research_task "
        "description lists them. run_julia is offered only where this campaign "
        "has authored Julia."
    ),
    "workspace_arguments_too_large": (
        "arguments_json holds at most 12288 bytes, so one write_file carries "
        "about 9 KiB of file content. Write a larger file from run_python into "
        "../output instead: what a run writes there is exported to your "
        "workspace."
    ),
    "public_material_unknown": (
        "public_material serves only the material names listed below; choose "
        "one of them."
    ),
    "read_file_range": (
        "read_file reads count bytes, 1 to 65536, from offset, 0 or more, of "
        "one of your files. inventory lists each file's size in bytes."
    ),
    "workspace_name_invalid": (
        "A workspace file name is flat, never a path: 1 to 96 letters, digits, "
        "'_', '.' or '-', starting with a letter or digit."
    ),
    "workspace_file_missing": (
        "No file of that name is in your workspace. inventory lists your "
        "files; public_material writes the public ones, and a run exports "
        "what it writes to ../output."
    ),
    "write_file_content_invalid": (
        "content_base64 is the file's bytes in standard base64 (A-Z, a-z, 0-9, "
        "'+', '/' and '=' padding), with no line breaks."
    ),
    "write_file_expected_digest_conflict": (
        "expected_digest guards against overwriting a change you have not "
        "seen. It is the digest the file has now, as inventory or read_file "
        'reports it ("sha256:..."), or null when the file does not exist '
        "yet. The digest sent is not the file's current one: read inventory, "
        "then write again with the digest it reports."
    ),
    "notebook_kind_unknown": (
        "notebook kind is one of the kinds listed below; body is a JSON object."
    ),
    "notebook_body_reserved": (
        "That body has the miner-message schema, which only the miner's own "
        "page writes. Record the note in another shape."
    ),
    "capability_request_object_required": (
        "request is one JSON object with the string fields "
        + ", ".join(sorted(CAPABILITY_FIELDS))
        + ", and optionally capability."
    ),
    "capability_request_field_missing": (
        "request needs every one of "
        + ", ".join(sorted(CAPABILITY_FIELDS))
        + "; the first one missing is named."
    ),
    "capability_request_field_unexpected": (
        "request takes only "
        + ", ".join(sorted(CAPABILITY_FIELDS))
        + ", and optionally capability."
    ),
    "capability_request_reason_unknown": (
        "request.reason is one of: " + ", ".join(sorted(CAPABILITY_REASONS)) + "."
    ),
    "capability_request_text_bounded": (
        "Each request field is a string of 1 to "
        + str(CAPABILITY_TEXT)
        + " characters."
    ),
    "capability_id_unknown": (
        "request.capability, when given, is a registry id of this campaign's "
        "Challenge, as roadmap lists them; omit it otherwise."
    ),
    "check_design_shape": (
        "design is {strategy, capabilities?}: the strategy object under "
        "design.strategy and, optionally, registry ids under "
        "design.capabilities, and nothing else. A discovery example's strategy "
        "is a design's strategy as is; its validation is not part of a design."
    ),
    "check_design_strategy_shape": (
        "design.strategy is {schema_version, challenge_id, backbone, "
        "parameters}, with parameters a JSON object."
    ),
    "check_design_capabilities_shape": (
        "design.capabilities, when given, is a list of at most 256 registry ids."
    ),
    "run_hypothesis_required": (
        "run_python and run_julia take hypothesis and expected_effect in their "
        "arguments too: each a string of 1 to 2048 characters, stated before "
        "the run."
    ),
    "run_source_required": "source is the program text, a non-empty string.",
    "run_files_invalid": (
        "files lists distinct names of your own workspace files to stage beside "
        "the program; an empty list stages none. Names the carrier uses itself "
        "are refused (listed below, where that is the cause)."
    ),
    "run_seconds_invalid": (
        "seconds, when given, is a whole number of seconds, at least 1: the "
        "run's own wall allowance."
    ),
    "run_seconds_required": (
        "You set a compute-time budget for this campaign, so each run needs a "
        "wall allowance: give seconds, a whole number within what the budget "
        "has left."
    ),
    "julia_environment_unknown": (
        "run_julia's environment is one of the environments listed below; "
        "omitted, it is the default."
    ),
}

#: A Carbon-written value a correction may list (a material name, a backend,
#: an environment): never text a requester sent.
_CHOICE = re.compile(r"[A-Za-z0-9_.:+-]{1,96}\Z")


class TaskContractMismatch(ValueError):
    """Allow-listed corrective feedback, never a private exception message.

    Carries the correction code, the one argument field that broke it and,
    optionally, the Carbon-written choices the correction lists.
    """

    def __init__(self, code, field, choices=()):
        choices = tuple(choices)
        if (
            code not in TASK_CORRECTIONS
            or not registered_field(field)
            or any(type(c) is not str or not _CHOICE.match(c) for c in choices)
        ):
            raise TypeError("allow-listed correction and field required")
        super().__init__(code, field)
        self.choices = choices


#: Registered sub-fields of a workspace argument, named in a correction.
SUBFIELDS = {
    "design": frozenset({"strategy", "capabilities"}),
    "request": frozenset(CAPABILITY_FIELDS | {"capability"}),
}
#: Names for the request as a whole: the tool's name, its arguments object.
_WHOLE = ("tool", "arguments")


def registered_field(field):
    """Whether a correction may name `field`: a name Carbon wrote, never one a
    requester sent. A start_research_task nullable field, any tool's own
    argument name, the tool or its arguments as a whole, or a registered
    workspace argument (`arguments_json.<name>`, or `.<name>.<sub>`)."""
    if type(field) is not str:
        return False
    if field in NULLABLE_TASK_FIELDS or field in _WHOLE:
        return True
    if any(field in fields for fields in FIELDS.values()):
        return True
    return _registered_argument(field)


def _registered_argument(field):
    """`arguments_json.<name>` where <name> is a field some workspace action
    registers, or `arguments_json.<name>.<sub>` for its registered sub-fields:
    a name Carbon wrote, never one a requester sent."""
    from .research_tasks import workspace_fields

    prefix = "arguments_json."
    if type(field) is not str or not field.startswith(prefix):
        return False
    name, _, sub = field[len(prefix) :].partition(".")
    if sub:
        return sub in SUBFIELDS.get(name, ())
    return any(
        name in required | optional
        for required, optional in map(
            workspace_fields, (*DEVELOPMENT_WORKSPACE_ACTIONS, "run_julia")
        )
    )


#: The start_research_task fields whose value is either a string or JSON null.
NULLABLE_TASK_FIELDS = ("strategy_json", "action", "arguments_json")


def task_correction(code, field, value, *, choices=(), tool=None):
    """The correction for one broken field: what it must hold, the values
    Carbon allows where it lists them, which field and tool, and - for a field
    that may be null - that null is JSON null. The string "null" stays
    refused."""
    text = TASK_CORRECTIONS[code]
    if choices:
        text += " Allowed here: " + ", ".join(choices) + "."
    text += " The field that broke the contract: " + field + "."
    if tool is not None:
        text += " The tool: " + tool + "."
    if value == "null":
        text += (
            ' It holds the string "null". null means JSON null (unquoted), '
            'not the string "null".'
        )
    elif field in NULLABLE_TASK_FIELDS:
        text += ' null means JSON null (unquoted), not the string "null".'
    return text


def registered_correction(value):
    """Whether a REJECTED_BEFORE_DISPATCH record carries only registered
    correction text: its code, its field and a correction that
    `task_correction` produces for them. A door that forwards a refusal can
    check it with this, rather than with an exact text that a named field or
    a listed choice extends."""
    if type(value) is not dict:
        return False
    code, field, text = (
        value.get("correction_code"),
        value.get("field"),
        value.get("correction"),
    )
    if code not in TASK_CORRECTIONS or not registered_field(field):
        return False
    if type(text) is not str or not text.startswith(TASK_CORRECTIONS[code]):
        return False
    choices = ()
    listed = " Allowed here: "
    rest = text[len(TASK_CORRECTIONS[code]) :]
    if rest.startswith(listed):
        choices = tuple(
            rest[len(listed) :].split(". The field that broke", 1)[0].split(", ")
        )
        if not all(_CHOICE.match(c) for c in choices):
            return False
    tool = next((t for t in FIELDS if " The tool: " + t + "." in text), None)
    return any(
        text == task_correction(code, field, value, choices=choices, tool=tool)
        for value in (None, "null")
    )


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


#: The research tools rule a campaign freezes for its agent (LP-PROD-D):
#: the same twelve operations and schemas as `TOOLS`, with descriptions that
#: say what each workspace action takes and returns, what a run costs and
#: exports, the device choice, and what a refusal means. A campaign whose
#: frozen run plan names no rule keeps `TOOLS` byte for byte, and `TOOLS`
#: itself never changes: Graphite's roles digest it.
TOOLS_RULE = "carbon.autoresearch.research-tools.v2"
TOOLS_RULES = (TOOLS_RULE,)
DESCRIPTIONS_V2 = {
    **DESCRIPTIONS,
    "start_research_task": (
        "Run one real practice recipe, or one workspace action. The call "
        "returns once the task has finished, with its result: there is "
        "nothing to poll. "
        "kind=practice: strategy_json is the registered recipe as a JSON "
        "string; action and arguments_json are null. A practice spends one "
        "research-trial slot and runs only on a backend this host serves "
        "(the initial observation lists them). "
        "kind=workspace: strategy_json is null, action names the action, and "
        "arguments_json is its arguments object encoded as a JSON string, "
        'such as "{\\"name\\":\\"objective\\"}", never a bare object. null '
        'always means JSON null (unquoted), never the string "null". '
        "Actions and their arguments: "
        "public_material {name: a name the discovery document lists} writes "
        "that public document or data to your workspace; "
        "inventory {} lists your files with their size and digest; "
        "read_file {name, offset: 0 or more, count: 1 to 65536} returns the "
        "bytes as content_base64 and, when they are UTF-8 text, as "
        "content_utf8 (null otherwise); "
        "write_file {name, content_base64, expected_digest}: expected_digest "
        "is the file's current digest as inventory or read_file reports it, "
        "or null for a new file, so a write never overwrites a change you "
        "have not seen; arguments_json holds at most 12288 bytes, about 9 KiB "
        "of content per write; "
        "notebook {kind: hypothesis|decision|notebook, body: object}; "
        "capability_request {request: {purpose, operation, hypothesis, "
        "public_evidence, reason: "
        + "|".join(sorted(CAPABILITY_REASONS))
        + ", expected_benefit, estimated_cost, minimal_safe_design, "
        "verification, capability?: a registry id of this Challenge, counted "
        "as demand}}; "
        "check_design {design: {strategy: {schema_version, challenge_id, "
        "backbone, parameters}, capabilities?: [registry ids]}} - can I submit "
        "this? a verdict per choice and, when every choice is rebuildable, the "
        "canonical design Carbon would rebuild, or each rebuild issue with any "
        "strategy capture limit exceeded named in limits_exceeded; each "
        "discovery example is a design as is; charges nothing; "
        "roadmap {} - every capability of this Challenge, what blocks it, and "
        "how many miners asked; "
        "run_python {source, files: [names of your own files to stage beside "
        "the program; [] stages none], seconds?: a wall allowance in whole "
        "seconds - omit it for none unless you set a compute-time budget, "
        "device?: cpu (the default) or gpu - gpu only where the initial "
        "observation lists a GPU lane, hypothesis, expected_effect}. A run "
        "spends one research-trial slot; Carbon sets no limit on its time, "
        "memory, CPU or output size. The program runs with the staged files "
        "in its working directory; the files it writes to ../output "
        "(/scratch/output), top level and at most 8 MiB each, are exported to "
        "your workspace as <last 20 characters of the task id>-<name> and "
        "listed in workspace_exports. Its result returns program_output: the "
        "last 4096 bytes of stdout and of stderr and, on a nonzero exit, the "
        "tail of the traceback. "
        "A request refused before dispatch returns REJECTED_BEFORE_DISPATCH "
        "with correction_code, field and correction: nothing started and no "
        "research-trial slot was charged; correct the named field and call "
        "again. A request refused when it runs completes with outcome "
        "REQUEST_REFUSED and the same three fields."
    ),
    "get_research_result": (
        "Read one task's state and result again by its task_id. "
        "start_research_task already returns a finished task's result, so "
        "this is for reading it again. poll_sequence is 0 for the first read "
        "of a task and one more for each later read of the same task."
    ),
    "cancel_research_task": (
        "Cancel a task that is still running, by its task_id. A finished task "
        "answers that it is too late."
    ),
    "inspect_prior_alignment": (
        "Unavailable: no prior pack is registered. It computes nothing and "
        "returns UNAVAILABLE, recorded as a refusal; it is not worth a call."
    ),
}
TOOLS_V2 = [
    (
        {**tool, "description": DESCRIPTIONS_V2.get(tool["name"].removeprefix(PREFIX))}
        if tool["name"].removeprefix(PREFIX) in DESCRIPTIONS_V2
        else tool
    )
    for tool in json.loads(canonical(TOOLS))
]
#: What run_julia adds to start_research_task's description, per rule.
_JULIA = {
    None: (
        " Prospectively admitted run_julia uses the same workspace arguments as run_python "
        "plus optional environment: current (default; newest SciML core - "
        "ModelingToolkit, Symbolics, OrdinaryDiffEq/DifferentialEquations, Lux, Enzyme, "
        "Zygote, Optimization, SymbolicRegression, NeuralOperators, FFTW, Turing and "
        "more) or pde (NeuralPDE, MethodOfLines, DataDrivenDiffEq on the prior core). "
        "Julia 1.13.0, packages pinned and precompiled in the isolated image; no runtime "
        "package installation. Exports: finite .json, little-endian finite .f64le, "
        "UTF-8 .txt, at most 8 MiB each. All output remains MINER_SELF_REPORTED."
    ),
    TOOLS_RULE: (
        " run_julia takes the same workspace arguments as run_python, "
        "including seconds and device, plus optional environment: current "
        "(default; newest SciML core - ModelingToolkit, Symbolics, "
        "OrdinaryDiffEq/DifferentialEquations, Lux, Enzyme, Zygote, "
        "Optimization, SymbolicRegression, NeuralOperators, FFTW, Turing and "
        "more) or pde (NeuralPDE, MethodOfLines, DataDrivenDiffEq on the prior "
        "core). device=gpu runs only in current, which carries CUDA.jl. Each "
        "run_julia spends one research-trial slot, as run_python does. Julia "
        "1.13.0, packages pinned and precompiled in the isolated image; no "
        "runtime package installation. Exports from ../output: finite .json, "
        "little-endian finite .f64le, UTF-8 .txt, at most 8 MiB each. Its "
        "result returns program_output as run_python's does. All output "
        "remains MINER_SELF_REPORTED."
    ),
}
#: `tools_for_sdk` reads the rule from the campaign unless given one.
_FROM_CAMPAIGN = object()


def frozen_tools_rule(manifest):
    """The research tools rule a frozen campaign manifest's run plan records.

    None - the historical tools - when the plan names none, or when the
    manifest has no run plan object at all. A rule this code does not know is
    refused, never read as the historical one.
    """
    plan = manifest.get("provider") if type(manifest) is dict else None
    rule = plan.get("research_tools") if type(plan) is dict else None
    if rule is not None and rule not in TOOLS_RULES:
        raise ValueError("unknown research tools rule")
    return rule


def campaign_tools_rule(ledger):
    """The rule the ledger's frozen campaign manifest records (None without
    a ledger, or before a manifest is frozen)."""
    if not callable(getattr(ledger, "db", None)):
        return None
    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    return None if row is None else frozen_tools_rule(json.loads(row[0]))


def tools_for_sdk(sdk, rule=_FROM_CAMPAIGN):
    """Prospective discovery only; historical campaign tool schemas are immutable.

    `rule` is a research tools rule (`TOOLS_RULES`) or None for the historical
    tools; omitted, it is the one the SDK's campaign froze in its run plan
    (`frozen_tools_rule`), so a campaign is offered the tools it froze."""
    if rule is _FROM_CAMPAIGN:
        rule = campaign_tools_rule(getattr(sdk, "ledger", None))
    if rule is not None and rule not in TOOLS_RULES:
        raise ValueError("unknown research tools rule")
    base = TOOLS if rule is None else TOOLS_V2
    image = getattr(
        getattr(getattr(sdk, "composition", None), "executor", None),
        "julia_image",
        None,
    )
    if image is None:
        return base
    from .julia_analysis import authorize_julia

    authorize_julia(sdk.ledger, sdk.owner, image)
    result = json.loads(canonical(base))
    tool = next(
        item for item in result if item["name"] == PREFIX + "start_research_task"
    )
    tool["parameters"]["properties"]["action"]["enum"].append("run_julia")
    tool["description"] += _JULIA[rule]
    return result


#: The protocol's bound on a workspace task's encoded arguments
#: (`carbon.research.model`, DevelopmentWorkspaceTaskSpec), in UTF-8 bytes.
WORKSPACE_ARGUMENT_BYTES = 12_288


def _object(args, field):
    """`args[field]` decoded as the one JSON object it must encode, or the
    refusal that names the field."""
    try:
        return _json(args[field])
    except ValueError:
        raise TaskContractMismatch("json_object_required", field) from None


def _task_id(args):
    try:
        return research.ResearchTaskId(args["task_id"])
    except (ValueError, TypeError):
        raise TaskContractMismatch("task_id_invalid", "task_id") from None


def _bounded(args, field, low, high):
    """Refuse, naming `field`, an integer argument outside its schema's range."""
    value = args[field]
    if type(value) is not int or value < low or (high is not None and value > high):
        raise TaskContractMismatch("tool_value_invalid", field)


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


class PreDispatchRefusal(Exception):
    """A refusal raised where nothing can have been dispatched yet.

    A distinct type rather than a flag, because the caller's transport catches
    every other exception and conservatively reports that dispatch *may* have
    occurred - which is right when the controller could be holding an ambiguous
    reservation, and wrong when the refusal fired before any reservation was
    possible. Those two are indistinguishable once both are `Exception`, and a
    miner told their work may have started when it provably did not will go
    looking for consumption that does not exist.

    Raised only where the refusal is established up front - no campaign, or
    admission closed before any reservation - so every instance is one where
    "nothing happened" is a fact rather than a hope.
    """

    def __init__(self, reason: str, *, next_action: str):
        super().__init__(reason)
        self.reason = reason
        self.next_action = next_action


class ResearchMinerTools:
    def __init__(self, *, connection, wrapper, composition, ledger, owner):
        self.connection, self.wrapper, self.composition = (
            connection,
            wrapper,
            composition,
        )
        self.ledger, self.owner = ledger, owner

    @property
    def challenge(self):
        """The Challenge this SDK's composition serves. The composition names
        it (`research_service` records Burgers for the historical campaign);
        a composition that names none is refused rather than given one."""
        challenge = getattr(self.composition, "challenge", None)
        if challenge is None:
            raise ValueError("the research composition names no Challenge")
        return challenge

    def _check_values(self, action, arguments, key, identity):
        """The executor's own value check, before dispatch (LP-PROD-D).

        A value Carbon would refuse starts no task, charges no trial slot and
        is answered with its code, field and fix, rather than becoming a task
        that fails as infrastructure. The checks that read the workspace or
        the budget are skipped when this operation id already started a task:
        resending it returns that task, so a write that already happened is
        never then refused for its own guard."""
        from .research_tasks import WorkspaceRequestRefused, check_workspace_request

        c = self.composition
        started = getattr(getattr(c, "tasks", None), "started_task", None)
        state = not (callable(started) and started(key, identity) is not None)
        try:
            check_workspace_request(c.executor, action, arguments, state=state)
        except WorkspaceRequestRefused as refused:
            raise TaskContractMismatch(
                refused.code, refused.field, refused.choices
            ) from None

    def _request(self, operation, args, identity):
        c = self.composition
        # A JSON-string field sent as a JSON object (or list, or number) is
        # named before anything parses it. JSON null stays the per-kind rule.
        for field in NULLABLE_TASK_FIELDS:
            if field.endswith("_json") and field in args:
                value = args[field]
                if value is not None and type(value) is not str:
                    raise TaskContractMismatch("json_string_required", field)
        if (
            operation == "start_research_task"
            and args.get("kind") == "workspace"
            and args.get("arguments_json") is None
        ):
            raise TaskContractMismatch("json_string_required", "arguments_json")
        # The composition's own Challenge, never a default: a battery
        # composition's requests name battery, and the gateway refuses any
        # request whose key differs from the one it authenticates for.
        key = self.challenge
        support = c.discovery.info.training_support_ref
        if operation == "get_challenge_info":
            return research.GetChallengeInfoRequest(key)
        if operation == "get_interaction_manifest":
            return research.GetInteractionManifestRequest(key)
        if operation == "get_prior":
            return research.GetPriorRequest(key, research.NoPriorSelector())
        if operation == "get_mock_scaffold":
            return research.GetMockScaffoldRequest(key, support, None)
        if operation == "dry_validate":
            return research.DryValidateRequest(key, _object(args, "strategy_json"))
        if operation == "compile_strategy":
            return research.CompileStrategyRequest(
                key, _object(args, "strategy_json"), support
            )
        if operation == "inspect_resources":
            return research.InspectResourcesRequest(
                key, _object(args, "strategy_json"), c.inspection.policy_ref
            )
        if operation == "forecast_resources":
            strategy = _object(args, "strategy_json")
            _bounded(args, "seconds", 1, 600)
            return research.ForecastResourcesRequest(
                key, strategy, c.inspection.policy_ref, args["seconds"]
            )
        if operation == "get_research_result":
            task = _task_id(args)
            _bounded(args, "poll_sequence", 0, None)
            return research.GetResearchResultRequest(key, task, args["poll_sequence"])
        if operation == "cancel_research_task":
            return research.CancelResearchTaskRequest(key, _task_id(args), identity)
        if operation != "start_research_task":
            raise ValueError("operation requires unavailable prior")
        for name in ("hypothesis", "expected_effect"):
            if type(args[name]) is not str or not 1 <= len(args[name]) <= 2048:
                raise TaskContractMismatch("tool_text_bounded", name)
        if args["kind"] == "practice":
            # The first field that breaks the contract is the one named.
            if (
                type(args["strategy_json"]) is not str
                or args["strategy_json"] == "null"
            ):
                raise TaskContractMismatch("practice_recipe_required", "strategy_json")
            for field in ("action", "arguments_json"):
                if args[field] is not None:
                    raise TaskContractMismatch("practice_recipe_required", field)
            strategy = _object(args, "strategy_json")
            # A backend this host cannot practise is refused here, before
            # anything starts or is charged, with the backends it serves.
            served = getattr(
                getattr(getattr(c, "executor", None), "practice", None),
                "backend_refusal",
                None,
            )
            refused = served(strategy) if callable(served) else None
            if refused is not None:
                raise TaskContractMismatch(
                    "backend_not_served", "strategy_json", refused
                )
            spec = research.PracticeTaskSpec(strategy, None)
        elif args["kind"] == "workspace":
            if args["strategy_json"] is not None:
                raise TaskContractMismatch(
                    "workspace_recipe_forbidden", "strategy_json"
                )
            if args["action"] not in (*DEVELOPMENT_WORKSPACE_ACTIONS, "run_julia"):
                raise TaskContractMismatch("workspace_action_unknown", "action")
            constructor, version = (
                research.DevelopmentWorkspaceTaskSpecV1,
                "carbon.autoresearch.workspace.v1",
            )
            if args["action"] == "run_julia":
                from .julia_analysis import authorize_julia

                image = getattr(getattr(c, "executor", None), "julia_image", None)
                if image is None:
                    raise TaskContractMismatch("workspace_action_unknown", "action")
                authorize_julia(self.ledger, self.owner, image)
                constructor, version = (
                    research.DevelopmentWorkspaceTaskSpecV2,
                    "carbon.autoresearch.workspace.v2",
                )
            arguments = _object(args, "arguments_json")
            from .research_tasks import workspace_fields

            # The executor's own field table, checked before dispatch: a
            # request with the wrong fields starts no task, so it can never
            # be recorded as an infrastructure failure (tier 3A, N2).
            required, optional = workspace_fields(args["action"])
            missing = sorted(required - set(arguments))
            if missing:
                raise TaskContractMismatch(
                    "workspace_field_missing", "arguments_json." + missing[0]
                )
            if not set(arguments) <= required | optional:
                raise TaskContractMismatch(
                    "workspace_field_unexpected", "arguments_json"
                )
            text = canonical(arguments).decode()
            if len(text.encode()) > WORKSPACE_ARGUMENT_BYTES:
                # Named first: no other correction can make it fit.
                raise TaskContractMismatch(
                    "workspace_arguments_too_large", "arguments_json"
                )
            self._check_values(args["action"], arguments, key, identity)
            try:
                spec = constructor(version, args["action"], text)
            except ValueError:
                raise TaskContractMismatch(
                    "workspace_action_unknown", "action"
                ) from None
        else:
            raise TaskContractMismatch("tool_value_invalid", "kind")
        return research.StartResearchTaskRequest(
            key,
            identity,
            spec,
            support,
            research.NoPriorSelector(),
            c.inspection.policy_ref,
            c.inspection.resource_class_ref,
            c.discovery.manifest.practice_scope_ref,
        )

    async def task_call(self, mode, args, identity):
        """Trusted extension entry, retaining signing, admission and accounting."""
        if mode not in {"start", "observe", "cancel"}:
            raise ValueError("closed task mode required")
        import uuid

        token = _TASK_MODE.set(mode)
        try:
            operation = {
                "start": "start_research_task",
                "observe": "get_research_result",
                "cancel": "cancel_research_task",
            }[mode]
            return await self.call(
                PREFIX + operation,
                args,
                identity,
                transport_request_id="mcp-task-" + uuid.uuid4().hex,
            )
        finally:
            _TASK_MODE.reset(token)

    async def call(self, name, args, identity, *, transport_request_id=None):
        """Keep business identity stable while optionally renewing transmission.

        Legacy campaign calls retain their existing transport identity. External
        adapters supply a fresh transport request ID on each transmission while
        reusing ``identity`` for admission, task idempotency and cancellation.
        A fresh signature/request never grants another numerical allowance.
        """
        if self.ledger is None:
            # Checked once, for every research operation rather than only the
            # dispatching ones. They all reach the validator through
            # `supervised_call`, which requires a composition a campaign
            # supplies, so without one none of them can do anything - and
            # failing at the top says so honestly instead of failing deep with
            # a message about a campaign that is not accepting work.
            #
            # Written for an agent, because only an agent reaches it: the
            # browser never touches the sdk. It names no tool to call because no
            # operation creates a campaign.
            raise PreDispatchRefusal(
                "NO_CAMPAIGN",
                next_action=(
                    "This server has no campaign to account against, and no "
                    "operation on it creates one. Reconnect to a server with a "
                    "campaign attached, then retry with the same operation_id. "
                    "A budget is optional and is never what is missing here."
                ),
            )

        if name == PREFIX + "start_research_task" and (
            getattr(getattr(self.composition, "executor", None), "cleanup_only", False)
            or getattr(self.wrapper, "_closing", False)
        ):
            # Checked before any reservation or task admission, so refusing
            # here is a fact that nothing started, not a hope.
            raise PreDispatchRefusal(
                "ADMISSION_CLOSED",
                next_action=(
                    "This server is shutting down or cleaning up and admits no "
                    "new research. Nothing was started. Reconnect to a server "
                    "that is accepting work, then retry with the same "
                    "operation_id."
                ),
            )

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
        # A research-trial slot is charged by the executor that starts the
        # task, in its own reservation, and nowhere else: a request refused
        # before dispatch started nothing and costs no slot
        # (OWNER-BATTERY-V2-DISCLOSURE-01, change 9). The operation id is
        # still bound to its request here, charging nothing, so a changed
        # request under a used id is refused as a replay conflict. Ledgers
        # written before this keep their historical `trial-attempt-` charges.
        numerical = (
            name == PREFIX + "start_research_task"
            and type(args) is dict
            and (
                args.get("kind") == "practice"
                or args.get("action") in {"run_python", "run_julia"}
            )
        )
        if numerical:
            bound = self.ledger.reserve(
                "task-request-" + identity,
                owner=self.owner,
                phase="research",
                request=args,
                resources={},
            )
            if bound["dispatch"]:
                self.ledger.finish(
                    "task-request-" + identity,
                    owner=self.owner,
                    state="SUCCEEDED",
                    actual={},
                    result={"status": "REQUEST_BOUND", "trial_charged": False},
                )
        return await self._call(
            name, args, identity, transport_request_id=transport_request_id
        )

    def _journal(self, kind, body):
        """Record against the campaign journal, when there is a campaign.

        A journal entry belongs to a campaign. A miner who has not started one
        has nothing to write to, and that is a supported state rather than a
        missing dependency - registration gates the research environment, a
        campaign does not gate learning why a request was refused.

        The caller's feedback never depends on this. Every site that journals
        also returns the same record to the requester, so skipping the write
        loses the durable copy and nothing the miner was told.
        """
        if self.ledger is not None:
            self.ledger.note(owner=self.owner, kind=kind, body=body)

    def rejected(
        self,
        operation,
        args,
        identity,
        *,
        reason="contract_incompatibility",
        correction=None,
        field=None,
        choices=(),
        tool=None,
    ):
        """A pre-dispatch rejection is feedback, never an ambiguous execution.

        It is journalled as a refusal, not a capability request: the requester
        broke a disclosed contract, it did not ask for something Carbon lacks.
        Only the agent's own capability_request action files demand.

        With a registered correction, the result names its code, the field and
        (in the correction text) the tool, and lists any Carbon-written
        `choices`; `tool` is named only when it is a registered tool.
        """
        record = {
            "purpose": args.get("expected_effect", "Not supplied by the requester"),
            "operation": operation,
            "hypothesis": args.get("hypothesis", "Not supplied by the requester"),
            "public_evidence": "Rejected request " + identity,
            "request_digest": digest(canonical(args)),
            "reason": reason,
            "authority_granted": False,
        }
        if correction in TASK_CORRECTIONS:
            record["correction_code"] = correction
            record["field"] = field
        self._journal("refusal", record)
        result = {
            "status": "REJECTED_BEFORE_DISPATCH",
            "reason": reason,
            "detail": "Request does not satisfy the disclosed argument/recipe contract. Inspect capabilities and correct the request. Nothing started and no research-trial slot was charged.",
            "authority_granted": False,
        }
        if correction in TASK_CORRECTIONS:
            result["correction_code"] = correction
            result["field"] = field
            result["correction"] = task_correction(
                correction,
                field,
                args.get(field),
                choices=choices,
                tool=tool if tool in FIELDS else None,
            )
        return result

    async def _call(self, name, args, identity, *, transport_request_id=None):
        operation = name.removeprefix(PREFIX)
        if name != PREFIX + operation or operation not in FIELDS:
            # Never repeats the name sent: only that it is not a tool.
            return self.rejected(
                name,
                args if type(args) is dict else {},
                identity,
                correction="tool_unknown",
                field="tool",
            )
        if type(args) is not dict:
            return self.rejected(
                name,
                {},
                identity,
                correction="tool_arguments_object_required",
                field="arguments",
                tool=operation,
            )
        missing = sorted(set(FIELDS[operation]) - set(args))
        if missing or set(args) != set(FIELDS[operation]):
            # A missing field is a registered name; an extra one is the
            # requester's own text and is never repeated.
            return self.rejected(
                name,
                args,
                identity,
                correction="tool_field_missing" if missing else "tool_field_unexpected",
                field=missing[0] if missing else "arguments",
                tool=operation,
            )
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
            code, field = exc.args
            return self.rejected(
                operation,
                args,
                identity,
                correction=code,
                field=field,
                choices=exc.choices,
                tool=operation,
            )
        except (ValueError, TypeError, KeyError):
            # What no named check covers: the request as a whole, still
            # refused before anything could start.
            return self.rejected(operation, args, identity)
        # Authentication and execution exceptions remain operational stops. Only
        # the pre-dispatch closed request validation above is repairable feedback.
        cleanup_registration = getattr(
            self.connection, "check_cleanup_registration", None
        )
        observed = await (
            cleanup_registration()
            if (operation == "cancel_research_task" or _TASK_MODE.get() == "observe")
            and callable(cleanup_registration)
            else self.connection.check_registration()
        )
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
            self.challenge,
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
        mode = _TASK_MODE.get()
        result = await self.wrapper.supervised_call(
            body,
            headers,
            {self.owner: self.composition},
            **({"task_mode": mode} if mode is not None else {}),
        )
        if unavailable:
            value = {
                "operation": operation,
                "status": "UNAVAILABLE",
                "reason": "missing_data_support",
                "detail": "No registered public prior pack; no alignment computation occurred",
                "authority_granted": False,
            }
            # A refusal of an operation this profile cannot serve, not a
            # request for something: only the agent's own capability_request
            # action files demand, so the demand stream stays the agent's.
            self._journal("refusal", value)
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
                kind="refusal",
                body={
                    "operation": operation,
                    "request_digest": digest(canonical(args)),
                    "reason": "contract_incompatibility",
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
            **(
                {"original_operation_id": result["original_operation_id"]}
                if "original_operation_id" in result
                else {}
            ),
        }
