# Carbon Miner Research Interface and Prior Pack Contract

**Status:** OWNER-REVIEW CONTRACT CANDIDATE. This file specifies proposed Wave B behavior. It does not change the ratified Wave A MCP, authorize Wave B implementation, publish a production prior, or qualify a public practice service.
**Version:** 0.3
**Applies with:** `Miner_MCP.md`, `Physics_Intelligence_System.md`, `Landscape_Agent.md`, `Build_Out.md`, `Build_Out_Constitutional_Overlay.md`, `Launch_Bar.md`, and `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`
**Sequencing:** `.agent/WAVE_B.md`

---

# 1. Executive decision

Carbon should give mining agents a complete public research instrument, not a partial copy of the protected judge.

The agent must be able to discover the legal search space, construct an executable Strategy, estimate whether it fits the resource contract, reconstruct it, run honest practice experiments, compare interventions on common fresh cases, and submit the frozen Strategy for official evaluation. Carbon should withhold only information that would let the public loop substitute for the protected exam or reconstruct individual protected evidence.

The target behavior is:

> **An agent that optimizes Carbon's public research loop should be pushed toward transferable physical behavior. An agent should not be able to win by learning protected case realizations, hidden mixture weights, exact decision margins, or validator quirks.**

This distinction matters. Low practice-to-official correlation is not itself a safety goal. If a model learns better physics, good performance should transfer. The prohibited shortcut is incremental knowledge of the protected realization after controlling for performance on evaluator-held shadow cases sampled from the declared public distribution and unavailable to the attacking agent.

```text
public task + legal construction space + evidence-labeled priors
                              ↓
                    miner-owned hypothesis
                              ↓
             deterministic semantic compilation
                              ↓
          reconstruction rehearsal + honest practice
                              ↓
          paired intervention evidence on fresh cases
                              ↓
                 frozen official submission
                              ↓
 producer-independent reconstruction + protected fresh exam
```

---

# 2. The information boundary

## 2.1 Publish what an agent needs to do science

| Public object | What it tells the agent | Why it is public |
|---|---|---|
| `ChallengeInteractionManifest` | Exact public contract identities and available research capabilities | The agent cannot act reproducibly without it |
| `PhysicalSystemSpec` and `CandidateOutputContract` references | The physical job and required candidate behavior | The target must be understood |
| `InstanceDistributionContract` and public `SamplingPlan` references | The registered population, support, strata, and sampling law, excluding realized draws | Optimizing the intended distribution is desired behavior |
| `TrainingSupportContract` | The public support and closed `R_strategy` policy family from which training draws may be generated | Training-data search must be useful, reconstructable, and unable to rewrite the official exam |
| `MeasurementContract` and public score/evidence-use policy references | Exact observables, gates, thresholds, transforms, weights, and decision rule | The objective must be transparent and auditable |
| `CandidateAssemblyContract` | How a registered candidate family is assembled | Reconstruction cannot depend on undocumented knowledge |
| `ParameterCatalog` | Legal levers, types, units, domains, dependencies, and resource classes | A Strategy must be executable rather than inert JSON |
| compiler identity and `ResolvedConstructionPlan` | The exact meaning Carbon assigned to a Strategy | Silent interpretation is unacceptable |
| `PracticeScopeStatement` and practice-pack identities | What public practice does and does not cover | Practice must be scientifically honest in its declared scope |
| `PriorPack` | Evidence-labeled hypotheses about interventions worth testing | Agents should benefit from accumulated knowledge |
| public scaffolds and method resources | Runnable cold starts and reviewed explanations | Agents should not need private repository archaeology |
| resource forecast model identity | Whether a construction is likely to fit declared resources | Avoid preventable failed experiments |

## 2.2 Protect what would turn the interface into an exam oracle

Carbon does not disclose:

- official seeds, draw identities, protected cases, or reversible case identifiers;
- realized stratum counts, realized stress composition, or validator routing signals; the registered population and sampling law remain public;
- reference outputs for protected cases;
- candidate-specific per-case gate margins, live uncertainty intervals, or unresolved near-frontier ordering;
- per-case or worst-case official measurements;
- current champion recipes, multi-lever combinations, weights, or checkpoints;
- individual private ExperimentRecords, card identities, hotkeys, or contributor identities;
- unlagged private outcomes or small-cell statistics that support membership inference;
- dynamic answers computed from the private evidence store at request time.

Carbon never publishes false physics as an anti-gaming measure. When safe, useful guidance cannot be released, the system publishes `INSUFFICIENT_EVIDENCE` or `NOT_INCLUDED`.

---

# 3. Separate facts, hypotheses, and measurements

The interface uses different objects for different epistemic jobs.

| Object | Role | Candidate-specific | May use protected evidence | Scientific authority |
|---|---|---:|---:|---:|
| `ChallengeInteractionManifest` | Facts about the public research contract | No | No | Contract authority only |
| `ParameterCatalog` | Facts about executable Strategy levers | No | No | Construction authority only |
| `PriorPack` | Curated or learned hypotheses | No | Only through an offline approved publisher | Decision support only |
| `PublishedScaffold` | One executable public baseline | No | No champion inversion | None |
| `PracticeRunOutcome` | Measurements from a declared public practice scope | Yes | No | Non-authoritative practice evidence |
| `EvaluationCard` | Budgeted projection of one protected official result | Yes | Yes, through the official evaluator | Exact registered projection only |

Challenge facts do not belong in a prior. A prior does not define parameter semantics. Practice evidence does not become an official score. Keeping these objects separate makes the system understandable and prevents accidental authority transfer.

---

# 4. ChallengeInteractionManifest

The manifest is the single public entry point for an autonomous research agent. It is immutable, content-addressed, Challenge-bound, and historically retrievable.

It must reference, at minimum:

```text
ChallengeKey
PhysicalSystemSpecRef
CandidateOutputContractRef
InstanceDistributionContractRef
SamplingPlanRef
TrainingSupportContractRef
MeasurementContractRef
PublicScorePolicyRef
CandidateAssemblyContractRef
StrategySchemaRef
ParameterCatalogRef
compiler identity
public method/resource codebook refs
PracticeScopeStatementRef
practice-pack refs
public scaffold catalog ref
PriorChannelRef and PriorPolicyBundleRef, or explicit no-prior state
resource-policy ref
disclosure-policy ref
available capability set
```

