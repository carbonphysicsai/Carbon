# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The Autoscience Mira adapter: planned artifact handoff, live execution BLOCKED.

Mira is Autoscience Mira, https://www.autoscience.ai/mira (owner answer
2026-10-01). Its public material describes an ML research agent that reads
papers, matches techniques to a customer's repositories and implements
improvements. It does not establish a self-service integration contract: no
documented task API, tool mechanism, cancellation, usage reporting, spending
cap, workspace separation, version identifiers, red-team scope or output
rights. The capability report is
`docs/development/mira/CAPABILITY_REPORT.md`; every unverified item is
UNVERIFIED there.

Lead vendor research (2026-10-01, secondary sources: search results, because
autoscience.ai is blocked by this environment's network policy): Mira is
offered as early access by contacting the Autoscience team; pricing, docs, API,
SDK and MCP details are not public; it is described as deployed into customer
codebases, shipping improvements as code changes. The working integration mode
is therefore repository/artifact handoff (Mira proposes code or recipes; a
Carbon runner imports and executes them), unverified until the vendor confirms.

So this adapter verifies nothing and sends nothing. Every lifecycle operation
raises `ProviderUnavailable`, and the controller refuses to dispatch to it
because its capabilities are not `dispatchable`. No endpoint is invented here,
and no OpenAI-compatible inference access is treated as the Mira research
agent. Live Mira execution stays BLOCKED until the owner supplies verified
access (documentation or account evidence for the §3 questions) and a spending
grant (`grant.py`). Replacing this class is the only route to live execution,
and it needs that evidence first.
"""

from __future__ import annotations

from .provider import (
    Capabilities,
    IntegrationMode,
    ProviderUnavailable,
)

PROVIDER = "autoscience-mira"
PRODUCT = "Autoscience Mira"
PRODUCT_URL = "https://www.autoscience.ai/mira"
INQUIRY_URL = "https://www.autoscience.ai/get-started"
BLOCKED = (
    "live Mira execution is BLOCKED: no verified integration contract "
    "(task supply, cancellation, usage, spending limits, workspace separation) "
    "and no completed spending grant (spending is approved in principle; the "
    "per-campaign ceiling is unset); see docs/development/mira/CAPABILITY_REPORT.md"
)


class MiraProvider:
    """Refuses every operation until the integration contract is verified."""

    def capabilities(self) -> Capabilities:
        return Capabilities(
            provider=PROVIDER,
            # The planned mode; unverified, so never dispatchable.
            mode=IntegrationMode.ARTIFACT_HANDOFF,
            verified=False,
            supports_idempotent_start=False,
            supports_cancel=False,
            reports_worker_termination=False,
            reports_usage=False,
            basis=(
                "planned mode from secondary sources (search results; vendor site "
                "blocked here); public product description only; every lifecycle, billing, "
                "isolation and rights question is UNVERIFIED (" + INQUIRY_URL + ")"
            ),
        )

    def _refuse(self, *_args, **_kwargs):
        raise ProviderUnavailable(BLOCKED)

    start = find = status = events = artifacts = cancel = usage = _refuse
