# Ticket B-01E — Canonical Development Environment and Legacy Quarantine

**Wave:** B active in bounded development scope
**Status:** `done` only under the closeout authority gate below
**Depends on:** B-01 (`done`)
**Implementation branch:** `agent/b-01e-dev-environment-legacy-quarantine`
**Closeout branch:** `agent/b-01e-closeout`
**Reviewed implementation head/tree:**
`2025e235c83a994ed4f16c9a3a9d3c2766700061` /
`4a506a1ae46cfcbf180eb5dbf68ed50caa0f1e09`
**Implementation merge/tree:**
`b4744a435e8bc7220c7dc03e6a993bb0a54c16a5` /
`4a506a1ae46cfcbf180eb5dbf68ed50caa0f1e09`
**Exact-main implementation CI:** run `33319267255`, `success`
**Master questions:** MQ-018, bounded development-governance slice only
**Decision:** B-01E-D1
**Evidence:** `.agent/evidence/wave_b/b-01e.md`
**Authority:** executive-owner direction dated 2026-08-30; `CONSTITUTION.md`;
`AGENTS.md`; `.agent/INVARIANTS.md`; `.agent/WAVE_B.md` version 0.5;
`.agent/evidence/wave_b/b-01.md`

> **Closeout authority gate.** This documentation branch proposes `done`; it
> does not make that state authoritative. B-01E's prior authoritative status
> remains `in_progress` until this closeout's exact head is independently
> reviewed with every blocking finding and thread resolved, required PR CI
> passes, it normally merges under separate authorization with the reviewed
> tree preserved, and exact-main closeout CI succeeds, despite any prospective
> closeout token on a branch or newly merged main. B-02A remains `todo` and
> unstarted throughout this candidate. After the gate, starting B-02A still
> requires a fresh authorized
> ticket session and its own readiness/branch checks.

## Goal

Make one pinned Linux environment the sole ordinary Carbon development-
evidence platform and move superseded executable prototypes out of active
main without deleting provenance. After this ticket, ordinary development is
controlled by:

```text
./scripts/dev/doctor.sh
./scripts/dev/ci.sh
```

This is an infrastructure and code-authority boundary only. It creates no
scientific, security, economic, network, `LIVE`, frontier, product,
settlement, weight, emission, launch, or production authority.

## Definition of Done

- [x] Preserve the exact pre-quarantine main commit and tree under the
      annotated tag `archive/pre-wave-b-legacy-2026-08-30` and branch
      `archive/legacy-prototypes`, and verify both remote identities before
      removing any active-main path.
- [x] Derive every quarantine action from B-01's 30-component audit; do not
      infer removal from a directory name.
- [x] Record path/component, B-01 disposition, canonical imports, tests, CI,
      package inclusion, authority references, future owner, action, and
      reason in the evidence manifest.
- [x] Prove each `ARCHIVE_REMOVE_MAIN` path is not required by canonical
      `carbon/`, CPU/invariant tests, packaging, default CI, active fixtures,
      active scripts, or an authority file as executable input.
- [x] Map `NEW_OWNER_DECISION_REQUIRED` to `DEFER_OWNER_DECISION`; do not
      migrate or bless physical values, populations, thresholds, weights, or
      qualification rules.
- [x] Add the current legacy retrieval index and a machine-readable current
      code-authority record.
- [x] Keep current Carbon implementation, tests, fixtures, specifications,
      authority records, build tooling, CI, examples, and deliberately
      reserved current package seams on main.
- [x] Establish Ubuntu 24.04/glibc, exact CPython 3.11, bash, and pinned `uv`
      as the canonical environment, with a committed `uv.lock`.
- [x] Add `.devcontainer/`, `.python-version`, `.gitignore`, the five
      `scripts/dev/` entry points, and `docs/development/ENVIRONMENT.md`.
- [x] Separate `dev`, `science-jax`, `science-torch`, and `chain` dependency
      groups; ordinary sync and CI install only `dev`.
- [x] Make native Windows fail clearly as a canonical evidence platform and
      document WSL2/dev-container use from a Linux-filesystem clone.
- [x] Make GitHub Actions and local development execute the same repository-
      controlled `./scripts/dev/ci.sh` semantics on `ubuntu-24.04`.