The manifest contains no protected exam-pack identity, protected data identity, official seed material, private reference location, fee secret, or validator topology. `PublicScorePolicyRef` exposes the registered objective and decision rule, never realized cases, references, or live candidate margins.

An autoresearch agent should be able to start from this manifest without undocumented repository knowledge. A research task additionally pins the exact `PriorIndexSnapshotRef` and `PriorPackRef` it consumed; changing the active prior does not silently change an already-started run or the compiler semantics.

---

# 5. Executable Strategy semantics

## 5.1 Current gap

The ratified Strategy v1 envelope has four top-level fields and deliberately treats `parameters` as inert JSON. This is a sound Wave A boundary, but it does not tell a validator how to construct a candidate. A practice runner built directly on that envelope would either ignore parameters or introduce undocumented interpretation.

Wave B closes the gap without accepting arbitrary code.

```text
TrainingStrategy v1
        +
Challenge-bound ParameterCatalog
        +
CandidateAssemblyContract
        +
exact compiler identity
        ↓
ResolvedConstructionPlan
```

## 5.2 ParameterCatalog

`TrainingSupportContract` is an immutable Challenge-owned contract defining the
training support, permitted source/generator material, physical and
representation invariants, data rights, and the closed grammar of allowed
training sampling, curriculum, and augmentation policies. The catalog exposes
only bounded levers inside that grammar.

The compiler materializes those selected levers into one canonical
`ResolvedTrainingSamplingPolicy`. Carbon denotes that fully instantiated policy
by `R_strategy`. `TrainingSamplingPolicyRef` is the content-addressed reference
to those exact canonical bytes. It is not a free-form function, a template
name, a seed, or an official sampling law. The resolved object binds its
`TrainingSupportContractRef`, catalog surfaces and values, executable semantics,
and the registered abstract training-randomness purposes and role-key labels.
It binds no entropy domain or seed material. Each nominal execution context
selects its own authorized entropy domain and derives the actual train seeds
and draws beneath those purposes.

Every executable lever has a stable public `surface_id`. A catalog entry declares:

```text
surface_id
semantic owner / consumer
value type
unit, where applicable
allowed values or public bounded domain
required or optional status
explicit default, if a default is permitted
compatibility and dependency rules
policy-agnostic static resource dimensions, contributions, and impact tags
public outcome-family tags
optional structural-component / physical-assumption / claimed-behavior refs
implementation/build pins and fixed-versus-trainable boundary, when applicable
applicability, limitation, and public falsification refs, when applicable
deprecation / supersession state
```

The catalog is bound to exact Challenge, candidate-assembly, backbone, compiler, and environment identities where those identities affect meaning.

When the Challenge owns the outer assembly workflow, the catalog may expose a
closed set of versioned, reconstructible structure-preserving components or
assembly choices. Examples include conservative or monotone operators,
positive-semidefinite dissipation, divergence-free or positivity-preserving
parameterizations, equivariant layers, symplectic integrators, and Hamiltonian
or dissipative blocks when the registered physics supports them. Each entry
states the physical assumption, exact executable semantics, fixed and
trainable boundary, applicability, known limitations, resource impact, and
public falsification checks.

These entries are optional construction levers, not scientific certificates.
A component name, implementation pin, claimed invariant, or passing component
unit test cannot satisfy a mandatory gate or enter the official score. Carbon
still reconstructs the complete candidate and measures its output on fresh
cases and hidden stress evidence under the same Challenge contracts used for
all architectures.

The first catalog remains declarative. It may include a registered hybrid
neural-operator backbone or learned-component slot only when Carbon owns the
outer assembly workflow. It may also expose a closed set of Challenge-bounded
training sampling, curriculum, and augmentation levers. Those levers select a
`TrainingSamplingPolicyRef` for the resolved `R_strategy` inside the Challenge-owned
`TrainingSupportContract`; the nominal execution context derives the actual
training draws in its own role-separated seed domain. The catalog does not authorize participant-defined
composition graphs, imports, executable code, arbitrary dependencies, file
paths or URIs, network access, deserialization payloads, raw or custom dataset
uploads, miner-selected seeds, official `P`, `Q`, or `w` controls, evaluation or
stress selection, references, gates, or scorer controls.

## 5.3 StrategyCompiler

The compiler returns either one canonical `ResolvedConstructionPlan` or one typed rejection. It must:

- reject unknown and unused parameters;
- reject incompatible combinations;
- reject implicit coercion and silent clamping;
- make every applied default explicit in the resolved plan;
- bind the exact catalog, assembly contract, compiler, dependency, and environment identities;
- resolve any registered training-data levers to one exact canonical
  `ResolvedTrainingSamplingPolicy` / `TrainingSamplingPolicyRef` pair and keep
  it semantically disjoint from the target population
  `P`, official proposal/SamplingPlan `Q`, and evidence weights `w`;
- compute a canonical plan hash;
- emit exact policy-agnostic static resource dimensions, requirements, and
  impact tags without deciding policy admissibility or guessing execution
  success;
- use the same semantic identity for practice and official reconstruction.

An accepted Strategy cannot contain a parameter that the construction backend silently ignores. That invariant is central to both miner usefulness and validator reconstruction.

## 5.4 ResolvedConstructionPlan

The plan is private-to-requester during research and becomes part of the official reconstruction evidence after submission. It contains normalized, fully resolved construction instructions expressed only in the registered catalog vocabulary. When permitted, it binds the exact canonical `ResolvedTrainingSamplingPolicy` denoted `R_strategy` and its `TrainingSamplingPolicyRef`; the execution service derives train seeds and draws rather than accepting them from the miner. It also carries immutable policy-agnostic static resource requirements and impact tags. B-02C evaluates those requirements against a separate `ResearchResourcePolicy` and cannot mutate the plan or compiler semantics. The plan contains no official randomness or evaluation controls.

The plan is not a candidate artifact, score, or proof of successful reconstruction.

---

# 6. Practice as an honest non-authoritative experiment

## 6.1 Practice objective

Practice should answer questions such as:

- Does this Strategy reconstruct under the public contract?
- Does the resulting model satisfy public physical checks?
- Did intervention B improve over A on common fresh public cases?
- Is the result stable enough to justify an official exam?
- What resources did reconstruction actually consume?

Practice does not predict an official score, rank, gate result, winner probability, weight, emission, or settlement.

## 6.2 PracticeScopeStatement

Every practice pack declares its relationship to the physical task and its intentional limitations. A practice scope may reduce:

