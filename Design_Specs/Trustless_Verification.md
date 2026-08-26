# Trust-Minimized Verification and Data Generation

> **Current authority reconciliation:** Official root material crosses the
> typed `BeaconProvider` boundary only as exact 32-byte `OfficialEntropy`.
> A4 derives role-separated 32-byte values with RFC 5869 HKDF-SHA-256 and
> canonical identity bindings. A4 does **not** select or qualify a production
> beacon/provider, observation time, chain event, finality/reorg rule, nonce
> lifecycle, fallback, or hybrid composition; those remain owner decisions.

This document defines how Carbon can make official evaluation
**trust-minimized, committed, reproducible, and auditable** while keeping
protected realizations unavailable to miners before evaluation. It does not
claim fully cryptographic trustlessness, proof of correct execution, or that
seeding alone establishes scientific truth.

---

## 1. Philosophy and Goals

Carbon replaces an informal promise that the team did not leak an exam with a
chain of scoped controls: a prospectively registered Challenge, qualified case
and reference paths, typed domain-separated entropy, immutable exam identity,
controlled execution, commitments, retained evidence, and independent audit.

### Core goals

- **Trust-minimized:** no individual validator is the scientific authority;
  official decisions are constrained by registered artifacts and auditable
  evidence.
- **Auditable:** identities, generator/reference implementations,
  qualifications, commitments, and permitted result projections are
  reviewable without disclosing protected realizations.
- **Unpredictable before commitment:** miners cannot reliably precompute the
  exact official cases from public or miner-controlled inputs.
- **Scientifically credible:** the exam's population, sampling, truth,
  measurements, and evidence-use policy earn authority independently.
- **Agent-friendly:** public research support is useful but remains
  nominally and authoritatively separate from official evaluation.

Public code and cryptographic commitments are important controls. Neither one
proves that the scientific task, reference, measurement, or execution is
adequate.

---

## 2. Separate the Scientific and Execution Layers

The following objects must not be collapsed:

| Layer | Responsibility | What it does not establish |
|---|---|---|
| **Truth target** | The Challenge-owned physical quantity, output, and claim to be evaluated within an exact envelope and intended use | It does not choose cases or compute answers |
| **Instance generator** | Deterministically realizes canonical cases from the registered population and `SamplingPlan` | Generated inputs are not ground truth |
| **Primary reference** | Computes the Challenge-authorized reference realization for a canonical case under a `ReferencePolicy` | Solver reputation alone is not truth authority |
| **`TruthAsset`** | Binds an accepted reference realization to the canonical case, reference implementation/version, provenance, uncertainty, applicability, qualification status, and failure state | It is not interchangeable with the generator or an unqualified solver output |

A corroborating witness tests the primary reference under a prospectively
registered qualification or audit campaign. It does not silently vote with
the primary reference or replace the `ReferencePolicy`. Reference failure,
disagreement, or unavailable truth is a typed evidence/reference outcome and
must not become candidate failure.

Only after the canonical case and eligible `TruthAsset` exist may Carbon form
a reference-labelled training or evaluation example. The same physical case
must survive every representation adapter unchanged.

---

## 3. Official Entropy and Domain Separation

### 3.1 Current A4 boundary

Provider-origin official material is acquired once through a typed
`BeaconProvider` observation and must be exact `OfficialEntropy` containing
exactly 32 bytes. Acquisition fails closed on absence, wrong type, wrong
length, or provider failure. Validator/miner identities, Strategy contents,
ambient RNG state, call order, retry count, clocks, and process state are not
entropy inputs.

A4 then applies RFC 5869 HKDF-SHA-256:

```text
salt = ASCII("carbon/a4-seeding/hkdf-sha256/v1")
PRK  = HKDF-Extract(salt, OfficialEntropy)
OKM  = HKDF-Expand(PRK, canonical_domain_info, 32)
```

The canonical information binds the registered challenge, generator,
scoring, seed-scheme, evaluation, domain, role, and draw identities. The
official top-level domains are `official_train`, `official_eval`, and
`official_stress`; internal purposes such as generator sampling,
augmentation, shuffle, initialization, and batch order are role keys beneath
the appropriate domain. Outputs are retained as exact private 32-byte values,
not truncated or reused across roles.

