# B-06 plan — Validation Dossier and qualification manifest

**Ticket:** B-06  
**Status:** third coherent structural slice implemented; campaign schemas next
**Branch:** `agent/b-06-dossier-manifest`  
**Worktree:** dedicated worktree; absolute host path intentionally not tracked  
**Exact starting main:** `2500e51042f39a31f5056c74ce2ac5065657ec2a`  
**Exact starting tree:** `89763523576cef09f40fd8a205aa86d169d679de`  
**Working contract:** `Design_Specs/Validation_Dossier_Manifest_Contract.md`  
**Evidence:** `.agent/evidence/wave_b/b-06.md`  
**Primary Hub map_ref:** `WAVE-B/B-06`

## 1. Owner-directed activation

PR #87 merged B-05's repaired tree into the exact starting main above. The
owner explicitly accepts that merged implementation as the B-06 dependency
despite incomplete routine B-05 delivery steps. Record the exception in
B-06-D0 and current Wave selection without inventing reviews, approval,
completed CI, or an external receipt. Do not reopen B-05 or wait for another
confirmation.

The one-time opening observation recorded PR #87 as merged. Delivery
preflight, Development Hub, and canonical-environment checks were successful;
the GPT review gate failed; a clean-image job and the main CI run were still
in progress at observation time. Do not poll or retrigger them. No observed
failure changes the B-06 structural dependency.

## 2. Selected engineering decisions

- **B-06-D0:** accept the exact merged B-05 tree as the owner-directed
  dependency for this transition only; preserve the incomplete ordinary
  delivery history.
- **B-06-D1:** implement the first slice under the already reserved
  `carbon.qualification` package, reusing A3 identity/digest grammar and
  B-02A strict primitives while leaving A3's legacy manifest and gate
  unchanged.
- **B-06-D2:** encode D1–D12 as exact ordered slots with slot-specific primary
  evidence classes, explicit requirement/completeness/status states, and
  supplemental campaign refs that cannot substitute for the primary class.
- **B-06-D3:** require the exact B-06 accountable signer-role tuple but expose
  only missing or populated-unverified bindings. Keep signer authorization,
  qualification-manifest issuance, active-registry comparison, and scientific
  signoff outside Slice 1.
- **B-06-D4:** use exact B-02A owner/top-level refs and B-05 measurement refs
  for the evidence subject graph, preserving B-03/B-04 reverse-import
  boundaries; require explicit closed claim mappings.
- **B-06-D5:** represent the dependence/coverage identity graph only under
  `OWNER_RATIFICATION_PENDING`; do not treat the v2.1/v4.1 proposal or B-05
  types as scientific ratification.
- **B-06-D6:** keep intended/realized attempt accounting, secrecy evidence,
  and scoped limitations opaque, typed, non-substitutable, and
  non-authorizing.
- **B-06-D7:** KEEP/WRAP A3's immutable public values only; compare one
  caller-supplied snapshot without store/gate imports, lookup, I/O, mutation,
  or activation.
- **B-06-D8:** domain-separate the B-06 candidate and exact A3 qualification
  snapshot fingerprints; neither fingerprint establishes trust or approval.
- **B-06-D9:** consume external identity-validation, exact-role authorization,
  and cryptographic-verification facts as separate typed inputs without
  implementing their trust policy or scientific signoff.

These are reversible engineering decisions within the active ticket. Notify
issue #42 mentioning `@harshaa765`; development continues without waiting for
a response unless an explicit blocking direction arrives.

## 3. Implementation slices

### Slice 1 — dossier identity and evidence-slot foundation

Implement exact enums, nominal evidence and signer-artifact refs,
`DossierSection`, `ValidationDossier`, same-Challenge/version/supersession
validation, fixture-origin propagation, canonical bytes/digest/ref and strict
decode. Add focused CPU and invariant tests for missing/placeholder evidence,
slot and signer substitution, wrong Challenge/version, deterministic identity,
and fixture inability to qualify.

Checkpoint result: implemented with focused native diagnostics. The canonical
Docker environment remains unavailable and is recorded as infrastructure, not
as a passing result. Issue #42 comment `5554513577` carries the required
non-gating notification.

### Slice 2 — evidence-class and cross-section completeness

Add the ticket's complete typed evidence manifests for population,
SamplingPlan, generator, reference, representation, measurement, statistical
sufficiency, secrecy, censoring, uncertainty, campaign, and limitation
evidence. Enforce claim-support/non-substitution matrices without choosing
scientific sufficiency.

