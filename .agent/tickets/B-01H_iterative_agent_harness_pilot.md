# Ticket B-01H — Carbon Iterative Agent Harness Pilot

**Wave:** B active in bounded development scope
**Status:** `in_progress`
**Owner decision:** `OWNER-DX-02`
**Depends on:** B-01F, completed B-04 delivery predicate
**Blocks:** B-05 start only; B-01G remains todo and non-blocking
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Delivery mode:** `SINGLE_TICKET_PR`
**Separate-contract exception:** `NOT_APPLICABLE`
**Starting base commit:** `650b035dae5629ae75b9e3f549b289f28cdbb9ba`
**Starting base tree:** `6d3664b3b29189cde8c7ffdeaa5a7c851f530955`

## Goal

Implement a bounded, executor-agnostic Harness-of-Harness controller around
independent Planner, Developer, and Tester invocations. B-05 is the first
planned pilot after this ticket closes, but this ticket does not implement any
B-05 scientific contract or runtime behavior.

## Owned scope

- deterministic outer-loop orchestration and strict versioned packets;
- isolated Planner, Developer, and Tester role contracts;
- exact authority, ticket, requirements-manifest, role-profile, candidate-head,
  and candidate-tree binding;
- requirement-state tracking, accepted evidence, explicit regressions, and
  regression-first replanning;
- deterministic external run-state persistence and identity-bound resume;
- progressive, controller-mediated repository context disclosure;
- an executor adapter seam, deterministic fake/manual adapters, and a Codex
  adapter using the verified supported `codex exec` surface;
- a non-authoritative B-05 requirements navigation manifest bound to the exact
  ticket bytes;
- synthetic end-to-end and focused CPU tests; and
- Development Hub and development-governance reconciliation.

## Authority ceiling

The harness proposes work and verifies engineering evidence. It cannot approve
or merge a pull request, satisfy Carbon's final Codex/GPT review gate, create
scientific truth or qualification, activate `LIVE`, authorize production,
accept security, create rights, choose economics, or implement B-05 science.
`FINAL_CANDIDATE_READY` hands the unchanged candidate to
`.agent/DELIVERY_PROTOCOL.md`.

## Working architecture

```text
current authority + selected ticket + requirements manifest
→ PLANNER (fresh/read-only projected context)
→ validated IterationPlan
→ DEVELOPER (fresh/workspace-write dedicated ticket worktree)
→ freeze exact candidate head/tree and changed-path manifest
→ TESTER (fresh/read-only projected candidate)
→ validated IterationEvidence
→ deterministic controller
    → PLANNING / PAUSED_HUMAN / PAUSED_INFRA / FINAL_CANDIDATE_READY
```

The controller, not a model assertion, owns state transitions. A requirement
becomes `VERIFIED` only from accepted evidence in a valid Tester packet. A
previously verified requirement that later fails becomes an explicit
regression and is required ahead of new work in the next plan.

## Role boundaries

- **Planner:** receives bounded disclosed context and structured prior evidence;
  cannot write the candidate and emits only a plan.
- **Developer:** writes only in the dedicated ticket worktree; receives the
  accepted plan and disclosed context; cannot certify requirements.
- **Tester:** starts in a fresh invocation, receives the exact frozen candidate
  and prior verified states but not developer self-assessment as evidence;
  cannot write or repair the candidate.

The Codex adapter uses explicit `read-only` or `workspace-write` sandbox modes,
`--ignore-user-config`, ephemeral independent invocations, and JSON Schema
output. Read roles operate on controller-built projections rather than the
writable ticket worktree. Controller identity and before/after Git checks are
additional fail-closed boundaries; they are not a production security audit.

## Definition of Done

- [ ] Strict v1 schemas and validators cover `RunManifest`,
      `RequirementsManifest`, `IterationPlan`, `IterationEvidence`, and
      `ControllerState`.
- [ ] Required statuses are exactly `UNTESTED`, `VERIFIED`, `FAILED`,
      `BLOCKED_HUMAN`, `BLOCKED_INFRA`, and `OUT_OF_SCOPE`.
- [ ] Unsupported `VERIFIED` claims and model-asserted authority transitions
      fail closed.
- [ ] Exact authority/head/tree, ticket, requirements, role-profile, and resume
      identities are checked at every transition.
- [ ] Planner and Tester are read-only; Developer is confined to the dedicated
      worktree and declared path scope.
- [ ] Regressions reopen verified requirements and lead the next plan.
- [ ] Protected hidden-evaluation paths and values cannot enter role packets,
      disclosures, or persisted run state.
- [ ] Run state is atomic and external to the reviewed tree under the Git common
      directory by default.
- [ ] The B-05 manifest maps stable IDs to unchanged ticket requirements and is
      bound to the exact ticket identity/digest.
- [ ] Synthetic evidence proves failure, replan, repair, independent success,
      and `FINAL_CANDIDATE_READY` handoff.
- [ ] Focused, invariant, full CPU, quality, delivery, and Hub checks applicable
      to the final classified manifest pass canonically.
- [ ] Exact-head checks, `Merge gate`, fresh complete-diff Codex/GPT review,
      finding repair/disposition, distinct non-author approval with receipt,
      `GPT review gate`, zero unresolved threads, normal exact-head merge,
      reviewed-tree preservation, exact-main `Merge gate`, and the normalized
      external receipt all pass before B-01H is `done` or B-05 starts.

## Human-reserved values

Every B-05 measurement, tolerance, weighting, uncertainty, applicability,
reconstruction-stage, stopping, qualification, physical, and production value
remains unavailable. The pilot manifest contains navigation text only. A run
using unresolved reserved values must remain explicit and fail closed; unrelated
authorized structural work may continue.

## Conditional closeout

This branch may prepare B-01H `done` and B-05 `in_progress` as its first pilot,
but those states remain inert until the complete delivery predicate above is
satisfied and its external receipt records the exact new `main`. The harness
Tester never substitutes for Carbon's final review process.
