# Carbon Miner Research Interface and Prior Pack Contract

**Status:** **AGENT-SELECTED WORKING ARCHITECTURE CONTRACT** for B-07R engineering. It preserves the Wave-A MCP unchanged and confers no scientific truth or qualification, security acceptance, rights/legal approval, economic authority, LIVE, launch, settlement, weight, emission, or production authority. It becomes the merged Wave-B engineering architecture only when the exact reviewed tree passes CI, every valid Greptile finding is repaired with zero Greptile threads unresolved, it normally merges, and its exact-main CI passes. A documented invalid finding may be closed with rationale; any tree change requires rereview.
**Version:** 0.4
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

The ownership-preserving architecture is:

```text
ChallengeInteractionManifest
        ↓
Strategy + ParameterCatalog + CandidateAssemblyContract
        ↓
ResolvedConstructionPlan
        ↓
ResearchTask
        ↓
nominal practice/research execution
        ↓
private ExperimentRecord
        ↓
bounded ResearchReceipt
        ↓
separate prior / evidence / resource projections
        ↓
B-07F fixture-official reconstruction through the unchanged Wave-A v1 service
```

Each arrow is an explicit reference or consumer boundary, never an authority
promotion. B-02B owns construction semantics, B-02C resource policy, B-07S the
exact research protocol, B-07A through B-07G their assigned implementation
layers, and B-07F the later fixture-official consumer. B-07R fixes this
architecture and ownership only; it implements no service or wire contract.

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

The plan is private-to-requester during research and may become part of official
reconstruction evidence only in a later qualified official flow. In Wave B,
B-07F may consume it only through fixture-official provenance with no official
authority. It contains normalized, fully resolved construction instructions
expressed only in the registered catalog vocabulary. When permitted, it binds
the exact canonical `ResolvedTrainingSamplingPolicy` denoted `R_strategy` and
its `TrainingSamplingPolicyRef`; the execution service derives train seeds and
draws rather than accepting them from the miner. It also carries immutable
policy-agnostic static resource requirements and impact tags. B-02C evaluates
those requirements against a separate `ResearchResourcePolicy` and cannot
mutate the plan or compiler semantics. The plan contains no official
randomness or evaluation controls.

The plan is not a candidate artifact, score, or proof of successful reconstruction.

The four scientific/data roles remain exact and non-interchangeable:

```text
P          = target or workload population
Q          = official proposal / SamplingPlan law
w          = evidence weighting
R_strategy = resolved training sampling policy inside Challenge-owned support
```

`R_strategy` cannot alter `P`, `Q`, `w`, official evaluation, stress,
reference evidence, measurements, gates, or score. It binds policy semantics,
not randomness. Each nominal validator or execution context derives its own
authorized randomness; no miner seed authority exists.

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

Wave B provides a local, reproducible Miner Lab using the same public catalog
and compiler identities. A local/in-process agent adapter exposes the
B-07S-ratified research contract without a network listener, credentials,
authenticated remote transport, or charged execution. It may later be
expressed as a bounded stdio MCP or equivalent CLI only as B-07S specifies. A
bounded in-process practice referee may establish parity and resource receipts.
Remote authentication, transport, identity linkage, quotas, and execution
quotes belong to Wave C.

The topology has two separate authority planes. The existing exact Wave-A
seven-tool service retains the sole official submission/result store,
lifecycle, and error authority. A distinct local research plane owns only
discovery, compilation, practice, prior, record, and resource capabilities.
The descriptive labels `carbon_protocol_v1` and `carbon_research_v2` may be
used in architecture discussion, but they are not ratified wire identifiers;
B-07S owns exact service/version identifiers, namespace rules, and
compatibility negotiation. No merged alias exists, and the research adapter
never wraps, mirrors, or reimplements the official store or lifecycle.

Local agents keep private sweeps and failed experiments locally. Carbon does not require miners to upload their entire research history.

---

# 7. ResearchTask, ExperimentRecord, and receipts

## 7.1 ResearchTask

A research task is a Challenge-bound, requester-bound unit of local research.
At the semantic layer it pins the following information; B-07S owns exact
field names, wire shapes, bounds, and canonical bytes:

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