- [x] Preserve every current invariant, CPU, quality, package/wheel, and
      outside-tree import gate while adding a canonical/legacy boundary gate.
- [x] Prove the candidate in a clean image from lock sync through all gates,
      and prove native-Windows rejection without running Linux acceptance on
      Windows.
- [x] Record B-01E-D1 and deliver the non-blocking lead notification through
      issue #42 mentioning `@harshaa765`.
- [x] Opened draft implementation PR #58 and stopped before merge; B-01E was
      not marked `done`, and B-02A was not begun, during implementation
      handoff. The later merge used separate exact-head authorization.

## Legacy disposition rules

| B-01 disposition | B-01E rule |
|---|---|
| `KEEP` | `KEEP_MAIN` |
| `WRAP` | Keep only when an authorized active/future ticket needs the source directly; otherwise archive. |
| `REPAIR` | Keep only when the owning near-term ticket should repair the source in place; otherwise archive. |
| `REPLACE` | `ARCHIVE_REMOVE_MAIN` after dependency proof. |
| Explicit historical/excluded | `ARCHIVE_REMOVE_MAIN` after dependency proof. |
| `NEW_OWNER_DECISION_REQUIRED` | `DEFER_OWNER_DECISION`; no destructive semantic migration. |

Historical or explanatory specifications remain on main when their authority
notice is accurate. The cleanup target is superseded executable material.

## Canonical environment contract

```text
OS family: Linux
distribution: Ubuntu 24.04 LTS, glibc
architecture: x86_64 (`linux/amd64`); no ARM64 qualification is claimed
Python: exact CPython patch recorded in .python-version
dependency manager: exact uv version recorded in the dev image and docs
shell: bash
host Windows/macOS: editor/container host only
native Windows Python: unsupported for canonical evidence
```

No default environment installs JAX, Torch, neuraloperator, PhysicsNeMo,
Bittensor, Julia, CUDA, NVIDIA, or GPU libraries. A selected ticket must own
and request the corresponding optional group.

## Required commands

```text
./scripts/dev/bootstrap.sh  synchronize the exact locked dev environment
./scripts/dev/doctor.sh     inspect canonical-environment validity
./scripts/dev/test.sh       run the ordinary CPU engineering lane
./scripts/dev/ci.sh         run every ordinary pre-PR gate
./scripts/dev/shell.sh      enter the project environment
```

`doctor.sh` is observational and must not mutate repository authority.

## Code-authority invariant

The machine-readable record must enumerate canonical roots, canonical tests,
the exact archive identities, retired runtime namespaces, retired executable
paths, and any explicit exceptions. Tests must use Python import/path
semantics rather than an undifferentiated text grep to prove that canonical
code and tests do not import retired code, packaging excludes it, default CI
does not invoke it, and reintroduction fails closed.

## Must not

B-01E must not implement B-02A or any later Wave B behavior; choose scientific
tasks, populations, sampling plans, thresholds, measurements, or scoring
semantics; repair JAX/FNO or Julia science; migrate MCP v1 to v2; implement
Bittensor; change weights or emissions; or create `LIVE`, launch, product,
commercial, security, network, settlement, or production authority.

## Closeout maturity

```text
SPECIFIED: YES for the B-01E-D1 bounded environment/quarantine scope
IMPLEMENTED: YES for the merged B-01E bounded engineering scope
TESTED: YES only for the recorded canonical CPU, invariant,
        package/wheel/outside-tree, started-image, quality,
        authority-boundary, and diff-hygiene evidence
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
COMMERCIAL / LIVE / LAUNCH / SETTLEMENT / WEIGHT / EMISSION AUTHORITY: NO
```

Archive presence grants no current implementation authority. B-01 row 30
remains `DEFER_OWNER_DECISION`; B-01E adopted no historical threshold,
physical value, scoring weight, population, SamplingPlan, measurement policy,
or qualification rule. The exact 169-file audited quarantine is unchanged.

## Completion gate

The implementation passed exact-head independent review, normally merged with
its reviewed tree preserved, and passed exact-main CI at the identities above.
This separate closeout candidate now proposes B-01E `done`. The proposal
becomes authoritative only after the closeout authority gate at the top of
this ticket passes. B-02A is only the prospective next selected `todo`; it
remains unstarted and is not authorized by this branch.
