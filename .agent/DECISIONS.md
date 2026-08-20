# Agent decisions log

## 2026-08-20 — Post-merge A1 cold-start backbone registry correction

**Historical correction and status.** A1 PR #5 was reviewed at
`c4d0a9210aaacad077287c2ca14e20b2bb6d396e` and merged as
`5f810a57379a608119aa9cc9bbd6fc78a48baf13` before a subsequent independent
review's optional-backend blocker was repaired. At that merged head, a cold
`carbon.backbones` import had no known adapters, the CPU tests imported adapter
modules before exercising lookup, and `carbon.backbones.registry` owned a
second disconnected mapping. This corrects the registry-path implementation
and test claim in the 2026-08-19 A1 decision below; it does not rewrite the
original install, CPU CI, quality-ratchet, or PoC evidence.

**Corrective decision (WRAP/REPAIR).** The initial fetch found the expected
post-PR-#6/PR-#7 `main` at
`3e29fef703d4b60c97ff4873cb395d2436cdad0a`. Before publication, `main`
advanced through PR #8, which changed only the scientific-reference canon and
did not overlap this repair. The branch was fast-forwarded, so its actual repair
base is `7f499e589b86ed127745831ccacdc1c8e4ffb677`. `carbon.backbones` remains
the package-facing API and is now the sole registry state owner. An explicit
map links `physicsnemo_fno`, `fno`, `deeponet`, and `uno` to their local Carbon
adapter modules. Listing names imports no adapter, and resolving a built-in
imports only its local adapter. The compatibility API in
`carbon.backbones.registry` delegates registration, listing, and resolution to
the package registry while preserving its historical construct-with-keywords
behavior; it no longer owns a second mapping.

Fresh isolated subprocess tests block `physicsnemo`, `neuralop`, and `torch`,
prove all four names are cold-discoverable without loading those packages, and
exercise extra-specific construction failures through the registry for both
backend families. Separate cold-registry tests prove a transitive
`ModuleNotFoundError` is re-raised unchanged. Installed-backend API
compatibility, model behavior, and scientific or production qualification
remain untested and unclaimed. This correction introduces no A2+ behavior.

**Local corrective evidence.** In a fresh Python 3.11.11 virtual environment,
the literal `python -m pip install -e ".[dev]"` exited 0 and installed
`carbon==0.9.0`; `python -m pytest -q` exited 0 with 27 passed and no skipped,
xfailed, or failed tests. The nine optional-backend tests passed individually,
including both registry-path missing-extra cases and both transitive-error
cases. An isolated cold-process diagnostic listed all four built-ins, resolved
their local wrapper classes, and found no `physicsnemo`, `neuralop`, or `torch`
module loaded. The quality gate passed at Ruff 757/776 and Black 62/68 with all
three changed Python files strict-clean. Compared with untouched repair base
`main` at Ruff 769/776 and Black 64/68, the patch removes 12 Ruff and two Black
fingerprints and adds none. `git diff --check` exited 0. With the explicit PoC
extra installed, `POC_FAST=1 bash poc/scripts/smoke.sh` exited 2 at the unchanged
inherited import failure for absent `poc.generators.burgers1d.role_seed`.

At the corrective branch's pre-merge record, A1 remained `in_progress` until
the draft PR received independent rereview and was merged. A2 remained `todo`
behind that temporary sequencing gate. Local and GitHub Actions evidence for
the final corrective head was recorded in the corrective PR because a commit
cannot record its own SHA or subsequent run IDs.

**Corrective merge and A1 closure.** The independently rereviewed PR #9 final
head `a247bb189d44ddf18de504572ef620cf5d501d10` passed final-head CI run
`32326384939`: the CPU job ran the default suite with 27 passing tests, and the
code-quality job passed the existing no-new-debt ratchet. PR #9 then merged as
`819da3c163c2fb9476a6881aab8740cc6984066e`. That merge is ancestral to the
closure base `fb6bbf393f77ae80d76abf3eda0e53a7dfd12f17`; intervening PR #10 added
only non-conflicting specification and context documents. The cold-start
registry gap is therefore repaired on current `main`, and A1 is `done`. A2 is
the next Build_Out ticket and remains `todo`; no A2 implementation begins in
this closure. Installed-backend API compatibility, scientific correctness, and
scientific or production qualification remain untested and unclaimed.