Checkpoint result: the common manifest and exact slot-specific subject graph,
claim matrix, statistical scope, accounting, secrecy, limitation, canonical
identity, and focused tests are implemented. The supplemental campaign
classes are structurally representable as typed refs with explicit claim
mappings. Campaign-specific acquisition/result schemas for MMS observed-order,
mutation, analytic-anchor, witness/convergence/disagreement,
generator-oracle-adversarial, and measurement-floor studies remain a later
B-06/B-E1 concern and are not marked implemented by this checkpoint.

#### Slice-2 rule-to-source-to-test matrix

| Rule | Authority status and controlling source | Claim/evidence and exact binding | Structural accept / reject | Human-owned judgment | Positive / negative proof |
|---|---|---|---|---|---|
| S2-R1 exact subject graph | Existing ratified architecture: `Generator_Validation.md` v2.0 D1-D12; `Challenge_Instance_Distribution.md` §§4-8, 26 | Every manifest pins the exact Challenge plus the applicable physical-system, claim-scope, population, SamplingPlan, generator, reference, representation, and measurement refs | Accept the slot-specific minimum graph; reject shared-Challenge-only, cross-Challenge, wrong nominal role, and omitted required object bindings | Whether any pinned object is scientifically adequate | valid D3-D9 graphs / missing object, wrong population role, cross-Challenge and wrong-version scope tests |
| S2-R2 explicit claim support | Existing evidence doctrine: `Evidence_and_Envelope_Standards.md` §§1-2; merged B-05-D2; B-06 ticket | Each evidence ref is explicitly mapped to a closed claim role and exact claim-scope ref | Accept authorized one-to-many mappings; reject unsupported roles and implicit cross-section satisfaction | Sufficiency and applicability of eligible evidence | explicit reuse / MMS-to-physical, product, LIVE and generator-reference-measurement substitution tests |
| S2-R3 statistical scope | Delegated structural requirement: active B-06 ticket; merged B-05-D4 types. Scientific dependence amendment remains proposal-only: `Generator_Validation.md` v2.1 and scientific canon v4.1 | Exact uncertainty policy, estimand, sampling/resampling/independence units, case/stratum scope, interval method, dependence/applicability, coverage, stopping, missing-cell, and evidence-set refs | Accept a structurally complete graph only with `OWNER_RATIFICATION_PENDING`; reject missing/wrong-kind/wrong-Challenge refs and any claimed ratified dependence policy | Method choice, independence, covariance, coverage, power, minima, stopping, false-promotion control, and applicability | pending complete graph / different-seed inference, component-table substitution, wrong-kind and false-ratification tests |
| S2-R4 intended/realized accounting | Existing ratified architecture: `Generator_Validation.md` v2.0 D4/D6/D12; `Challenge_Instance_Distribution.md` §§19, 26 | Exact SamplingPlan, protected intended-unit, realized-accounting, censoring, missingness, exclusion refs, plus typed attempt dispositions | Accept distinct registered dispositions; reject missing plan/accounting, cross-Challenge refs, duplicates, or reclassification of reference failure as candidate failure | Whether censoring or missingness is acceptable and how it affects inference | complete accounting / duplicate, omitted, cross-Challenge, and failure-collapse tests |
| S2-R5 secrecy and role separation | Existing ratified architecture: `Generator_Validation.md` v2.0 D11; current disclosure standards | Exact disclosure/blinding policy plus decontamination and role-separation audit refs; no seed, realization, truth payload, path, or locator fields | Accept opaque protected refs; reject missing policy/audit roles and unsafe field expansion | Security adequacy, decontamination, identity, authorization, and separation-of-duties acceptance | complete D11 graph / omitted role and public-surface/invariant tests |
| S2-R6 scoped limitations | Existing ratified architecture: `Generator_Validation.md` v2.0 D12; evidence standards §2 | Each limitation binds affected evidence, claim roles, and exact claim scope | Accept explicit scoped limitations; reject dangling evidence, empty scope, cross-Challenge, duplicate bindings, or automatic envelope mutation | Residual-risk acceptance and any prospective envelope/population revision | scoped limitation / dangling, duplicate, empty-scope and no-mutation tests |
| S2-R7 honest completeness | Existing B-06 contract §§4-7 and ticket | Manifest shape, section completeness, fixture origin, and signer state stay distinct | Accept incomplete/deferred values; reject a complete section whose required typed manifest is absent/mismatched; fixture and unverified signer state never gain authority | Section verdicts, signer authorization, qualification, and LIVE activation | valid incomplete round trip / unsupported completeness, fixture laundering, and signer-inference tests |
| S2-R8 deterministic identity | Delegated implementation decision under A3/B-02A canonical conventions and B-06-D1 | Evidence-manifest ID/version, same-ID supersession, exact canonical bytes and digest | Accept canonical ordering and byte-exact round trip; reject duplicates, stale/wrong-version supersession, tampering, unknown fields, and trailing bytes | No scientific judgment is encoded | stable permutation digest / tamper, duplicate-key, wrong predecessor and trailing-byte tests |