- resolution;
- sample count;
- training duration;
- reference depth;
- regime breadth;
- stress breadth;
- audit strata;
- rollout horizon.

The statement identifies those omissions using public categories. It does not disclose the protected exam's realized mixture or cases.

Practice must use honest reference data inside its stated scope. Memorizing a static case list should fail because practice uses fresh role-separated draws. Learning the declared physical distribution should transfer.

## 6.3 Nominal separation

Practice uses nominal objects such as:

```text
MockExecutionRequest
MockRunOutcome
MockTrainEvalService
PracticeMeasurementPack
```

These objects cannot enter A5 scoring, A6 card publication, A7 official submission lifecycle, official leaderboard publication, frontier promotion, weights, emissions, or settlement. No caller-selected `mock | official` mode exists.

A `PracticeMeasurementPack` may reuse a public qualified measurement implementation when rights and identities permit, but it has its own non-authoritative configuration. It cannot import official thresholds, masquerade as a Score Pack, or call A5.

## 6.4 Paired comparison

The primary scientific practice primitive is a paired comparison on common fresh cases. It reports a bounded aggregate difference and uncertainty under the public practice pack. Common cases remove avoidable sampling noise and give agents a much more useful intervention signal than two unrelated scalar runs.

The practice service may also support single-run reconstruction rehearsal and measured resource receipts. It must not expose per-case data when the registered disclosure policy excludes it.

## 6.5 Local-first topology

Wave B should provide a local, reproducible Miner Lab using the same public catalog and compiler identities. A local-only agent adapter exposes the exact v2 discovery and serialization contract without a network listener or credentials; it may be a stdio MCP or equivalent bounded CLI. A bounded in-process practice referee may establish parity and resource receipts. Authenticated remote transport belongs to Wave C.

The local topology has two distinct service identities: the unchanged
`carbon_protocol_v1` service owns official submission/result operations, and
`carbon_research_v2` owns the research operations in §8. Duplicate operation
names are namespace-qualified; no merged unqualified alias exists. B-E4 agents
connect to both identities explicitly. The v2 adapter never wraps, mirrors, or
reimplements the official store or lifecycle.

Local agents keep private sweeps and failed experiments locally. Carbon does not require miners to upload their entire research history.

---

# 7. ResearchTask, ExperimentRecord, and receipts

## 7.1 ResearchTask

A research task is asynchronous and idempotent. It binds:

```text
task identity and requester binding
task kind
ChallengeInteractionManifestRef
Strategy and StrategyHash
ResolvedConstructionPlanRef
optional parent Strategy / comparison arm refs
public practice and resource-policy refs
PriorPackRef used by the agent, if any
requested public resource class
```

Initial task kinds are:

- `RECONSTRUCTION_REHEARSAL`;
- `PRACTICE_RUN`;
- `PAIRED_PRACTICE_COMPARE`;
- `RESOURCE_CALIBRATION`.

The closed task-state machine is:

```text
QUEUED -> RUNNING -> SUCCEEDED | FAILED
   |         |
   |         -> CANCEL_REQUESTED -> CANCELLED | SUCCEEDED | FAILED
   -> CANCELLED
```

`CANCEL_REQUESTED` is an operational state, not a scientific outcome. A queued task cancels immediately. A running task may cross its declared non-cancellable commit point before the cancellation is observed; in that race the actual terminal state wins and is reported. A terminal task never reopens.

Idempotency is scoped to `(requester_binding, task_kind, client_idempotency_key)`. Reuse with the same canonical request bytes returns the same task. Reuse with different canonical request bytes returns `IDEMPOTENCY_CONFLICT`. The provider owns bounded retries only for typed infrastructure failures and records every attempt under the same task; it does not retry strategy, reconstruction, reference, or measurement outcomes as though they were infrastructure. Every terminal state has a bounded receipt. Poll throttling is operational policy and cannot alter scientific evidence.

## 7.2 ExperimentRecord

The private ExperimentRecord preserves the intervention-outcome evidence required for reproducibility and later intelligence. It records independently computed plan differences rather than trusting a miner's description of what changed.

It includes exact public contract identities, task lineage, execution identity, evidence class, typed failure class, resource observations, aggregate practice outcomes, and retention/reuse scope. Protected seeds and case identities remain private and are never copied into public prior artifacts.

## 7.3 ResearchReceipt

The miner-facing receipt is a bounded positive projection. It reports:

- task and contract identities;
- lifecycle status;
- evidence class;
- typed strategy, reconstruction, reference, or infrastructure failure category;
- public aggregate practice findings allowed by policy;
- observed resource interval or receipt;
- reproducibility and limitations statements;
- no official scientific or economic entitlement.

Infrastructure failure never becomes negative scientific evidence.

---

# 8. Estimation and measurement are separate evidence classes

The current Wave A `estimate` operation remains frozen as structural alignment with a public v1 prior. Wave B must not silently change that meaning.

## 8.1 Versioned service migration

Wave B should add a nominal in-process `ResearchMcpService` with schema version
`"2.0"`. The current `McpService`, its schema `"1.0"`, seven tools, types, and
errors remain unchanged. Version selection occurs outside the v1 call envelope;
v1 gains no negotiation field or alias.

The proposed exact v2 operation vocabulary is:

```text
get_challenge_info
get_interaction_manifest
get_prior
get_mock_scaffold
dry_validate
compile_strategy
inspect_prior_alignment
inspect_resources
forecast_resources
start_research_task
get_research_result
cancel_research_task
```

`get_prior` returns PriorPack v2 on the v2 service. The existing v1 operation
and provider semantics remain exactly frozen; Carbon does not install a
production v2-backed v1 provider. `start_research_task` carries the closed task kind, so separate
`light_train` and `light_compare` aliases are not added. The task result
carries its evidence class and authority ceiling. Agents and clients call the
separately namespaced, unchanged Wave A v1 service for official submission and
result retrieval. The v2 service neither exposes nor delegates those
operations and creates no second official lifecycle or store. Network transport,
authentication, execution quoting, and remote process hosting remain Wave C.

All v2 requests and results require exact nominal schemas, canonical bytes,
resource bounds, error precedence, and safe error mappings before
implementation. Architecture ratification does not substitute for that wire
contract.

B-07S owns the exact protocol specification. B-07A implements the shared
wire-visible nominal refs, requests, results, resource envelopes, errors, and
service primitives from that ratified specification. Domain tickets consume
those common primitives and own their validation, providers, stores, and
execution semantics; they do not redefine the wire types. B-07G owns only the
final in-process service composition, dispatch, and cross-operation
conformance.

