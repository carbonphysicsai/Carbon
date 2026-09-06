# Validation Dossier and Qualification Manifest Contract

**Ticket:** B-06 — Validation Dossier and qualification-manifest machinery
**Contract version:** 0.7
**Status:** third complete-diff review findings repaired; fresh exact-head CI
and complete-diff review pending
**Maturity ceiling:** bounded structural engineering only
**Implementation owner:** `carbon.qualification`
**Registry owner:** `carbon.registry` remains unchanged; Slice 3 wraps only its
public immutable value types

This contract defines the exact Challenge-bound D1–D12 evidence layout and
signer-role boundary that B-06 may implement without deciding whether any
evidence, signer, Challenge, or exam is scientifically adequate. The first two
slices are an identity, typed-evidence-binding, and serialization foundation.
They contain no qualification-manifest issuer, active-registry comparator,
signature verifier, scientific pass/fail engine, or `LIVE` transition. Slice 3
adds only a structural candidate and a pure comparison against an explicitly
supplied A3 record snapshot. Slice 4 adds only typed campaign
acquisition/result records and their exact evidence-reference projection; it
does not execute or judge a campaign.

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
carbon.authoring exact public refs ─────────┤
carbon.measurement exact public refs ───────┼─> carbon.qualification
Python standard library ────────────────────┘
```

Neither slice imports registry store/gate classes, generator/evaluation
runtime packages, scoring, TrainEval, MCP, cards, fees, leaderboard, chain,
network, frontier, product, settlement, or legacy code. Slice 2 imports only
the B-05 public nominal measurement refs and B-02A public owner/top-level refs.

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

`ValidationDossierRef` binds Challenge, dossier ID/version, schema/profile, the
tagged SHA-256 digest of the complete domain-framed canonical bytes, and the
effective structural origin. Origin composition is monotonic across every
contributing reference: `FIXTURE_ONLY` dominates `DRAFT_OR_UNRESOLVED`, which
dominates `REGISTERED_REFERENCE`. Canonical/ref projection and supersession
cannot cleanse nested fixture or unresolved provenance.
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
Qualification-candidate construction additionally derives one exact primary
`DossierEvidenceRef` from each supplied typed D1-D12 manifest and requires it
in that exact complete required section. Challenge, slot/class, ID, version,
digest, and effective origin must all match; two independently valid but
unrelated graphs cannot be combined.

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
registration binding; this package does not verify the registry. One shared
pure origin join applies the precedence `FIXTURE_ONLY` >
`DRAFT_OR_UNRESOLVED` > `REGISTERED_REFERENCE` across dossiers, evidence
manifests, campaigns, signer/artifact refs, attempts, limitations, statistical
evidence, and predecessors. Hashing, copying, serializing, superseding, or
attaching signer slots cannot cleanse fixture or unresolved origin.

No first-slice API can construct a qualification manifest, compare an active
registry record, verify a signer, activate a Challenge, or return a positive
qualification result. Fixtures may therefore exercise every structural path
without becoming evidence that can qualify a real Challenge.

## 8. Slice-2 evidence-manifest identity

The second slice adds a separate exact canonical domain for
`DossierEvidenceManifest`. It does not change or renumber D1-D12 and does not
change the Slice-1 `ValidationDossier` bytes. Each manifest binds exactly one
existing `DossierSlot`, its own canonical ID/version, structural origin,
optional same-Challenge/same-ID predecessor, a typed subject graph, a
canonical set of evidence refs, and explicit claim mappings.

The evidence-manifest schema version is exact string `"1.0"`, canonical
profile is exact string `carbon_dossier_evidence_manifest_canonical_v1`, and
domain header is exact bytes
`carbon.qualification.evidence-manifest.canonical.v1\x00`. A helper may create
the corresponding `DossierEvidenceRef`; the exact manifest ref also preserves
structural origin so a fixture predecessor cannot be cleansed by supersession.
Neither helper dereferences the evidence or asserts adequacy. Collection
duplicates are detected by nominal identity—evidence class, ID, and version—
before full digest/origin ordering, so conflicting content or provenance for
one versioned identity fails closed.

The subject graph reuses, rather than redefines, exact refs owned by B-02A,
B-03, B-04, and B-05:

- `PhysicalSystemSpecRef`, `CandidateOutputContractRef`,
  `InstanceDistributionContractRef`, and `SamplingPlanRef`;
- B-02A exact `ClaimScopeRef`, `GeneratorRef`, `RepresentationRef`,
  `DistributionConformanceRef`, and `ReferenceQualificationPolicyRef` seams
  already populated by the B-03/B-04 implementations; and
- B-05 `MeasurementContractRef` and
  `MeasurementQualificationEvidenceRef`.

Every supplied ref has the manifest's exact Challenge. D3 target-population
manifests require `TARGET_WORKLOAD_P`; D4 binds that exact population and an
exact SamplingPlan; D6 additionally binds the exact generator and conformance
facts; D7 binds the exact reference policy; D8 binds the candidate-output and
representation refs; and D9 binds the target population, measurement contract,
and separate qualification-evidence inventory. A shared Challenge ID without
these slot-specific object/version/digest bindings is incomplete and rejects a
complete manifest.

## 9. Claim/evidence compatibility and non-substitution

`EvidenceClaimBinding` maps one included evidence ref to one closed
`DossierClaimRole` and the manifest's exact `ClaimScopeRef`. The same artifact
may have multiple explicit mappings where the closed matrix permits it. Its
presence in one manifest or section supplies no implicit mapping elsewhere.

The twelve primary evidence classes may map to their own D1-D12 claim role.
Supplemental campaigns map only to the narrow roles justified by the evidence
standards and the merged B-05 evidence-role matrix: implementation
verification, discretization convergence, reference agreement, limiting-case
behavior, generator-conformance diagnostics, measurement-floor diagnostics,
decision-resolution diagnostics, or residual-limitation disclosure. No
supplemental class can map to physical-system adequacy, claim/envelope
adequacy, target-population adequacy, SamplingPlan adequacy, customer context
of use, product qualification, or LIVE activation. No evidence class in this
slice can map to customer context, product qualification, or LIVE activation.

Generator conformance, reference adequacy, representation fidelity, and
measurement adequacy remain distinct primary roles. Agreement across two
layers cannot fill the missing third layer. MMS, analytic anchors, mutation,
convergence, and passing fixtures can support only their registered narrow
diagnostic roles; they cannot establish a whole-section or broader physical
claim.

Compatibility is structural eligibility, never sufficiency. A manifest does
not return `PASS`, `QUALIFIED`, `AUTHORIZED`, or `LIVE`.

## 10. Statistical scope and pending dependence authority

`StatisticalScopeManifest` reuses one exact B-05 `UncertaintyPolicyRef` and
exact `MeasurementDefinitionRef` values for estimand, sampling unit,
resampling unit, independence unit, case scope, stratum, decision-interval
method, dependence assumption, applicability test, reconstruction-by-case and
reconstruction-by-stratum interaction, coverage evidence, stopping rule,
missing-cell/censoring policy, and evidence set. Every ref kind is checked
exactly and every ref is bound to the manifest Challenge.

The v2.0 ratified architecture requires statistical sufficiency, estimand
clarity, prospective SamplingPlan/censoring semantics, and distinct intended
and realized evidence. The more prescriptive dependence text added by
`Generator_Validation.md` v2.1 and scientific canon v4.1 is still labelled an
owner-ratification proposal. The active B-06 ticket and merged B-05 contract
authorize structural fields for later review, not acceptance of that policy.
Therefore the only Slice-2 dependence-policy state is
`OWNER_RATIFICATION_PENDING`. A populated statistical manifest cannot claim
that separate seeds prove independence, component uncertainty proves interval
coverage, an applicability test passed, or a method is qualified.

No numeric sample size, coverage target, covariance, power threshold,
decision formula, minimum resolvable improvement, or stopping value is stored
or inferred by this layer. B-E1 retains campaign execution and empirical or
simulated coverage analysis.

## 11. Intended/realized accounting, secrecy, and limitations

`EvidenceAccountingManifest` binds the exact SamplingPlan plus B-02A exact
owner refs for the protected intended-unit manifest, realized-evidence
accounting, censoring policy, missingness adjustment, and exclusion assessment.
Its opaque attempt evidence refs carry a closed disposition. Generator,
reference, infrastructure, candidate, timeout, invalid-case,
measurement-non-applicability, corrupted-observation, registered exclusion,
and valid-evidence dispositions remain distinct. The structure cannot convert
one disposition to another and exposes no case, seed, realization, truth
payload, filesystem path, network locator, or private provenance field.

`SecrecyEvidenceManifest` binds exact disclosure and blinding policies plus
distinct decontamination and role-separation audit evidence. It is evidence
inventory only. It does not evaluate security, verify a role, or authorize a
signer. The two audit refs must have distinct nominal kind/ID/version
identities; changing the digest of one nominal audit version cannot make it a
second audit. Distinct versions remain distinct prospective identities.

Each `LimitationBinding` pins one residual-limitation ref to non-empty affected
evidence refs, affected claim roles, and the exact claim scope. Dangling,
cross-Challenge, duplicate, or empty-scope bindings reject. Recording a
limitation does not alter a population, SamplingPlan, claim envelope, registry
record, or scientific status; any such prospective change requires its owning
versioned workflow.

## 12. Slice-2 completeness, fixture, and disclosure boundary

A typed evidence manifest can be represented as explicit
`INCOMPLETE_MISSING`, `INCOMPLETE_PLACEHOLDER`, or `COMPLETE_REFERENCED`.
Incomplete states carry no evidence or claim mappings and remain blocked for
qualification. A complete manifest must contain its own slot-primary evidence
class, every slot-required exact subject binding, every referenced optional
submanifest required by its slot, and only compatible explicit claim mappings.

Fixture origin propagates from the manifest, evidence, accounting attempts,
or limitation evidence and cannot be cleansed by canonicalization,
aggregation, or supersession. Signer records remain the Slice-1
missing/populated-unverified values and are not inputs to evidence-manifest
completeness. No public projection, resolver, filesystem/network fetch, or
untrusted reference dereference is added.

## 13. Slice-3 qualification-manifest and active-registry seam

Slice 3 defines an immutable `QualificationManifestCandidate` that references
one exact `ValidationDossierRef`, exact D1-D12 evidence-manifest bindings,
exact scientific-object identities, signer records, and a closed deterministic
artifact set. A pure fail-closed comparator accepts:

```text
exact active A3 ChallengeRecord snapshot
+ exact expected ChallengeKey
+ exact ValidationDossier ref and structural state captured by the candidate
+ exact qualification-manifest candidate bytes/ref
+ externally verified signer authorization results
+ exact artifact identifiers/digests from the candidate and record snapshot
```

and returns only a typed comparison result. It rejects missing,
placeholder, fixture, unsigned, unauthorized, wrong-version, stale,
cross-Challenge, malformed, role-confused, or digest-mismatched input. It may
not infer scientific sufficiency from schema completeness or execute a LIVE
transition. A3 remains lifecycle owner; integration requires an explicit
one-way B-06 adapter that preserves legacy history and compares the exact
caller-supplied registry record rather than creating or searching a parallel
registry.

The current A3 public surface has no qualification-manifest digest function.
Slice 3 therefore defines a separate B-06 domain-framed fingerprint over the
exact current public `QualificationManifest` fields. It exists only to detect
snapshot drift. It is not an A3-owned qualification hash, an artifact-byte
check, a signature, an approval, or a LIVE capability. Exact A3 slot/state,
artifact-ID bindings, and required human-reference presence/non-placeholder
structure remain independently compared. The latter reuses A3's exact pure
missing/placeholder vocabulary; a populated reference is not verified
authorization or approval.
The record-level and qualification-manifest scientific-authoring graph
fingerprints must both be present and equal, matching A3's existing gate
invariant. B-06 does not recompute or verify that graph.

The comparator accepts only a pre-activation `draft` record as lifecycle
compatible. `fixture` and already-`live` records reject. It does not call the
A3 store or gate, read artifact paths, hash artifact files, mutate the supplied
record, or activate anything. A3 retains its independent artifact-byte,
authoring-graph, lifecycle, and activation gates.

Signer authorization input preserves five separate facts: the signer slot is
populated, the identity structure was externally validated, that identity was
externally authorized for the exact role, the signature was externally
cryptographically verified, and scientific approval remains unrepresented.
No certificate authority, trust root, organization policy, reviewer identity,
quorum, role assignment, or cryptographic implementation is added.

An incomplete candidate may remain canonically representable, but
`machine_prerequisites_satisfied` is false. A positive value means only that
the exact represented machine-checkable inputs match. It does not mean
scientifically qualified, security qualified, production qualified, approved,
or LIVE.

## 14. Slice-4 campaign acquisition and result manifests

`CampaignEvidenceManifest` is a separate exact B-06 canonical domain. It
contains a prospective `CampaignAcquisitionManifest` and an optional
`CampaignResultManifest`. Both bind one exact supplemental
`DossierEvidenceClass`; the class determines a closed `CampaignFamily` and
family-specific required artifact roles. A helper derives the exact
`DossierEvidenceRef` consumed by the existing D1-D12 evidence/claim graph.

The acquisition record binds the exact Challenge, claim scope, applicable
B-02A target population and SamplingPlan, B-03 generator owner ref, B-04
reference-qualification-policy owner ref, representation ref, B-05
MeasurementContract, exact case/stratum/estimand/method definition refs, an
ordered artifact-role set, provenance, and a closed acquisition state. Fields
that do not apply are absent because the family matrix does not require or
allow them; no magic null represents applicability.

The result record is externally supplied evidence. It binds the exact
acquisition identity, a closed family-compatible outcome, exact result,
uncertainty, exclusion, failure, and limitation artifact refs, and the same
case/stratum scope. It carries no calculated interval, float, threshold,
expected order, mutation score, acceptable disagreement, acceptable floor,
winner calculation, or automatic pass/fail. A missing result honestly
represents specified/attempted/partial acquisition. A produced, blocked,
invalid, inapplicable, indeterminate, or scientific-judgment-pending result is
representable without manufacturing approval.

An acquisition still in `CAMPAIGN_SPECIFIED` state must have no result. The
attempted, partially completed, and completed states retain the contract's
existing family-compatible result options; B-06 defines no broader
state/result policy or scientific interpretation.

The family set is exactly MMS/refinement/observed order, planted-defect
mutation, analytic/limiting anchor, primary/witness convergence/disagreement,
generator-oracle adversarial, measurement floor, decision resolution, and
residual limitation. Family-required artifact roles preserve per-level MMS
results, mutation identities, anchor applicability, distinct primary/witness
roles, adversarial oracle/checker identity, external floor results,
decision-resolution audit refs, and scoped limitations. Wrong families,
roles, versions, digests, upstream objects, scopes, duplicates, or incomplete
produced results reject. Campaign collections use nominal identity for
collision detection and a separate full key for canonical ordering: one
definition or attempt ID/version cannot carry conflicting digests or origins.

Decision-resolution dependence/resampling/coverage/power/stopping fields are
structural refs under exact `OWNER_RATIFICATION_PENDING` authority. B-06 does
not execute B-E1 algorithms, infer independence, calculate an interval or
power, select a winner, promote a candidate, or interpret a pending field as
approved policy.

The campaign schema exposes only IDs, versions, tagged digests, closed enums,
and existing protected refs. It has no seed, realization, truth payload,
filesystem path, URL, locator, embedded bytes, credential, signer secret,
resolver, or I/O field. Canonical decoding is bounded, duplicate-key rejecting,
strict UTF-8, exact enum/type checked, byte-for-byte re-encoded, and rejects
trailing or tampered input. Fixture origin and stale/superseded state remain
visible and cannot be cleansed by aggregation or supersession.

Campaign-to-claim compatibility remains the closed Slice-2 matrix. In
particular MMS cannot establish physical validity; mutation cannot establish
product qualification; generator-oracle evidence cannot establish SamplingPlan
adequacy; primary/witness agreement cannot establish truth; a floor result
cannot establish score eligibility; and decision-resolution evidence cannot
establish LIVE.

## 15. Slice tests

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

Slice 2 additionally proves exact subject/version binding, the closed
claim/evidence matrix, explicit one-to-many mappings, wrong-layer
substitution, pending dependence authority, exact statistical ref kinds,
intended/realized accounting, failure-class separation, scoped limitations,
manifest canonical ordering/round trip/tamper behavior, honest incomplete
states, and fixture propagation.

Slice 3 additionally proves deterministic candidate/artifact-set identity,
exact nested-object coverage, duplicate/orphan rejection, exact A3
qualification snapshot and required-slot comparison, missing/extra/wrong-
digest artifacts, distinct dossier and measurement mismatches, draft-only
lifecycle compatibility, fixture/placeholder/stale rejection, exact external
signer-result binding, fail-closed unverified authorization, deterministic
multi-mismatch ordering, byte-exact round trip, and no registry mutation or
LIVE side effect.

Slice 4 additionally proves every campaign family's required exact acquisition
and result bindings, honest pre-result states, family/outcome vocabulary,
duplicate/role/scope/version rejection, fixture/currentness propagation,
canonical permutation stability and byte-exact round trip, tamper/trailing/
oversize rejection, hostile protected-surface boundaries, and cross-family/
cross-claim non-substitution. It proves decision-resolution remains pending
authority and imports or implements no execution, statistical, registry, or
LIVE engine.

The campaign acquisition and combined-manifest encoders apply the same exact
2 MiB document ceiling as the decoder after canonical encoding. Bytes at or
below the ceiling remain accepted unchanged; an oversized serialization and
every digest/ref helper that depends on it fail closed with `SIZE_LIMIT`.

Native tests on this macOS host are diagnostic only. The first six findings
`B06-CR-001` through `B06-CR-006` remain verified repaired. The third fresh
review at head `8d23b70cda6a08fd99f0ad4174b7c381e2f7ac7b` returned
`FINDINGS`; this revision repairs `B06-CR-007/008` by rejecting results on
merely specified acquisitions and requiring distinct nominal D11 audit
identities. All earlier CI and reviews are stale for the changed tree. Fresh
exact-head CI and a fourth completely fresh complete-diff review remain
required. No closed receipt or human approval exists; merge and closeout
remain external delivery predicates.

## 16. Deferred and human-reserved work

Slice 4 owns the campaign-specific manifests not represented by Slice 2.
The complete ticket has been reconciled after the bounded third-review repair;
no known machine-implementable B-06 feature requirement remains, subject to a
fresh complete-diff review of the repaired tree. Slice 3
implements candidate construction and a pure exact A3 snapshot comparison;
Slice 4's synthetic D7 test proves campaign-digest projection into that
existing evidence graph.
Actual signer identity/role authorization and cryptographic verification stay
external; B-06 consumes their exact typed results but does not implement or
claim them.

Slice 2 represents every ticket-named supplemental campaign as an exact typed
evidence ref plus explicit claim mapping, and Slice 4 supplies their closed
acquisition/result shapes. Campaign execution, scientific interpretation, and
decision machinery remain B-E1 or human work; structural implementation does
not claim any real campaign has occurred or is adequate.

Humans retain every real physical claim, envelope, population, SamplingPlan,
generator/reference/measurement adequacy decision, uncertainty/dependence and
coverage judgment, evidence minimum, stopping rule, signer identity and
authority, security acceptance, scientific signoff, launch decision, and
`LIVE` activation. B-E1 retains statistical campaigns; B-07F retains official
execution composition. Bittensor, frontier, treasury, settlement, product,
commercial, and later-wave behavior remain out of scope.
