# Carbon Hub Newcomer Presentation Contract

**Decision:** `OWNER-HUB-01`  
**Date:** 2026-09-02  
**Status:** OWNER-DIRECTED presentation architecture  
**Owner:** Carbon owner  
**Primary map ref:** `SYSTEM/DEVELOPMENT-HUB`  
**Authority ceiling:** presentation, orientation, and routing only

## Decision

Carbon uses **one Development Hub with progressive disclosure**.

The default reader experience is **Overview**. It assumes the reader has never
heard of Carbon, Bittensor, SciML, miners, validators, MCP, Score Packs, or the
Wave system.

**Technical Detail** exposes the existing canonical Hub record for the same
Wave or ticket. Overview and Technical Detail may differ in density and
vocabulary. They may not carry different status, maturity, scientific meaning,
or product claims.

Do not create separate `Client` and `Dev` narratives that can drift.

## Newcomer contract

Every captured Wave Overview must answer:

1. **What are we building?**
2. **Why does Carbon need it?**
3. **What will be true when it is done?**
4. **What is still not true yet?**

Every captured ticket Overview must answer:

1. **What are we doing?**
2. **Why does it matter?**
3. **What changes when it is finished?**
4. **What does this ticket not do?**

The first sentence should make sense without Carbon-specific vocabulary.
Introduce canonical names after the underlying idea has been explained.

## Status contract

Overview may translate canonical status into these reader-facing labels:

| Canonical state | Overview label |
|---|---|
| Wave `closed`; ticket `done` | Built in bounded scope |
| Wave `active`; ticket `in_progress` | Building |
| Wave `planned`; ticket `todo` | Planned |
| Ticket `blocked` | Blocked |

The exact canonical status and maturity/authority ceiling remain owned by the
Technical Detail record.

`Built in bounded scope` does not mean scientifically qualified, security
qualified, network qualified, commercially validated, production qualified, or
LIVE unless those states are separately supported by repository authority.

## Data binding

Plain-language copy is split into reviewable, non-authoritative projections:

```text
data/newcomer_projection_v1.json
data/newcomer_tickets_wave_a_v1.json
data/newcomer_tickets_wave_b_v1.json
```

The Wave file carries the A-N roadmap projection. Ticket copy is split by
captured Wave so reviewers can inspect it without one large opaque data blob.

Every projection record binds to the same stable `map_ref` as its canonical
Wave or ticket. `tools/render_newcomer.py` fails if:

- a captured Wave or ticket lacks newcomer copy;
- newcomer copy contains an unknown Wave or ticket;
- the bound `map_ref` differs from the canonical stable location;
- projection files disagree on schema, map owner, or owner decision;
- generated Overview output is stale when `--check` is used.

Canonical status, title, dependencies, maturity, authority, specifications,
decisions, implementation evidence, and repository links remain owned by the
existing Hub and underlying repository records.

## Overview output

`tools/render_newcomer.py` generates:

```text
newcomer.html
technical.html
```

`newcomer.html` is the plain-English Overview. `technical.html` is a local
handoff to the existing complete `index.html` Hub.

The target public Pages behavior is to make Overview the front door while
preserving the current technical Hub as Technical Detail. **That publication
staging is not claimed active merely because this contract and renderer exist.**
Changing the Pages workflow crosses the Hub's existing authority-repin boundary
and must land through its own validated repository change.

## Copy rules

- Explain capability before naming the implementation object.
- Prefer concrete human questions over architecture labels.
- Keep scientific, network, commercial, and product-qualification authority
  separate.
- Preserve negative states. If the repository says a capability is planned,
  the Overview says `Planned`.
- Do not market future architecture as a live capability.
- Do not imply that Bittensor, revenue, a leaderboard, or a successful software
  test creates scientific truth.
- Do not place protected evaluation information, customer-confidential
  information, credentials, or private operational data in Overview.

## Decision record

**Established fact:** The existing Hub is an orientation layer; repository
authority controls exact semantics, implementation, review, tests, evidence,
and activation.

**Founder decision:** Make the Hub usable by a complete newcomer and use one
progressive-disclosure product rather than separate client and developer
narratives.

**Rationale:** One shared surface reduces claim drift and lets investors,
customers, researchers, miners, scientists, and engineers start from the same
company/system state before choosing depth.

**Risks:** Simplified language can overstate maturity or erase a scientific
boundary.

**Controls:** Exact canonical status and maturity remain in Technical Detail;
every newcomer record binds to one canonical map ref; future capabilities retain
explicit `still not true` language; the renderer rejects incomplete coverage.

**Reversibility:** High. The projection and renderer can be removed without
changing scientific, protocol, business, or implementation authority.

**Dependencies:** Current Hub stable IDs, deterministic generation, Hub
validation, and public-safe repository content.

**Affected projects:** Development Hub orientation and future Hub publication.

## Validation

Run the existing Hub checks plus:

```bash
python docs/development/carbon_hub/tools/render_newcomer.py
python docs/development/carbon_hub/tools/render_newcomer.py --check
```

The Overview is presentation evidence only. It grants no later maturity.