| v2 operation | Domain implementation authority | B-07G integration duty |
|---|---|---|
| `get_challenge_info`, `get_interaction_manifest` | B-07A | Dispatch the manifest/discovery provider |
| `get_prior`, `inspect_prior_alignment` | B-07D3 | Dispatch the exact provider/alignment implementation |
| `get_mock_scaffold` | B-07C | Dispatch the scaffold provider |
| `dry_validate` | A2 validation semantics | Adapt and dispatch without reinterpreting A2 |
| `compile_strategy` | B-02B | Dispatch the canonical compiler |
| `inspect_resources`, `forecast_resources` | B-07E | Dispatch static analysis and calibrated-forecast seams |
| `start_research_task`, `get_research_result`, `cancel_research_task` | B-07B lifecycle and records; B-07C practice executor for practice task kinds | Dispatch one lifecycle and inject the registered executor |

No row grants v2 official submission, result, score, or store authority.

`ResearchResourcePolicyRef` binds the immutable domain contract produced before
manifest, practice, or forecasting implementation. That contract defines
resource classes, exact static construction dimensions, declared ceilings,
enforcement and kill semantics, and observed receipt fields. It does not
contain calibrated forecast parameters, a price, a quota, or authority to
execute. `inspect_resources` and `forecast_resources` consume this policy; they
do not define it.

The future research interface separates:

| Operation | Output | Authority |
|---|---|---|
| `inspect_prior_alignment` | Applicable public prior item IDs | Deterministic public matching only |
| `inspect_resources` | Exact plan-derived dimensions and declared constraints | Static exact analysis only |
| `forecast_resources` | Non-binding runtime, memory, storage, and reconstruction-risk intervals | Calibrated forecast with model identity and support status |
| `start_research_task` with practice task kind | Measured public-practice evidence | Non-authoritative scientific practice |

The future Wave C `quote_execution` operation is a separate binding operational/economic contract. It is not implemented or implied by a Wave B forecast.

A forecast declares its model version, calibration window, applicable hardware/resource class, uncertainty, and support state. Unsupported input returns `UNRESOLVED`.

No estimation operation predicts official quality, official score, rank, gate outcome, frontier status, weight, emission, or settlement.

## 8.2 Resource staging cannot become scientific authority

The research resource policy and its inspection or forecast operations may
support a later `ReconstructionEvidencePolicy`, but they do not define or
satisfy scientific evidence. A future official policy may separate:

1. deterministic schema, dependency, hermeticity, and static resource checks;
2. the Challenge-registered complete producer-independent base reconstruction
   evidence, comprising one or more builds as required by the construction
   family, used for ordinary scientific scoring or nomination;
3. separately realized, producer-independent reconstruction replicates and
   fresh common cases required for a frontier-promotion claim; and
4. random repeat audits used to estimate missed instability.

A frozen reconstructed artifact may be reused across the authorized cases in
its evaluation window; reconstruction is not repeated once per case.
Registered pairing or common random numbers are permitted, but shared data,
backbone, seed-role, hardware, and implementation dependence remains modeled.
Before complete base evidence exists, a quality forecast, partial build,
resource estimate, proxy, or screen may schedule work only. It cannot
permanently deny base evidence on predicted quality and an uncompleted path
returns typed `EVIDENCE_DEFERRED`, never a scientific outcome. After base
evidence, official evidence may stop sequentially only at coverage-qualified
decision boundaries. A separate heuristic futility stop may conserve resources
only by returning `EVIDENCE_DEFERRED` and must be prospective and audited for
false elimination. An exhausted scientific evidence budget returns
`INDETERMINATE` with reason `INSUFFICIENT_EVIDENCE`.

B-05 owns the exact scientific policy and its Score Pack/UncertaintyPolicy
binding. B-02C owns resource ceilings, enforcement, capacity/funding seams, and
factual receipts only. B-E1 owns the fixture coverage, stopping, and false-
elimination harness. None of those owners may reinterpret resource estimates
as scientific evidence.

---

# 9. PriorPack v2

## 9.1 Purpose

A prior is a compact set of evidence-labeled hypotheses about which public interventions are worth testing. It should reduce wasted search while preserving uncertainty and search diversity.

The design objective is:

```text
maximize prospective held-out physics progress per unit research compute
subject to:
  equal public access
  calibrated epistemic claims
  a registered disclosure policy
  a human-approved search-diversity metric and floor
  no protected-realization oracle
```

API usage and prior-following are not success metrics.

## 9.2 PriorPackRef and pack identity

The canonical `PriorPack` bytes bind:

```text
ChallengeKey
prior_id and prior_version
canonicalization_id
publication_class
evidence_cutoff_epoch
publication_epoch
activation_epoch
ChallengeInteractionManifestRef
ParameterCatalogRef
PriorPolicyBundleRef
builder version
```

The canonical pack bytes do not contain their own hash or `PriorPackRef`.
`PriorPackRef` binds the canonicalization and version identity plus
`content_hash = SHA-256(canonical PriorPack bytes)`. The content hash is outside
the hashed preimage; self-referential pack identities are invalid.

`PriorPolicyBundleRef` pins the eligibility, feature-extraction, public-estimand,
aggregation, band-definition, epistemic-promotion, coarsening/disclosure,
rights, release-cadence, and gauntlet policies. Pack meanings cannot drift under
unchanged identities.

All packs are immutable and content-addressed within their authorized stores.
Externally active public packs are historically retrievable and published on
fixed epochs. A stable `PriorChannelRef` identifies the Challenge's public
channel. An immutable `PriorIndexSnapshotRef` records which exact pack was
active, superseded, or withdrawn at one atomic activation epoch without
mutating any pack. Wave B provides canonical content-addressed records and a
test-only signer seam; production algorithms, keys, registry, rotation,
revocation, and custody belong to a later security/network contract.

Publication references form an acyclic chain:

```text
PreviousIndexSnapshotRef
        ↓
PriorPublicationReceipt
        ↓
NewIndexSnapshot
```

The receipt pins the exact candidate hash, policy bundle, gauntlet evidence,
owner approvals, disclosure-ledger expected and committed states, activation
epoch, previous index snapshot, and proposed transition digest. It does not
reference the resulting snapshot. The new index snapshot binds the receipt.

