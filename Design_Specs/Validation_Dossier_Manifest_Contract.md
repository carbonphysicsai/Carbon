# Validation Dossier and Qualification Manifest Contract

**Ticket:** B-06 — Validation Dossier and qualification-manifest machinery  
**Contract version:** 0.1  
**Status:** agent-selected working engineering contract  
**Maturity ceiling:** bounded structural engineering only  
**Implementation owner:** `carbon.qualification`  
**Registry owner:** `carbon.registry` remains unchanged in the first slice

This contract defines the exact Challenge-bound D1–D12 evidence layout and
signer-role boundary that B-06 may implement without deciding whether any
evidence, signer, Challenge, or exam is scientifically adequate. The first
slice is an identity and serialization foundation. It contains no
qualification-manifest issuer, active-registry comparator, signature verifier,
scientific pass/fail engine, or `LIVE` transition.

## 1. Authority and owner-directed opening

The repository owner directed B-06 to begin from merged PR #87 at main commit
`2500e51042f39a31f5056c74ce2ac5065657ec2a`, tree
`89763523576cef09f40fd8a205aa86d169d679de`, while preserving the fact that
B-05's ordinary review/approval/check/receipt predicate did not complete.
This is a narrow sequencing exception: the merged B-05 tree is accepted as a
B-06 dependency, and no missing B-05 review, approval, CI result, or receipt is
invented. The exception grants no scientific, security, production,
qualification, or `LIVE` authority and does not change future ticket delivery.

Controlling domain semantics are `Generator_Validation.md`,
`Evidence_and_Envelope_Standards.md`, and `Launch_Bar.md`, read with the
scientific canon, Build Out and its constitutional overlay, the owner-approved
Science/GTM integration record, A3, and merged B-02A/B-03/B-04/B-05 contracts.
Where a scientific value or signoff rule is absent, the implementation remains
explicit and fail closed.

## 2. KEEP → WRAP → REPAIR → REPLACE

| Existing seam | Disposition | B-06 use |
|---|---|---|
| A3 `ChallengeKey` and tagged SHA-256 grammar | KEEP + WRAP | Exact Challenge identity and digest validation; no second Challenge grammar. |
| A3 legacy eight-slot `QualificationManifest` and LIVE gate | KEEP | Unchanged in Slice 1. A later B-06 slice supplies an exact comparison input rather than silently replacing A3. |
| B-02A strict identifier/version/text primitives and prospective supersession | KEEP + WRAP | Exact built-in types, immutable refs, same-Challenge history, no `latest`. |
| B-03 generator conformance facts | KEEP | Evidence input only; conformance cannot substitute for reference or measurement adequacy. |
| B-04 reference policy/run/comparison/admission refs | KEEP | Evidence input only; agreement or an admitted fixture asset does not qualify a Dossier. |
| B-05 measurement/evidence/uncertainty refs | KEEP | Evidence input only; a measurement inventory or scalar-ready fixture is not Dossier qualification. |
| Empty `carbon.qualification` namespace | WRAP | Becomes the B-06 package with its own closed canonical domain. |
| Untyped evidence dictionaries, free-form D1 names, signer names as authority, and Boolean qualification | REPLACE / EXCLUDE | Exact enums, refs, structural states, and no positive authority path. |

Dependency direction is one way:

```text
carbon.registry identity/digest primitives ─┐
carbon.authoring strict value primitives ───┼─> carbon.qualification
Python standard library ────────────────────┘
```

The first slice does not import registry store/gate classes, generator,
evaluation, measurement, scoring, TrainEval, MCP, cards, fees, leaderboard,
chain, network, frontier, product, settlement, or legacy code.

## 3. Exact identity and canonical profile

Schema version is exact string `"1.0"`. Canonical profile is exact string
`carbon_validation_dossier_canonical_v1`. The domain header is exact bytes
`carbon.qualification.validation-dossier.canonical.v1\x00`.

`ValidationDossier` contains:

- exact A3 `ChallengeKey`;
- canonical `dossier_id` and exact `dossier_version`;
- optional exact same-Challenge, same-dossier `ValidationDossierRef`
  supersession edge;
- the exact ordered D1 through D12 section tuple;
- the exact ordered B-06 accountable signer-role bindings; and
- an exact structural origin class.

`ValidationDossierRef` binds Challenge, dossier ID/version, schema/profile, and
the tagged SHA-256 digest of the complete domain-framed canonical bytes.
Changing any section, evidence reference, signer binding, origin, or
supersession edge changes the digest. A new material meaning requires a new
dossier version. Supersession never rewrites, revokes, qualifies, or transfers
authority from the predecessor.

