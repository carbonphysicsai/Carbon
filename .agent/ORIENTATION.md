# Carbon A-1 Repository Orientation

**Ticket:** A-1 only (audit/orientation; no A0–A12 implementation)  
**Audit date:** 2026-08-18  
**Git commit:** `0eed4e92609b4f26bd095a90f8cba9b7376fbe09`  
**Build_Out pin:** **v1.4** (`Design_Specs/Build_Out.md`, version field)  
**Working branch at audit:** `work`

## Scope and evidence

This note records archaeology, not an implementation endorsement. Historical code is assessed against current domain-owned specifications. A passing historical test would be evidence of execution only, not semantic compliance. No implementation, package layout, scientific threshold, security policy, economic value, or LIVE setting was changed.

Read in full for this ticket: root `AGENTS.md`; `agent_pack/EXECUTION_PROTOCOL.md`; `.agent/tickets/A-1_orientation.md`; `Design_Specs/Build_Out.md` §§0–8 and §12; `Design_Specs/Miner_MCP.md`; `Design_Specs/Scoring.md`; root `README.md` and `SPEC.md`; and all current context documents listed below. The requested uppercase context paths do not exist on this case-sensitive filesystem. Their actual tracked names are:

- `docs/context/Carbon_Context.md`
- `docs/context/Architecture_Rationale.md`
- `docs/context/Decisions.md`
- `docs/context/Implemented_vs_Specified` (no `.md` suffix)
- `docs/context/Open_Questions.md`

The canonical board and tickets are verified under root `.agent/`. `agent_pack/.agent/` does not exist and is retired; `agent_pack/` contains the execution protocol/templates/executor notes only.

## Authority for Wave A

Authority is domain-owned rather than inferred from implementation:

| Domain | Authority |
|---|---|
| Constitution and working rules | root `AGENTS.md` |
| Architecture/protocol invariants | root `SPEC.md` |
| Miner free/paid behavior and disclosure | `Design_Specs/Miner_MCP.md` |
| Scoring mathematics and forbidden inputs | `Design_Specs/Scoring.md` |
| Official data/seeding | `Design_Specs/Data_Management.md` + `Design_Specs/Trustless_Verification.md` |
| Generator/scientific qualification | generator, validation, evidence/envelope specifications |
| Stop-ship/readiness | `Design_Specs/Launch_Bar.md` |
| Sequencing, dependencies, Wave acceptance | `Design_Specs/Build_Out.md` v1.4 |
| Ticket translation/board | root `.agent/` |

The five `docs/context/` documents are useful reconciled context and a provisional implementation ledger; each says `v1 — team review` (or provisional). They do not supersede the domain owners above.

## Complete repository map (real versus expected)

The complete tracked/current file tree was enumerated with `find . -path './.git' -prune ... -type f -print | sort`. Material top-level roots are:

| Root | Present | Verified contents / role |
|---|---:|---|
| `.agent/` | Yes | Canonical `WAVE.md`, decisions, invariants, A-1 and A0–A12 tickets, plans. |
| `.github/workflows/` | Yes | One `ci.yml` with Ruff, Black, and root `tests/` jobs. |
| `Design_Specs/` | Yes | Current Build Out and domain specifications. |
| `docs/context/` | Yes | Five requested documents, but casing/suffix differs as documented above. |
| `poc/` | Yes | Burgers-1D/FNO offline vertical: configs, schema, fixtures, generator, train/eval/validator code, 18 test files, smoke script. |
| `Carbon_Logic/` | Yes | 50-file historical Python tree for common logic, challenges, training, validator, miner, Landscape, specialists, SciML, emissions. Directory name does not match its own `carbon.*` imports. |
| `neurons/` | Yes | Historical Bittensor miner/validator entrypoints plus scoring, stress, strategy, determinism and symbolic modules. |
| `Julia/` | Yes | SciML HTTP/service skeleton, handlers/solvers/utilities, Docker/scripts, and two test files; `Project.toml` is malformed/duplicated. |
| `tests/` | Yes | Five legacy root Python test modules plus `test.md`. |
| `docker/`, `k8s/` | Yes | Historical deployment definitions; not qualification evidence. |
| `scripts/`, `examples/` | Yes | Historical local validation, leaderboard/Landscape/prior scripts and miner examples. |
| `agent_pack/` | Yes | Current protocol plus plan/executor material; no canonical tickets. |
| `zBuild Appendices/`, `zDesign Archive/` | Yes | Historical/reference documents. There is no top-level directory literally named `appendices/`. |
| `carbon/` | **No** | This is the package name declared by `pyproject.toml` and imported throughout, but no directory/symlink exists. |
| `hydrogen/` | **No** | Numerous `Carbon_Logic/` modules still import this superseded namespace. |

