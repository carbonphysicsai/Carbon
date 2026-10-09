# V3-SCORE-INPUTS-01: development input collection for battery v3

**Status:** working implementation. **Authority:** owner request, 2026-10-09;
VALIDATOR-26 and the registered score-tuning v4 rule. **Maturity ceiling:**
DEVELOPMENT evidence. No hidden, official, LIVE, solver, or qualification use.

## Contract

For one confirmed battery strategy and seed, reconstruct once on CPU and infer
on a registered public-development screening panel and Q3 lattice. Bind all
inputs and output to SHA-256 identities. Reuse the battery exam error,
`score_tuning` accuracy and G-FEAS definitions, `quiz.q3_settle`, and the
registered G-FEAS/A-Q@0.05 candidate. Missing reference or incomplete quiz is
`FAILED_INFRA`; missing/non-finite candidate predictions are ineligible. A
gate breach is ineligible. This script never changes validator rule v2/v3 or
records an official score.

The development panel registration names a separate screening reference set,
Q3 scenarios, standard and refined solved records, settlement rule, contract,
and their digests. It must be committed before evaluation and may refer only
to public-development files in its own evidence directory. Q3 selection sees
predictions only; reference judgement follows commitment. The full lattice is
required, with all expected refinement attempts terminal. An unresolved
candidate that could change the best or the pick leaves q unmeasured.

For Graphite run-5, recompute v2/v3 rank correlations only on a common
eight-recipe panel with all three v3 inputs. Historical v2 records remain
historical and are not rewritten.

## Evidence and tests

Toy fixtures exercise digest/refusal, missing reference versus candidate
failure, settled Q3 regret and rule parity. `./scripts/dev/canonical.sh` runs
the focused tests. The current-main reference inventory and CPU work estimate
are in `docs/development/V3_SCORE_INPUTS_01.md`.

## Conditional completion

One PR to PR Lead with script, tests, evidence inventory, and exact-head
validation. The run-5 numerical v3 comparison remains unmeasured until the
registered development inputs exist.