Canonical payloads use strict UTF-8 JSON with lexicographically sorted keys,
fixed separators, exact full-field objects, closed enum strings, no floats,
no coercion, no unknown/missing fields, no duplicate keys, and complete-byte
consumption. The digest includes the domain header. Decoding reconstructs exact
nominal types and re-encodes byte-for-byte.

## 4. Exact D1–D12 slots

The slot IDs, order, and titles come directly from
`Generator_Validation.md`:

| Slot | Exact title | Primary evidence class |
|---|---|---|
| D1 | Physical-system adequacy | `PHYSICAL_SYSTEM_ADEQUACY` |
| D2 | Claim / envelope adequacy | `CLAIM_ENVELOPE_ADEQUACY` |
| D3 | Target-population adequacy | `TARGET_POPULATION_ADEQUACY` |
| D4 | SamplingPlan / finite-evidence adequacy | `SAMPLING_PLAN_FINITE_EVIDENCE_ADEQUACY` |
| D5 | Generator implementation integrity | `GENERATOR_IMPLEMENTATION_INTEGRITY` |
| D6 | Generator distribution conformance | `GENERATOR_DISTRIBUTION_CONFORMANCE` |
| D7 | Reference / truth adequacy | `REFERENCE_TRUTH_ADEQUACY` |
| D8 | Representation fidelity | `REPRESENTATION_FIDELITY` |
| D9 | Measurement adequacy and applicability | `MEASUREMENT_ADEQUACY_APPLICABILITY` |
| D10 | Statistical sufficiency and estimand clarity | `STATISTICAL_SUFFICIENCY_ESTIMAND_CLARITY` |
| D11 | Evaluation secrecy, decontamination, and role separation | `EVALUATION_SECRECY_DECONTAMINATION_ROLE_SEPARATION` |
| D12 | Censoring, limitations, and residual uncertainty | `CENSORING_LIMITATIONS_RESIDUAL_UNCERTAINTY` |

Every `REQUIRED` section that claims `COMPLETE_REFERENCED` must carry at least
one exact primary evidence ref for its own slot. Evidence for another slot or
supplemental campaign cannot satisfy that requirement. This structural rule
preserves the specified separation among population, SamplingPlan, generator,
reference, representation, measurement, statistics, secrecy, and limitations.

## 5. Evidence references, requirements, and completeness

Each `DossierEvidenceRef` binds one exact Challenge, closed evidence class,
canonical evidence ID/version, tagged digest, and exact structural origin.
Besides the twelve primary classes, v1 includes the ticket-authorized
supplemental classes:

```text
MMS_REFINEMENT_OBSERVED_ORDER
PLANTED_DEFECT_MUTATION_CAMPAIGN
ANALYTIC_LIMITING_CASE_ANCHOR
PRIMARY_WITNESS_CONVERGENCE
REFERENCE_DISAGREEMENT
GENERATOR_ORACLE_ADVERSARIAL_TEST
MEASUREMENT_FLOOR
DECISION_RESOLUTION_STUDY
RESIDUAL_LIMITATION
```

Supplemental evidence can be referenced but cannot replace a required
section's own primary evidence class. In particular, MMS or another
verification campaign cannot satisfy D1, D2, D3, D4, physical validation,
customer context of use, product qualification, or a `LIVE` decision.

Section requirement states are the exact specification values:

```text
REQUIRED
NOT_APPLICABLE_WITH_RATIONALE
DEFERRED_BLOCKING_LIVE
```

Structural completeness states are:

```text
INCOMPLETE_MISSING
INCOMPLETE_PLACEHOLDER
COMPLETE_REFERENCED
```

These states describe references and shape only. They are not evidence
adequacy, approval, signer authorization, qualification, or `LIVE`. Missing or
placeholder states require `BLOCKED` section status. A required complete
section needs its own primary evidence. `NOT_APPLICABLE_WITH_RATIONALE`
requires an exact rationale ref and exact `NOT_APPLICABLE` status.
`DEFERRED_BLOCKING_LIVE` requires an exact rationale ref and `BLOCKED` status.
Placeholder identifiers and references are rejected; the placeholder state is
an explicit fail-closed marker with no fake evidence object.

The section status vocabulary remains exactly the Dossier specification:

```text
PASS
FAIL
NOT_APPLICABLE
BLOCKED
PASS_WITH_LIMITATIONS
```

Constructing or serializing one of these values records a claimed section
state. It does not verify the claim or make it authoritative.

