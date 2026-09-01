# Carbon Architecture Rationale
**Status:** v1 — team review

## Why strategies rather than trusted checkpoints
Carbon wants reproducible methods, not opaque one-run artifacts. Strategies can be independently retrained on fresh data; checkpoints can hide contamination, provenance problems, or tricks. Official evaluation therefore retrains.

## Why producer and examiner are separate
If miners control their evidence, Carbon becomes a self-reported benchmark. Independent validator retraining is the mechanism that makes the exam meaningful. Validator compute is a trust cost, not incidental overhead.

## Why public physics / hidden realization
Hiding the governing problem rewards benchmark guessing. Carbon should reward learning the declared physical regime. Publish the domain and rules; hide the future realized exam and reconstruction-sensitive feedback.

## Why validators share one exam
Validator-specific random exams mix model quality with sampling variance. Independent validators should reproduce/attest the same scientific experiment; distributional breadth belongs inside the challenge's eval/stress design.

## Why train/eval/stress separation
Miners need freedom to optimize training without choosing the answer key. Separate roles preserve search versus examination and let stress target rare in-envelope failure modes.

## Why the envelope is contractual
A certification is defensible only when tested and claimed domains match. Hard edge cases are valid; secret score-bearing extrapolation beyond the declared envelope is not.

## Why binary gates plus continuous margins
Some failures are disqualifying and cannot be traded for accuracy. Binary gates establish admissibility. Margins then reward stronger physical safety among survivors.

## Why weighted geometric scoring
Arithmetic sums permit excessive compensation; raw multiplication ignores explicit weights. Weighted geometric aggregation preserves weights while penalizing a weak leg, aligning incentives toward balanced physics, robustness, and accuracy.

## Why scientific numbers live in packs
PDE families differ in numerical floors, conserved quantities, failure modes, and engineering consequences. Protocol documents define structure; qualified packs define scientific numbers.

## Why generator validation is core
Procedural and deterministic does not automatically mean physically credible. The dossier establishes the generator's defendable envelope, evidence, coverage, uncertainty, and threshold calibration.

## Why reference caches are not the live exam
Fixed references are excellent qualification evidence but become an answer key if used as the routine leaderboard set. Qualify the generator against references; examine miners on fresh draws.

## Why free practice is incomplete but honest
Agents need dense feedback, but an exact public replica of the official grader becomes an oracle. Free practice is cheaper, shallower, coverage-limited, and coarser—not fake physics.

## Why feedback is budgeted
Repeated detailed queries can reconstruct a hidden exam even when seeds are protected. Diagnostic granularity is therefore part of the security boundary.

## Why an EvaluationReceipt exists
A Model Card is scientifically rich but not the best primitive for protocol audit, while an EvaluationCard is intentionally too coarse. Carbon therefore needs a compact signed execution-evidence object between the private transcript and public/miner projections.

The EvaluationReceipt commits to what was executed, under which versions/backend, and what result was produced without publishing the hidden exam. This makes the same evidence usable for reproducibility, disputes, validator accountability, network publication, later qualification, and customer provenance.

## Why commitment is not disclosure
Public auditability and hidden evaluation are not opposites. A cryptographic commitment can prove that a validator fixed an exam/result identity before later dispute handling without revealing the seed or draw. Carbon therefore commits to hidden evidence rather than serializing hidden evidence into public logs.

## Why reproducibility has three layers
Exact floating-point bit identity across arbitrary accelerators is neither necessary nor generally defensible. Carbon instead requires exact identity for discrete/configuration artifacts, measured numerical reproducibility inside a qualified backend cohort, and stable scientific decisions within the approved uncertainty band.

This avoids weakening scientific gates to accommodate uncontrolled hardware while also avoiding a false universal bitwise-determinism promise.

## Why P0 uses a narrow qualified backend cohort
The first trust proof benefits more from a measured, reproducible execution environment than from broad hardware portability. Carbon can add backends and accelerator cohorts later as separate qualification events. P0 therefore targets a JAX-first qualified path and treats other backend adapters as non-emission-capable until separately qualified.

## Why infrastructure failures are type-separated from science
A solver crash, node failure, OOM policy kill, queue loss, or reference-service exception says nothing about whether the submitted strategy violates physics. Encoding infrastructure outcomes in distinct result types prevents accidental conversion of operational failures into authoritative scientific zeros.

## Why scientific results, network policy, and settlement are separate
Bittensor is Carbon's economic coordination layer, not the definition of physical truth. The durable scientific record should survive changes in weight-setting mechanics, validator incentives, or even future network implementations.

Carbon therefore records the scientific result first, then creates a
Carbon-owned policy event, then a nominal typed chain intent, and only then
publishes through a narrow adapter. During C2, Challenge-local result/rank may
decide whether a new eligible test leader exists; score magnitude never sets
weight magnitude. Mainnet scientific-economic authority follows fresh
frontier promotion → `FrontierAdvanceEvent` → `SettlementObligation` →
treasury settlement. Economic consensus cannot silently rewrite historical
scientific evidence.

## Why validator free-riding is an explicit threat
Independent scientific evaluation is expensive. If a validator can cheaply follow public consensus instead of executing the exam, honest evaluation becomes a public-good problem. Carbon should design for a nonzero copier/free-rider population rather than assuming perfect validator participation.

The correct response is not to label correlated weights as cheating. Honest validators share an exam and should correlate. Carbon instead measures whether enough real execution evidence exists, whether honest evaluator economics remain sustainable, and whether a copier can claim Carbon-controlled validator-service compensation without valid assignment, execution, or audit evidence. Treasury routing therefore needs separately evidenced `ValidatorAssignment`, `ValidatorExecutionReceipt`, `ValidatorAuditReceipt`, `ValidatorServiceObligation`, and `ValidatorServiceSettlement` policies.

