"""The MCP door onto Carbon's Challenge registry: list and describe.

Open tier, like onboarding: a miner decides which Challenge to research before
they own a campaign, so discovery needs no campaign, no ledger and no
registration, and it creates, consumes and grants nothing.

Selecting a Challenge is not a tool here. A selection is bound where work is
admitted: `launch` records the exact Challenge id and version in the frozen
campaign manifest, and every research operation of that campaign is then
served by that Challenge's composition. There is no default and no fallback.
"""

from __future__ import annotations

from typing import Annotated

PREFIX = "carbon_challenges_v1__"
CATALOG_URI = "carbon://challenges/v1/catalog"
COMPACT_SCHEMA = "carbon.challenge-description.compact.v1"

#: The practice-call corrections an agent meets first while sending a recipe,
#: by their registered `research_tools.TASK_CORRECTIONS` codes.
_COMPACT_TASK_CORRECTIONS = ("practice_recipe_required", "json_string_required")
#: The Level 0 compile codes a strategy most often meets, by their registered
#: `construction.compiler` texts.
_COMPACT_STRATEGY_CODES = (
    "strategy.challenge_mismatch",
    "strategy.backbone_mismatch",
    "parameter.unknown",
    "parameter.missing_required",
    "parameter.domain_mismatch",
)


def _names(field):
    """The names a recipe binds: a mapping's keys or a list's items."""
    if isinstance(field, dict):
        return list(field)
    if isinstance(field, list):
        return [name for name in field if isinstance(name, str)]
    return None


def _template(kind, document):
    """An unfilled graph recipe template: its source names no graph yet, so
    it is not ready to send (graph route v2's `graph_route.example`)."""
    source = document.get("source") if isinstance(document, dict) else None
    return (
        kind == "recipe"
        and isinstance(source, dict)
        and source.get("kind") == "graph"
        and source.get("submission_digest") is None
    )


def _ready_example(described):
    """The first published example the description itself marks ready: a
    one-key {kind: document}, admitted where an admission verdict is listed,
    and not an unfilled graph template."""
    examples = described.get("examples") or []
    verdicts = described.get("examples_admission")
    for index, example in enumerate(examples):
        if not isinstance(example, dict) or len(example) != 1:
            continue
        if verdicts is not None and not (
            index < len(verdicts) and verdicts[index].get("valid") is True
        ):
            continue
        ((kind, document),) = example.items()
        if _template(kind, document):
            continue
        return kind, document
    return None, None


def _refusal_hints(kind):
    """Registered refusal codes and their registered text, grouped by text:
    never written here, never a requester's words."""
    from carbon.development_session.research_tools import TASK_CORRECTIONS

    pairs = [(code, TASK_CORRECTIONS[code]) for code in _COMPACT_TASK_CORRECTIONS]
    if kind == "recipe":
        from carbon.development_session.research_service import (
            _RECIPE_ISSUE_PATH,
            RECIPE_ISSUE_DEFAULT,
            RECIPE_ISSUE_TEXT,
        )

        pairs.append(("construction_recipe_malformed", RECIPE_ISSUE_DEFAULT))
        pairs += [
            (code, RECIPE_ISSUE_TEXT.get(code, RECIPE_ISSUE_DEFAULT))
            for code in _RECIPE_ISSUE_PATH
        ]
    elif kind == "strategy":
        from carbon.construction.compiler import _ISSUE_MESSAGES

        pairs += [(code, _ISSUE_MESSAGES[code]) for code in _COMPACT_STRATEGY_CODES]
    grouped = {}
    for code, text in pairs:
        grouped.setdefault(text, []).append(code)
    return [{"codes": codes, "fix": text} for text, codes in grouped.items()]


def compact_description(described):
    """The essentials for building one recipe, projected from the full public
    description `described` (so it adds nothing hidden): interface names,
    catalog ids, one ready example, source kinds and refusal hints. An item a
    version does not have is null with its reason, never silently absent."""
    models = described.get("models") or {}
    interface = described.get("interface") or {}
    catalog = models.get("catalog") if isinstance(models, dict) else None
    adapter = models.get("graph_training_adapter") if isinstance(models, dict) else None
    kind, ready = _ready_example(described)

    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    catalog_ids = sorted(entries) if isinstance(entries, dict) else None

    kinds = []
    for holder in (catalog, adapter):
        if isinstance(holder, dict) and isinstance(holder.get("source_kind"), str):
            kinds.append(holder["source_kind"])
    if kind == "recipe" and isinstance(ready, dict):
        source_kind = (ready.get("source") or {}).get("kind")
        if isinstance(source_kind, str):
            kinds.append(source_kind)
    source_kinds = sorted(set(kinds)) or None

    rebuildable = models.get("rebuildable") if isinstance(models, dict) else None
    backbones = [
        m["selector"]
        for m in rebuildable or []
        if isinstance(m, dict) and isinstance(m.get("selector"), str)
    ]

    compact = {
        "schema": COMPACT_SCHEMA,
        "challenge_id": described.get("challenge_id"),
        "version": described.get("version"),
        "title": described.get("title"),
        "status": described.get("status"),
        "interface": {
            "inputs": _names(interface.get("inputs")),
            "outputs": _names(interface.get("outputs")),
        },
        "backbones": backbones or None,
        "catalog_ids": catalog_ids,
        "ready_recipe_kind": kind,
        "ready_recipe": ready,
        "source_kinds": source_kinds,
        "refusal_hints": _refusal_hints(kind),
        "full_answer": "describe with compact=false gives every field",
    }
    reasons = {}
    if catalog_ids is None:
        reasons["catalog_ids"] = "this version serves no backbone catalog"
    if ready is None:
        templated = any(
            isinstance(example, dict)
            and len(example) == 1
            and _template(*next(iter(example.items())))
            for example in described.get("examples") or []
        )
        reasons["ready_recipe"] = (
            "no tested catalog entry yet: stage your graph and fill the graph "
            "template in describe's examples (graph_route.example on graph route "
            "v2) with its submission_digest"
            if templated
            else "this version publishes no admitted example"
        )
    elif kind == "strategy":
        reasons["ready_recipe"] = (
            "this version takes a Level 0 strategy (schema_version, challenge_id, "
            "backbone, parameters), sent as is"
        )
    if source_kinds is None:
        reasons["source_kinds"] = (
            "this version takes no construction recipe source"
            if kind != "recipe"
            else "the description names no source kind"
        )
    if not backbones:
        reasons["backbones"] = "the description lists no rebuildable backbone"
    if reasons:
        compact["reasons"] = reasons
    return compact