The v2.1 dependence additions in `Generator_Validation.md` and matching v4.1
scientific-canon additions remain explicit owner-ratification proposals. This
slice may preserve their exact identity fields because the active B-06 ticket
and merged B-05 types require a forward-compatible structural seam, but it
must label their scientific-policy status `OWNER_RATIFICATION_PENDING` and
must expose no accepted/qualified alternative.

### Slice 3 — qualification-manifest candidate and registry comparison

**Selected implementation decisions before code:**

- **B-06-D7 — KEEP/WRAP A3 values, not its store or gate.** Consume only the
  exact public `ChallengeRecord`, `QualificationManifest`,
  `QualificationEvidence`, `ArtifactBinding`, required-slot constants, and
  digest grammar. The caller supplies one exact record snapshot. B-06 performs
  no lookup, filesystem verification, registry mutation, or LIVE transition.
- **B-06-D8 — domain-separate the B-06 candidate and A3 snapshot fingerprints.**
  Current A3 exposes no public qualification-manifest digest API. B-06 may
  canonically fingerprint the exact current public A3 manifest fields solely
  as a comparison input. That fingerprint is not an A3 qualification hash,
  artifact-byte verification, scientific verdict, or activation token.
- **B-06-D9 — external authorization is a typed input, not a signer.** A pure
  comparison accepts exact per-role results that keep identity structure,
  role authorization, and cryptographic signature verification distinct.
  It implements none of those trust decisions and records no scientific
  approval state.

#### Slice-3 source-to-rule-to-test matrix

| Rule | Controlling source and existing A3 seam | Structural accept / reject | Human-owned decision | Positive / negative proof |
|---|---|---|---|---|
| S3-R1 candidate identity | B-06 ticket; Build Out §8; A3 `ChallengeKey` and tagged digest grammar | Exact candidate id/version/profile and domain-framed digest; reject malformed, duplicate, tampered, or trailing bytes | Whether the candidate should be issued or accepted | deterministic round trip / malformed, tampered, duplicate-key, trailing-byte tests |
| S3-R2 exact Challenge binding | Generator Validation v2.0 §5; A3 `ChallengeKey` | Every nested dossier, evidence, artifact, signer, subject, measurement, and authorization input equals one exact key | Whether that Challenge is scientifically defensible | matching key / wrong challenge and version tests |
| S3-R3 dossier binding | Generator Validation v2.0 §§5, 14-15; B-06 `ValidationDossierRef` | Exact dossier id/version/digest/currentness and structural completeness; reject missing, placeholder, fixture, stale, or registry-digest mismatch | D1-D12 adequacy and signoff | exact dossier artifact / wrong digest, fixture, stale, incomplete tests |
| S3-R4 exact artifact set | Build Out §8; A3 `ChallengeRecord.artifacts` and `ArtifactBinding` | Closed ordered refs with exact id/version/digest/kind/origin/currentness; reject duplicates, implicit latest, missing/extra registry IDs, or digest mismatch | Trust, provenance authenticity, and artifact adequacy | exact set equality / missing, extra, duplicate, stale and wrong-digest tests |
| S3-R5 signer population vs authorization | B-06 signer contract; A3 reserved-binding boundary | Exact five populated signer roles plus exact external identity-valid, role-authorized, signature-verified results | Identity proof, trust roots, role policy, crypto verification, and scientific approval | all exact results / missing, wrong-role, unverified and unauthorized tests |
| S3-R6 active-record comparison | Build Out/overlay A3 KEEP+EXTEND; exact public `ChallengeRecord` snapshot | Pure caller-supplied snapshot comparison only; reject wrong key, fixture provenance, or incompatible lifecycle | Registry selection and whether supplied snapshot is authoritative/current | compatible draft snapshot / wrong key, fixture, lifecycle tests |
| S3-R7 qualification/hash comparison | Build Out §8; A3 public `QualificationManifest`, record/manifest authoring-graph fingerprint, required slots/states, artifact IDs/digests | Exact B-06-domain snapshot fingerprint, equal non-missing A3 record/manifest graph fingerprint, and slot/artifact binding; reject missing/wrong state, artifact, graph, mode, or digest | Truth of human-owned A3 state strings and artifact contents | exact fingerprint / changed graph, slot, state, ref and digest tests |
| S3-R8 lifecycle compatibility | A3 `LIFECYCLE_STATES` and checked draft-to-LIVE activation ownership | Candidate comparison accepts only exact pre-activation `draft`; fixture/live reject; no state is mutated | Activation and LIVE decision | draft comparison / fixture and live tests, before/after record equality |
| S3-R9 fixture/placeholder isolation | Constitution; Generator Validation v2.0; B-06 origin/completeness types; A3 `fixture_origin` | Represent incomplete candidates honestly but never ready; any fixture or placeholder input rejects | Whether non-fixture evidence is authentic and sufficient | incomplete round trip / fixture and placeholder readiness tests |
| S3-R10 stale/superseded rejection | Constitution historical-evidence invariant; B-06 prospective versioning | Exact currentness enum and predecessor refs; non-current inputs and record digest drift reject; no `latest` lookup | Which version is the approved active scientific version | current exact refs / superseded, revoked, wrong-version tests |
| S3-R11 deterministic reasons | A3 deterministic diagnostic precedent; disclosure invariants | Closed enum in fixed evaluation order; no paths, protected bytes, signer secrets, or free text | Meaning/acceptance of underlying evidence | stable multi-error tuple / ordering and no-leakage tests |
| S3-R12 readiness ceiling | Constitution; Generator Validation §§15, 18-19; A3 reserved-binding boundary | `machine_prerequisites_satisfied` means only represented structural checks succeeded | Scientific/security adequacy, approval, production qualification, and LIVE | fully matching synthetic graph / assertions that no approval/LIVE API or side effect exists |