## 2026-08-19 — A1 truthful CPU CI and pytest baseline

**Base, branch, and scope.** A fresh fetch verified `origin/main` at the
authorized `0b2eec30250f1767cc434836e189cca219154d4d`, which is also merged PR
#4's merge commit. A1 started from that exact commit on
`agent/a1-ci-skeleton`. This decision implements engineering infrastructure
only; it does not promote or qualify A2+ schemas, registries, seeding, scoring,
cards, fees, TrainEval, MCP, leaderboard, logging, invariants, Bittensor
transport, or scientific behavior.

**Inherited baseline and actual Actions stages.** The local baseline used an
isolated detached worktree, CPython 3.11.11, and pip 24.0. Exact results:

| Command | Base result |
|---|---|
| `python -m pip install -e ".[dev]"` | Exit 1: no matching `physicsnemo` distribution. |
| `python -m pytest -q` | Forced diagnostic, exit 2: 22 collection errors from unavailable PoC/scientific and legacy dependencies. |
| `pytest tests/ -q --tb=no` | Forced exact-workflow diagnostic, exit 2: five legacy collection errors; first material signature is missing `neurons`. |
| `ruff check .` | Exit 1: 776 findings, 544 fixable. |
| `black --check .` | Exit 123: 66 files would reformat, 70 unchanged, and parse failures at `carbon/challenges/navier_stokes_2d.py:34:61` and `carbon/validator/sciml_validation.py:37:8`. |
| `POC_FAST=1 bash poc/scripts/smoke.sh` | Exit 2 after the oracle and three JAX fixture runs; final pytest collection cannot import `role_seed` from `poc.generators.burgers1d`. |
| Editable `--no-deps` install plus isolated imports from outside the tree | Exit 0 for `carbon==0.9.0`, `carbon`, and all 14 A0 role packages. |
| `git diff --check` | Exit 0. |

Base Actions run `32244438188` is the authoritative workflow record. Test job
`96041796858` failed installation and **skipped** its pytest step. Quality job
`96041796669` installed tools, failed Ruff on 776 findings, and skipped Black.
The forced commands above are diagnostics, not descriptions of skipped Actions
stages.

**Dependency decision (REPAIR).** The canonical root and 14 A0 role packages
import with every inherited third-party dependency blocked, so the truthful
core dependency set is empty. The supported `dev` extra pins pytest 9.1.1,
Ruff 0.16.3, and Black 26.5.1. Bittensor is retained only behind optional
`chain`, `validator`, and `miner` aliases; the aliases use plain Bittensor
because upstream has no `validator` or `miner` extras. NeuralOperator,
PhysicsNeMo, and the historical PoC each have explicit optional extras.
PhysicsNeMo uses the actual `nvidia-physicsnemo` distribution and its documented
`physicsnemo.models.fno` import boundary; that extra is Python 3.11+ upstream.
The retained NeuralOperator model-argument compatibility remains explicitly
deferred and unqualified.

Both backend adapters now register lazily without importing their scientific
packages. Direct or registry-based construction without an extra raises an
actionable extra-specific error. A missing transitive module in an installed
backend is re-raised rather than mislabeled as an absent backend. No fake or
vendored scientific package was introduced.

**Test classification (WRAP).** The default `python -m pytest -q` lane is
`tests/cpu/`: 22 tests cover `carbon`, all 14 A0 roles, distribution identity,
isolated outside-tree imports, optional-dependency absence, and backend failure
contracts. Five inherited root tests were moved with assertions preserved to
`tests/legacy/`; they target retired `neurons` APIs or superseded
scoring/schema/seeding behavior and contain collection/API failures not solved
by installing heavyweight dependencies. The 67 PoC tests remain in place and
are marked `poc`; 32 are additionally integration, two JAX-backend, and one
gold. The `invariant` marker is registered for A12, but no A12 tests or behavior
were added.