`get_prior` accepts either `EXACT(PriorPackRef)` or
`ACTIVE(PriorChannelRef)`. Both public selectors enforce publication class,
exact-hash approval, and withdrawal state. `ACTIVE` atomically reads one index
snapshot and returns its exact snapshot ref, publication receipt ref, pack ref,
and canonical bytes. `EXACT` returns canonical bytes for an approved active or
superseded `BOOTSTRAP_PUBLIC`/`LEARNED_PUBLIC` pack. A withdrawn pack returns
only its hash-bound audit status and public reason class; its bytes remain in
the private audit store. Withdrawal stops Carbon from newly serving the bytes
but cannot make previously retrieved public copies secret or revoke their
historical receipt. `TEST_ONLY` and unapproved bytes are available only
through a nominal private test adapter. There is no unversioned implicit
`latest`. Every research task pins the exact returned pack ref.

The Wave B gauntlet constructs the ordinary `carbon_research_v2` protocol with
a nominal `FixtureResearchContext` and an injected `TestOnlyPriorProvider`.
That structurally private, local-only service may satisfy an exact-ref
`get_prior` request for a structurally approved fixture `TEST_ONLY` pack and
must advertise the explicit `TEST_ONLY_FIXTURE_PRIOR` capability. The exact
result binds its `TestOnlyPriorApprovalReceiptRef`. The returned pack and every
dependent receipt retain both `TEST_ONLY` and `NOT_UTILITY_QUALIFIED` ceilings
permanently. A passing B-E4 creates separate gauntlet evidence and may qualify
only the bounded Wave B mechanism; it never mutates or reclassifies the fixture
pack. An external/public research context cannot be constructed
with that provider and rejects the same pack. No caller-selected mode,
alternate request schema, direct internal API, or v1 projection is used. B-07S
owns the exact nominal context/provider, result, and capability types; B-07D3
owns their enforcement.

Every requester receives identical bytes for the same pack reference. The provider performs no server-side personalization, arbitrary private query, LLM answer generation, or paid informational upgrade. Agents personalize locally using their private research records.

For any externally active pack, `evidence_cutoff_epoch + minimum_lag` must
precede `activation_epoch`. Evidence created during an activation window cannot
affect the pack consumed in that same window. Exact bytes are stored before the
atomic index activation.

## 9.3 Publication classes

| Class | Permitted source | Wave B behavior |
|---|---|---|
| `TEST_ONLY` | Fixtures and synthetic records | Implementable and testable; mechanically not public learned guidance |
| `BOOTSTRAP_PUBLIC` | Human-reviewed public science and public method resources; actionable guidance must be grounded in cited public evidence | Schemas, source-eligibility validators, and negative activation seams only; no Wave B bootstrap builder or activation |
| `LEARNED_PUBLIC` | Eligible qualified Carbon aggregate evidence | Not activatable from Wave B fixtures; requires Launch Bar, publisher qualification, rights, and security approval |

Practice evidence remains `PRACTICE_NON_AUTHORITATIVE`. It may support public falsification resources, but it cannot be presented as qualified official Carbon evidence.

The immutable origin-to-class ceiling is:

| Publication class | Allowed item origins |
|---|---|
| `TEST_ONLY` | `synthetic_test_fixture` only |
| `BOOTSTRAP_PUBLIC` | `curated_public_science` only |
| `LEARNED_PUBLIC` | `qualified_official_aggregate` and optionally `curated_public_science`, with every item retaining its own origin and epistemic label |

The policy bundle may narrow this matrix but cannot expand it. Pack class never
upgrades an item's origin or epistemic status.

## 9.4 PriorGuidanceItem

Initial v2 items each address one public executable lever. Multi-lever combinations are withheld until a recipe-reconstruction gauntlet demonstrates that interactions can be released safely. Every actionable intervention targets one registered `ParameterCatalog.surface_id`. A `PublicMethodArtifact` may supply reviewed citations, formulas, rationale, or falsification resources, but it is non-executable unless and until a catalog surface registers it.

A guidance item may recommend testing a registered structural-component
surface when its evidence and applicability support that hypothesis. The pack
must not suppress material null, negative, mixed, or out-of-scope evidence.
Each actionable positive item carries typed counterevidence and applicability
entries, or an explicit `NONE_FOUND` statement bound to a public search-scope
reference and evidence cutoff. Guidance never upgrades the component's
epistemic status or makes its claimed structure gate evidence.

Each item contains:

```text
item_id
kind: STEER | AVOID | EXPLORE | INSUFFICIENT_EVIDENCE

intervention:
  exact ParameterCatalog.surface_id target
  ENABLE | DISABLE | INCREASE_CATALOG_BAND |
  DECREASE_CATALOG_BAND | SUBSTITUTE | COMPARE
  action-specific baseline_ref / from_ref / to_ref

scope:
  public backbone refs
  public context refs
  public resource-class refs

expected_outcomes:
  public_estimand_ref
  IMPROVE | DEGRADE | MIXED | UNRESOLVED
  optional coarsened effect-magnitude band

evidence:
  evidence_origin
  epistemic_type
  evidence-strength band
  uncertainty band
  stability band
  replication band
  coarse support band
  contributor-diversity band
  selection-bias and caveat codes

counterevidence_and_applicability:
  one or more entries, each containing:
    public_estimand_ref
    NULL | NEGATIVE | MIXED | OUT_OF_SCOPE
    public scope/context refs
    evidence_origin and epistemic_type
    evidence-strength / uncertainty / replication bands
    applicability, limitation, and caveat codes
  OR explicit NONE_FOUND with public search_scope_ref and evidence_cutoff

falsification:
  public practice-test refs
  optional reviewed PublicMethodArtifact refs

provenance:
  aggregate publication/cohort refs only
```

Action semantics are exact. `ENABLE` and `DISABLE` bind a public baseline state.
Band changes bind catalog-defined `from_ref` and `to_ref`; `SUBSTITUTE` binds
exact public alternatives; and `COMPARE` binds an exact public baseline and
intervention. Empty scope lists are invalid. Universal public applicability is
an explicit `ALL_REGISTERED_PUBLIC_CONTEXTS` value. Multiple outcome claims are
separate entries, each with its own estimand and uncertainty.

Counterevidence entries are not alternate secret recommendations. They use the
same public estimand, scope, provenance, coarsening, rights, disclosure, and
canonical-order rules as positive evidence. A publisher must reject an
actionable item when material eligible contrary or out-of-scope evidence is
known but omitted. `NONE_FOUND` means no eligible contrary evidence was found
within the declared public search scope by the cutoff; it is not a claim that
none exists.

