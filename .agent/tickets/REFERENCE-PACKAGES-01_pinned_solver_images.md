# REFERENCE-PACKAGES-01 — pinned solver images for #787's reference-route triage

**Selection:** Test Lead, 2026-10-08, under the owner's decision to run #787's
triage (OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01, PR #801). #787 requires package
and build work to have its own bounded ticket. **State:** in_progress.
**Scope/maturity:** DEVELOPMENT. Packages reach IMPLEMENTED and smoke-TESTED
only. No reference adequacy, adoption or qualification.
**Starting base:** `8e75df215df1a617ea82f071f8d88017f897ba47`. **Branch:** `claude/reference-packages-01`.
Merges go through the PR Head.

## Working contract

Build, for each of #787's five families, a locally built container image from
upstream sources with recorded checksums, pinned by digest. Each image runs
with no network at solve time and has an analytic or closed-form smoke case.
Each package returns #787's manifest fields: immutable source archive URL and
sha256, the dependency lock (base image digest and a dated Debian snapshot),
compiler, BLAS and MPI options, the image digest, licence, smoke deck and
observer digests, and smoke results.

Order: Elmer `release-26.2.1` first, as one source build serving f02
(transient heat) and f13 (scalar Helmholtz). Then CalculiX `ccx 2.23` (f08),
OpenFOAM (f17, exact distribution recorded) and Meep (f06: the 2D screen and
the 30-nm 3D route only). Package notes handed over by Codex's acquisition
agents are reused if they arrive; the work does not wait for them.

## Boundaries

- Packaging and smoke cases only. Running #787's eight-case panels belongs to
  the triage under OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01, after it merges.
- No hidden material, no runtime registration, no Score Pack, validator,
  protocol-stage or pipeline timing changes. No paid compute: builds run on the
  operator host's free CPU.
- Each download of upstream sources, base images and build dependencies is
  approved by the owner in chat before it happens.
- A family whose feature proof (#787 table) fails stays blocked. It is never
  replaced by an unrequested route.

## Plan and acceptance

1. Per family: `scripts/dev/reference_packages/<family>/` holds a Dockerfile,
   `sources.lock.json` (URLs, sha256, snapshot date, base digest), a build
   script that verifies every checksum, and `smoke/` (deck, observer,
   expected analytic values and tolerance).
2. Build locally. Record the image digest and a manifest
   `docs/development/evidence/reference-packages-01/<family>.json`.
3. Smoke: run with `--network none`, read-only root and the pinned digest.
   The observer compares with the analytic value. Record results.
4. Report each pinned family to the Test Lead. Once Elmer is pinned, send the
   owner the console block for the triage host.

Expected manifest: this ticket; `scripts/dev/reference_packages/`;
`docs/development/evidence/reference-packages-01/`; one static test of the
locks' completeness.

## Scope additions (Test Lead, 2026-10-08)

- f08: the #787 triage panel runs on the operator host's free CPU, one CPU
  per ccx process, with no grant or spend (`calculix/f08_freeze.py`,
  `triage_run.py --family f08`).
- f02: #846 (CHALLENGE-VALUE-COST-01) asks for a measurement of a denser,
  preregistered schedule menu inside the existing bounds, reusing this
  package's deck on local free CPU (`elmer/f02_menu.py`,
  `evidence/reference-packages-01/f02-menu-v2/`). It is diagnostic: no packet
  adoption, no reference adequacy claim.
