"""An MCP server that starts before the miner has anything, and grows.

Two properties, and they are the whole point of the module.

The first is the access tier as a structural fact: before a campaign is
attached, the registered-tier tools are *absent*, not present-and-refusing.
That is the difference between a boundary and a per-tool check, and it is what
the D10 decision - registration gates the research environment - is worth.

The second is that attaching does not weaken anything. Attachment inserts
pre-built tools into a live registry rather than re-registering them through the
SDK, precisely because the SDK's `add_tool` would re-derive their metadata and
discard `ExactMetadata`. So the tests assert the strictness survived, and assert
that the guard which checks it actually refuses a tool that lost it.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_standard_mcp_adapter import make_adapter

from carbon.miner_mcp.mcp_onboarding import PREFIX as ONBOARDING_PREFIX
from carbon.miner_mcp.open_tier import (
    OPEN_TIER,
    CampaignAlreadyAttached,
    _assert_strict,
    attach_campaign,
    create_open_tier_server,
)
from carbon.miner_mcp.standard_server import PREFIX as RESEARCH_PREFIX

ONBOARDING = {
    ONBOARDING_PREFIX + name
    for name in ("requirements", "status", "prepare", "confirm")
}


def names(server):
    """The tools as a *client* sees them, not as the registry stores them."""
    return {tool.name for tool in asyncio.run(server.list_tools())}


def read(server, uri):
    return json.loads(asyncio.run(server.read_resource(uri))[0].content)


def test_the_server_starts_with_no_profile_campaign_or_ledger():
    """The failure this module exists to fix.

    `standard_cli.load_profile` needs a closed runner profile and a frozen
    campaign admitted by registration. An unregistered miner has none, so the tools telling them
    how to register were reachable only once they no longer needed them.
    """
    server = create_open_tier_server()
    assert names(server) == ONBOARDING


def test_the_registered_tier_is_absent_rather_than_refusing():
    """The tier boundary is what exists, not what each tool decides.

    Exposing the research tools and having them refuse would be less code and
    would leak the registered surface into the open tier. Asserted as absence so
    a later tool that refuses politely still fails this test.
    """
    server = create_open_tier_server()
    assert not [name for name in names(server) if name.startswith(RESEARCH_PREFIX)]


def test_the_open_tier_declares_its_own_boundary():
    server = create_open_tier_server()
    tier = read(server, "carbon://onboarding/v1/tier")
    assert tier["schema"] == OPEN_TIER
    assert tier["tier"] == "OPEN"
    assert tier["campaign_attached"] is False
    assert "compute selection" in tier["requires_registration"]


def test_the_exam_environment_is_readable_without_registration():
    """Public exam disclosure is open tier: it is what a miner reads to decide.

    And it discloses honestly to an unregistered reader: declared is not
    qualified, so the reader learns the environment exists and that nothing has
    certified it.
    """
    server = create_open_tier_server()
    environment = read(server, "carbon://validator/v1/exam-environment")
    assert environment["qualification"]["declared"] is True
    assert environment["qualification"]["qualified"] is False
    assert environment["qualification"]["backend_support"] == "UNRESOLVED"


def test_attaching_adds_the_registered_tier_to_the_live_server():
    """No restart: a miner registers mid-session and keeps their connection."""
    server = create_open_tier_server()
    added = attach_campaign(server, make_adapter()[1])

    assert added, "attachment reported nothing"
    live = names(server)
    assert {name for name in live if name.startswith(RESEARCH_PREFIX)} == set(added)
    assert ONBOARDING <= live, "onboarding survived attachment"


def test_attaching_publishes_the_registered_tier_resources():
    """Tools without their catalogue would be a half-attached server."""
    server = create_open_tier_server()
    before = set(server._resource_manager._resources)
    attach_campaign(server, make_adapter()[1])
    assert set(server._resource_manager._resources) > before


def test_the_tier_resource_reports_the_attachment():
    server = create_open_tier_server()
    attach_campaign(server, make_adapter()[1])
    assert read(server, "carbon://onboarding/v1/tier")["campaign_attached"] is True


def test_strict_argument_handling_survives_attachment():
    """The reason attachment does not go through the SDK's `add_tool`.

    `ExactMetadata` stops the pinned SDK parsing object-looking strings before
    strict validation. An attachment that re-derived metadata would silently
    produce laxer tools that answer identically until something malformed
    arrives - so the property is asserted on the tools a client actually gets.
    """
    server = create_open_tier_server()
    attach_campaign(server, make_adapter()[1])

    registry = server._tool_manager._tools
    research = [name for name in registry if name.startswith(RESEARCH_PREFIX)]
    assert research
    for name in research:
        metadata = registry[name].fn_metadata
        assert type(metadata).__name__ == "ExactMetadata", name
        assert metadata.pre_parse_json({"a": "{}"}) == {"a": "{}"}, name


def test_the_strictness_guard_refuses_a_tool_that_lost_its_metadata():
    """The guard is only worth having if it actually refuses.

    Built the way the SDK would build it - from a function - which is exactly
    the path that discards `ExactMetadata`.
    """
    from mcp.server import MCPServer

    plain = MCPServer("reference")

    def echo(value: str) -> str:
        return value

    plain.add_tool(echo)
    tool = plain._tool_manager._tools["echo"]

    with pytest.raises(RuntimeError, match="metadata was not preserved"):
        _assert_strict("echo", tool)


def test_a_second_campaign_is_refused_rather_than_replacing_the_first():
    """One server, one campaign. Replacing would need its own ownership lock."""
    server = create_open_tier_server()
    _sdk, adapter = make_adapter()
    attach_campaign(server, adapter)

    with pytest.raises(CampaignAlreadyAttached):
        attach_campaign(server, make_adapter(owner="bob")[1])

    assert ONBOARDING <= names(server), "the refusal changed nothing"


def test_the_open_tier_creates_no_campaign_and_touches_no_ledger(tmp_path, monkeypatch):
    """The tier rule, stated so it survives tools this test has not seen.

    Whatever the open tier grows, it must not create a campaign, consume compute
    or write the ledger. Exercised by running every open-tier tool that answers
    without a chain and looking for artefacts on disk.
    """
    monkeypatch.chdir(tmp_path)
    server = create_open_tier_server()

    result = asyncio.run(server.call_tool(ONBOARDING_PREFIX + "requirements", {}))
    assert result

    assert list(tmp_path.glob("**/*.sqlite3")) == []
    assert list(tmp_path.glob("**/campaign-manifest.json")) == []


def test_no_open_tier_tool_offers_to_sign():
    """Carbon never accepts key material, and nothing here signs.

    Asserted over tool names and their declared argument fields rather than
    prose, so the docstrings that *state* the rule cannot satisfy it.
    """
    server = create_open_tier_server()
    forbidden = ("sign", "mnemonic", "seed", "private", "keypair", "submit")

    for tool in asyncio.run(server.list_tools()):
        assert not any(word in tool.name for word in forbidden), tool.name
        fields = (tool.input_schema or {}).get("properties", {})
        assert not any(
            word in field.lower() for field in fields for word in forbidden
        ), (tool.name, sorted(fields))


def test_the_cli_serves_the_open_tier_when_no_profile_is_given(monkeypatch):
    """Reachability is the slice.

    The onboarding tools were already implemented and already tested before
    this; what they were not was *startable*, because the only entry point
    demanded the profile a new miner does not have. A mode nobody can start is
    not delivered, so the routing is asserted rather than assumed.
    """
    from carbon.miner_mcp import standard_cli

    served = []

    async def open_tier():
        served.append("open")

    async def campaign(configuration, campaign, *, cleanup_only=False):
        served.append(("campaign", configuration, campaign, cleanup_only))

    monkeypatch.setattr(standard_cli, "serve_open_tier", open_tier)
    monkeypatch.setattr(standard_cli, "serve", campaign)

    assert standard_cli.main([]) == 0
    assert served == ["open"]

    assert (
        standard_cli.main(
            ["--configuration", "/nowhere/profile.json", "--campaign", "a" * 32]
        )
        == 0
    )
    assert served[1][0] == "campaign"
    assert served[1][2] == "a" * 32


def test_a_profile_without_a_campaign_serves_every_operation(monkeypatch):
    """With a profile and no campaign, a miner's own client gets the operations
    tier - onboarding and every operation, launch included - instead of a
    refusal: creating a campaign needs nothing Carbon issues (gap 1.4)."""
    from carbon.miner_mcp import standard_cli

    served = []

    async def operations(configuration):
        served.append(("operations", configuration))

    monkeypatch.setattr(standard_cli, "serve_operations", operations)
    assert standard_cli.main(["--configuration", "/nowhere/profile.json"]) == 0
    assert served == [("operations", Path("/nowhere/profile.json"))]


def test_cleanup_only_without_a_campaign_is_refused():
    """Cleanup names a campaign. Without one the flag has no referent."""
    from carbon.miner_mcp import standard_cli

    with pytest.raises(SystemExit):
        standard_cli.main(["--cleanup-only"])


def test_the_open_tier_entry_point_takes_no_ownership_lock(monkeypatch):
    """It owns nothing, so it must not behave as though it does.

    Asserted by making the lock fail loudly: a path that reaches for it is a
    path that thinks it has a campaign.
    """
    from scripts.dev.miner_launchpad import controller

    def refuse(*args, **kwargs):
        raise AssertionError("the open tier took a campaign ownership lock")

    monkeypatch.setattr(controller, "owner_lock", refuse)

    server = create_open_tier_server()
    asyncio.run(server.call_tool(ONBOARDING_PREFIX + "requirements", {}))