def configured_host_facts(profile=None):
    """This host's facts, with the operator-configured ones from a runner
    profile: a trusted worker image counts only once it loads and the host's
    numerical doctor accepts it, and counts as the PyTorch CPU worker only
    when it is that pinned parent."""
    from carbon.challenge_registry import HostFacts

    configured = set()
    paths = (profile or {}).get("paths", {})
    manifest = paths.get("image_manifest")
    if manifest:
        try:
            from carbon.reconstruction.worker.docker_runtime import (
                doctor,
                load_image_identity,
            )

            image = load_image_identity(manifest)
            if doctor(image_id=image.image_id, image_identity=image).eligible:
                configured.add("trusted_worker_image")
                from carbon.challenge_registry.registry import TORCH_CPU_WORKER
                from carbon.development_session.gpu_practice import (
                    direct_parent_backend,
                )

                if direct_parent_backend(image) == "torch_cpu":
                    configured.add(TORCH_CPU_WORKER)
        except Exception:  # noqa: BLE001, S110 - an unusable image is a missing fact
            pass
    return HostFacts.observe(configured)


def make_challenge_tools(*, guard=None, host_facts=None):
    """`list` and `describe`, over `carbon.challenge_registry`. `host_facts` is a
    zero-argument callable returning `HostFacts`; by default this host is
    observed with nothing operator-configured."""
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.mcpserver.tools import Tool
    from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
    from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model

    from carbon import challenge_registry as challenges

    class StrictArguments(ArgModelBase):
        model_config = ConfigDict(strict=True, extra="forbid")

    class ExactMetadata(FuncMetadata):
        def pre_parse_json(self, data):
            return data

    class ChallengeResult(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        operation: str
        payload: dict[str, JsonValue]
        official_eligible: bool = False

    facts = host_facts or challenges.HostFacts.observe
    identifier = Annotated[str, Field(min_length=1, max_length=96)]

    list_model = create_model("challenges_list", __base__=StrictArguments)
    describe_model = create_model(
        "challenges_describe",
        __base__=StrictArguments,
        challenge_id=(identifier, Field(..., description="The exact Challenge id.")),
        version=(
            Annotated[str, Field(min_length=1, max_length=32)] | None,
            Field(
                ..., description="The exact version; null only for unversioned entries."
            ),
        ),
        compact=(
            bool,
            Field(
                False,
                description=(
                    "true returns only what building a recipe needs: interface "
                    "names, catalog ids, one ready recipe, source kinds and "
                    "refusal hints. Default false: the full description."
                ),
            ),
        ),
    )

    async def list_challenges():
        if guard is not None:
            guard()
        return ChallengeResult(operation="list", payload=challenges.catalog(facts()))

    async def describe(challenge_id, version, compact=False):
        if guard is not None:
            guard()
        try:
            payload = challenges.describe(challenge_id, version, host=facts())
        except challenges.ResolutionError as refused:
            # A stable code and the next step; the caller's text never echoes.
            raise ToolError(
                f"{refused.code}; next_action={refused.next_action}"
            ) from None
        if compact:
            payload = compact_description(payload)
        return ChallengeResult(operation="describe", payload=payload)

    from mcp_types import ToolAnnotations

    def tool(fn, name, model, description):
        return Tool(
            fn=fn,
            name=PREFIX + name,
            description=description,
            parameters=model.model_json_schema(),
            fn_metadata=ExactMetadata(arg_model=model, output_model=ChallengeResult),
            is_async=True,
            # Reading the registry changes nothing (H18).
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
        )

    return [
        tool(
            list_challenges,
            "list",
            list_model,
            "Every Carbon Challenge: implemented, reserved or deferred, with each "
            "execution profile's requirements and whether it is usable on this "
            "host now. Reads only; grants nothing.",
        ),
        tool(
            describe,
            "describe",
            describe_model,
            "One Challenge in full: task, interface and units, public material, "
            "reference method, models and controls, limits, exam gates, permitted "
            "feedback, validated examples and unsupported capabilities. "
            "compact=true returns only the recipe essentials (interface names, "
            "catalog ids, one ready recipe, source kinds, refusal hints). Refuses "
            "an unknown, reserved, deferred or wrong-version Challenge by code.",
        ),
    ]


def register_catalog_resource(server, *, guard=None, host_facts=None):
    import json

    from carbon import challenge_registry as challenges

    facts = host_facts or challenges.HostFacts.observe

    @server.resource(CATALOG_URI, mime_type="application/json")
    def catalog() -> str:
        if guard is not None:
            guard()
        return json.dumps(challenges.catalog(facts()), allow_nan=False)

    return catalog