**Quality debt decision (WRAP/REPAIR).** Full cleanup is not appropriate in A1:
the base has 776 Ruff findings across legacy code, 66 Black reformat candidates,
and two files Black cannot parse. A complete normalized fingerprint inventory
is committed at `.ci/quality-baseline.json` and anchored to the authorized base.
The blocking gate enumerates Python files explicitly, runs pinned isolated
Ruff, runs Black with the empty `/dev/null` configuration, validates Black's
full-file summary, rejects diagnostics absent from the base inventory, and
strictly checks every added/touched Python file. It permits debt removal, not
new debt, and uploads the complete current report. This converts a permanently
red inherited job into a meaningful ratchet without deleting, excluding, or
making quality controls non-blocking. Running the committed generator against
a second clean detached checkout of the starting SHA reproduced the baseline
JSON byte-for-byte: 776 Ruff diagnostics and 68 Black debt entries.

**Local clean-candidate result.** In a detached candidate worktree, `python -m
pip install -e ".[dev]"` exited 0 and installed `carbon==0.9.0`; `python -m
pytest -q` exited 0 with 22 passed. Isolated imports from `/private/tmp` passed
for the package and all 14 roles. A separate wheel build/install contained 69
files, included all 14 roles, and imported `carbon` from `site-packages`. The
quality gate exited 0 at Ruff 769/776 and Black 64/68, with seven Ruff and four
Black baseline entries removed, no additions, and 12 changed Python files
strict-clean. Raw audits remain visibly red at 769 Ruff findings (537 fixable)
and Black exit 123 with 62 reformat candidates, 79 unchanged files, and the same
two parse failures. `git diff --check` exited 0.

The post-change `POC_FAST=1 bash poc/scripts/smoke.sh` again exited 2 at the
same missing-`role_seed` collection error after completing its oracle/fixtures.
This is an unchanged inherited PoC failure, not a passed A1 stage or scientific
claim.

**Authoritative draft-PR result.** Draft PR #5 run `32250522522` completed
successfully on Ubuntu/Python 3.11.15. CPU tests job `96060233144` passed the
supported development install, reached the actual `python -m pytest -q` step,
and reported 22 passed in 0.13 seconds. Code-quality job `96060233203` passed at
Ruff 769/776 and Black 64/68 with all 12 changed Python files strict-clean, then
uploaded complete report artifact `9364221072`. No blocking step was skipped.

A1 is now **IMPLEMENTED and TESTED** for its CPU engineering-infrastructure
scope. Scientific, security, LIVE, emissions, and production qualification
remain unclaimed. The exact final PR head and its post-evidence Actions run are
maintained in the draft PR body because a commit cannot record its own SHA.

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

### Blocking-review follow-up: installability and CI-equivalent evidence

**Compared states and isolation.** The review follow-up compared detached,
clean Git worktrees created with `git worktree add --detach`: base
`ab765b07bc8c41106194ce6d06b4a2bd1c03f9a1` at
`/private/tmp/carbon-a0-base.Mxz8U8` and the pre-follow-up A0 head
`e2f91a428c91a963caf261747f2ffd05ea0e1821` at
`/private/tmp/carbon-a0-head.ZWnuEh`. Each workflow path used a separate clean
virtual environment. Local comparisons used CPython 3.11.11 on macOS arm64
with virtual-environment pip 24.0. Neither worktree was dirty.

**No-dependency editable-install proof (A0 head).** From a clean virtual
environment, the actual project build configuration succeeded without a
packaging-metadata change:

```text
python -m pip install --no-deps -e /private/tmp/carbon-a0-head.ZWnuEh
exit 0; built and installed distribution carbon==0.9.0
```