## 6. Required signer roles without authorization invention

The first slice uses the exact accountable roles named for B-06 by the Wave-B
board, in this order:

```text
PHYSICS_SCIML
STATISTICS
PROTOCOL
SECURITY
INDEPENDENT_REVIEW
```

Every Dossier contains exactly one binding for every role in that order.
Substitution, duplication, omission, extra roles, cross-Challenge refs, or
role-confused identity/signature/authorization refs reject.

Each role binding is either `REQUIRED_MISSING` or
`POPULATED_UNVERIFIED`. The populated state binds exact nominal
`SignerArtifactRef` values for signer identity and signature and may bind an
authorization-evidence ref. The artifact kinds are distinct:
`SIGNER_IDENTITY`, `SIGNATURE`, and `AUTHORIZATION_EVIDENCE`.

There is deliberately no `VERIFIED`, `AUTHORIZED`, or `APPROVED` signer state
in this slice. A signer name, signature bytes, populated slot, or authorization
evidence link does not prove identity, key custody, authority, separation of
duties, or valid approval. Those checks remain human/security/governance owned
and belong to the later qualification-manifest workflow.

## 7. Structural origin and fixture isolation

Evidence and dossiers use closed structural origin classes:

```text
FIXTURE_ONLY
DRAFT_OR_UNRESOLVED
REGISTERED_REFERENCE
```

`REGISTERED_REFERENCE` means only that a reference claims an external
registration binding; this package does not verify the registry. A Dossier is
fixture-derived when its own origin or any nested evidence/signer artifact is
`FIXTURE_ONLY`. Hashing, copying, serializing, superseding, or attaching signer
slots cannot cleanse fixture origin.

No first-slice API can construct a qualification manifest, compare an active
registry record, verify a signer, activate a Challenge, or return a positive
qualification result. Fixtures may therefore exercise every structural path
without becoming evidence that can qualify a real Challenge.

## 8. Later qualification-manifest and active-registry seam

A later B-06 slice may define an immutable `QualificationManifestCandidate`
that references one exact `ValidationDossierRef` and the exact qualified exam
artifacts required by Build Out and Launch Bar. A separately configured,
fail-closed comparator will accept:

```text
exact active A3 ChallengeRecord snapshot
+ exact expected ChallengeKey
+ exact ValidationDossier bytes/ref
+ exact qualification-manifest candidate bytes/ref
+ externally verified signer authorization results
+ exact artifact bytes/digests
```

and return only a typed comparison result. It must reject missing,
placeholder, fixture, unsigned, unauthorized, wrong-version, stale,
cross-Challenge, malformed, role-confused, or digest-mismatched input. It may
not infer scientific sufficiency from schema completeness or execute a LIVE
transition. A3 remains lifecycle owner; integration requires an explicit
prospective adapter/migration that preserves legacy history and compares the
exact active registry record rather than creating a parallel registry.

This seam is contractual only in Slice 1. No registry, store, signer, key,
execution, or activation implementation is authorized here.

## 9. First-slice tests

Focused proof must cover:

- exact D1–D12 order, titles, and primary evidence classes;
- exact Challenge and version binding across every nested ref;
- deterministic bytes, digest, ref, round trip, and tamper rejection;
- missing and placeholder evidence remaining blocked;
- cross-section evidence substitution rejection;
- signer-role omission, duplication, order, and artifact-kind substitution;
- wrong-version/cross-Challenge supersession and nested input rejection;
- structural completeness remaining distinct from section status;
- fixture origin propagation and absence of a qualification/LIVE API; and
- package/dependency/root-export boundaries.

Native tests on this macOS host are diagnostic only. Canonical Linux checks,
complete-diff review, human delivery approval, merge, and closeout are reserved
for the mature B-06 candidate.

## 10. Deferred and human-reserved work

Deferred B-06 slices own the full evidence inventories and cross-section
claim-adequacy checks; statistical/dependence/coverage manifests; exact
qualification-manifest construction; signer-authorization verification seam;
active-registry comparison; lifecycle and negative integration tests; and
final validation/review.

Humans retain every real physical claim, envelope, population, SamplingPlan,
generator/reference/measurement adequacy decision, uncertainty/dependence and
coverage judgment, evidence minimum, stopping rule, signer identity and
authority, security acceptance, scientific signoff, launch decision, and
`LIVE` activation. B-E1 retains statistical campaigns; B-07F retains official
execution composition. Bittensor, frontier, treasury, settlement, product,
commercial, and later-wave behavior remain out of scope.