Each immutable `public_estimand_ref` defines the comparison/baseline,
population and public scope, directionality, aggregation functional,
measurement unit, independence or resampling unit, and uncertainty method. It
does not reveal the protected exam's realized cases or mixture.

`evidence_origin` is a separate closed enum:

- `synthetic_test_fixture`;
- `curated_public_science`;
- `qualified_official_aggregate`.

The canonical `epistemic_type` values reuse `Physics_Intelligence_System.md`:

- `observed`;
- `predictive`;
- `causal_candidate`;
- `experimentally_supported`.

The policy bundle contains the allowed origin/status matrix and promotion
rules. `synthetic_test_fixture` can only appear in `TEST_ONLY`. Curated public
science receives the status supported by its reviewed study design, not by the
act of curation. Eligible qualified official aggregates default to `observed`;
they may become `predictive` after prospective held-out validation. Practice
evidence is not a `PriorGuidanceItem` evidence origin: a separately labeled
`PRACTICE_NON_AUTHORITATIVE` artifact may appear only as a public falsification
resource and cannot support or promote the item's claim. Official aggregates
cannot become `causal_candidate` without a registered identification
argument, overlap and sensitivity evidence, and explicit selection-bias
limits. `experimentally_supported` requires a registered controlled
intervention or equivalently strong independently reviewed public evidence.
Large effect, repeated publication, or model sophistication cannot upgrade
epistemic status by itself.

Reviewed immutable resources carry papers, formulas, citations, and explanatory prose. The publisher does not generate free text from private evidence. Provenance refs resolve only public aggregate publication/cohort artifacts and can never resolve individual cards, submissions, hotkeys, contributors, lineages, or row-level records.

Items are canonically sorted by public `item_id`. List order carries no
priority, effect, confidence, or internal ranking signal.

## 9.5 What makes a prior useful

The highest-value public content is not a blurred champion recipe. It is:

- which legal lever appears relevant;
- the intervention direction worth testing;
- a coarsened effect-magnitude band when disclosure and support permit it;
- the public context where it may transfer;
- the physical outcome family involved;
- the strength, uncertainty, stability, and replication of the evidence;
- known null, negative, mixed, and conflicting findings;
- an inexpensive public falsification experiment;
- explicit gaps where exploration has information value.

Negative and null evidence can save more compute than a weak winner hint. `EXPLORE` items preserve underexplored plausible regions rather than collapsing the population onto the current fashion.

The intended agent workflow is deliberately local:

1. resolve the manifest, scaffold, catalog, resource policy, and one exact prior pack;
2. filter items by exact applicability and executable support;
3. turn a guidance item into a one-lever hypothesis against its declared baseline;
4. run the cited inexpensive falsification check or a paired common-case practice comparison;
5. update the agent's private local notebook/posterior, including null and
   failed interventions; Carbon's service independently retains its private
   `ExperimentRecord` and returns only the bounded `ResearchReceipt`;
6. allocate part of the remaining budget to `EXPLORE` items or unsupported plausible regions so the prior does not collapse search diversity;
7. freeze and submit only the Strategy chosen by the miner's own accumulated evidence.

Carbon supplies the shared evidence map. It does not choose the miner's next move at request time. That keeps private adaptation and genuine discovery with the miner while letting the ecosystem's reusable scientific lessons compound.

## 9.6 Offline publication pipeline

`get_prior` serves only a prebuilt approved artifact. It never queries the card lake, Landscape, official evaluator, or private ExperimentRecords during a miner request.

A private persistent `PriorDisclosureLedger` is a required publisher input and
output. It records cumulative disclosure by Challenge, channel, policy,
estimand, scope, field combination, cohort, provenance class, and release
history. Publication must atomically authorize and append the proposed release;
an unavailable or conflicting ledger makes publication fail closed. Disclosure
tests operate on joint cells and cross-version differences, not one field at a
time.

### Wave B TEST_ONLY staging gate

Wave B needs fixed prior bytes before B-E4 can measure their utility and
conditional leakage. It therefore uses a deliberately weaker, nominally
separate pre-gauntlet gate that cannot authorize a public pack or a utility
claim:

1. freeze and content-address one fixture `TEST_ONLY` pack;
2. run exact-hash schema, canonicalization, source-eligibility, redaction,
   canary, raw-string, poisoning, duplicate-lineage, joint-cell, and release-
   differencing conformance checks;
3. obtain science, statistics, security, protocol, and rights approval for
   fixture testing only, bound to the exact bytes and expected fixture
   disclosure-ledger state;
4. atomically append the fixture ledger delta and record a
   `TestOnlyPriorApprovalReceipt` in a private immutable approval snapshot.

The receipt and its content-addressed reference are nominally distinct from a
`PriorPublicationReceipt`. They carry `TEST_ONLY / NOT_UTILITY_QUALIFIED`,
permit only exact-ref retrieval through `FixtureResearchContext`, and cannot
enter a public channel, public active index, public or production v1 provider,
external surface, or publication-class promotion. It may be input only to the
private offline compatibility projector in §9.7; that output remains a private
test artifact and is never used by the B-E4 v2-prior arm. B-E4 then pins those exact pack and approval
references for every v2-prior arm run and replicate. A passing B-E4 result
creates separate gauntlet evidence but leaves the pack test-only. A failure or
indeterminate result also blocks Wave B closeout.

### External/public publication gate

Future public construction begins with one nominal source branch:

**`BOOTSTRAP_PUBLIC` branch**

1. freeze an exact, rights-reviewed public corpus of cited science and method
   artifacts;
2. verify provenance, citations, licenses, applicability, and public
   falsification resources;
3. require every actionable guidance item to be grounded in cited public
   evidence and carry only the epistemic status supported by that study design;
   an explicit speculative hypothesis may exist only as a reviewed,
   non-executable `PublicMethodArtifact`, not as evidence for an actionable
   intervention claim;
4. reject private Carbon records, official evaluation aggregates, Strategy or
   contributor lineages, and any claim that curated material is Carbon-learned
   causal evidence.

**`LEARNED_PUBLIC` branch**

1. freeze an exact private evidence snapshot;
2. admit only rights-eligible, full, reconstructed evaluations from the exact
   qualified Challenge and evidence-use identities;
3. exclude fixtures, mocks, partial paths, infrastructure failures,
   stale/superseded evidence, and rights-ineligible records;
