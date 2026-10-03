"""Any MCP agent gets what Carbon's own agent gets (RSURF-D1, D5, D6).

- The research view and the journal are operation tools, generated from the
  one table: `carbon_campaign_view` and `carbon_note`.
- Attaching a campaign brings the research prompts, not only the tools and
  resources, and detaching takes them away again.
- The operations server offers the research skill, which an MCP client can
  only negotiate when the server is built.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_standard_mcp_adapter import make_adapter

from carbon.miner_mcp.mcp_operations import Attachment, operation_tool_names
from carbon.miner_mcp.mcp_skills import SKILL_URI, SKILLS_EXTENSION
from carbon.miner_mcp.open_tier import attach_campaign, create_open_tier_server

PROMPTS = {"carbon_research_workflow_v1", "carbon_research_workflow_v2"}


def prompts(server):
    return {prompt.name for prompt in asyncio.run(server.list_prompts())}


def test_the_view_and_the_journal_are_operation_tools():
    assert {"carbon_campaign_view", "carbon_note"} <= set(operation_tool_names())


def test_attaching_brings_the_research_prompts():
    server = create_open_tier_server()
    before = prompts(server)
    assert not PROMPTS & before
    attach_campaign(server, make_adapter()[1])
    assert PROMPTS <= prompts(server) - before


def test_detaching_removes_what_attaching_added(monkeypatch):
    from carbon.miner_mcp import standard_cli

    @contextlib.asynccontextmanager
    async def attached(configuration, campaign):
        yield make_adapter()[1], None

    monkeypatch.setattr(standard_cli, "attached", attached)
    server = create_open_tier_server()
    before = (set(server._prompt_manager._prompts), set(server._tool_manager._tools))
    attachment = Attachment(server, Path("/nowhere/profile.json"))
    result = asyncio.run(attachment.attach("a" * 32))
    assert PROMPTS <= set(result["research_prompts"])
    assert PROMPTS <= prompts(server)
    asyncio.run(attachment.detach())
    assert (
        set(server._prompt_manager._prompts),
        set(server._tool_manager._tools),
    ) == before


def test_the_operations_server_offers_the_research_skill(monkeypatch):
    from carbon.miner_mcp import open_tier, standard_cli
    from scripts.dev.miner_launchpad import runner

    built = []
    real = open_tier.create_open_tier_server

    def capture(**kwargs):
        server = real(**kwargs)

        async def no_stdio():
            return None

        server.run_stdio_async = no_stdio
        built.append(server)
        return server

    class Host:
        def configured(self):
            raise RuntimeError("no profile here")

        def close(self):
            return None

    monkeypatch.setattr(open_tier, "create_open_tier_server", capture)
    monkeypatch.setattr(
        runner.RunnerAdapter, "for_profile", classmethod(lambda cls, path: Host())
    )
    asyncio.run(standard_cli.serve_operations(Path("/nowhere/profile.json")))
    (server,) = built
    assert SKILLS_EXTENSION in {e.identifier for e in server._extensions}
    assert SKILL_URI in {str(uri) for uri in server._resource_manager._resources}
    assert {"carbon_campaign_view", "carbon_note"} <= set(server._tool_manager._tools)
    # Specimen: the bare open tier, with no profile, offers no skill.
    assert not create_open_tier_server()._extensions
