# OWNER-RB20-SOLVER-REPIN-PASTIX-01: Ribbed Bracket 2.0 reference solver re-pinned to a 64-bit PaStiX build

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes to (b) Route A for Ribbed Bracket 2.0: re-pin the F08 reference solver to the 64-bit PaStiX build after its checks pass, with the deck migration; the F08 reference solver image is never distributed outside Carbon. Bring me the measured memory figure before raising the per-case limit."
Basis: codex-queue/reports/RB20_SOLVER_OWNER_CHOICE_DRAFT_20261101.md rev 2 (sha256 fb4d40de1d9a79b9c15ea7a7f3a811486c2d350ca136f16cfcdd7c428f43da22, Validator-confirmed); TE plan F08_CCX_PASTIX_PLAN_20261101/PLAN.md (2e85dd72…); licence note F08_20_SOLVER_REPIN_LICENCES_20261101.md (f59132f9…).
Evidence (1 Nov): the pinned CalculiX 2.23 + SPOOLES (32-bit) solves ≤ ~335 k nodes. Every mesh from ~426 k nodes up SIGSEGVs whatever the memory cap: the a2, a3 and √2 ladders all failed (Launchpad board lines 16:15–17:2x).

## Decided (Ribbed Bracket 2.0 only)
1. Re-pin the F08 2.0 reference solver to a new image: the same CalculiX 2.23 with 64-bit integers, PaStiX + Scotch + OpenBLAS ILP64, serial, built from a pinned Dockerfile.
2. It is used only AFTER its checks pass (the Validator rules): MMS + patch test + closed-form rod; F08 1.7 parity within its registered U; run-to-run and two-host-class bit checks; then the 0033 purpose test.
3. Deck migration: F08 2.0 decks gain the solver selection. Deck/solvers_id/image digests change, so every 2.0 plan and job is re-derived and re-receipted. F08 1.7 is untouched.
4. The F08 reference solver image is NEVER distributed outside Carbon (external validators included). Licences: CalculiX GPL-2.0-or-later; PaStiX CeCILL-C; Scotch CeCILL-C; OpenBLAS, arpack-ng and hwloc BSD-3-Clause; gmsh GPL-2.0-or-later. CeCILL-C is GPL-incompatible, so the image is internal use only.

## NOT yet decided
- The per-case reference memory limit stays 9 GiB until the owner approves a MEASURED figure. The Lead brings the measured peak (0033 + the heaviest job on the new build) as one question.

## Unchanged
- F08 1.7's SPOOLES history is never rescored. Every F08 host-class check is redone for the new image. Spend is inside the week's USD 250 (estimate ~$5–15).
