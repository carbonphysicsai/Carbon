# Agent decisions log

## 2026-08-19 — A0 canonical package layout

**Base and scope.** A0 started from clean `main`/`origin/main` at
`ab765b07bc8c41106194ce6d06b4a2bd1c03f9a1` on branch
`agent/a0-repo-layout`. The root `.agent/` directory remains the runtime board:
`.agent/WAVE.md`, `.agent/tickets/`, and `.agent/INVARIANTS.md` are canonical;
`agent_pack/` contains protocol documentation only.

**Package-root decision.** Keep the existing root-layout `carbon/` package as
the sole canonical namespace. It is already selected by
`[tool.setuptools.packages.find] where = ["."]` and `include = ["carbon*"]`, so
introducing `src/carbon/` would create a second mapping without A0 benefit.
`carbon/__init__.py` already makes `python -c "import carbon"` succeed. A0 adds
only the required package boundaries: `schema`, `registry`, `seeding`,
`scoring`, `cards`, `fees`, `traineval`, `mcp`, `leaderboard`, `logging_utils`,
`evaluation`, `audit`, `chain`, and `qualification`. The empty `evaluation`
and `chain` boundaries reserve the adapter seam: future scientific/evaluation
code remains independent of Bittensor SDK objects, while SDK implementations
belong behind `carbon.chain`. No chain, receipt, audit, qualification, scoring,
or scientific behavior is implemented by A0.

**Current-tree mapping.** The current base differs from the older A-1 tree
snapshot: a 51-file legacy `carbon/` tree is present, while `Carbon_Logic/` is
absent. No legacy module is thereby promoted as current-spec compliant.

| Current root | A0 mapping |
|---|---|
| `carbon/` | Canonical import/package root; legacy modules remain audit inputs until later scoped tickets promote, wrap, repair, or replace them. |
| `poc/` | First Burgers TrainEval promotion source only; its current science, scoring, seed disclosure, and fixed values are not qualified. |
| `Carbon_Logic/` | Legacy selective-promotion source named by the maintainer disposition, but absent at this base; it is not recreated or supported as a namespace. |
| `neurons/` | Preserved legacy Bittensor reference; A0 found no import/layout acceptance need to reuse it. |
| `Julia/` | Preserved v0 generator-verification path; inclusion is not repair, scientific validation, or qualification. |
| `Design_Specs/` | Domain-owned semantic authority. |
| `.agent/` | Canonical runtime board, tickets, decisions, and invariants. |
| `agent_pack/` | Execution protocol/templates only, never a competing board. |

**Import inventory and migration decision.** The audit found 40 lowercase
`carbon` import statements, 21 `hydrogen` statements, one uppercase `Carbon`
statement, and no `Carbon_Logic` import statement. No import migration is
required for A0 acceptance because the canonical root import already succeeds;
changing legacy callers would broaden A0 into implementation repair. Migrated
callers: **none**. Deferred retired-namespace callers:

- `hydrogen`: `carbon/base/validator.py`;
  `carbon/challenges/{burgers,darcy_2d,heat,navier_stokes_2d}.py`;
  `carbon/data/__init__.py`; `carbon/landscape/agent.py`;
  `carbon/specialist/distillation.py`; `carbon/symbolic/pysr_evolver.py`;
  `carbon/training/{physicsnemo_trainer,trainer}.py`; and
  `carbon/validator/validator.py` (21 statements total).
- uppercase `Carbon`: `scripts/generate_leaderboard.py` (one statement).
- `Carbon_Logic`: none in the current Python import inventory.

These callers are explicitly unsupported/deferred, not compatibility promises.

**Pre-change baseline (Python 3.11.11).** These commands were run on the clean
A0 branch before package-boundary edits. The inherited baseline is red.

