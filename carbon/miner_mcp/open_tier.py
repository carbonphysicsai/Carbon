"""An MCP server a miner can start before they have anything.

The tools in `mcp_onboarding` were reachable only by someone who no longer
needed them. `standard_cli.load_profile` requires a closed runner profile and a
prepared, frozen campaign admitted by registration; an unregistered miner has
neither, so they could not start the server that would tell them how to
register. The browser had no such problem - its controller takes the
research profile as an optional flag - which left MCP strictly less capable than
the browser for the very first step, the exact inverse of the browser being a
client of the MCP layer.

So this starts with nothing: no profile, no campaign, no ledger.

**Attachment adds tools rather than unlocking them.** The registered tier could
have been exposed from the start with every research tool refusing until a
campaign arrived, which would have been less code. It would also have put the
registered-tier surface in front of an unregistered caller and relied on each
tool to refuse - the tier boundary becoming a per-tool check rather than a
property of what exists. The decision that registration gates the research
environment is better kept as: the tools are not there.

**Attaching does not restart.** A miner registers in the middle of a session,
and tearing down their connection at that moment would be both a poor first
experience and a state-loss hazard, at precisely the point they have just done
the one irreversible thing. So attachment mutates a live server.

One limitation, measured rather than assumed: **the pinned SDK sends no
list-changed notification.** A client sees the registered tier on its next
`tools/list`, not before. This is not a consequence of how attachment is
implemented here - the SDK's own `add_tool` has no notification path either, and
`MCPServer` exposes no such mechanism. A client that caches its tool list
indefinitely will not see the new tools until it re-lists. Worth knowing before
a front door is built on this; not worth working around inside the SDK.

What this does not do: decide *when* to attach. That is the caller's, because
the trigger differs by front door - an operator supplying a profile, a
confirmed registration, or a supervisor watching a path. This provides the
capability and refuses to guess the policy.
"""

from __future__ import annotations

OPEN_TIER = "carbon.mcp.open-tier.v1"

#: What an unregistered caller can reach. Named rather than implied, so the
#: boundary can be asserted instead of reviewed.
#:
#: The rule is the same one the browser door is tested against: nothing here
#: creates a campaign, consumes compute or touches the ledger.
OPEN_TIER_CAPABILITIES = (
    "chain onboarding: requirements, status, prepare, confirm",
    "the published validator exam environment",
    "capability discovery and guidance",
)


class CampaignAlreadyAttached(RuntimeError):
    """One server, one campaign. A second would need its own ownership lock."""


def create_open_tier_server(
    *, reader=None, context=None, guard=None, sink=None, **settings
):
    """A stdio server carrying only the open tier.

    `reader` and `context` are optional. Without them `requirements` still
    answers, which is what an unregistered visitor needs first, and the reads
    report that the operator configured no chain endpoint rather than guessing
    one.
    """
    from mcp.server import MCPServer

    from carbon.development_session.exam_environment import exam_environment
    from carbon.miner_mcp.mcp_onboarding import make_onboarding_tools

    server = MCPServer(
        "Carbon Onboarding",
        version="1.0.0",
        instructions=(
            "Carbon open tier. Register on the subnet before selecting research "
            "compute. Carbon never accepts a private key, seed phrase or "
            "mnemonic, and no tool here signs: you execute registration in your "
            "own wallet tooling. Reading grants no authority."
        ),
        tools=make_onboarding_tools(
            reader=reader, context=context, guard=guard, sink=sink
        ),
        **settings,
    )

    @server.resource(
        "carbon://validator/v1/exam-environment", mime_type="application/json"
    )
    def exam() -> str:
        import json

        if guard is not None:
            guard()
        return json.dumps(exam_environment(), allow_nan=False)

    @server.resource("carbon://onboarding/v1/tier", mime_type="application/json")
    def tier() -> str:
        import json

        if guard is not None:
            guard()
        return json.dumps(
            {
                "schema": OPEN_TIER,
                "tier": "OPEN",
                "available_without_registration": list(OPEN_TIER_CAPABILITIES),
                "requires_registration": [
                    "compute selection",
                    "campaigns and research services",
                    "submission",
                ],
                "rule": (
                    "Nothing in the open tier creates a campaign, consumes "
                    "compute or touches the ledger."
                ),
                "campaign_attached": bool(getattr(server, "_carbon_attached", False)),
            },
            allow_nan=False,
        )

    server._carbon_attached = False
    return server


def attach_campaign(
    server, adapter, *, guard=None, workbench=None, authorize_workbench=None
):
    """Add the registered tier to a running server, without restarting it.

    Returns the names added. Refuses a second attachment rather than silently
    replacing the first: one server owns one campaign, and a second would need
    its own ownership lock, generation and cleanup.

    The tools are taken from the real server factory and inserted into the live
    registry, rather than re-registered through the SDK's `add_tool`. That is
    deliberate and it is not a shortcut. `add_tool` re-derives a tool's metadata
    from its function signature, which would discard `ExactMetadata` - the
    override that stops the pinned SDK parsing object-looking strings before
    strict validation. Attaching that way would silently weaken argument
    validation on exactly the tools that most need it.

    So attachment must preserve the metadata, and `_assert_strict` checks that
    it did rather than assuming. The SDK version is already pinned and asserted
    elsewhere; if a future version changes the registry, that check fails loudly
    instead of quietly admitting laxer tools.
    """
    from carbon.miner_mcp.standard_server import _create_server

    if getattr(server, "_carbon_attached", False):
        raise CampaignAlreadyAttached("this server already owns a campaign")

    # A reference server built by the real factory, used only as the source of
    # correctly-constructed tools and then discarded. Registration performs no
    # I/O, so this costs an object rather than a connection.
    reference = _create_server(
        adapter,
        guard=guard,
        workbench=workbench,
        authorize_workbench=authorize_workbench,
    )

    added = []
    target = server._tool_manager._tools
    for name, tool in reference._tool_manager._tools.items():
        if name in target:
            continue
        _assert_strict(name, tool)
        target[name] = tool
        added.append(name)

    # The registered tier is not only its tools. `_create_server` also publishes
    # the capability catalogue and current guidance, and a miner who attached
    # rather than restarted would otherwise hold a server whose tools answer and
    # whose descriptions of them are absent.
    resources = server._resource_manager._resources
    for uri, resource in reference._resource_manager._resources.items():
        resources.setdefault(uri, resource)

    server._carbon_attached = True
    return tuple(added)


def _assert_strict(name: str, tool) -> None:
    """An attached tool must be as strict as a constructor-registered one.

    The property that matters is not that a tool arrived, but that it arrived
    with the argument handling Carbon requires. Checked, because the failure
    mode otherwise is silent: a laxer tool answers exactly like a strict one
    until something malformed reaches it.
    """
    metadata = getattr(tool, "fn_metadata", None)
    if metadata is None or type(metadata).__name__ != "ExactMetadata":
        raise RuntimeError(
            f"refusing to attach {name}: argument metadata was not preserved"
        )