## Why probabilistic re-execution audits
Re-running every expensive evaluation on every validator wastes compute. Running none provides weak execution assurance. Random post-commit re-execution creates a middle ground: validators cannot know which evaluations will be checked when they sign the first receipt, while Carbon spends duplicate compute only on a sampled subset.

Disagreement triggers contest/retry/quarantine, not an automatic miner physics zero.

## Why the evidence ledger is append-only
Scientific provenance loses value if historical records can be silently edited. An append-only receipt commitment log provides tamper evidence while keeping bulk transcripts and tensors off-chain. Signed Merkle/MMR checkpoints provide durable ordering and integrity without making the blockchain a data warehouse.

## Why Bittensor is behind an adapter
Scientific challenge logic should not be coupled to SDK-specific metagraph, commit/reveal, or extrinsic objects. A narrow chain adapter protects Carbon's scientific core from network API churn, improves testing, and preserves the option to use the evidence protocol in other deployment contexts.

The adapter consumes only the nominal intent appropriate to its registered
mode: `StructuralLocalnetWeightIntent`, `TestnetWinnerWeightIntent`, or
`TreasuryRoutingWeightIntent`. It rejects raw score dictionaries, scientific
result objects, hidden measurements, payout values, and caller-selected
authority Booleans. A structural test cannot become testnet or production
authority by configuration.

## Why Bittensor wraps the Miner MCP
Bittensor supplies hotkey/UID identity, discovery, network presence, and the
authenticated application-transport context. Carbon's Miner MCP owns the
practice, research, submit, and result semantics. Keeping those roles separate
lets Carbon test and reuse the application protocol without making SDK objects
the application ontology, and it preserves the rule that the official exam is
not miner-facing.

## Why the direct-weight path is testnet-only
Carbon must prove real chain weight setting before claiming network
integration, but that proof arrives before frontier and settlement machinery.
C2 therefore uses an expiring winner-triggered event and intent marked
`TESTNET_ONLY`, `NON_LIVE`, `NON_SETTLING`, and
`NOT_FRONTIER_QUALIFIED`. It demonstrates authenticated candidate-to-chain
wiring; it does not prove Wave-D science or create lasting economic merit.

## Why no winner is an explicit non-paying state
Omitting a weight update can leave the previous participant economically
active. Expiry, contest, indeterminacy, validator disagreement, unavailable
candidate, identity mismatch, reference/infrastructure failure, supersession,
or bad chain binding must instead route to an approved non-paying sink while
participant miners are zero. The policy is structural; the exact sink
identity/custody remains a network/economic/security decision.

## Why mainnet routes through treasury
Direct scientific-winner weights collapse scientific comparison, normalized
chain allocation, custody, and payout into one mechanism and cannot represent
per-Challenge obligations cleanly. Treasury routing keeps the production
chain vector free of raw scores, hidden measurements, thresholds, and payout
amounts. A frozen scientific event creates an immutable settlement obligation;
custody and payout execution can retry, fail, or be audited without changing
the scientific record.

## Why CI is constitutional
Carbon is agent-assisted software with security- and science-critical invariants. Ordinary unit tests are not sufficient if a future change can make the suite green by weakening the invariant itself. Dedicated trust-boundary tests make no-seed-leakage, mock isolation, score semantics, stub non-emission, infra/science separation, and qualification gating mechanically difficult to regress.

## Why industry V&V/VVUQ terminology matters
Carbon should not invent a private language for credibility if established engineering reviewers already use concepts such as context of use, verification, validation, uncertainty, configuration management, and evidence lineage. Mapping Carbon dossiers onto that vocabulary improves legibility and commercial trust while keeping Carbon's actual qualification decisions challenge-specific.

A terminology crosswalk is not the same as claiming compliance with a standard.

## Why P0 is proof-ready but proof-free
Proving neural-operator training is not a sensible P0 dependency. Stable canonical commitments and receipt schemas preserve future cryptographic option value at low current cost. If narrow proofs over committed predictions or gate verdicts become commercially useful later, the evidence objects already exist.

## Why adaptive science is not adaptive grading
Landscape should discover weaknesses and propose better future exams. It must not silently vary the mandatory score-bearing exam per miner. Changes become supplemental probes or new pack versions.

## Why competition and product qualification are separate
Search needs throughput; product credibility needs deep job-shaped testing. The lean exam finds promising methods. Product Battery determines whether an artifact is fit to sell.

## Why winners may become candidates
Carbon pays miners to discover useful methods. A winner should be eligible as a candidate. What is prohibited is qualification by rank/checkpoint rather than fresh independent execution.

## Why Landscape remains epistemically subordinate
Causal/symbolic models are useful hypotheses fitted from observational competition data. They can guide decisions but cannot become hard-gate truth or waive fresh execution.

## Why Carbon can be an evidence rail rather than only a CAE platform
The highest-value durable asset is the verified lineage of which methods, models, and operating envelopes survive independent scientific exams. That evidence can be consumed by Carbon products or by external engineering-AI platforms. Keeping the evidence/provenance layer neutral expands possible roles for outside platforms: competitor, miner, integrator, customer, or qualified-evidence consumer.

## Why P0 is narrow
One honest end-to-end challenge proves more than many partial PDE modules. P0 should expose integration, security, scoring, disclosure, determinism, qualification, evidence, and Bittensor wiring before breadth.

## Why agents do not make science
Agents can implement interfaces, harnesses, tests, and approved formulas. Production thresholds, envelopes, solver credibility, reproducibility tolerances, and launch judgment require designated human authority.

## Why KEEP → WRAP → REPAIR → REPLACE
The reconciled design supersedes historical scaffolding, but useful code should not be discarded reflexively. Preserve it when it can satisfy current specs without weakening invariants.