No directory name alone identifies a canonical executable implementation.

## Package and namespace archaeology

1. `pyproject.toml` names the distribution `carbon` and setuptools includes `carbon*`, but the only comparable source root is `Carbon_Logic/`. On a case-sensitive filesystem an editable install cannot expose `carbon.common` from `Carbon_Logic/common`.
2. The git history records an earlier package rename (`hydrogen` → `carbon`) in `pyproject.toml`, followed later by addition of the entire directory as `Carbon_Logic/`. The source imports were never consistently migrated.
3. `Carbon_Logic/` is internally split: some files import `carbon.*`, while validator/training/challenge/Landscape/specialist files still import nonexistent `hydrogen.*`.
4. `scripts/generate_leaderboard.py` imports nonexistent capitalized `Carbon.*`, a third Python namespace spelling.
5. `poc/` is a real package, but it depends on `carbon.common.{seeds,scoring,model_card}` and is therefore currently non-importable.
6. `neurons/` uses namespace-package behavior (no root `__init__.py`) and likewise depends on `carbon.*`; Bittensor is not installed in the audited environment.
7. `pyproject.toml` defines optional groups only for `validator` and `miner`; CI installs `.[dev]`, but no `dev` extra exists. CI also installs Ruff/Black only in a separate job and does not install project/runtime dependencies there.
8. `poc/requirements.txt` is a smaller independent environment and does not install the root distribution; that still cannot resolve the missing `carbon` package.

**Likely canonical implementation direction (not an A0 decision):** current specs and Build Out clearly target a future lowercase `carbon/` package. There is no current canonical implementation that runs under that name. The Burgers PoC is the strongest candidate vertical to wrap/repair selectively, while small common primitives in `Carbon_Logic/common/` may be salvageable only after semantic repair. A0 must make the actual package mapping decision; A-1 does not rename or copy anything.

## Verified implementation observations

### PoC

The PoC has the most coherent vertical structure: strategy-only handoff, schema/clamps, role-separated data generation, retraining, stress categories, gates, score pack, cards, deterministic fixtures, and focused tests. Structurally this is valuable.

It is not currently executable because of the namespace break. It is also not current-scoring compliant: `poc/eval/score.py` calls the historical common scorer, uses linear clipped margins, and the common scorer uses an arithmetic weighted sum. `Scoring.md` requires binary gates followed by quadratic physics margins and a weighted-geometric aggregate. The PoC card path embeds raw seed bundles, train/eval/stress seeds, hashes and block/run material; that may be acceptable only in a strictly private internal card, never in EvaluationCard/MCP/public output. `HandoffEnvelope.to_public_dict()` currently calls its seed context “safe to log” and returns `block_hash`/`run_nonce`, which conflicts with current leakage/disclosure doctrine for miner-visible/public paths.

The PoC's fixed numeric configs and claimed proof text predate current dossier-bound `HUMAN_INPUT` rules. They are synthetic historical fixtures, not LIVE-qualified science. Its generator/solver/training code must not be casually rewritten: it provides useful scientific reference structure, but its numerical credibility is unqualified.

### `Carbon_Logic/`

Useful structural primitives exist: deterministic hashing/canonical strategy hash, seed-domain helper shape, strategy validation/clamps, model-card persistence shape, backbone registry, physics/generator/training concepts, and SciML client shape. Positive semantic compatibility is limited:

- `common/scoring.py` implements arithmetic aggregation and linear margins, directly superseded by current `Scoring.md`.
- `common/seeds.py` exposes official raw/master/role seeds and block material in returned bundles intended “for cards”; its domains (`data`, `stress`, etc.) do not exactly implement Build Out's required `mock | official_train | official_eval | official_stress | reference | dossier` model or structural mock refusal.
- `common/model_card.py` stores strategies and raw seeds wholesale and has no EvaluationCard allow-list/budget layer.
- `common/strategy_schema.py` says unknown keys reject but actually passes unknown loss keys and preserves unrecognized top-level input; constants are historical values without current qualification.
- Two files do not parse: `challenges/navier_stokes_2d.py` and `validator/sciml_validation.py`.
- Several modules retain nonexistent `hydrogen.*` imports. Validator code also has undefined `torch` references and randomized scoring behavior; it is not a trustworthy official evaluator.
- Landscape and Specialist implementations are post-P0 prototypes and must not be represented as operational or score-bearing.

### `neurons/` / Bittensor entrypoints

`neurons/miner.py` and `neurons/validator.py` are apparent Bittensor entrypoints, but both depend on the missing lowercase package. They are legacy skeletons, not a demonstrated testnet path. The validator wires historical stress/scoring/tracker mechanics, not the Build Out submission FSM, pinned TrainEvalAPI, exact qualification gate, or disclosure boundary. `Carbon_Logic/validator/validator.py` is a separate competing validator implementation using old `hydrogen` imports. Neither earns canonical status.

The historical winner tracker/emission mechanics may offer data-structure/reference value, but must be audited for current weighted-geometric scoring, immutable pack pinning, fee exclusion, `FAILED_INFRA`, stub non-emission, and Bittensor semantics before reuse. No actual current testnet scores→weights proof was found.

### Julia tree

The Julia tree is a sizeable SciML service skeleton with HTTP handlers, reference/adjoint/symbolic solvers, reproducibility utilities, deployment files and tests. It is scientifically sensitive and should be preserved as reference pending specialist review rather than rewritten casually.

It is not runnable as checked: Julia is unavailable in the current environment, and `Julia/Project.toml` contains duplicate keys (`authors`, `version`, `JSON3`, `CUDA`, `ReverseDiff`, others) plus mutually conflicting `NeuralPDE` UUIDs. Several UUIDs appear placeholder-like and require Julia/SciML owner verification. Existing Julia tests are narrow smoke contracts and cannot establish solver correctness, reproducibility, or qualification.

### CI and tests

CI is present but not green by inspection or local execution. The root test job cannot install `.[dev]` because that extra is absent, then root tests import a package that is not installed. The lint job checks the entire historical tree and currently reports syntax and style failures. CI has no PoC, Julia, package-import, mock-isolation, leakage, or Wave A invariant coverage.

Root tests largely encode historical scorer/stress/tracker behavior. In particular, tests expecting arithmetic scoring or legacy aliases are potentially stale against current `Scoring.md`; they must not be made authoritative merely by restoring their imports.

## KEEP → WRAP → REPAIR → REPLACE classification

“Structurally reusable” below is distinct from “semantically compliant.” No component is asserted production-qualified.

