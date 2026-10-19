"""A fresh miner's open-tier MCP failure is actionable (Launchpad J0, 19 Oct).

With no runner profile, `carbon-mcp` serves the open tier. When that failed it
printed only "Carbon MCP unavailable." - no code, no next action. It now names
the closed code and the catalog's next action, and still never the exception's
text or a path.
"""

from __future__ import annotations

from carbon.miner_mcp import standard_cli
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS


def test_an_open_tier_failure_names_its_code_and_next_action(monkeypatch, capsys):
    async def failing(**_kwargs):
        raise RuntimeError("private detail /home/miner/secret")

    monkeypatch.setattr(standard_cli, "serve_open_tier", failing)
    assert standard_cli.main([]) == 2
    err = capsys.readouterr().err
    assert err == (
        "Carbon MCP unavailable: carbon_mcp_failed. "
        + NEXT_ACTIONS["carbon_mcp_failed"]
        + "\n"
    )
    assert "secret" not in err and "/home/" not in err