4. aggregate reconstruction repeats within Strategy, then within related
   lineages;
5. cap contributor and near-duplicate lineage influence;
6. estimate associations with declared confounders, overlap, heterogeneity,
   and time-stability checks;
7. suppress small, unstable, identifying, or unsupported cells.

The branches then converge without erasing origin:

1. compile findings into the closed public catalog vocabulary while retaining
   each item's exact evidence origin and epistemic type;
2. apply the branch-appropriate deterministic coarsening, disclosure, lag,
   cadence, and bounded-version policy, then calculate the cumulative-
   disclosure ledger delta without committing it;
3. store candidate bytes and run redaction/canary, utility, conditional-
   leakage, poisoning, and version-differencing gauntlets against the exact
   hash; a Wave B test-only approval receipt cannot satisfy this step;
4. obtain science, security, protocol, and rights approvals bound to the exact
   hash, source branch, policy, gauntlet evidence, and expected ledger state;
5. construct the publication receipt against the previous index and proposed
   transition, then in one compare-and-swap transaction reauthorize/append the
   disclosure-ledger delta and activate the new receipt-binding index snapshot.

If the ledger or approval state changes before the final transaction, activation fails and the
candidate must be reauthorized. Candidate storage, approval, or a ledger append
alone never makes a pack active.

Carbon should not rely on informal random perturbation of champion weights. Repeated releases can average that noise away, and arbitrary perturbation damages research utility. Randomized or differential-privacy noise is allowed only under a formal privacy budget and measured utility evidence.

## 9.7 Wave A compatibility

The ratified `PublishedPrior` v1 and its error/provider semantics remain
unchanged. Carbon does not install a production v2-backed v1 provider. PriorPack
v2 is the only future external learned-prior surface.

A private offline compatibility projector may map supported v2 `kind`, action,
and catalog identifiers into the closed v1 directive vocabulary for migration
testing. Unsupported, ambiguous, multi-outcome, or information-losing items are
omitted rather than rewritten into a stronger claim. The resulting
`PublishedPrior` bytes never enter a public v1 provider. A separate internal
`PriorProjectionReceipt` pins the source v2 pack, mapping version, omissions,
and output hash because the frozen v1 type has no fields for that provenance.

The external v2 operation `inspect_prior_alignment` deterministically maps a
Strategy to public item IDs using only the public pack and catalog. It never
reads private outcomes.

---

# 10. Adaptive disclosure and the aligned-cheating test

Carbon evaluates leakage across the full interaction transcript, not one endpoint at a time. The policy covers:

- priors and their version differences;
- practice outcomes;
- EvaluationCards;
- leaderboards;
- diagnostics and errors;
- timing and queue behavior;
- resource forecasts and quotes;
- near-duplicate Strategy lineages;
- related requesters and coordinated batches.

Budgets apply to requester identity and Strategy lineage or near-duplicate cluster. Wave B exercises this boundary only through an injected test-only `DisclosureSubjectResolver` over fixture identities. When lawful linkage is unavailable, the local service provides only requester-local accounting and makes no Sybil-resistance claim. Live cross-hotkey linkage, authentication, privacy/legal basis, false-merge handling, appeal, and enforcement belong to a later Wave C security contract.

The red-team question is conditional:

> After controlling for performance on evaluator-held shadow cases sampled from the declared public distribution and unavailable to the attacking agent, does the interaction transcript provide material incremental ability to infer protected case realizations, hidden stress composition, exact margins, or unresolved near-frontier ordering?

If yes, Carbon reduces granularity, changes cadence, coarsens or withdraws the affected surface, or versions the Challenge prospectively. It does not blame the miner for an exam vulnerability.

---

# 11. Evidence and authority classes

Every result declares one of these non-interchangeable classes:

| Evidence class | Meaning | May enter official score |
|---|---|---:|
| `STRUCTURAL_ONLY` | Validation, compilation, or public prior matching | No |
| `STATIC_EXACT` | Deterministic calculation from public contracts | No |
| `CALIBRATED_RESOURCE_FORECAST` | Non-binding resource prediction with calibration evidence | No |
| `PRACTICE_NON_AUTHORITATIVE` | Measured public-practice result | No |
| `OFFICIAL_EVIDENCE` | Result from the protected registered evaluation path | Only through the registered Score Pack |

No type conversion from a lower class to `OFFICIAL_EVIDENCE` exists.

---

# 12. Qualification gauntlet

## 12.1 Utility experiment

Run representative autoresearch agents under matched time and compute budgets using:

1. no prior;
2. a generic static prior;
3. the Wave A directive projection;
4. PriorPack v2.

The Wave B gauntlet uses a semantically responsive toy physics fixture whose
registered levers measurably change public outcomes. A Strategy-insensitive
stub can test plumbing but cannot establish prior utility.

Measure:

- time and compute to a semantically executable Strategy;
- attempts to first candidate passing the declared non-authoritative practice checks;
- best result on independent held-out physical cases;
- transfer to a shadow generator or reference audit;
- reconstruction success and invalid-run rate;
- diversity of tested interventions;
- a deferred prospective frontier-lift metric to be populated only when later qualified official evidence becomes available.

## 12.2 Leakage and integrity attacks

Attack:

- protected-case and hidden-mixture inference;
- champion and multi-lever recipe reconstruction;
- membership and attribute inference;
- prior release differencing;
- near-duplicate adaptive querying;
- Sybil splitting;
- poisoned, duplicated, and strategically withheld evidence;
- timing and resource side channels;
- raw miner-string or prompt injection into published prior content.

The prior must improve held-out physics search. Improvement that exists only on the current protected exam indicates leakage or Goodhart pressure.

Before B-E4 runs, research, science, statistics, security, and protocol owners
must preregister the exact agent profiles, matched budgets, utility estimand,
practical effect floor, uncertainty-aware decision rule, intervention-diversity
metric and floor, and conditional-leakage limit. Missing values block the
gauntlet; descriptive measurements alone cannot close B-E4 or support a public
utility claim. Later public-release cohort, lag, cadence, granularity, and
activation policy may remain separately unresolved and fail closed.

---

# 13. Decisions fixed by this candidate

Subject to contract ratification, Wave B fixes these architectural choices:

1. Wave B remains declarative and does not accept arbitrary participant code.
2. `ParameterCatalog` plus a deterministic compiler gives Strategy parameters executable meaning.
3. Unknown, ignored, coerced, or silently clamped parameters are rejected.
4. Practice and official execution remain nominally and authoritatively separate.
5. Paired practice comparison uses common fresh public cases.
6. Research tasks are asynchronous, idempotent, lineage-bearing, and receipt-producing.
7. Existing structural `estimate`, static resource inspection, resource forecast, future execution quote, and practice measurement remain separate operations.
8. Carbon publishes no official-score predictor.
9. Priors are immutable Challenge-level artifacts identical for every miner.
10. Prior personalization happens miner-side.
11. Prior guidance references public executable levers and reports evidence quality, uncertainty, context, and limitations.
12. Deterministic coarsening, suppression, lag, and persistent cumulative disclosure accounting precede optional formal privacy noise.
13. Wave B fixtures retain `TEST_ONLY / NOT_UTILITY_QUALIFIED` permanently,
    cannot activate `BOOTSTRAP_PUBLIC` or `LEARNED_PUBLIC` guidance, and no
    v2-backed projection enters the public v1 provider.
14. Prior, practice, scaffold, forecast, novelty, and information value never enter A5 score or ordinary scientific ranking.
15. B-07R ratifies architecture; exact wire types, canonicalization, errors, bounds, and lifecycle semantics require the blocking B-07S contract.
16. Wave B training-data search is limited to registered `R_strategy` sampling,
    curriculum, and augmentation levers inside Challenge-owned support. Raw or
    custom datasets, miner seeds, and all official `P`, `Q`, `w`, stress,
    reference, gate, and scorer controls remain forbidden.
17. A resolved-plan fixture-official adapter may exercise the unchanged v1
    lifecycle only under fixture provenance. It does not convert practice or
    research evidence into official authority and cannot alter the Wave A wire,
    store, lifecycle, or error contract.
18. B-07A implements the ratified shared v2 nominal primitives once; domain
    tickets consume them, and B-07G owns only the final twelve-operation local
    service composition, dispatch, and conformance.
19. Challenge-owned structure-preserving components may be exposed as optional,
    exactly reconstructible catalog surfaces; architecture labels and component
    claims carry no scientific or score authority.
20. Resource checks and staged evidence allocation may conserve compute but
    cannot replace the complete reconstruction and repeat evidence required by
    the registered decision. Unresolved evidence fails closed.

---

# 14. Human inputs and evidence still required

These do not block fixture schemas and contract tests. They fail closed for the first external or learned deployment.

| Input | Owner | Master question | Blocks |
|---|---|---|---|
| First executable lever catalog, units, ranges, hybrid assembly, backbones, training support, and allowed `R_strategy` sampling/curriculum/augmentation policies | SciML + protocol + security | MQ-015, MQ-024 | Real compiler catalog |
| Structural-component assumptions, exact implementations, applicability, limitations, and falsification tests | SciML + protocol + security | MQ-005, MQ-015, MQ-024 | Real structural-component catalog entries or guidance |
| Practice population relationship, honest reference, measurement selection/applicability, intentional omissions, and disclosure | SciML + statistics + security | MQ-002, MQ-003, MQ-004, MQ-005, MQ-016 | External practice release |
| Runtime ceilings and qualified hardware/resource classes | SRE + security | MQ-008, MQ-015 | Real reconstruction |
| ReconstructionEvidencePolicy, family-specific complete-base evidence, artifact-reuse window, scientific stopping/extension, typed deferral, heuristic-futility error control, and stability-audit rate | Statistics + SciML + protocol | MQ-007, MQ-008 | Real scientific ranking and later frontier promotion |
| Validator capacity, reconstruction funding, queueing, and operational evidence budget | SRE + operations + economics | MQ-008, MQ-017 | Operational availability of registered evidence; otherwise `EVIDENCE_DEFERRED` |
| Resource forecast calibration and unsupported-input rule | SRE + statistics | MQ-017 | Calibrated forecast claim |
| Prior estimands, cohort, lag, cadence, coarsening, allowed granularity, and search-diversity metric/floor | Landscape + science + statistics + security | MQ-025, MQ-026 | Any external prior activation |
| Preregistered B-E4 agent profiles, matched budgets, utility estimand/effect floor, uncertainty rule, diversity floor, and conditional-leakage limit on evaluator-held shadow cases | Research + science + statistics + security + protocol | MQ-016, MQ-026 | B-E4 execution and any public prior/agent claim |
| First curated bootstrap content and citations | SciML + publication owner | MQ-025, MQ-051 | `BOOTSTRAP_PUBLIC` activation |
| Reuse rights for Strategy and ExperimentRecord aggregates | Business + counsel | MQ-045 | Unrestricted learned ingestion |
| Named prior publication approvers and future signer/key custody | Governance + security | MQ-018 | External activation/signing |
| Remote practice quotas, fees, and congestion policy | Operations + economics | MQ-017 | Charged remote service |

---

# 15. Wave boundary

Wave B may implement and test:

- public contract schemas and fixture identities;
- the catalog/compiler seam;
- a local/in-process Miner Lab;
- nominal fixture-only practice execution;
- a semantically responsive resolved-plan fixture-official adapter behind the
  unchanged v1 lifecycle, with fixture-only provenance and no official or
  economic authority;
- research tasks and receipts;
- PriorPack models, immutable storage/index snapshots, a private TEST_ONLY v1-projection adapter, and a fixture publisher mechanically limited to `TEST_ONLY`;
- a persistent fixture disclosure ledger and production signer/key seams with no production custody claim;
- public publication schemas, source-eligibility validators, and negative
  activation seams; no bootstrap builder or activation;
- adaptive-disclosure and agent-workflow gauntlet harnesses.

Wave B may not claim:

- real miner training or production reconstruction;
- authenticated remote MCP transport;
- live cross-requester identity linkage, production signing, or execution quoting;
- official scientific evidence;
- a qualified public practice signal;
- learned Carbon priors from qualified official evidence;
- production security, network, commercial, or launch readiness.

Wave C owns real reconstruction, authenticated transport, live identity enforcement, execution quoting, and the real practice/official vertical. Wave D owns scientific and security qualification. Landscape activation from qualified evidence remains gated by `Launch_Bar.md` and its later wave.

---

# 16. Closing rule

> **Carbon should expose the physics problem, the legal construction language, and enough honest evidence to run productive experiments. It should protect the realized exam and its decision boundary. The result is an interface where optimizing the public loop teaches transferable physics, while official authority remains producer-independent and protected.**