Build isolation was left enabled; `--no-build-isolation` was not necessary.
From `/private/tmp` (outside the repository), the installed interpreter
`/private/tmp/carbon-a0-venvs.pRnWzd/head-editable/bin/python` imported
`carbon` and all fourteen required role packages at exit 0. Resolved paths
were:

```text
carbon              -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/__init__.py
carbon.schema       -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/schema/__init__.py
carbon.registry     -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/registry/__init__.py
carbon.seeding      -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/seeding/__init__.py
carbon.scoring      -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/scoring/__init__.py
carbon.cards        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/cards/__init__.py
carbon.fees         -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/fees/__init__.py
carbon.traineval    -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/traineval/__init__.py
carbon.mcp          -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/mcp/__init__.py
carbon.leaderboard  -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/leaderboard/__init__.py
carbon.logging_utils -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/logging_utils/__init__.py
carbon.evaluation   -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/evaluation/__init__.py
carbon.audit        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/audit/__init__.py
carbon.chain        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/chain/__init__.py
carbon.qualification -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/qualification/__init__.py
```

This proves only editable installation and import discovery for A0. It does
not prove that application dependencies, scientific behavior, CI, or any
backend is healthy or production-qualified.

**Exact current-workflow base/head comparison.** The authoritative workflow is
`.github/workflows/ci.yml`. It uses Python 3.11, a test job with
`pip install -e ".[dev]"` followed by `pytest tests/ -q --tb=no`, and a lint
job with `pip install ruff black pytest`, `ruff check .`, then
`black --check .`.

| Workflow command / stage | Base `ab765b07` | A0 head `e2f91a42` | Delta |
|---|---|---|---|
| `pip install -e ".[dev]"` | Exit 1 while resolving declared dependencies: `No matching distribution found for physicsnemo` | Exit 1 at the same stage with the same first material error | No new A0 failure; the workflow test command was not reached in either sequential job. |
| `pytest tests/ -q --tb=no` (forced in the isolated lint-tool environment because the test-job install cannot complete) | Exit 2; five collection errors; first material signatures are missing `neurons`, then `carbon` | Exit 2 with the same five files and signatures | No delta. This forced run is not represented as a successful or reached test-job stage. |
| `pip install ruff black pytest` | Exit 0 | Exit 0 | No delta. |
| `ruff check .` | Exit 1; 776 errors, 544 fixable | Exit 1; 776 errors, 544 fixable | Identical inherited lint failure. |
| `black --check .` (forced after Ruff for comparison; Actions skips it after Ruff fails) | Exit 123; 66 files would reformat, 56 unchanged, and two legacy parse failures | Exit 123; 66 files would reformat, 70 unchanged, and the same two parse failures | Same failure stage/signatures; the fourteen new one-line package markers account for the additional unchanged files. |

GitHub Actions corroborates the local comparison. Base run
`32232686102` and PR-head run `32234794106` both fail the test job at
`pip install -e ".[dev]"` on unavailable `physicsnemo`, skip the test step,
install lint tools successfully, and fail Ruff with the same 776 findings;
Black is skipped in both actual runs. These are inherited CI failures, not A0
regressions.

**Maturity statement.** The lowercase namespace and fourteen behavior-free
package boundaries are **IMPLEMENTED**. Editable installation and outside-tree
imports are **TESTED** by the isolated proof above. Full dependency resolution,
the inherited test/lint baseline, scientific semantics, backend behavior,
Bittensor integration, LIVE readiness, and production qualification are not
green and are not claimed. No packaging defect was found, so A0 changes no
packaging metadata or dependency declaration. The evidence supports retaining
A0 as `done`: installation/import acceptance is proven, exact base/head
workflow failures are non-regressing, and the base-to-head diff remains solely
A0 layout, mapping, evidence, and status work.

After this evidence-only documentation update, the no-dependency editable
install and all outside-tree imports passed again; the full workflow install,
forced test/Ruff/Black comparisons, and every original A0 baseline command
retained the signatures recorded above. `git diff --check` also passed. No
generated smoke artifacts, bytecode, or editable-install metadata is included.

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
