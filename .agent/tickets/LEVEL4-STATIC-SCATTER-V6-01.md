# LEVEL4-STATIC-SCATTER-V6-01 — prospective static-index Torch scatter

Status: in progress, development source only. Starting base:
`8e986717b42850204d390b44c70833f5c1256332`.

## Working contract

Add a separately versioned Level 4 allowlist that permits the already
implemented `aten.scatter_add.default` lowering only when the index is a
captured static int64 tensor. Lowering must check shapes, dtypes, index bounds
and existing graph resource caps, and emit ordered ordinary primitives rather
than a GPU atomic scatter. The direct Carbon graph `scatter_add` opcode remains
review-only and unavailable to the v0 interpreter. Frozen v1–v5 bytes and
digests remain unchanged. No dynamic-index admission, new cap or GPU
determinism claim is in scope.

This is a prospective source capability, not a served Challenge version or a
normal-path model PASS. The present worker/door's trusted-material selection
must continue to reject v6 until an integration ticket binds a new Challenge
version, exact allowlist digest, fixed TRAIN, isolated build and source-free
inference, with hardware parity and custody evidence. The existing CR14
static-stencil packet is a separate capability and stays outside the frozen
ten-case denominator.

Authority: `2026-10-17-OWNER-CONSTRUCTION-REBUILD-BREADTH-01` permits tested,
bounded, trusted reconstruction expansion prospectively while retaining the
current allowlist, isolation and historical pins; `OWNER-LEVEL4-GRAPH-ONLY-01`
requires graph-only construction. The v0 scatter policy and GPU concern are
recorded in `docs/development/graphite/level4/PHASE0_SPIKE_REPORT.md` and
`PHASE1_PLAN.md`. No scientific, security, production or LIVE authority follows.

Primary Development Hub `map_ref`: `SYSTEM/AGENT-EXECUTION`. Hub impact: no
change to this node's purpose, placement, maturity, dependency or primary
links; this branch adds only prospective allowlist material and focused tests,
without selecting or serving a new contract.

## Plan and acceptance

1. Preserve v5 byte-for-byte; create v6 with one ATen entry. Leave the Carbon
   graph opcode's `v0_interpreter=false` and every cap unchanged.
2. Replace the in-memory prospective allowlist in the static-scatter tests
   with exact v6 bytes. Assert v5 refusal, v6 static lowering, direct opcode
   refusal, dynamic-index/out-of-bounds/resource typed refusals.
3. Where pinned JAX is available, test forward/gradient parity including
   repeated indices, one bounded fit against the Challenge's exact public
   TRAIN bytes, and inert graph/numeric-state reload without Torch source.
4. Run focused diagnostics, pinned style and diff checks. Canonical Linux and
   GPU checks remain required before integration/serving; absent evidence is
   reported as pending, not a PASS.

Baseline on this Windows host: `python -m pytest -q
tests/cpu/test_level4_torch_scatter_add.py` returned `7 passed, 1 skipped`;
the JAX-dependent case skipped because this Python has Torch but no JAX.

Candidate Windows diagnostics: `python -m pytest -q
tests/cpu/test_level4_torch_scatter_add.py
tests/cpu/test_synthetic_linear_field_2d.py` returned `23 passed, 2 skipped`.
The skips are the JAX forward/gradient parity and fixed-TRAIN fit/inert-state
tests. Pinned Black 26.5.1, Ruff 0.16.3 and `git diff --check` passed on the
changed test. Docker daemon is unavailable, so canonical Linux evidence is
pending; no inference or fit PASS is inferred from a skipped test.

Dependencies: frozen 8e source, pinned Level 4 v5 semantics, public synthetic
TRAIN fixture. Invariants: no submitted weights or participant code in the
grader; fixed TRAIN binding; typed unsupported-operation refusals; versioned
historical evidence; bounded deterministic reconstruction; source-free inert
inference. Completion predicate for this branch is reviewed source and focused
available-host tests, with canonical/GPU/normal-path maturity explicitly held.
