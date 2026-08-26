# Carbon Data Management Specification

> **Current authority reconciliation:** A4 provides typed entropy contexts and
> RFC 5869 HKDF-SHA-256 domain separation. Wave B may expose only a
> catalog-registered, Challenge-bounded training policy reference. It does not
> authorize raw/custom data upload or participant control over official
> evaluation, stress, `SamplingPlan`, evidence weighting, or gates.

**Classification:** Core Protocol — Security Critical

**Related:** `SPEC.md`, `Trustless_Verification.md`,
`Challenge_Instance_Distribution.md`, `Strategy_Schema.md`,
`Miner_MCP_Wave_B_Research_Contract.md`, `Scoring.md`

---

## 1. Purpose and Current Scope

Carbon separates four things that older drafts conflated:

```text
target population P(x)
finite official SamplingPlan Q(x)
evidence/score weighting w(x)
training-only strategy policy R_strategy
```

`P`, `Q`, and `w` are Challenge/scientific authorities. `R_strategy` is a
bounded construction choice affecting only how the independently reconstructed
candidate consumes authorized TRAIN-role material. Seed separation supports
this boundary but does not prove semantic decontamination or scientific
adequacy.

The current Wave B package is a science-ready, fixture-oriented authoring and
research skeleton. It does not authorize real miner training, official
scientific evidence, LIVE activation, network weights, or learned public
priors from official outcomes.

---

## 2. Non-Negotiable Data Invariants

1. **Training, evaluation, and stress are separate domains.** A4's official
   domains are `official_train`, `official_eval`, and `official_stress`, with
   purpose-specific role keys beneath them. This separates randomness and
   realized samples; it does not require mutually disjoint physical
   distributions. The Challenge declares their scientific relationship.
2. **Official realization material stays private.** Official entropy, seeds,
   derived seeds, draw/case identities, hidden ordering, protected tensors,
   private reference outputs, and reconstruction-sensitive metadata never
   cross miner/public surfaces.
3. **The Challenge owns official evidence design.** Participants cannot alter
   the target population, official `SamplingPlan`, strata, exclusions,
   reference policy/fidelity, measurement applicability, Score Pack, gates,
   thresholds, transforms, evidence weights, or disclosure policy.
4. **One mandatory official pack.** Every eligible candidate receiving a
   nonzero score completes the same registered lean pack. A conclusive
   mandatory scientific failure may stop later work because the result is
   zero; a partial path never produces a positive score.
5. **Practice is separate.** Practice uses nominal request/result/data rights,
   mock-only entropy, and non-authoritative measurement packs. It cannot
   access, approximate by authority, or contribute to the official exam.
6. **Reference and infrastructure failure are not candidate failure.** Missing,
   inapplicable, disputed, or failed truth/reference evidence retains its own
   typed outcome.
7. **Material scientific change is prospective.** Changes to `P`, `Q`, `w`,
   generator, reference, measurements, or Score Pack require a new registered
   and qualified Challenge/version; historical results are not silently
   rescored.

---

## 3. The Only Wave B Training-Data Control

### 3.1 `R_strategy` / `TrainingSamplingPolicyRef`

The only participant-selectable training-data controls are registered catalog
levers that the compiler materializes as one canonical
`ResolvedTrainingSamplingPolicy`, denoted `R_strategy`, for the exact Challenge
version. `TrainingSamplingPolicyRef` is the content-addressed reference to that
fully instantiated object's canonical bytes. It is not a free-form function,
seed, or official sampling law. The resolved policy may contain only reviewed,
bounded choices such as:

- an allowed TRAIN-role sampling schedule inside the Challenge support;
- a registered curriculum over authorized training strata or resolution;
- a registered augmentation policy that preserves the physical and
  representation invariants declared by the Challenge.

The catalog entry, not free-form participant input, defines the executable
semantics, bounds, compatibility, and canonical identity. A Strategy can
select only explicitly cataloged bounded parameter values; the compiler
materializes the resolved policy object and its reference. The Strategy cannot
provide executable sampling code, arbitrary distributions, data locations,
file paths, imports, callbacks, or unregistered transforms.

`R_strategy` is neither the target population `P(x)` nor the official
`SamplingPlan` `Q(x)`. It has no authority over official evidence selection or
weighting and creates no claim that its training exposure matches the target
population. Learning the declared physical distribution is legitimate and
desired; access to protected official realizations is not.

### 3.2 Deterministic compilation and validator seeding

The semantic compiler resolves the selected catalog levers against the exact
Challenge-owned training support, materializes the canonical
`ResolvedTrainingSamplingPolicy` and `TrainingSamplingPolicyRef`, and freezes
both into the canonical compiled training plan. The compiler rejects:

- unknown, stale, cross-Challenge, or incompatible references;
- parameters outside the registered bounds;
- policies that request EVAL/STRESS roles or official `SamplingPlan` fields;
- policies that alter truth, measurement, scoring, gates, or disclosure;
- nondeterministic or environment-dependent semantics.

The validator supplies official TRAIN-domain entropy through the typed A4
context. The participant does not supply a seed, nonce, RNG state, draw ID, or
hidden ordering. Curriculum stages, augmentation decisions, shuffle, and other
sampling purposes derive from distinct registered role keys beneath
`official_train` using the A4 RFC 5869 HKDF-SHA-256 contract.

The same canonical compiled plan must be consumed by the nominal fixture
roles used to prove practice/official-shaped compilation parity in Wave B.
The plan binds only abstract registered training-randomness purposes and
role-key labels, never an entropy domain or seed material. The practice context
derives beneath `mock`; the fixture-official or later official context derives
beneath its separately authorized train domain. Parity means identical policy
semantics, not shared entropy authority. That parity is an engineering
property, not official scientific or production authority.