| Component | Class | Evidence and boundary |
|---|---|---|
| Root specs, `.agent/` board/protocol | **KEEP** | Current authority/sequencing artifacts; canonical board verified. |
| Existing GitHub Actions workflow | **REPAIR** | Useful two-job skeleton, but nonexistent `dev` extra, broken package mapping, no PoC/Julia/invariant coverage, and red baseline. |
| PoC strategy fixtures/schema/handoff shape | **WRAP / REPAIR** | Structurally useful bounded strategy/retrain handoff; must align with current schema, disclosure, mock isolation and human-owned limits. |
| PoC Burgers generator, FNO, train/eval/oracle code | **WRAP** as historical/scientific reference | Most coherent vertical and tests exist; scientific semantics/thresholds are not dossier-qualified. Preserve behind explicit fixture/mock boundaries pending SciML review. |
| PoC scorer/config/card output | **REPLACE** scorer semantics; **REPAIR** plumbing | Linear/arithmetic scoring conflicts materially with current quadratic/weighted-geometric spec; raw seed-rich cards cannot be public. Retain tests only when rewritten to current contracts. |
| `Carbon_Logic/common/scoring.py` | **REPLACE** | Direct normative conflict (arithmetic aggregate, linear margin, embedded default thresholds). Clean current pack-driven engine is lower risk than semantic salvage. |
| `Carbon_Logic/common/seeds.py` | **REPAIR** | Hash/domain-separation utilities structurally reusable; official/mock role model and non-leak public projections are incomplete/unsafe. Derivation formula still requires human confirmation. |
| `Carbon_Logic/common/strategy_schema.py` | **REPAIR** | Useful validation/clamp shape, but behavior contradicts unknown-key claim and contains unqualified historical rails/allow-list. |
| `Carbon_Logic/common/model_card.py` | **WRAP / REPAIR** | Canonical JSON hashing and append shape reusable internally; must separate private Model Card from allow-listed EvaluationCard and exclude official seed material from public views. |
| `Carbon_Logic` backbones/data/challenge/training/physics | **WRAP** selectively, otherwise **REPAIR** | Historical structural/reference value; imports and semantics are inconsistent, dependencies heavy, and scientific correctness unverified. Challenge code does not earn preservation as current packs merely by existing. |
| Broken `navier_stokes_2d.py`, `sciml_validation.py` | **REPLACE or focused REPAIR after scope review** | They do not parse. Out of A-1 scope and not required for Wave A vertical; do not broaden A0 merely to fix them. |
| `Carbon_Logic` validator implementations | **REPLACE** as official architecture | Competing legacy path, nonexistent imports, undefined names/random score adjustment, and absent current TrainEval/FSM/pin/security contracts make salvage higher risk. Individual helpers may still be wrapped after audit. |
| `neurons/miner.py` | **REPAIR / WRAP** | Bittensor entrypoint shape may be reusable, but package imports and current miner/MCP contract are absent. Miner neuron is optional in Build Out C8. |
| `neurons/validator.py` + scorer/tracker/stress | **REPLACE** official orchestration; **WRAP** isolated utilities only | Legacy orchestration materially misses current pinned evaluation, FSM, infra/science, disclosure, qualification, and stub boundaries. Stress/data classes may provide reference value after semantic audit. |
| Landscape/specialist/symbolic code and related scripts | **KEEP as historical reference only; defer** | Post-P0 and explicitly not Wave A. Not evidence of a live knowledge/product layer and forbidden as lean score inputs. |
| Julia SciML tree | **WRAP / REPAIR after human SciML review** | Valuable specialist structure; malformed manifest and unavailable runtime prevent execution. Scientific solvers require positive evidence, not replacement by convenience. |
| Docker/Kubernetes manifests | **REPAIR later** | Deployment scaffolding exists but contains historical images/config and is not isolation, reproducibility, or production qualification evidence. |
| Root legacy tests | **REPAIR / REPLACE assertions selectively** | Useful failure shapes but imports are broken and some expected scoring semantics are stale. Reconcile each with domain specs rather than preserving behavior blindly. |

## Baseline results (pre-existing; no repairs made)

Environment: Python `3.12.13`; branch `work`; clean tracked tree before documentation edits; JAX importable; Bittensor absent; Julia executable absent.

| Exact command | Result |
|---|---|
| `python -m pytest tests/ -q --tb=no` | **FAIL**, exit 2: five collection errors. Four paths fail on missing `carbon`; tracker also fails on missing `bittensor`. No tests ran. |
| `python -m pytest tests/ -q` | **FAIL**, exit 2: confirmed full traces for the five collection errors above. |
| `POC_FAST=1 PYTHONPATH=. python -m pytest poc/tests -q` | **FAIL**, exit 2: 16 collection errors, all rooted in missing `carbon` imports; no tests ran. |
| `POC_FAST=1 ./poc/scripts/smoke.sh` | **FAIL**, exit 126: tracked script lacks executable permission despite README instructions. |
| `POC_FAST=1 bash poc/scripts/smoke.sh` | **FAIL**, exit 1 at oracle import: `ModuleNotFoundError: No module named 'carbon'`; JAX was detected. |
| `python -m compileall -q Carbon_Logic neurons poc tests scripts examples` | **FAIL**, exit 1: syntax errors in `Carbon_Logic/challenges/navier_stokes_2d.py` and `Carbon_Logic/validator/sciml_validation.py`. |
| `ruff check .` | **FAIL**, exit 1: 101 findings, including the two syntax failures, undefined names, stale imports, and style errors. |
| `black --check .` | **FAIL**, exit 123: 66 files would be reformatted and the same two files cannot parse. |
| `julia --version` | **NOT RUNNABLE**, exit 127: Julia is not installed in this environment. |