The architecture requires asynchronous execution, requester-scoped
idempotency, immutable lineage, cancellation without scientific relabeling,
typed separation of infrastructure failure from scientific outcome, and a
bounded terminal receipt. Reconstruction rehearsal, practice, paired practice,
and resource calibration are required capability families. B-07S alone fixes
the exact task-kind literals, lifecycle states and transitions, idempotency
identity and conflict behavior, cancellation cutoffs and races, retry rules,
polling bounds, request/result shapes, and error precedence. No lifecycle
state may itself become scientific evidence, and a terminal record may never
be silently reopened or rewritten.

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

Wave B adds one nominal local/in-process research plane while the current exact
Wave-A `McpService`, its seven tools, types, errors, lifecycle, and store remain
unchanged. Version selection and namespace separation occur outside the v1
call envelope; v1 gains no negotiation field, research alias, or v2-backed
production provider. The research plane creates no second official submission
or result path. Network transport, authentication, execution quoting, remote
process hosting, and production identity linkage remain Wave C.

The research plane must express these capability families without merging
their authority: Challenge and interaction discovery; static prior retrieval
and alignment; scaffold retrieval; dry validation; semantic Strategy
compilation; static resource inspection; calibrated resource forecasting; and
research-task creation, observation, and cancellation. These are architectural
capabilities, not ratified operation names or a ratified operation count.

B-07S owns the complete exact protocol: wire objects; service/version and
operation names; lifecycle states; request and response shapes; error taxonomy
and precedence; canonical bytes and hashing; bounds and resource envelopes;
pagination; idempotency; provider interfaces; local adapter; compatibility and
version negotiation; and disclosure behavior. It must preserve the authority
separations in this contract. B-07R does not pre-ratify any wire/protocol
literal, encoding, state transition, selector, provider signature, or error
value; domain-semantic objects and enums explicitly fixed elsewhere in this
contract remain architecture requirements for B-07S to express.

B-07A implements B-07S's shared nominal primitives once. Domain tickets own
their semantics, validation, providers, stores, and execution: B-07A discovery
and manifest data; B-07D3 prior retrieval/alignment; B-07C scaffold and
practice execution; A2 validation; B-02B compilation; B-07E resource analysis
and forecast; and B-07B task lifecycle and records. B-07G owns only composition,
dispatch, and cross-capability conformance for the B-07S-ratified closed
operation set. No layer may expose or delegate official submission, result,
score, or store authority.

`ResearchResourcePolicyRef` binds the immutable domain contract produced before
manifest, practice, or forecasting implementation. That contract defines
resource classes, exact static construction dimensions, declared ceilings,
enforcement and kill semantics, and observed receipt fields. It does not
contain calibrated forecast parameters, a price, a quota, or authority to
execute. Static inspection and calibrated forecasting consume this policy;
they do not define it.

The future research interface keeps four results distinct:

| Capability | Output | Authority |
|---|---|---|
| prior alignment | Applicable public prior item references | Deterministic public matching only |
| static resource inspection | Exact plan-derived dimensions and declared constraints | Static exact analysis only |
| calibrated resource forecast | Non-binding runtime, memory, storage, and reconstruction-risk intervals | Forecast with model identity, uncertainty, and support state |
| practice research task | Measured public-practice evidence | Non-authoritative scientific practice |

The future Wave C operational quote/admission capability is a separate binding
operational/economic contract. A forecast declares its model version,
calibration window, applicable hardware/resource class, uncertainty, and
support state; unsupported input is unresolved and fail closed. No research
capability predicts official quality, score, rank, gate outcome, frontier
status, weight, emission, settlement, or winner.

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

At the semantic layer, a `PriorPack` identity binds the Challenge; prior
logical/version identity; canonicalization identity; publication class;
evidence cutoff, publication, and activation epochs; exact interaction-
manifest, catalog, and policy-bundle references; and builder version. B-07S
owns the exact field names, object shapes, canonical encoding, digest algorithm,
and wire reference representation.

The pack's content address is computed over its B-07S-canonical bytes. Neither
the address nor its enclosing reference may appear in that hashed preimage;
self-referential identities are invalid. B-07S owns the exact reference fields
and digest expression.

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

The protocol must support exact-reference retrieval and atomically resolved
active-channel retrieval without an unversioned implicit latest. Both paths
enforce publication class, exact-hash authorization, and withdrawal state.
Active resolution returns the exact snapshot, publication receipt, pack
reference, and bytes from one index state. Exact retrieval may return an
authorized active or superseded public pack. Withdrawal stops new byte service
but cannot make earlier public copies secret or erase their historical receipt.
Every research task pins the exact returned pack reference. B-07S owns selector
literals, request/result shapes, error behavior, and pagination.

