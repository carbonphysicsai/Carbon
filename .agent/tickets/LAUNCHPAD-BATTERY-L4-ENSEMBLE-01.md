# LAUNCHPAD-BATTERY-L4-ENSEMBLE-01 — rebuild graph ensembles

Status: IN_PROGRESS. Builder: Launchpad checkout lane. Base:
`8e986717b42850204d390b44c70833f5c1256332`. One PR to main after
canonical and actual worker evidence. Primary Development Hub map_ref:
`SYSTEM/AGENT-EXECUTION`; hub impact is an implementation/test correction under
the existing construction boundary. No current hub purpose, placement,
selection, authority, or maturity claim changes.

## Working contract

A battery Level 4 strategy with `ensemble_members > 1` currently crashes in
interface/admission because a native `recipes.Ensemble` lacks single-member
layout and feature attributes. The registered recipe's ensemble semantics are
already defined: identical members, each `steps // members`, with distinct
Carbon-derived seeds and fieldwise averaged predictions
(`2026-10-07-TRAINING-BUDGET-01-S1`; `recipes.Ensemble`). Admitting the graph
without applying those semantics would silently ignore a declared control.

Use a compiled member only to derive the graph interface and lower its
forward/init documents. Preserve the native wrapper for native training.
Build graph members independently from the same verified submission and fixed
TRAIN, split steps and seeds as the native recipe does, preserve the existing
graph-only/composed training paths, and retain every member in a self-contained
source-free inference state. Keep the public graph state kind so the existing
worker dispatch remains applicable. Do not alter the registered graph policy,
allowlist, 16 KiB per-document constant cap, implementation snapshots, native
recipe source, scientific grades, or live activation.

## Validation and maturity ceiling

Focused tests must cover MLP and DeepONet interface/batch parity, actual
ensemble graph lowering and admission, two trained members and their budget,
prediction averaging, graph-only and composed rebuild, staged worker parity,
and state-only inference roundtrip. Run canonical CPU and required changed-path
checks, then an unpublished isolated worker test before a PR. A test PASS is
development execution evidence only, not scientific/security qualification or
mainnet permission. Review the complete exact-head diff before publication.

Completion is conditional on those checks, repaired review findings, a normal
merge at an exact expected head, and a matrix update from real receipts.
