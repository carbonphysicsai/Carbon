# Ticket B-01F — Development Throughput Hardening

**Wave:** B active in bounded development scope
**Status:** `done` only under the conditional completion gate below
**Execution state before that gate:** owner-directed `in_progress` insertion;
B-04 runtime remains paused
**Depends on:** merged B-04 bounded engineering contract in PR #72
**Branch:** `agent/b-01f-development-throughput`
**Exact base commit/tree:** `79293d5b65efef8553c0583ba6cf9bc5d0922ff6` /
`62ccbe40d5df0c8c45403609dc14cc7ca892bb25`
**Decision:** `OWNER-DX-01`
**Plan:** `.agent/plans/B-01F_development_throughput_hardening.md`
**Evidence:** `.agent/evidence/wave_b/b-01f.md`
**Delivery mode:** `SINGLE_TICKET_PR`
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Hub impact:** `HUB_UPDATE_REQUIRED`; `map_structural`; affects
`SYSTEM/GOVERNANCE`, `SYSTEM/DEVELOPMENT-SEQUENCING`, `SYSTEM/CI`,
`SYSTEM/PR-MAINTENANCE`, `SYSTEM/DEVELOPMENT-HUB`,
`SYSTEM/DEVELOPMENT-HUB/VALIDATION`, `SYSTEM/MATURITY`, `WAVE-B`,
`WAVE-B/B-01F`, `WAVE-B/B-01G`, and `WAVE-B/B-04`

## Goal

Turn Carbon's owner-directed development-throughput rules into durable
repository authority and machine enforcement before B-04 runtime work begins.
The ticket removes avoidable approval, separate-contract, empty-commit,
host-environment, full-CI, and generated-Hub churn while preserving every
substantive engineering and human-reserved gate.

B-01F changes development delivery only. It does not alter the already merged
B-04 contract, implement a reference runtime, choose scientific values, accept
security risk, or grant qualification, `LIVE`, launch, or production authority.

## Definition of Done

- [x] Record `OWNER-DX-01`, the one-PR ticket default, standing merge-and-
      advance authority, exact-head merge predicate, post-merge predicate,
      Greptile routine correctness gate, asynchronous human oversight, and
      fail-closed human-reserved boundaries in repository protocols.
- [x] Add stable tracked evidence and normalized external completion-receipt
      authority. Remove any process requirement for commits whose only purpose
      is storing CI, review, merge, or validation-retrigger facts.
- [x] Make current pull-request body/state edits trigger Development Hub
      validation and make validation read the live body and current head, with
      a deterministic local override and tests proving declaration edits need
      no Git commit and cannot substitute for repository changes.
- [x] Add standard-library delivery-hygiene enforcement for tracked text,
      introduced commits, and author/committer identities, including real
      workstation paths, hostnames, and `.local` email rejection with narrow
      documented placeholder/fixture allowances.
- [x] Add `./scripts/dev/canonical.sh` as the one supported noncanonical-host
      entry point, with direct canonical execution, pinned `linux/amd64`
      container execution, correct worktree/Git metadata mounting, canonical
      non-root ownership, safe cache reuse, shell/focused/full support,
      deterministic dry-run, and fail-closed Docker behavior.
- [x] Classify changed paths as `RUNTIME_FULL`, `CONTRACT_AUTHORITY`, or
      `DERIVED_DOCUMENTATION`, fail unknown paths closed to `RUNTIME_FULL`, run
      delivery preflight before expensive work, and expose an always-present
      final job named exactly `Merge gate` that reflects every required job for
      the detected scope without weakening runtime acceptance.
- [x] Reduce Development Hub validation/render fan-out so a one-ticket
      semantic transition rewrites only semantically affected output, while
      preserving static-first, JavaScript-disabled, `file://`, accessibility,
      deterministic-generation, drift, route, and browser checks. After all
      non-Hub candidate content settles, reconcile the semantic Hub source and
      immutable event once and commit only the generated outputs whose rendered
      bytes truly change.
- [x] Update the pull-request template and add the short Codex launcher.
      Prepare a versioned main ruleset and an admin apply command with
      `--dry-run`; apply only with repository-administration permission and
      report the live state truthfully.
- [x] Queue B-01G as `todo` and explicitly non-blocking for B-04.
- [x] Bind the candidate to focused tests plus the full canonical B-01F
      acceptance, clean dev-container acceptance, Development Hub
      validation/render/route/
      browser checks, and `git diff --check`; require exact-head `Merge gate`,
      exact-head Greptile, repair of all valid findings, and zero unresolved
      Greptile threads.
- [x] Preserve PR #72's exact B-04 contract and add no B-04 runtime, solver,
      fixture runner, Julia service, Cole–Hopf method, artifact store,
      measurement, scoring, Dossier, B-05, B-06, B-07S, or later-ticket
      implementation.

## Conditional completion and B-04 resumption gate

The `done` status in this candidate and the coordinated selection of B-04's
runtime phase are inert until all of the following are true for this exact
candidate:

1. every scope-required exact-head check succeeds, including `Merge gate`;
2. Greptile Review succeeds on the same exact head;
3. every valid finding is repaired and reviewed, unresolved thread count is
   zero, and no applicable block remains;
4. the PR normally merges with an exact expected-head guard;
5. the merge's second parent equals the reviewed head and the merge tree equals
   the reviewed tree;
6. fetched `origin/main` equals that merge; and
7. exact-main `Merge gate` succeeds; and
8. the completed normalized external receipt, with no required `PENDING`
   field, is posted at its declared external location.

Only then is B-01F authoritatively `done` in its bounded delivery-tooling scope
and B-04 runtime implementation the selected work. If any predicate fails, the
pre-B-01F merged state remains controlling and B-04 runtime stays paused. No
recursive closeout commit or pull request is required merely to copy the
dynamic identities; use the external completion receipt.

## Maturity ceiling

```text
SPECIFIED: YES — BOUNDED DEVELOPMENT-SYSTEM CONTRACT
IMPLEMENTED: YES only when the conditional completion predicate passes
TESTED: YES only for the exact recorded delivery/tooling acceptance scope
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE / LAUNCH / DEPLOYMENT AUTHORITY: NO
```

## Human input

Repository administration permission is required to apply the prepared GitHub
ruleset. Insufficient credentials leave the artifact and smallest manual owner
action explicit; they do not permit a false claim that the live ruleset was
applied. No human response or silence gate is added to routine engineering
review or merge.

## Must not

Do not weaken runtime acceptance, required ticket dependencies, scientific or
statistical evidence, security review/acceptance, protocol compatibility,
rights, operational policy, qualification, `LIVE`, launch, deployment, or
production gates. Do not rewrite history, use squash/rebase merge, enable
auto-merge, grant a routine bypass, or implement B-04 runtime or later science.