This is separation of randomness roles and realized samples, not a blanket
requirement that TRAIN, EVAL, and STRESS use mutually disjoint physical
distributions. Their scientific relationship is declared by the Challenge's
population and `SamplingPlan`. Learning the declared physical distribution is
desired; learning protected official realizations is not.

`MockEntropy`, `QualificationEntropy`, and `FixtureOfficialEntropy` use
separate exact types, contexts, and entry points. There is no caller-selected
`mock | official` mode and fixture material cannot be relabelled as
provider-origin official material.

### 3.2 Production policy remains unresolved

The prior shorthand
`hash(challenge_id || block_hash || run_nonce)` and statements that a hybrid
beacon is the current production choice are not normative. A future production
policy must separately ratify and qualify the provider, authentication,
observation timing, commitment point, finality/reorg behavior, entropy quality,
nonce lifecycle, fallback behavior, and any chain/drand/hybrid composition.
Until then, A4 supplies the typed provider boundary and deterministic
derivation contract, not live beacon authority.

---

## 4. One Official Exam Identity and One Mandatory Pack

Official evaluation is bound to immutable Challenge, generator,
`ReferencePolicy`/truth, measurement, Score Pack, environment/backend, seed
scheme, and evaluation identities required by the active contract. An opaque
exam commitment may make that binding auditable without revealing official
entropy, seeds, draw IDs, hidden ordering, or reversible identifiers.

Every eligible candidate that receives a nonzero official score must complete
the **same registered mandatory official lean pack** under that shared exam
identity. Validators may schedule mandatory checks in a cost-efficient order
and may stop after a conclusive mandatory scientific failure because the only
permitted scientific outcome is zero. A partial or shallow path can never
produce a positive score.

The following are forbidden for the registered official score:

- predicted-easy candidates receiving fewer graded cases than frontier
  candidates;
- candidate-specific stress mass, measurement depth, reference fidelity,
  gate samples, thresholds, or Score Pack weights;
- noisy, perturbed, lower-fidelity, or otherwise candidate-dependent truth;
- novelty, similarity, reputation, stake, sponsorship, prior alignment, or
  Landscape forecasts changing exam depth or scoring evidence.

Supplemental diagnostics or later audits may use separate registered evidence
contracts, but they cannot rewrite the mandatory official pack or the
historical score.

---

## 5. Scientific Credibility of Cases and Truth

Procedural generation is valuable because it can realize fresh cases from a
registered distribution. It is not self-validating.

Qualification must address, at minimum:

- the truth target and claimed operating envelope;
- target population `P(x)`, finite-evidence `SamplingPlan`/`Q(x)`, and any
  evidence weighting `w(x)` as separate semantics;
- generator determinism, support and exclusion compliance, distribution
  conformance, censoring, and failure rates by stratum;
- primary-reference implementation, independent witness evidence,
  uncertainty, applicability, and disagreement/failure policy;
- representation parity from canonical case to every consumer;
- measurement implementation and Score Pack evidence-use policy.

Generator validation samples registered cases and compares the actual
production reference path with methodologically independent evidence where
the `ReferencePolicy` requires it. Published harnesses, exact versions,
commands, cases permitted for disclosure, limitations, and results strengthen
auditability. A handful of known reference cases can be useful for regression
and qualification, but neither those cases nor an open generator substitute
for a qualified official `TruthAsset` path.

---

## 6. Practice and Agent Research Are Separate

Practice uses nominally separate request, result, data-handle, quota,
measurement-pack, and service types. It uses public or mock-only data rights
and fresh public cases; it never acquires official contexts, packs, seeds,
protected cases, `TruthAsset`s, or private evaluator state.

Practice may reuse reviewed internal numerical kernels only behind that
separate authority boundary. Its measurements are non-authoritative and may
be useful for paired comparisons on common public cases. Practice cannot:

- predict or claim an official score, rank, gate outcome, winner, weight,
  emission, frontier state, or settlement;