These are baseline failures, not introduced by A-1. A-1 intentionally does not repair them.

## Wave A (§12) gap map

No Wave A checklist item is currently evidence-green.

| Component | Current evidence / gap |
|---|---|
| C0 monorepo/CI | Roots and CI exist, but package mapping and CI install/test commands are broken. |
| C2 strategy schema | Legacy/PoC schemas exist; no single current strict contract or deny-list evidence. |
| C1 registry/LIVE gate | No verified exact-version qualification-manifest gate. |
| C6 seeds/mock guards | Useful helpers/tests exist, but required official domains, structural mock refusal, and leakage controls are not established. |
| C5 scoring engine/packs | Historical pack/scorers conflict with current normative weighted-geometric/quadratic design and contain unqualified numbers. |
| C12 card store/disclosure | Internal JSON card writer exists; no authenticated budgeted EvaluationCard allow-list. |
| C13 fees/submission/FSM | No verified permanent submission ID ledger with `CANCELLED`, `FAILED_INFRA`, refund/retry and versioned idempotency. |
| C9 Miner MCP | Miner agent/client fragments exist; current required tools/policy guards are not demonstrated. |
| C14 leaderboard | Script/reference fragments only; public allow-list/leakage tests absent. |
| C16 observability | No verified structured redaction/failure-tag/metrics contract. |
| TrainEvalAPI stub | No verified shared contract or mechanically enforced `emission_capable=False`. |
| §12 invariant CI | Root and PoC suites do not collect; leakage and mock isolation acceptance evidence absent. |

## Document conflicts and ambiguities requiring human treatment

1. **Context filenames:** the user's requested uppercase/suffixed paths differ from actual tracked casing/suffix. This audit read the only matching current documents and records the discrepancy; maintainers should decide whether to normalize names later. A-1 does not rename them.
2. **Open questions mixed with proposals:** `docs/context/Open_Questions.md` begins with unresolved human-owned questions, then appends “Architect Recommendations” explicitly labelled proposals, including a proposed first LIVE challenge. These recommendations are not ratified decisions and must not be implemented as authority. Human owners must ratify/move dispositions before relying on them.
3. **Historical code/tests versus current scoring:** implementation and tests use arithmetic/linear scoring while current `Design_Specs/Scoring.md` owns weighted-geometric/quadratic semantics. This is not an unresolved same-domain document conflict: current Scoring is authoritative; old tests/code are stale. Any scientific pack values remain human/dossier-owned.
4. **PoC README link:** it points to `appendices/POC_Burgers_FNO.md`, but the current spec is `Design_Specs/POC_Burgers_FNO.md` and no `appendices/` directory exists. Treat the README link/layout as stale.
5. **Build Out ticket reference:** A-1 cites Build Out §§11 and 16 while its mandatory reading and protocol require §§0–8 and §12. Both were inspected as applicable repository layout/doctrine context, but A-1 implementation remains orientation only.

No material conflict was found among the current domain-owned architecture, Miner MCP, Scoring, and Build Out sequencing rules that A-1 needs to resolve. Where legacy behavior differs, it is classified as legacy rather than silently elevated.

## Maintainer dispositions recorded after the audit

The maintainer supplied the following directions after the audit. The canonical decision record is `.agent/DECISIONS.md`; these notes preserve their relationship to the audit findings:

1. Establish lowercase `carbon/` as canonical and support only needed import paths; retire `Carbon_Logic`, `hydrogen`, and `Carbon` as canonical namespaces.
2. Use Burgers as the first vertical promotion source without approving its present science or fixed values.
3. Reuse `neurons/` only if useful after audit.
4. Include Julia in the first build as the v0 data-generator verification path; inclusion is not scientific qualification.
5. Normalize context filenames in a scoped ticket. Use the `Open_Questions.md` proposal appendix as the v0 direction subject to team audit and the existing authority order.

