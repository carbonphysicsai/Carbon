# B-01E Implementation Plan — Canonical Environment and Legacy Quarantine

**Status:** executing
**Exact base:** `4ee58d56862d0441d5d151d79db1fe3036f1025d`
**Exact base tree:** `9f767ea16ffb7185ab64acff2542c7a8dcc2e339`
**Branch:** `agent/b-01e-dev-environment-legacy-quarantine`

## 1. Start gate

Fetch `origin/main` without `git pull`; verify the exact commit/tree, clean
worktree, Wave B active state, B-01 `done`, B-02A `todo` and unstarted, and no
conflicting owner/lead direction. Create this branch from exact
`origin/main`. Stop if any dependency fails.

## 2. Scope and non-goals

Implement only environment reproducibility, dependency locking, local/CI
command parity, machine-enforced current-code authority, and provenance-
preserving quarantine. Do not implement or decide science, security
qualification, economics, network behavior, MCP v2, B-02A, or later work.

## 3. Material decision and notification

Record B-01E-D1 in `.agent/DECISIONS.md`, update the live sequencing to
`B-01 → B-01E → B-02A`, and notify `@harshaa765` through issue #42.
Notification is non-blocking unless the lead explicitly records
`REQUEST_CHANGES` or `BLOCKED` for the affected change.

## 4. Manifest algorithm

1. Start from all 30 B-01 component rows.
2. Apply the ticket's disposition mapping.
3. Expand legacy executable components to exact tracked path groups.
4. Search canonical implementation, CPU/invariant tests, fixtures, scripts,
   workflow commands, packaging, and executable authority inputs.
5. Keep a mixed component at file granularity if any current dependency is
   found.
6. Record `DEFER_OWNER_DECISION` rather than guessing.

## 5. Archive and verification

Create the annotated tag `archive/pre-wave-b-legacy-2026-08-30` and branch
`archive/legacy-prototypes` over the exact base commit, not over an
intermediate B-01E commit. Verify annotated tag type, peeled commit, branch
commit, source tree, and remote refs. Do not force or rewrite either ref.

## 6. Environment discovery and pinning

Verify an exact stable CPython 3.11 patch exists for Ubuntu 24.04 x86_64 and
aarch64 in both the repository-controlled image mechanism and GitHub runner
tooling. Pin the Ubuntu image by OCI digest and pin `uv` by immutable version
and OCI/action identity. Record all identities in documentation and evidence.

## 7. Dependencies and lock

Add an explicit build system, narrow package support to CPython 3.11, move
development tools into PEP 735 groups, separate heavy optional groups, and
generate a universal `uv.lock`. Default sync is exact and includes only
`dev`; optional groups require explicit ticket-owned selection.

## 8. Commands and CI

Implement the five `scripts/dev/` commands. `ci.sh` composes doctor,
invariants, CPU tests, quality ratchet, package/wheel/outside-tree checks,
authority boundary tests, and diff hygiene. GitHub Actions installs pinned
`uv`, bootstraps from the lock, and invokes the same `ci.sh` on
`ubuntu-24.04`; workflow YAML must not duplicate test semantics.

## 9. Authority boundary and quarantine

Add a repository-native machine-readable authority record and a semantic
checker for retired namespaces and paths. Only after archive verification,
remove the proven `ARCHIVE_REMOVE_MAIN` set. Retain `carbon/backbones/**`, all
canonical role packages, current tests/fixtures/specifications, and
historical prose. Reconcile current-use path references with the archive
index without rewriting historical evidence.

## 10. Validation

Run from a clean Ubuntu image: image build, locked sync, doctor, package
import, invariant lane, CPU lane, quality gate, wheel/outside-tree lane,
authority boundary, and diff hygiene. Verify native Windows doctor rejection
separately. Push the candidate, require exact-head GitHub CI, and record exact
commands/results.

## 11. Reviewable commit sequence

1. governance/ticket and archive identities;
2. canonical environment and lock;
3. developer scripts and CI alignment;
4. code-authority boundary;
5. legacy quarantine/removal;
6. evidence and documentation.

Do not rewrite these commits merely to create one aggregate change.

## 12. Risks, reversibility, and stop condition

- A hidden canonical dependency would invalidate removal; fail closed and
  retain that file/component.
- A scientific value found in old code is not migrated; its meaning remains
  `DEFER_OWNER_DECISION` even when its historical bytes are archived.
- All removed bytes remain retrievable from the exact archive tag/branch.
- A future ticket may port only the justified component under then-current
  authority; archive presence alone grants no authority.
- Stop after opening a draft PR. B-01E remains `in_progress`; B-02A remains
  `todo`.
