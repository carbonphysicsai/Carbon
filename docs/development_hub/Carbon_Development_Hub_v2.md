# Carbon Development Hub v2

**Purpose:** A human-facing orientation and navigation layer for understanding what Carbon is building, why it exists, where changes belong, and which repository record owns implementation detail.  
**Source snapshot:** `b86daa5d8b0f8b3e86bb82c2661f405747a200df` on `main`, captured 2026-08-31T15:15:20Z.  
**Current:** Wave B, ticket B-03. Contract merged in PR #67; runtime implementation remains selected.

## Layer contract

| Layer | Answers | Detail owner |
|---|---|---|
| Hub | What, why, where, status, dependency | This package |
| Wave board | Ticket inventory, sequence, drivers, closeout | `.agent/WAVE*.md` |
| Ticket / contract | Bounded scope, exact semantics, non-goals, DoD | `.agent/tickets/*` and domain specs |
| Decision / PR | Rationale, implementation, review, repairs, tests | `.agent/DECISIONS.md` and GitHub PR |
| Evidence | Exact proof and maturity ceiling | `.agent/evidence/*` and wave reports |

## Wave spine

| Wave | What and why | Status |
|---|---|---|
| [A](explainers/waves/wave_a.md) | **Bounded protocol skeleton**: Prove Carbon's software authority boundaries before real scientific execution. | closed |
| [B](explainers/waves/wave_b.md) | **Science-ready authoring skeletons**: Make one scientific exam authorable and the miner research loop executable with fixtures. | active |
| [C](explainers/waves/wave_c.md) | **Real single-Challenge integration**: Run one real candidate through one real end-to-end scientific path. | planned |
| [D](explainers/waves/wave_d.md) | **Human scientific qualification**: Earn the right to call the first exam LIVE. | planned |
| [E](explainers/waves/wave_e.md) | **Landscape and evidence memory**: Learn from authoritative experiments without letting learned memory control the judge. | planned |
| [F](explainers/waves/wave_f.md) | **Product qualification and specialist systems**: Separate search success from deployable product evidence. | planned |
| [G](explainers/waves/wave_g.md) | **Commercial, private, and sponsored engagement plane**: Serve real enterprises without moving business authority into the judge. | planned |
| [H](explainers/waves/wave_h.md) | **Frontier promotion and Challenge portfolio**: Separate ordinary Challenge ranking from verified frontier advance. | planned |
| [I](explainers/waves/wave_i.md) | **Treasury and network settlement**: Settle verified entitlements without rewriting scientific merit. | planned |
| [J](explainers/waves/wave_j.md) | **Model-family neutrality**: Evaluate the registered physical job across qualified model families. | planned |
| [K](explainers/waves/wave_k.md) | **Generalized agentic construction discovery**: Widen search from training strategies toward construction methods and programs. | planned |
| [L](explainers/waves/wave_l.md) | **Generalized ReconstructionProtocol**: Run construction in an isolated producer-independent reconstruction plane. | planned |
| [M](explainers/waves/wave_m.md) | **Engineering system and product lifecycle**: Qualify exact deployable systems and preserve evidence through change. | planned |
| [N](explainers/waves/wave_n.md) | **Prospective Physics Intelligence**: Prove that accumulated evidence improves future registered decisions. | planned |

## Captured ticket map

