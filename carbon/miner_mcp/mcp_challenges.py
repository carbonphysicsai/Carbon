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


def configured_host_facts(profile=None):
    """This host's facts, with the operator-configured ones from a runner
    profile: a trusted worker image counts only once it loads and the host's
    numerical doctor accepts it."""
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
    )

    async def list_challenges():
        if guard is not None:
            guard()
        return ChallengeResult(operation="list", payload=challenges.catalog(facts()))

    async def describe(challenge_id, version):
        if guard is not None:
            guard()
        try:
            payload = challenges.describe(challenge_id, version, host=facts())
        except challenges.ResolutionError as refused:
            # A stable code and the next step; the caller's text never echoes.
            raise ToolError(
                f"{refused.code}; next_action={refused.next_action}"
            ) from None
        return ChallengeResult(operation="describe", payload=payload)

    def tool(fn, name, model, description):
        return Tool(
            fn=fn,
            name=PREFIX + name,
            description=description,
            parameters=model.model_json_schema(),
            fn_metadata=ExactMetadata(arg_model=model, output_model=ChallengeResult),
            is_async=True,
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
            "feedback, validated examples and unsupported capabilities. Refuses "
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