The Wave B gauntlet uses a structurally private, local-only research context
with an injected fixture prior provider. It may retrieve only an exact-ref,
structurally authorized `TEST_ONLY` pack, and the result binds a distinct
test-only authorization receipt. The pack and every dependent receipt retain
`TEST_ONLY / NOT_UTILITY_QUALIFIED` permanently. A passing B-E4 creates separate
gauntlet evidence and may qualify only the bounded mechanism; it never mutates
or reclassifies the fixture pack. An external/public context cannot be
constructed with that provider and rejects the same pack. No caller-selected
mode, alternate hidden API, or public v1 projection is used. B-07S owns the
exact context/provider/result/capability types; B-07D3 owns enforcement.

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

Each item semantically binds the following information. B-07S owns exact wire
field names/order/encoding and B-07D1 owns domain validation:

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

The prior-retrieval capability serves only a prebuilt artifact authorized for
its publication class. It never queries the card lake, Landscape, official
evaluator, or private ExperimentRecords during a miner request.

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
3. record a delegated, exact-byte structural fixture authorization after the
   applicable engineering checks and notifications; this is not science,
   security-acceptance, rights, utility, publication, or release approval;
4. atomically append the fixture ledger delta and record a test-only prior
   authorization receipt in a private immutable snapshot; B-07S owns its exact
   type and wire name.

The receipt and its content-addressed reference are nominally distinct from a
`PriorPublicationReceipt`. They carry `TEST_ONLY / NOT_UTILITY_QUALIFIED`,
permit only exact-ref retrieval through the private fixture context, and cannot
enter a public channel, public active index, public or production v1 provider,
external surface, or publication-class promotion. It may be input only to the
private offline compatibility projector in §9.7; that output remains a private
test artifact and is never used by the B-E4 v2-prior arm. B-E4 then pins those
exact pack and authorization references for every v2-prior arm run and
replicate. A passing B-E4 result
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
   hash; a Wave B test-only authorization receipt cannot satisfy this step;
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

The future prior-alignment capability deterministically maps a Strategy to
public item references using only the public pack and catalog. It never reads
private outcomes. B-07S owns its exact operation and result vocabulary.

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

The architecture preserves this complete authority ladder. Adjacent placement
does not imply conversion, and B-07S must make the classes nominally distinct:

| Layer | Meaning | Authority boundary |
|---|---|---|
| structural prior alignment | Deterministic matching of public Strategy/catalog facts to public prior items | No scientific or resource authority |
| static resource analysis | Exact plan-derived dimensions and declared constraints | No execution, forecast, quote, or scientific authority |
| calibrated resource forecast | Non-binding resource prediction with calibration identity, uncertainty, and support state | No admission, price, execution, or scientific authority |
| operational quote/admission | Future binding capacity/economic decision under Wave-C policy | Not a measurement, score, or scientific result |
| practice measurement | Measured result under a declared public practice scope | `PRACTICE_NON_AUTHORITATIVE`; cannot enter official evidence |
| official scientific evidence | Producer-independent result from the protected registered evaluation path | May be consumed only by its registered Score Pack |
| score | Exact registered projection of qualified official evidence | Cannot imply frontier, settlement, weight, or emission |
| frontier | Separately qualified promotion event under its own evidence and authority | Cannot imply settlement, weight, or emission |
| settlement | Separately authorized economic/chain consequence | Cannot retroactively create scientific evidence or frontier status |

No implicit or explicit lower-layer conversion to official evidence exists.
No prior, estimate, proxy, resource result, practice result, score predictor,
predicted winner, or ranking heuristic may substitute for a registered layer.

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

# 13. B-07R material architecture decisions

These eight decisions are the durable B-07R recommendation series. They become
the merged Wave-B engineering architecture only under the completion predicate
in the status header. Notification is not approval, and every reserved input
listed below remains fail closed.

## B-07R-D1 — Separate service planes and future transport

- **Agent recommendation:** keep the exact Wave-A seven-tool service as the
  sole official submission/result plane; add a distinct local/in-process
  research plane; leave exact identifiers and negotiation to B-07S and remote
  authentication, transport, identity, quotas, and quotes to Wave C.
- **Rationale:** official authority cannot leak through a research alias or a
  duplicated store, while local research needs no production network surface.
- **Alternatives rejected:** mutate v1; merge both planes; expose a generic
  mode flag; preselect remote transport or credentials in Wave B.