These dispositions narrow A0 but do not authorize mass deletion, semantic carry-over, LIVE activation, or work beyond the active ticket.
Before the corresponding later tickets/LIVE work, designated humans must also supply/approve: strategy search surface and resource rails; seed derivation/timing; first challenge envelope/dossier; Score Pack thresholds/categories; reproducibility tolerances/hardware profile; disclosure budget; fee/rate/retry policy; security/isolation acceptance; authorized signers; and the LIVE decision. None is decided here.

## Risks A0 and subsequent Wave A tickets must address

- A superficial directory rename could make imports pass while preserving superseded scoring, seed leakage, or unsafe validator semantics.
- Installing all current root dependencies is expensive and widens supply-chain/runtime risk; Wave A should keep CPU/unit boundaries narrow and justify dependencies.
- Restoring legacy tests without reconciling their assertions could institutionalize stale arithmetic scoring or legacy disclosure.
- PoC mock/local and “official” modes share code and seed bundles; structural isolation must be designed rather than inferred from flags/names.
- Private Model Cards, miner EvaluationCards, logs, MCP responses, and leaderboard projections are not separated today; raw seed and reconstruction metadata can leak.
- Competing validators (`Carbon_Logic/validator/*` and `neurons/validator.py`) invite accidental wiring to the wrong semantics.
- Historical fixtures/config constants could flow into LIVE unless registry/qualification gates reject placeholders mechanically.
- Stub results could reach tracker/emission paths unless `emission_capable=False` and downstream guards are mechanical.
- Infrastructure/resource failures are not modeled through the required FSM and could be mistaken for scientific zeroes.
- Julia/scientific solver code is untested here; rewriting it for convenience risks inventing science, while treating it as correct risks false qualification.

## Explicit A-1 non-goals

- No A0–A12 code or package-layout implementation.
- No LIVE activation, qualification, threshold/envelope/tolerance setting, emissions, fee, rate, or launch decision.
- No Landscape, Specialist Bank, product qualification, mainnet, or scientific solver expansion.
- No rename, archive, deletion, mass formatting, dependency addition, implementation repair, or stale-test weakening.
- No claim that the PoC, Python framework, Bittensor path, Julia service, CI, or science is production-qualified.

## A-1 conclusion

The repository contains substantial historical reference material but no currently runnable canonical lowercase `carbon` package. The most defensible path is audit-first selective reuse: preserve the PoC and scientific trees as evidence/reference, wrap or repair narrowly compatible primitives, and replace official semantics where current specifications materially supersede the prototype. A0 must begin only after human review of this orientation and must not infer semantic truth from the legacy layout.

---

# Wave B orientation — B-01 (2026-08-29)

> **Prospective appendix.** Everything above this divider is the historical
> A-1 orientation record and remains unchanged evidence of what was observed
> then. This appendix records the current B-01 audit at the verified Wave-B
> base. The full component map, conflict ledger, command output, and ticket
> crosswalk are canonical in
> [`.agent/evidence/wave_b/b-01.md`](./evidence/wave_b/b-01.md).

## Exact B-01 base and authority

| Item | Pin |
|---|---|
| Repository | `carbonphysicsai/Carbon` |
| Base commit | `cce1efec19601d4e460676e9b422cc569b9d66d0` |
| Base tree | `a270616e2d54401f5c73b408b469d8c9f6a8b1f9` |
| Branch | `agent/b-01-orientation` |
| Worktree | `C:\Users\Ryan_\source\Carbon` |
| Initial status | clean |
| `origin/main` at branch creation | `cce1efec19601d4e460676e9b422cc569b9d66d0` |
| B-01 ticket blob | `4702fe30305bf25556bedce95420cc07a4704b23` |
| Active wave | Wave B, active in bounded development scope |
| Controlling board | `.agent/WAVE_B.md` version 0.4 |
| Build Out | version 1.4 plus the owner-canonical constitutional overlay |
| Research contract | version 0.3, OWNER-REVIEW CONTRACT CANDIDATE; not ratified by B-01 |
| Scientific canon | v4 remains owner-canonical; v4.1 additions remain proposed |
| Post-merge CI at base | run 33282379171, successful exact-SHA push |

