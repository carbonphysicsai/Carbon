# MIRA-ADMISSION-01: supervised external research agent for admission testing

> **Superseded for this work, 2026-10-02 (OWNER-GRAPHITE-04).** The owner:
> "The plan is to use GRAPHITE not Mira for this testing." Graphite does the
> admission-testing work under
> `.agent/tickets/GRAPHITE-ADMISSION-01_graphite_admission_testing.md`. This
> ticket stays paused and is kept as history. What it built (the controller,
> boundaries, study sheet and design-search commitment layer, #475) is reused
> there. The Mira adapter keeps refusing every call.

**Authority:** the owner's handoff "integrate Autoscience Mira into Carbon's
internal admission testing" (2026-10-01), under OWNER-CHALLENGE-ADMISSION-01 as
amended 2026-10-01; owner answers of 2026-10-01 (Mira is Autoscience Mira,
https://www.autoscience.ai/mira; spending approved in principle with an
explicit, owner-supplied per-campaign ceiling).
**Primary map_ref:** SYSTEM/AGENT-EXECUTION; affects WAVE-C/C-09.
**Scope:** handoff §15 stages 1-2 only: repository and vendor reconciliation,
and the provider-independent implementation (adapter contract, fake provider,
durable campaign controller, spending grant, boundaries, Level-0 study sheet
prepared and not executed, design-search commitment layer, cost estimate).
No vendor contact, account, package, paid API, pod or campaign. No change to
EV4, its contract, panel or optimizer. No score, rule, permission or
qualification change.
**Status:** implementation; bounded engineering completion conditional on
required CI and normal merge under OWNER-DX-03.
**Paused by the owner, 2026-10-02** (OWNER-GRAPHITE-02: "stop Mira only").
No further Mira work, vendor contact or grant completion until the owner
resumes it. No code changed: the adapter keeps refusing every call.

## Definition of done

- Reconciliation, capability report (UNVERIFIED items marked), owner inquiry
  text and cost estimate in `docs/development/mira/`.
- A controller that persists intent, reserves worst-case spend, reconciles
  ambiguous dispatch, enforces limits outside the agent, halts on unknown state
  or usage, verifies cancellation, consumes findings and refuses expansion
  after one; crash recovery tested at each lifecycle boundary.
- The Mira adapter refuses every call; the controller cannot dispatch to it.
- Separate roles, workspaces and credentials; allowlisted research checkout;
  canary detection; EV4 material refused.
- Versioned search request/result with commitment before reference access.
- A real external-process MCP client test.
- Mutation tests showing each critical protection's test fails when disabled.

## Decisions

MIRA-D1 to MIRA-D5 are recorded in `docs/development/mira/README.md` §4.
Human-reserved values (grant and campaign ceilings, study population,
reconstruction tolerances, attacker model approval, isolation acceptance,
PB-INV/PB-ADV policies) remain HUMAN_INPUT and fail closed.

## Engineering verification

See the PR. Native-host results are diagnostics; canonical CI is acceptance.