- **Affected tickets:** A9, B-07S, B-07A, B-07G, B-07F, B-E4, Wave C.
- **Migration cost:** low before B-07S; high after wire clients exist because a
  merged namespace would require client, store, and authority migration.
- **Exact change path:** supersede by a normally merged change to this file
  §§6.5/8.1 and this decision; B-07S changes exact protocol details in
  `Miner_MCP_Wave_B_Service_Protocol.md` without rewriting v1.
- **Reserved input:** production transport/security/economic acceptance remains
  unavailable and is not needed for local fixture development.

## B-07R-D2 — Construction chain and P/Q/w/R_strategy law

- **Agent recommendation:** compile `Strategy` plus Challenge-bound
  `ParameterCatalog` and `CandidateAssemblyContract` into one
  `ResolvedConstructionPlan`; keep P, Q, w, and `R_strategy` nominally
  distinct; confine `R_strategy` to registered training support and derive all
  randomness in the authorized execution context.
- **Rationale:** executable semantics must be deterministic without allowing a
  miner to rewrite the exam, evidence law, or seed authority.
- **Alternatives rejected:** inert or ignored parameters; arbitrary code or
  data; miner seeds; treating training policy as P, Q, w, stress, reference,
  measurement, gate, or score control.
- **Affected tickets:** B-02A, B-02B, B-02C, B-03, B-05, B-07S, B-07C, B-07F.
- **Migration cost:** medium; post-merge semantic changes require prospective
  catalog/compiler/plan versions and preservation of historical refs.
- **Exact change path:** amend §§4–5 and B-02B's future
  `Candidate_Assembly_and_Strategy_Compiler_Contract.md`; B-07S owns only its
  exact wire projection.
- **Reserved input:** real catalog values, backbones, structural components,
  training sources, units, domains, and policy family remain unavailable.

## B-07R-D3 — Research lineage and practice/official separation

- **Agent recommendation:** every practice or research execution is a pinned
  `ResearchTask` producing a private immutable `ExperimentRecord` and a bounded
  `ResearchReceipt`; practice remains non-authoritative, while B-07F later
  consumes the same resolved-plan identity through unchanged fixture-official
  v1 authority.
- **Rationale:** reproducible lineage and honest paired practice are useful
  without turning research state into official evidence or a second lifecycle.
- **Alternatives rejected:** upload all miner history; return per-case protected
  data; caller-selected mock/official mode; reuse practice output in A5/A6/A7;
  build a second official store.
- **Affected tickets:** B-07S, B-07A, B-07B, B-07C, B-07F, B-07G, B-GATE.
- **Migration cost:** medium; lineage fields are prospective, but authority
  conversion would require invalidating records and consumers.
- **Exact change path:** amend §§6–7 and the later B-07S protocol; B-07B owns
  records/lifecycle, B-07C practice, and B-07F fixture-official consumption.
- **Reserved input:** real practice population, reference, measurements,
  disclosure, rights, and security acceptance keep external practice disabled.

## B-07R-D4 — Immutable same-bytes prior and miner-local personalization

- **Agent recommendation:** publish only immutable Challenge-level packs with
  exact historical retrieval, atomic active-index resolution, publication-
  class ceilings, persistent disclosure accounting, and identical bytes for
  every requester; personalization occurs only in the miner's local records.
- **Rationale:** shared scientific memory can improve search without a private
  request-time oracle, paid information tier, or personalized official truth.
- **Alternatives rejected:** dynamic private-store queries; server-side LLM
  answers; per-miner pack bytes; implicit latest; fixture-to-public promotion;
  production v2 projection into the frozen v1 provider.
- **Affected tickets:** B-07S, B-07D1, B-07D2, B-07D3, B-E4, Landscape, Wave C.
- **Migration cost:** medium to high; changing content identity or history
  requires a prospective version and preservation of every old pack/receipt.
- **Exact change path:** amend §9 and later prior-policy/publication contracts;
  B-07S fixes selector, receipt, index, and wire mechanics.
- **Reserved input:** estimands, cohorts, lag, cadence, coarsening, content,
  rights, public approvals, and signing custody keep public activation disabled.

## B-07R-D5 — Conditional protected-realization leakage objective

- **Agent recommendation:** test whether the cumulative interaction transcript
  adds material ability to infer protected realizations, hidden stress
  composition, exact margins, or unresolved ordering after controlling for
  transferable held-out physics performance.
- **Rationale:** Carbon should prevent exam-oracle shortcuts while rewarding
  genuine learning; deliberately poor practice physics defeats the product.