| Ticket | Purpose | Status |
|---|---|---|
| [A-1](explainers/tickets/a_1.md) | Audit the repository, pin authority, and record what to keep, wrap, migrate, or quarantine. | done |
| [A0](explainers/tickets/a0.md) | Create the stable package and role boundaries that later tickets can own without circular authority. | done |
| [A1](explainers/tickets/a1.md) | Establish repeatable CPU tests and preserve the existing quality pipeline. | done |
| [A2](explainers/tickets/a2.md) | Define the bounded declarative TrainingStrategy input and reject malformed submissions before execution. | done |
| [A3](explainers/tickets/a3.md) | Bind Challenge identity and qualification state to exact registered content. | done |
| [A4](explainers/tickets/a4.md) | Separate randomness domains for training, evaluation, stress, practice, and related roles. | done |
| [A5](explainers/tickets/a5.md) | Execute registered admissibility and ranking decisions against a bounded fixture pack. | done |
| [A6](explainers/tickets/a6.md) | Separate private result records from public-safe projections. | done |
| [A7](explainers/tickets/a7.md) | Create exact submission identity, terminal states, cancellation, and infrastructure-versus-science failure handling. | done |
| [A8](explainers/tickets/a8.md) | Exercise the official-shaped lifecycle through a deterministic fixture backend. | done |
| [A9](explainers/tickets/a9.md) | Expose the exact seven process-local miner operations for information, prior, scaffold, validation, estimate, submit, and result retrieval. | done |
| [A10](explainers/tickets/a10.md) | Publish only the fields permitted by the bounded public result state. | done |
| [A11](explainers/tickets/a11.md) | Record structured state, runtime, failure class, retry, environment, and safe evidence identifiers. | done |
| [A12](explainers/tickets/a12.md) | Test the authority boundaries as system invariants and close Wave A against its acceptance criteria. | done |
| [B-01](explainers/tickets/b_01.md) | Pin the exact authority set, reconcile conflicts, and establish baseline evidence for Wave B. | done |
| [B-01E](explainers/tickets/b_01e.md) | Make local and CI commands deterministic, pin dependencies, enforce code authority, and quarantine legacy executable paths. | done |
| [B-02A](explainers/tickets/b_02a.md) | Define the physical task, candidate output, target population, SamplingPlan, canonical cases, and their exact identities. | done |
| [B-02B](explainers/tickets/b_02b.md) | Define CandidateAssemblyContract, ParameterCatalog, optional structural components, StrategyCompiler, and ResolvedConstructionPlan. | done |
| [B-02C](explainers/tickets/b_02c.md) | Define resource classes, ceilings, reconstruction-stage receipt seams, enforcement outcomes, and non-scientific resource receipts. | done |
| [B-03](explainers/tickets/b_03.md) | Define and implement the generator API plus one structural fixed-viscosity Burgers fixture with exact case, attempt, outcome, accounting, conformance, provenance, and disclosure boundaries. | in_progress |
| [B-04](explainers/tickets/b_04.md) | Define ReferencePolicy, TruthAsset, primary and witness runner interfaces, applicability, uncertainty, independence, disagreement, and typed reference failures. | todo |
| [B-05](explainers/tickets/b_05.md) | Define MeasurementContract, ReconstructionEvidencePolicy, dependence-aware UncertaintyPolicy, and Score Pack authoring bindings. | todo |
| [B-06](explainers/tickets/b_06.md) | Build D1-D12 Dossier structure, interval-coverage evidence, cross-section consistency checks, and qualification-manifest machinery. | todo |
| [B-07R](explainers/tickets/b_07r.md) | Ratify the miner research architecture, operation ownership, rights boundaries, and separation from the official v1 submission lifecycle. | done |
| [B-07S](explainers/tickets/b_07s.md) | Ratify the exact v2 operation set, wire types, lifecycle, errors, canonicalization, bounds, and local-adapter contract. | todo |
| [B-07A](explainers/tickets/b_07a.md) | Implement shared v2 protocol primitives, ChallengeInteractionManifest, and public research-capability discovery. | todo |
| [B-07B](explainers/tickets/b_07b.md) | Implement ResearchTask, ExperimentRecord, ResearchReceipt, evidence classes, failure retention, and lineage. | todo |
| [B-07C](explainers/tickets/b_07c.md) | Implement mock-only practice tasks, practice packs, scaffold, rehearsal, and paired comparison on common fresh public cases. | todo |
| [B-07D1](explainers/tickets/b_07d1.md) | Define PriorPack, estimands, exact immutable storage and indexing, receipts, and an offline compatibility projection. | todo |
| [B-07D2](explainers/tickets/b_07d2.md) | Implement a TEST_ONLY publisher and persistent cumulative-disclosure ledger with publication schemas and negative activation tests. | todo |
| [B-07D3](explainers/tickets/b_07d3.md) | Implement exact and active prior retrieval, historical lookup, and deterministic alignment to the current Challenge. | todo |
| [B-07E](explainers/tickets/b_07e.md) | Implement static resource analysis, a future calibrated-forecast seam, and separate receipts for structural estimate, forecast, quote, admission, and observed use. | todo |
| [B-07F](explainers/tickets/b_07f.md) | Connect a ResolvedConstructionPlan to fixture-official reconstruction through the unchanged v1 lifecycle. | todo |
| [B-07G](explainers/tickets/b_07g.md) | Compose the B-07S operation set, dispatch each operation to one named domain owner, and test service-level conformance. | todo |
| [B-E1](explainers/tickets/b_e1.md) | Build R0/R1/R2 reproducibility, dependence-aware reconstruction by whole-case intervals, staged-evidence audit, and typed contested-outcome harnesses. | todo |
| [B-E2](explainers/tickets/b_e2.md) | Implement the complete typed reference outcome and failure contract for Julia and other registered reference paths. | todo |
| [B-E3](explainers/tickets/b_e3.md) | Map each scientific or engineering claim to supporting evidence, limitations, and the correct Dossier section. | todo |
| [B-E4](explainers/tickets/b_e4.md) | Test the autoresearch workflow for utility, hidden-exam leakage, poisoning, gaming, diversity collapse, and unsafe evidence use. | todo |
| [B-GATE](explainers/tickets/b_gate.md) | Run fixture integration, invariant proof, closeout reporting, and a no-placeholder-LIVE audit across the whole board. | todo |

## Change routes

- **Add a new Challenge**: Route a new physical job from authored semantics through real integration and human qualification.
- **Add or change a model architecture**: Place architecture work according to whether it changes a bounded catalog component, a reconstruction adapter, or the permitted search space.
- **Add or change a miner prior**: Route prior work through immutable schema, publication controls, deterministic provision, and leakage testing.
- **Change reference truth, measurement, or scoring**: Keep truth access, measurement definition, evidence use, and engine execution in separate owning records.
- **Change a protocol contract**: Route a cross-cutting protocol change through authority classification, bounded supersession, migration, and evidence.
- **Fix a bug or defect**: Attach the defect to the ticket that owns the violated contract, then preserve the repair and evidence trail.
- **Add a commercial or private deployment mode**: Route customer-facing capability through rights, privacy, truth access, delivery, acceptance, qualification, and lifecycle.

## Repository authority

- [Repository constitution](https://github.com/carbonphysicsai/Carbon/blob/b86daa5d8b0f8b3e86bb82c2661f405747a200df/CONSTITUTION.md)
- [Current wave register](https://github.com/carbonphysicsai/Carbon/blob/b86daa5d8b0f8b3e86bb82c2661f405747a200df/.agent/WAVE.md)
- [Wave B controlling board](https://github.com/carbonphysicsai/Carbon/blob/b86daa5d8b0f8b3e86bb82c2661f405747a200df/.agent/WAVE_B.md)
- [Agentic Development Master Plan](https://github.com/carbonphysicsai/Carbon/blob/b86daa5d8b0f8b3e86bb82c2661f405747a200df/Design_Specs/Agentic_Development_Master_Plan.md)
- [Agent decisions log](https://github.com/carbonphysicsai/Carbon/blob/b86daa5d8b0f8b3e86bb82c2661f405747a200df/.agent/DECISIONS.md)