PR #54 normally merged the reviewed Wave-B governance tree as the exact base.
Fresh remote, tree, status, board, ticket-selection, issue/review queue, and
reserved-human checks passed. No explicit `REQUEST_CHANGES` or `BLOCKED`
direction applies to B-01, and no reserved decision is required for
orientation.

## Wave A closure and Wave B boundary

A-1 and A0–A12 are closed only in their recorded bounded engineering scopes.
No Wave-A row remains conditional, unmerged, `todo`, `in_progress`, or
`blocked` within that closed scope. Closure and Wave-B activation create no
scientific, security, network, commercial, production, `LIVE`, launch,
frontier, product, settlement, chain, weight, or emission authority. Wave B
does not retroactively widen a Wave-A implementation.

B-01 is documentation/evidence orientation only. The proposed Wave-B research
architecture remains gated by B-07R; the exact v2 service protocol remains
gated by B-07S. B-02, B-07, and all other later implementation remain
unstarted.

## Current repository map

The root-layout `carbon==0.9.0` package is now canonical and includes bounded
Wave-A implementations for:

- exact Strategy v1 validation;
- Challenge registry and fail-closed LIVE qualification;
- typed seeding/domain separation;
- fixture-only Score Pack loading/scoring;
- private result storage and allow-listed EvaluationCard projection;
- submission identity/FSM and typed infrastructure failure;
- deterministic fixture TrainEval;
- the exact seven-operation v1 in-process MCP surface;
- fixture-only Challenge-bound leaderboard projection;
- redacted in-process observability; and
- invariant CI.

These are implemented/tested only in their recorded bounded scopes. Empty or
reserved `evaluation`, `audit`, `qualification`, and `chain` packages are
package seams, not implemented capabilities.

The following remain historical, optional, unqualified, or noncanonical:

- `poc/` Burgers/FNO generator, NumPy/JAX training, score/card, seed, and smoke
  paths;
- `Julia/` and legacy SciML client/validator paths;
- legacy miner, validator, protocol, Bittensor, emission, and direct-weight
  paths;
- noisy/random Landscape, specialist, symbolic, and prior paths;
- old generic Challenge/data loaders and rich Strategy helpers; and
- legacy arithmetic/fixed-threshold scoring and raw seed bundles.

No runtime implementation exists yet for the proposed `ParameterCatalog`,
`StrategyCompiler`, `ResolvedConstructionPlan`,
`ChallengeInteractionManifest`, research records/receipts, `PriorPack`,
`TruthAsset`, `ReferencePolicy`, `MeasurementContract`, `SamplingPlan`, or
`ResearchMcpService`.

## Reuse disposition summary

The 30-row canonical audit in the B-01 evidence record has:

- **KEEP:** 14
- **WRAP:** 5
- **REPAIR:** 3
- **REPLACE:** 7
- **NEW_OWNER_DECISION_REQUIRED:** 1

The principal KEEP choices are the canonical Wave-A Strategy, registry,
seeding, scoring, card, FSM, fixture TrainEval, seven-tool MCP, leaderboard,
observability, CI, package, and governance boundaries. Select PoC
generator/FNO/test ideas and optional backbone adapters are WRAP candidates
only after their owning scientific/protocol tickets. Julia and legacy SciML
paths require REPAIR after B-04/B-E2 authority. Legacy rich Strategy,
raw-seed, simulated-score, noisy-prior, generic Challenge, and network/direct
weight paths are REPLACE/EXCLUDE as Wave-B authority.

The owner-decision row covers physical identity/population, SamplingPlan,
generator/reference adequacy, measurements, thresholds/weights, backend
qualification, and gauntlet policy. Fixture work can remain structurally fail
closed; B-01 decides none of those values.

These dispositions record already-authoritative canonical-versus-legacy
boundaries and route future work. They do not adopt a new architecture or
authorize a later-ticket action.

## Conflict ledger