- **Alternatives rejected:** optimize for low practice/official correlation;
  review endpoints independently; rely on random recipe perturbation; claim
  local fixture tests establish production security.
- **Affected tickets:** B-07S, B-07C, B-07D2, B-07E, B-E4, Wave C, Wave D.
- **Migration cost:** low before gauntlet preregistration; high after disclosure
  budgets or public releases because cumulative history must remain auditable.
- **Exact change path:** amend §§9.6/10/12.2 and B-E4's preregistered contract;
  production security changes require the later security owner contract.
- **Reserved input:** linkage basis, adversary model, privacy policy, utility
  floor, diversity floor, and leakage limit remain human-owned.

## B-07R-D6 — Evidence/resource/authority ladder

- **Agent recommendation:** preserve the nine layers in §11 from structural
  prior alignment through settlement; require typed deferral or indeterminacy;
  prohibit every implicit conversion and every official-score/winner predictor.
- **Rationale:** resource conservation, hypotheses, practice, and forecasts are
  useful only if none can masquerade as registered scientific evidence.
- **Alternatives rejected:** quality-based denial before complete base evidence;
  score prediction; proxy promotion; treating failure as a scientific zero;
  inferring frontier or settlement from score.
- **Affected tickets:** B-02C, B-05, B-07E, B-07F, B-E1, B-E4, A5, A6, A10.
- **Migration cost:** high after evidence is persisted; any new class or
  conversion requires prospective schema/policy versions and requalification.
- **Exact change path:** amend §§8.2/11 and the owning B-05/B-02C/B-E1
  contracts; no research-service change may alter A5 authority.
- **Reserved input:** reconstruction budgets, coverage, stopping, forecast
  calibration, admission, pricing, frontier, and settlement policy stay absent.

## B-07R-D7 — B-07S protocol delegation and implementation layering

- **Agent recommendation:** B-07R fixes capabilities, authority, and ownership
  only. B-07S exclusively fixes exact wire objects, service/version and
  operation names, lifecycle, request/response, errors, canonical bytes,
  bounds, pagination, idempotency, providers, local adapter, negotiation, and
  disclosure. B-07A implements shared primitives once; domain tickets own
  semantics; B-07G composes the B-07S-ratified closed set.
- **Rationale:** one protocol owner prevents schema drift and avoids using an
  architecture candidate as unreviewed wire authority.
- **Alternatives rejected:** ratify exact wire/protocol literals in B-07R; let each domain
  ticket define duplicate types; make B-07G a semantic owner; implement before
  B-07S.
- **Affected tickets:** B-07S, B-07A through B-07G, B-02B, B-02C, A2, A9.
- **Migration cost:** low now; high after implementations because duplicate
  types and operation aliases would require coordinated client migration.
- **Exact change path:** amend §8.1 and the B-07S ticket/contract; architectural
  changes return to B-07R, exact-protocol changes stay in B-07S.
- **Reserved input:** none for bounded protocol engineering; security/rights/
  economics needed by remote or public capabilities remain fail closed.

## B-07R-D8 — Delegated engineering ratification and fail-closed maturity

- **Agent recommendation:** accept B-07R engineering after durable record and
  notification, applicable validation, exact-head CI, repair of every valid
  Greptile finding with zero Greptile threads unresolved, normal exact-tree
  merge, and exact-main CI. A documented invalid finding may be closed with
  rationale; any tree change requires rereview. Silence is no gate. Mark only
  bounded `SPECIFIED / RATIFIED`; every implementation and qualification state
  remains `NO`.
- **Rationale:** current delegated governance permits bounded progress while
  retaining human ownership of values and high-consequence activation.
- **Alternatives rejected:** multi-human preapproval; treating notification as
  approval; claiming qualification from architecture prose; recursively opening
  a closeout PR solely to restate immutable merge metadata.
- **Affected tickets:** B-07R, B-02B, B-07S, all later Wave-B implementation,
  B-GATE.
- **Migration cost:** low; an observed `CHANGE`, `BLOCKED`, or
  `REQUEST_CHANGES` is handled by a bounded normally merged successor change.
- **Exact change path:** amend this decision, `.agent/WAVE*.md`, ticket, plan,
  and evidence together; preserve historical evidence and record supersession.
- **Reserved input:** scientific truth/values, security acceptance, rights,
  economics, qualification, LIVE, launch, settlement, weight, emission, and
  production authority remain unavailable.

---