---

## 4. Forbidden Wave B Inputs and Controls

Wave B accepts **no raw or custom data upload** for validator-side training,
practice, evaluation, or stress. The following are forbidden:

- datasets, tensors, archives, object-store URLs, database handles, inline
  samples, participant file paths, checkpoints containing training examples,
  or custom data-loader code;
- participant-authored generator parameters or distributions outside a
  registered `R_strategy` catalog entry;
- participant seeds, seed material, nonces, draw/case selection, shuffle
  order, augmentation randomness, or replay identifiers;
- any official EVAL/STRESS generator, case, stratum, coverage, or allocation
  control;
- any target-population or official `SamplingPlan`/`Q(x)` control;
- any evidence weighting `w(x)`, Score Pack weight, metric, transform,
  threshold, gate, gate sample, reference fidelity, truth, or qualification
  control.

There is no “validate custom data then merge it” escape hatch in Wave B.
Future customer/private-data or participant-data paths require separately
ratified rights, privacy, security, poisoning, provenance, scientific, and
execution contracts and must not be added by widening
`TrainingSamplingPolicyRef`.

---

## 5. Official Evaluation and Stress

Official EVAL and STRESS cases are validator-controlled realizations of the
prospectively registered Challenge population and `SamplingPlan`. All
score-bearing cases remain inside the declared Challenge envelope and use the
registered generator, `ReferencePolicy`/eligible `TruthAsset` path,
measurements, and Score Pack.

The mandatory official pack is frozen before candidate outcomes are observed.
Candidate performance, identity, novelty, similarity, reputation, stake,
sponsorship, prior alignment, Landscape features, or training policy cannot
change its depth, stress mass, reference fidelity, measurements, gates,
thresholds, or weights. No noisy or candidate-specific truth path is allowed.

Validators may:

- schedule and prefetch work;
- order mandatory checks by expected cost;
- stop after a conclusive mandatory failure whose registered result is zero;
- run separately identified supplemental diagnostics or audits that do not
  alter the official historical score.

Every candidate with a nonzero official score must nevertheless complete the
same registered mandatory pack.

---

## 6. Entropy and Identity Contract

Official root material comes only from a `BeaconProvider` observation
returning exact 32-byte `OfficialEntropy`. A4 applies RFC 5869 HKDF-SHA-256
with canonical challenge, generator, scoring, evaluation, domain, role, and
draw bindings and retains full 32-byte private outputs.

The historical formula
`hash(challenge_id || block_hash || run_nonce)` is not current authority.
Production beacon/provider selection, authentication, observation timing,
chain event, finality/reorg handling, nonce lifecycle, entropy quality,
fallback, and chain/drand/hybrid composition remain unresolved and
owner-ratified future work.

Official exam commitments and public projections must not disclose entropy,
seeds, draw IDs, protected cases, hidden ordering, or reversible identifiers.
Validator identity is not a seed input.

---

## 7. Practice, Public Research, and Records

Practice operates on public/mock data rights through nominally separate
services. Paired practice comparisons may use common fresh public cases to
reduce avoidable sampling noise, but those cases and measurements are not the
official exam and do not create a score, gate result, rank, weight, emission,
frontier event, or settlement.

Research records may retain exact public contract identities, compiled
Strategy identity, evidence class, typed failure class, permitted resource
observations, and bounded aggregate practice outcomes. They must not retain or
publish official seeds, protected case identities, private reference outputs,
individual official evidence, or reconstruction-sensitive metadata.

---

## 8. Product-Battery Decontamination

When later product-promotion paths are live, evidence that identified an
opportunity must not be laundered into independent product qualification:

```text
opportunity-support evidence
        !=
bank retraining/verification evidence
        !=
product-battery evidence
```

Exact policies and exceptions belong to the later Specialist Bank/Product
Qualification authority. Reusing generator code can improve auditability;
reusing the same justifying draw instances as independent product-battery
proof cannot.

---

## 9. Implementation and Review Checklist

- [ ] Exact `TrainingSamplingPolicyRef` and immutable Challenge-bound catalog
      identity exist.
- [ ] Compiler rejects free-form/custom data, executable loaders, arbitrary
      sampling laws, and every official-evidence control.
- [ ] Compiled `R_strategy` is canonical, deterministic, bounded, and pinned
      into the reconstruction identity.
- [ ] Validator supplies all official TRAIN randomness through typed A4
      entropy/context and registered role keys.
- [ ] EVAL/STRESS/`SamplingPlan`/weight/gate inputs are structurally absent
      from participant schemas.
- [ ] Practice and official-shaped fixture consumers use separate nominal
      types while proving identical compilation semantics where required.
- [ ] Leakage tests cover cards, MCP, logs, errors, records, and public prior
      artifacts.
- [ ] No fixture or placeholder can enter LIVE, ranking, frontier, product,
      weight, emission, or settlement authority.

---

## 10. Source-of-Truth Rule

Current checked-in domain specifications, the active ratified wave/ticket
package, and exact implementation/tests are the source of truth. Historical
commit or blob references may be provenance only. They are never a current
coding authority and must not resurrect superseded custom-dataset, entropy
floor, adaptive-stress, or free-form generator controls.

---

*Do not weaken TRAIN/EVAL/STRESS separation, expose protected realization
material, widen `TrainingSamplingPolicyRef` into arbitrary data authority, or
let participant/Landscape inputs change the registered official exam.*
