"""Graphite on the miner path (CHALLENGE-PROTOCOL-04 slice 3).

Graphite drives the owner's battery campaign the way a miner's client does:
- it attaches through `standard_cli.attached`, which owns the campaign lock,
  generation, reconciliation and cleanup;
- it calls the same research operations through the bound SDK;
- practice runs in the campaign's carrier on the owner's host.

**What is refused.**
- A campaign that is not battery's.
- A campaign with its own agent. Graphite is the only agent, so its
  manifest says `agent: none`.

Graphite never submits. No role's manifest offers a submission tool, and its
selection is a candidate record that Carbon checks, rebuilds and scores
outside the agent (slice 4).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE


class MinerPathRefused(ValueError):
    """The campaign is not one Graphite may drive."""


def check_campaign(manifest):
    """Graphite drives only a battery campaign that has no agent of its own."""
    if (manifest.get("challenge") or {}).get("id") != BATTERY_CHALLENGE:
        raise MinerPathRefused("not_a_battery_campaign")
    if manifest.get("agent") != "none":
        raise MinerPathRefused("campaign_has_its_own_agent")
    return manifest


@contextlib.asynccontextmanager
async def battery_tools(configuration, campaign):
    """Attach to the owner's battery campaign. Yields `(sdk, profile)`: the
    bound SDK for `GraphiteProvider(miner_tools=...)`, and the campaign's
    loaded profile."""
    from carbon.miner_mcp.standard_cli import attached

    async with attached(Path(configuration), campaign) as (adapter, profile):
        check_campaign(profile.manifest)
        yield adapter.in_process_sdk(), profile