The A3 record's artifact paths and artifact bytes remain owned and verified by
the existing A3 gate. The pure B-06 comparator sees only artifact identifiers
and expected digests. A positive structural comparison is therefore not a
replacement for `ChallengeRegistry.assess_live_eligibility`, and neither
operation establishes scientific adequacy.

Checkpoint result: implemented. The candidate pins the exact dossier,
scientific objects, applicability-qualified representations, measurement set,
D1-D12 evidence manifests, signer records, closed artifact set, A3 slot
bindings, expected A3 snapshot fingerprint, and prospective supersession.
Canonical decode is byte-exact and the pure comparator returns a fixed-order
closed mismatch enum. A matching result is named only
`machine_prerequisites_satisfied`; the supplied A3 record remains `draft` and
is unchanged. Focused B-06/A3/boundary validation passed locally. The earlier
canonical Docker limitation was unchanged and was not retried.

### Slice 4 — campaign-specific evidence schemas

Implement the remaining bounded acquisition/result schemas for MMS observed
order, mutation, analytic anchors, witness convergence/disagreement,
generator-oracle adversarial studies, and measurement-floor studies. Preserve
the current common evidence ref/claim graph and leave campaign execution and
scientific conclusions to B-E1/humans.

### Slice 5 — integration and mature candidate

Compose a fully synthetic fixture graph, prove it cannot satisfy a production
qualification path, add package/wheel and cross-owner tests, reconcile the
Hub, run scope-required validation, and prepare the complete candidate for
fresh exact-head review. Do not begin B-E1 or B-07F execution.

## 4. Baseline and validation

The canonical wrapper was attempted once and correctly failed because Docker
or the exact Dev Container is unavailable. It will not be retried in this
checkpoint. Native Python 3.11.11 with the existing repository-pinned B-05
development environment ran the focused registry/B-05/invariant baseline:

```text
242 passed in 1.14s
```

After each slice, run the new B-06 tests and directly affected registry,
package, code-authority, and predecessor-boundary tests. Slice 2's expanded
local run passed 815 tests. Slice 3's final focused invocation passed 270 tests and
its expanded affected predecessor/package/authority invocation passed 1431
tests in 651.55 seconds; the final post-repair B-06/A3 focus passed 233 tests.
Counts are per overlapping invocation, not a summed
unique-test total. Native results remain diagnostic. No full canonical run or
complete-diff review occurs at this checkpoint.

## 5. Hub and commit shape

The selection/authority and implementation change requires a structural Hub
update at `WAVE-B/B-06`. Commit the contract, decisions, plan/evidence,
selection records, implementation, and tests as the authority commit **A**.
Then update Hub source, pin it to **A**, regenerate only through the normal Hub
renderer, validate the affected Hub surface, and commit it as **H**. Do not
push, open a PR, merge, or perform final review in this checkpoint.

## 6. Human-reserved blockers

Real evidence, scientific section status, signer identity/key custody and
authorization, separation-of-duties exceptions, statistical sufficiency,
security acceptance, qualification, Launch Bar approval, and LIVE activation
remain human-owned. They block positive real qualification but do not block
the bounded structural slices.