The canonical 23-row ledger is in
[`b-01.md` Section 6](./evidence/wave_b/b-01.md#6-conflict-ledger):

| Class | Count |
|---|---:|
| `NO_CONFLICT` | 2 |
| `DOCUMENTATION_LAG` | 3 |
| `IMPLEMENTATION_LAG` | 5 |
| `MIGRATION_REQUIRED` | 13 |
| `NEW_OWNER_DECISION_REQUIRED` | 0 |

The highest-risk seams are inert Strategy parameters versus later compiler
semantics; v1 seven-tool MCP versus proposed v2; mock/practice versus official
rights; A4 typed entropy versus raw legacy seeds; A5 scoring versus legacy
simulated scores; A8 fixtures versus real construction; allow-listed
disclosure versus seed-rich legacy cards; PriorPack versus noisy Landscape
publication; qualified TruthAsset authority versus PoC/Julia code presence;
and Wave-B local research versus legacy Bittensor weights.

## Dependencies and authority

All 24 Wave-B ticket rows were checked against their tickets:

- dependency mismatches: `0/24`;
- base-status mismatches: `0/24`;
- semantic Master-question mismatches: `0`; and
- every ticket after B-01 remained `todo`.

The ratification sequence is
`B-07R → B-02B/B-02C → B-07S → B-07A/domain implementations → B-07G`.
B-07F separately owns the resolved-plan fixture-official adapter behind the
unchanged v1 lifecycle; B-E4 and B-GATE join the research and v1-fixture
paths. No dependency order was changed.

## Open design questions

For B-01:

- `RESOLVED`: 1 (MQ-018's bounded-development governance slice);
- `DEFERRED_FAIL_CLOSED`: 17 (MQ-001–008, MQ-013, MQ-015–017, the broader
  MQ-018 production slice, MQ-024–026, MQ-045, and MQ-051); and
- `OWNER_BLOCKING`: 0.

Fail-closed mechanisms include `HUMAN_INPUT`/fixture-only identities, no LIVE
manifest, typed unavailable reference outcomes, `PACK_NOT_READY`,
`EVIDENCE_DEFERRED`/`INDETERMINATE`, `UNRESOLVED` forecasts, local-only/no
charged path, TEST_ONLY priors with no public-v1 provider, rights-ineligible
evidence exclusion, and no external release.

## Baseline

The exact base passed in an isolated CI-equivalent Linux/Python 3.11
environment:

| Check | Result |
|---|---|
| Invariants | 28 passed |
| Default CPU | 2310 passed |
| Quality | Ruff 757/776; Black 62/68; removed 19/6; zero changed Python files; no new debt |
| Package/wheel/outside-tree | 28 passed; `carbon-0.9.0-py3-none-any.whl`, `sha256:d6af2e51ff6e13d1d6046ac96814cd45d654ae6226a7a3f7d4c746700024f18f` |

Optional/inherited results:

- native Windows cannot satisfy POSIX `fcntl`, descriptor-relative I/O, and
  symlink assumptions; the same base is green in canonical Linux;
- `poc/tests` exits 2 on the inherited missing `role_seed` import;
- the PoC smoke's oracle and three NumPy fallback fixtures run, then the same
  collection error occurs; it explicitly reports protocol-only/no
  train-quality claim;
- `.[dev,poc]` cannot resolve `jaxlib` in the available musl environment, so
  no JAX parity/training check was claimed;
- Julia is unavailable, `Julia/Project.toml` is invalid at line 6, column 61,
  and no Manifest exists.

No inherited failure was repaired. Exact commands, timings, versions, and
diagnostics are in [`b-01.md` Section 9](./evidence/wave_b/b-01.md#9-baseline-validation).

## Maturity, risks, and human input

B-01 establishes a specified and tested orientation baseline and a
documentation/evidence candidate. It does not implement or test the Wave-B
research service. It earns no scientific, security, network, commercial, or
production qualification and no `LIVE`, launch, frontier, product,
settlement, chain, weight, or emission authority.

Later tickets own the recorded compiler/catalog, resource, generator,
reference, measurement, Dossier, prior, practice, service, gauntlet, and
legacy-migration risks.

**Human input required for B-01 completion:** None.
