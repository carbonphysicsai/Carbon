# GOAL-WORKBENCH-14: public Workbench onboarding edition, Phase 1

Programme: #139 (client-facing scoping and onboarding). Owner authority: the
owner-forwarded GOAL-WORKBENCH-13 execution handoff of 2026-09-22, Phase 1.
The handoff proposed the identifier `GOAL-WORKBENCH-13` and asked for it to be
verified rather than assumed; it is taken, by the merged host repairs recorded
as `GOAL-WORKBENCH-13-D1` in `.agent/DECISIONS.md`. `GOAL-WORKBENCH-14` is the
next free identifier in the series, which runs 02 through 13.

Status: bounded engineering delivery. No scientific qualification, security
acceptance, deployment authority, customer-data collection or publication is
claimed or authorized.

Primary Development Hub map_ref: `SYSTEM/BUSINESS-AUTHORITY`; impact
`mapped_detail`.

## Problem

A prospective client has no way to arrive at a Carbon-shaped problem statement
on their own. The internal Workbench can hold and assess one, but reaching it
means a conversation, and what comes out of a conversation is prose that
somebody then retypes into the scope fields. The retyping is where the
definition quietly changes.

The existing client intake surfaces solve a different problem: they capture a
commercial decision — the baseline, its limitation, what result is wanted — not
the physical scope the structural check reads. Nothing today lets a visitor
state a physical problem, see concretely what is unresolved about it, and hand
over an artifact the team imports without translation.

## Working contract

One public build target, emitted from the same sources as the internal bundle,
carrying an explicit allow-list rather than an exclusion list, and running
entirely in the visitor's browser under `connect-src 'none'`.

The accepted structural check is reused **unchanged**.
`CarbonScientificStudies.check` reads only `design.scope` and
`design.reference_plan`, and its two dependencies on the outside world —
`root.fetch` and `root.CarbonFit` — are reached only from `createAdapter`,
which a public build never calls. So the check runs in a bundle with no network
capability at all, and no scientific, rights or qualification semantics change.

A public workspace artifact with its own schema identity and its own
deterministic digest, distinct from the internal
`goal_workspace.schema.json`, which pins `source_sha256` constants to the
internal build and cannot be copied into a public edition.

An internal import adapter that builds a design through the existing exported
`newDesign` constructor and applies the public artifact's scope and reference
plan. The accepted internal import paths are not changed.

### Definition of Done

1. `tools/build.py` gains an explicit public mode emitting one tracked artifact
   whose CSP carries `connect-src 'none'` and `form-action 'none'`.
2. The public bundle contains no internal evidence, source assessment, CPES
   material, private fixture, owner console surface or private-service connect
   UI, asserted on bundle **content** rather than on a source list.
3. A visitor with no expertise reaches a usable draft through progressive
   disclosure; an expert can fill the scope fields directly.
4. Every issue the check returns is shown, in plain language, and no issue is
   softened, hidden or reclassified. Issues are grouped by who can close them —
   the visitor, or Carbon — which is presentation over the returned list and
   invents no issue class.
5. Export is deterministic and carries its own digest.
6. A test proves the round trip: the public artifact is accepted by the internal
   adapter, binds the same design and revision identity, and produces the same
   structural check status and issue list on both sides.
7. The freshness gate's declared artifact set covers the new generated file, and
   the gate stays read-only.
8. `workbench_scope.py` requires the Workbench lane for the new paths, with test
   coverage rather than inspection.
9. Browser journeys run against the generated artifact at desktop and narrow
   widths, including zero outbound requests.
10. Nothing exported claims qualification, capability, cost, timeline or a
    Carbon commitment. `NOT_QUALIFIED` and authority effect `NONE` hold end to
    end.

## Boundaries

No AI or LLM integration, no network call of any kind, no account or
authentication, no inquiry receiver, submission endpoint, notification or
customer data, no deployment, Worker, Pages or DNS change, and no modification
of the live `/workbench/` page, whose source is not in this repository.

The owner-pinned `scripts/dev/classify_changes.py` and
`scripts/dev/development_scope.py` are not edited.

Phase 2 (bounded AI assist) and Phase 3 (receiver, retention, consent,
activation) are future direction and are not authorized here.

## What this edition is

An onboarding and scoping aid. It qualifies no physics, measures nothing,
commits Carbon to nothing, and its output is a draft for a conversation rather
than a result.