- prequalify, prioritize, admit, reject, or score an official submission;
- contribute a lower-weight result to official scoring or Landscape as though
  it were official evidence;
- reconstruct the mandatory official pack.

The practice surface should be intentionally incomplete relative to the
official exam while still rewarding transferable physical improvement.

---

## 7. Gaming Resistance and Prospective Change

Learning the declared physics population is desired. Memorizing protected
realizations, exploiting leakage, or inducing candidate-specific grading is
not.

The control stack is:

1. prospectively registered Challenge, population, `SamplingPlan`, generator,
   reference, measurement, and Score Pack identities;
2. exact typed entropy and RFC 5869 domain separation;
3. immutable official exam binding and non-disclosing commitment;
4. controlled, independently reproducible execution;
5. no protected-state leakage through cards, MCP, logs, errors, or Landscape;
6. retained evidence, typed failure states, and independent audit;
7. prospective versioning and requalification when the scientific contract
   changes.

Network performance or Landscape findings may propose a future Challenge,
generator, `SamplingPlan`, truth, measurement, or Score Pack revision. They
must not adapt the live pack per candidate or change the ruler after results
are observed. A material change creates a new prospective qualified Challenge
version with its own identity and does not silently rescore history.

---

## 8. Audit Surface and Honest Claim

The audit surface should include:

- registered public Challenge and population/envelope material;
- versioned generator, reference, measurement, and Score Pack identities;
- qualification dossiers and disclosed validation/audit evidence;
- canonical seeding specification and golden vectors;
- opaque exam/result commitments and later signed receipts when implemented;
- execution/environment pins, typed infra/reference outcomes, retention, and
  dispute procedures;
- changelogs and prospective requalification triggers.

The defensible claim is that Carbon is **trust-minimized, committed, and
audited** under explicit qualifications and limitations. Public seeds,
open-source code, or hashes do not by themselves prove correct private
execution, provider honesty, scientific adequacy, or universal physical truth.

---

## 9. Proprietary Data Boundary

Wave B allows public/registered synthetic research inputs only through its
bounded declarative contracts. It does not accept raw or custom data uploads
for validator-side training, practice, official evaluation, or stress.

Future customer-controlled local fine-tuning, confidential computing,
federated learning, or privacy-preserving contribution paths require separate
rights, privacy, security, scientific, and product authority. Raw proprietary
data should remain in the customer's environment until such a path is
explicitly designed and qualified. No roadmap item is a claim that Carbon can
currently process proprietary data safely inside a decentralized network.

---

## 10. Scientific Parameter Documentation

Per-physics documentation should explain the scientific basis for registered
parameter support, exclusions, strata, query times, geometry/topology,
boundary and initial conditions, forcing, and reference applicability. For
example, a Burgers Challenge may document viscosity, initial-condition
regularity, shock-forming regimes, resolution, and rollout horizon; elliptic,
fluid, elasticity, and coupled Challenges require their own qualified tables.

Such tables are authored and approved through the Challenge and Validation
Dossier process. They are not populated from convenient defaults, historical
PoC values, or agent-generated scientific judgment.

---

## 11. Relationship to Other Systems

- **Challenge authoring:** owns the truth target, population, `SamplingPlan`,
  canonical case, and prospective versioning.
- **Generator/reference qualification:** owns generator conformance,
  `ReferencePolicy`, primary/witness evidence, and `TruthAsset` eligibility.
- **Scoring:** applies registered admissibility and evidence-use policy; it
  does not create truth.
- **Landscape:** may learn from eligible evidence and propose future work; it
  never changes a candidate's official pack.
- **Miner research:** uses nominal practice contracts and public data rights;
  it never crosses into official evaluation authority.
- **Evidence and audit:** commits, retains, signs, and audits permitted
  evidence without disclosing protected realization material.

---

*Carbon's verification model is a qualified, trust-minimized evidence chain:
define the physical job, qualify cases and truth, commit the official exam,
evaluate every eligible nonzero candidate under the same mandatory pack, and
audit the result without turning protected evidence into a public side
channel.*