| Exact command | Exit/result before A0 |
|---|---|
| `python -m pytest tests/ -q --tb=no` | Exit 2: three collection errors (`test_physics_gates.py`, `test_reproducibility.py`, `test_scorer.py`). |
| `python -m pytest tests/ -q` | Exit 2: the same three collection errors, rooted in missing `torch`. |
| `POC_FAST=1 PYTHONPATH=. python -m pytest poc/tests -q` | Exit 2: one collection error; `poc.generators.burgers1d` does not export `role_seed`. |
| `POC_FAST=1 ./poc/scripts/smoke.sh` | Exit 126: tracked script is not executable. |
| `POC_FAST=1 bash poc/scripts/smoke.sh` | Exit 2 after three protocol-only `numpy_fd` cases; its final PoC pytest step has the same missing-`role_seed` collection error. Generated artifacts were removed after capture. |
| `python -m compileall -q Carbon_Logic neurons poc tests scripts examples` | Exit 0 with `Can't list 'Carbon_Logic'`; all existing requested roots compiled. |
| `ruff check .` | Exit 127: `ruff` is not installed. |
| `black --check .` | Exit 127: `black` is not installed. |
| `julia --version` | Exit 127: `julia` is not installed. |

**A0 implementation plan / DoD mapping.** Retain the existing canonical root;
add only the fourteen required package markers; use `evaluation/` and `chain/`
as the SDK-independent seam; migrate no caller not needed by the import/layout
test; preserve all current PoC, neurons, Julia, specifications, tests, and
legacy code; then re-run the exact table above plus `python -c "import carbon"`
and `git diff --check`. A0 may be marked done only if the package inventory,
before/after signatures, and focused diff evidence every listed DoD item.

**Post-change validation and delta.** Every exact baseline command above was
re-run. Exit codes and failure signatures were unchanged: root pytest still has
the same three missing-`torch` collection errors; PoC pytest and the Bash smoke
path still stop at the same missing `role_seed`; direct smoke remains exit 126;
compileall remains exit 0 with the absent-`Carbon_Logic` notice; and
Ruff/Black/Julia remain unavailable at exit 127. Therefore A0 introduced zero
new baseline failures, but the inherited repository baseline remains red.
`python -c "import carbon"` passed at exit 0. `git diff --check` passed at exit
0. Generated smoke/test artifacts and bytecode caches were removed and are not
part of the change.

## 2026-08-19 — Evaluation evidence / validator audit extension

- `Design_Specs/Evaluation_Evidence_and_Validator_Audit.md` is the normative owner for execution evidence, receipts, reproducibility qualification, validator audit/re-execution, and scientific-vs-emission separation.
- `Design_Specs/Build_Out_Protocol_Extension.md` is an additive sequencing extension pending fold-in to the next `Build_Out.md` revision.
- **Do not reorder Wave A.** Continue A0 → A12 in the current board order.
- Fold receipt/evidence hooks into existing Wave A tickets only where the extension explicitly assigns them.
- JAX is the first P0 backend targeted for qualification; other backend adapters are non-emission-capable until separately qualified.
- Do not expose raw official seeds/draw IDs in receipts, cards, logs, MCP, leaderboard, or public evidence.
- No ZK/proof-of-training work is required for P0.

## 2026-08-18 — A-1 maintainer dispositions for A0

These decisions govern A0 planning; they do not implement A0 or qualify any scientific behavior.

- Establish lowercase `carbon/` as the canonical package. Support only import paths that remain necessary; do not preserve `Carbon_Logic`, `hydrogen`, or `Carbon` as canonical namespaces.
- Use the Burgers PoC as the first vertical promotion source, without treating its current science, fixed values, scoring, or disclosure behavior as qualified.
- Retire the legacy `Carbon_Logic`, `hydrogen`, and `Carbon` namespaces; reuse `neurons/` only where an A0 audit finds it useful.
- Include Julia in the first build as the verification path for the v0 data generator. Repair and scientific validation remain explicitly owned work, not implied by inclusion.
- Normalize the `docs/context/` filenames in the appropriate scoped ticket. Treat the proposal appendix in `Open_Questions.md` as the v0 direction, subject to team audit; it does not override domain-owned specifications or authorize LIVE values.

## 2026-08-17 — Canonical .agent path

- Root `/.agent/` is the only board/ticket location.
- `agent_pack/` holds protocol docs only; Hermes notes under `agent_pack/executors/hermes/`.
- Build_Out pin: **v1.4**.

## 2026-08-14 — Pack bootstrap (historical)

- Early path used Hermes + Engy; execution is now executor-agnostic.
- Scope lock: Wave A only until WAVE.md checklist is done.
- Existing repo dirs (`poc/`, `neurons/`, `Design_Specs/`) are mapped, not deleted.

## Escalate / spend log (agent fills)

| Date | Ticket | Why stop/escalate | Outcome |
|------|--------|-------------------|---------|
| | | | |
