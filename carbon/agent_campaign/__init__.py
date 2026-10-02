# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Supervised external research-agent campaigns for internal admission testing.

OWNER-CHALLENGE-ADMISSION-01 (amended 2026-10-01): an internal development
protocol, never mainnet and not a qualification gate. This package lets Carbon
use an external research agent (first: Autoscience Mira) for construction
research, adversarial research and optimizer development while Carbon keeps
every authority: dispatch, spend, stopping, evidence and grades.

- `provider`: the provider-independent adapter contract. Proposed Carbon-side
  operations, not claimed vendor endpoints.
- `mira`: the Autoscience Mira adapter. Live execution is BLOCKED until the
  owner supplies verified access and a spending grant; every operation refuses.
- `fake`: a deterministic in-process test double with fault injection.
- `grant`: the owner's spending grant; no grant, no dispatch.
- `boundaries`: separate roles, workspaces, credentials and an allowlisted
  research checkout; canary detection.
- `controller`: the durable campaign controller. It supervises the external
  agent, which `carbon.miner_mcp.agent_connection` deliberately does not.
- `study`: the Level-0 study sheet and permission inventory (prepared, not
  executed, not frozen while human values are missing).

Nothing here executes hostile code, authenticates a person, changes a score,
or grants scientific, security, economic or launch authority.
"""