# 14. Deferred inputs and explicit fail-closed behavior

These inputs do not block unrelated bounded architecture, schema, fixture, or
test work. They do block the named capability, exactly as shown.

| Deferred input (category + MQ) | Owner/domain | Affected capability | Fail-closed behavior now | Downstream ticket/seam | May unrelated development continue? |
|---|---|---|---|---|---|
| Real physical task, P/Q/w, reference, measurement, and qualification values (MQ-001, MQ-002, MQ-004–MQ-008) | SciML + statistics + protocol | Real authoring, exam, evidence, and qualification | Production objects reject or remain unregistered; fixtures confer no truth | B-03 through B-06; Wave D qualification | Yes |
| Real catalog, hybrid/structural components, TrainingSupport, and `R_strategy` values (MQ-015, MQ-024) | SciML + protocol + security | Real compiler and training reconstruction | Only closed non-authoritative fixtures; unknown values reject | B-02B | Yes |
| Exact research-protocol object fields, collection/resource-envelope bounds, pagination, polling, lifecycle/idempotency limits, and numeric ceilings (MQ-015–MQ-018, MQ-024–MQ-026) | Protocol + security + SRE | Any service-facing research implementation | No service implementation before the exact B-07S protocol normally merges; architecture and non-wire domain fixture work may continue | B-07S, B-07A, B-07G | Yes |
| External practice scope, reference, disclosure, rights, and security acceptance (MQ-002–MQ-005, MQ-015, MQ-016, MQ-045) | Science + statistics + security + rights | Public/remote practice | External practice unavailable; local fixture practice only | B-07C, B-E4, Wave C/D | Yes |
| Runtime ceilings, hardware classes, enforcement, and kill rails (MQ-008, MQ-015, MQ-017, MQ-024) | SRE + security + operations | Real reconstruction execution | Real execution rejected; fixture resource classes only | B-02C | Yes |
| Capacity, funding, queues, and operational evidence budget (MQ-017) | SRE + operations + economics | Admission of registered evidence work | Return `EVIDENCE_DEFERRED`; never a scientific outcome | B-02C, Wave C quote/admission | Yes |
| Forecast calibration, support window, uncertainty, and unsupported-input rule (MQ-017) | SRE + statistics | Calibrated resource forecast | Forecast capability returns `UNRESOLVED`; static analysis remains separate | B-07E | Yes |
| Complete-base evidence, coverage, stopping/extension, futility-error control, and audit rate (MQ-007, MQ-008, MQ-024) | Statistics + SciML + protocol | Scientific ranking and frontier evidence | Return `EVIDENCE_DEFERRED` or `INDETERMINATE`; no promotion | B-05, B-E1 | Yes |
| Prior estimands, cohorts, lag, cadence, coarsening, granularity, diversity, and first content (MQ-025, MQ-026, MQ-051) | Landscape + science + statistics + publication | Public prior activation | No public active pack; `TEST_ONLY / NOT_UTILITY_QUALIFIED` fixtures only | B-07D1, B-07D2, B-E4 | Yes |
| Reuse/publication rights, permitted aggregation, named public approvers, and signing custody (MQ-018, MQ-045, MQ-051) | Business + counsel + governance + security | Learned ingestion, publication, and signing | Rights-ineligible data rejected; public activation/signing unavailable | B-07D2, later security/publication seam | Yes |
| B-E4 agent profiles, budgets, utility estimand/effect rule, diversity floor, and conditional-leakage limit (MQ-016, MQ-026) | Research + science + statistics + security + protocol | Utility/leakage gauntlet and public claims | B-E4 cannot close; descriptive output has no utility/security authority | B-E4 | Yes |
| Remote identity, authentication, privacy basis, Sybil linkage, false-merge handling, and appeals (MQ-016, MQ-018, MQ-045) | Security + privacy/legal + protocol | Remote research service and cumulative enforcement | No authenticated remote service or cross-requester security claim | Wave C security contract | Yes |
| Remote quotas, fees, congestion, admission, and quote economics (MQ-017) | Operations + economics | Charged or capacity-binding service | Quote/admission and charging unavailable; forecast is non-binding | Wave C operations/economics | Yes |
| LIVE, launch, production qualification, frontier, settlement, weight, and emission authority (MQ-018, MQ-051) | Executive/domain owners under Launch Bar | Any production or network consequence | Remain `NO` and mechanically unavailable | B-GATE, Launch Bar, Wave D and later launch | Yes |

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
